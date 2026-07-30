"""Calcul RTT hebdomadaire tenant compte des absences (points 7 + 9).

Règle métier : le RTT provient uniquement des heures travaillées au-delà d'un seuil
hebdomadaire (par défaut 34,65 h). Une semaine à 35 h nominale produit donc
0,35 h de RTT (35 − 34,65). Une absence dans la semaine ne doit PAS faire perdre de
RTT au salarié : on réduit le seuil au prorata des jours d'absence.

Exemple : seuil 34,65 h, 1 jour d'absence (7 h) -> seuil ajusté 27,65 h. Si le
salarié a travaillé 28 h cette semaine-là, RTT = 0,35 h (équivalent d'une semaine
pleine à 35 h).

Le module expose :
- `calculer_rtt_semaine(...)` : fonction pure, unitairement testable.
- `calculer_rtt_hebdo(user_id, param)` : agrège sur l'exercice à partir des heures
  hebdomadaires saisies (HeuresHebdo) et des absences (Conge validés).
- `maj_rtt_allocations_hebdo(param, user_ids=None)` : applique le résultat sur
  AllocationConge.rtt_heures_allouees.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from models import db
from models.conge import Conge
from models.heures_hebdo import HeuresHebdo
from models.parametrage import AllocationConge, ParametrageAnnuel
from services.calcul_jours import get_dates_feries_set, _est_ouvrable

# Valeurs par défaut (modifiables via paramétrage annuel).
SEUIL_HEBDO_DEFAUT = 34.65
HEURES_PAR_JOUR_DEFAUT = 7


@dataclass(frozen=True)
class RttHebdoResult:
    user_id: int
    rtt_calculee: float  # heures RTT acquises, en décimal (ex. 16,1 h)
    nb_semaines: int
    detail: list  # liste de dicts par semaine : {lundi, heures, jours_absence, rtt}


def calculer_rtt_semaine(
    heures_reelles: float,
    jours_absence: float,
    seuil_hebdo: float = SEUIL_HEBDO_DEFAUT,
    heures_par_jour: float = HEURES_PAR_JOUR_DEFAUT,
    coef: float = 1.0,
) -> float:
    """RTT acquis sur une semaine donnée (fonction pure).

    Le seuil est réduit au prorata des jours d'absence pour ne pas pénaliser le
    salarié. Le RTT acquis est le surplus d'heures travaillées au-delà du seuil
    ajusté, multiplié par un coefficient (1.0 = surplus converti tel quel en heures RTT).
    """
    seuil_ajuste = max(0.0, float(seuil_hebdo) - float(jours_absence) * float(heures_par_jour))
    surplus = max(0.0, float(heures_reelles) - seuil_ajuste)
    # Arrondi à 2 décimales pour neutraliser les artefacts du flottant
    # (ex. 39 - 34.65 = 4.350000000000001) ; cohérent avec le round(total, 2)
    # appliqué par calculer_rtt_hebdo sur l'agrégat.
    return round(surplus * float(coef), 2)


def _coef_param(param: ParametrageAnnuel) -> float:
    """Coefficient de conversion surplus -> RTT. 1.0 par défaut (surplus = RTT)."""
    coef = float(getattr(param, "rtt_coef_surplus", 0.0) or 0.0)
    return coef if coef > 0 else 1.0


def seuil_hebdo_param(param: ParametrageAnnuel | None) -> float:
    """Seuil hebdomadaire RTT depuis le paramétrage actif, sinon constante par défaut."""
    if param is not None:
        val = getattr(param, "rtt_seuil_hebdo", None)
        if val is not None and float(val) > 0:
            return float(val)
    return float(SEUIL_HEBDO_DEFAUT)


def heures_par_jour_absence_param(param: ParametrageAnnuel | None) -> float:
    """Heures déduites du seuil par jour d'absence, depuis le paramétrage ou défaut."""
    if param is not None:
        val = getattr(param, "rtt_heures_par_jour_absence", None)
        if val is not None and int(val) > 0:
            return float(val)
    return float(HEURES_PAR_JOUR_DEFAUT)


def types_absence_exclus_param(param: ParametrageAnnuel | None) -> set[str]:
    """Types d'absence exclus de la réduction du seuil hebdomadaire RTT.

    Par défaut, tous les congés validés réduisent le seuil (comportement
    historique). Un type exclu (ex. ``Maladie``) ne réduira pas le seuil : le
    salarié ne perd pas de RTT en étant en arrêt maladie. Stocké comme une liste
    de codes séparés par des virgules dans ``rtt_types_absence_exclus``.
    """
    if param is None:
        return set()
    raw = getattr(param, "rtt_types_absence_exclus", "") or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


def _semaines_exercice(param: ParametrageAnnuel, jusqu_a: date | None = None) -> list:
    """Liste des lundis (semaines ISO) couvrant l'exercice, borné à ``jusqu_a``.

    Par défaut, le calcul s'arrête à aujourd'hui pour éviter d'anticiper des RTT
    sur des semaines futures de l'exercice.
    """
    lundi = _lundi(param.debut_exercice)
    fin = min(param.fin_exercice, jusqu_a or date.today())
    semaines = []
    while lundi <= fin:
        semaines.append(lundi)
        lundi += timedelta(days=7)
    return semaines


def _absence_fraction_par_jour(user_id: int, param: ParametrageAnnuel) -> dict:
    """Retourne {date: fraction d'absence (0.5 ou 1.0)} sur l'exercice.

    La fraction d'un jour correspond à la part ouvrable réellement absente, en
    cohérence avec le calcul des jours ouvrables (demi-journées aux bordures).
    Tous les congés validés comptent comme absence (ils représentent du temps
    non travaillé, ce qui justifie de réduire le seuil hebdomadaire), sauf les
    types explicitement exclus via ``rtt_types_absence_exclus`` (ex. Maladie).
    """
    debut = param.debut_exercice
    fin = param.fin_exercice
    feries = get_dates_feries_set(debut, fin)
    exclus = types_absence_exclus_param(param)

    q = Conge.query.filter(
        Conge.user_id == user_id,
        Conge.statut == "valide",
        Conge.date_debut <= fin,
        Conge.date_fin >= debut,
    )
    if exclus:
        q = q.filter(~Conge.type_conge.in_(exclus))
    conges = q.all()

    fractions: dict = {}
    for c in conges:
        jour = max(c.date_debut, debut)
        dernier = min(c.date_fin, fin)
        while jour <= dernier:
            if _est_ouvrable(jour, feries):
                frac = 1.0
                # Demi-journées aux bordures du congé (mêmes règles que le calcul ouvrable).
                if c.date_debut == c.date_fin:
                    if c.demi_journee_debut or c.demi_journee_fin:
                        frac = 0.5
                else:
                    if jour == c.date_debut and c.demi_journee_debut == "apres_midi":
                        frac = 0.5
                    elif jour == c.date_fin and c.demi_journee_fin == "matin":
                        frac = 0.5
                # On cumule sans dépasser 1 jour d'absence par date.
                fractions[jour] = min(1.0, fractions.get(jour, 0.0) + frac)
            jour += timedelta(days=1)
    return fractions


def _lundi(d: date) -> date:
    return d - timedelta(days=d.weekday())


def jours_absence_semaine(user_id: int, lundi: date, exclus: set[str] | None = None) -> float:
    """Nombre de jours ouvrables d'absence (congés validés) sur la semaine du `lundi`.

    Utilisé par l'écran de saisie hebdomadaire pour afficher le contexte d'absence.
    Les types listés dans ``exclus`` ne sont pas comptés (ex. Maladie).
    """
    lundi = _lundi(lundi)
    dimanche = lundi + timedelta(days=6)
    feries = get_dates_feries_set(lundi, dimanche)
    q = Conge.query.filter(
        Conge.user_id == user_id,
        Conge.statut == "valide",
        Conge.date_debut <= dimanche,
        Conge.date_fin >= lundi,
    )
    if exclus:
        q = q.filter(~Conge.type_conge.in_(exclus))
    conges = q.all()
    total = 0.0
    for c in conges:
        jour = max(c.date_debut, lundi)
        dernier = min(c.date_fin, dimanche)
        while jour <= dernier:
            if _est_ouvrable(jour, feries):
                frac = 1.0
                if c.date_debut == c.date_fin:
                    if c.demi_journee_debut or c.demi_journee_fin:
                        frac = 0.5
                else:
                    if jour == c.date_debut and c.demi_journee_debut == "apres_midi":
                        frac = 0.5
                    elif jour == c.date_fin and c.demi_journee_fin == "matin":
                        frac = 0.5
                total += frac
            jour += timedelta(days=1)
    return total


def calculer_rtt_hebdo(
    user_id: int,
    param: ParametrageAnnuel,
    jusqu_a: date | None = None,
) -> RttHebdoResult:
    """Agrège le RTT hebdomadaire d'un salarié sur l'exercice.

    Le RTT provient uniquement du surplus d'heures travaillées (HeuresHebdo)
    au-delà du seuil hebdomadaire ajusté selon les absences.
    """
    seuil = seuil_hebdo_param(param)
    heures_jour = heures_par_jour_absence_param(param)
    coef = _coef_param(param)
    fin_calcul = min(param.fin_exercice, jusqu_a or date.today())

    # Absences par semaine (lundi -> total jours d'absence ouvrables).
    absences_jour = _absence_fraction_par_jour(user_id, param)
    absences_semaine: dict = {}
    for jour, frac in absences_jour.items():
        lundi = _lundi(jour)
        absences_semaine[lundi] = absences_semaine.get(lundi, 0.0) + frac

    rows = (
        HeuresHebdo.query.filter(
            HeuresHebdo.user_id == user_id,
            HeuresHebdo.date_lundi >= _lundi(param.debut_exercice),
            HeuresHebdo.date_lundi <= fin_calcul,
        ).all()
    )
    heures_par_lundi = {r.date_lundi: (r.heures_travaillees or 0) for r in rows}

    # Semaines avec heures saisies ou absences (pour le détail UI).
    semaines = sorted(
        s for s in (set(heures_par_lundi.keys()) | set(absences_semaine.keys())) if s <= fin_calcul
    )

    total = 0.0
    detail = []
    for lundi in semaines:
        jours_absence = absences_semaine.get(lundi, 0.0)
        heures = heures_par_lundi.get(lundi)
        surplus = 0.0
        if heures is not None:
            surplus = calculer_rtt_semaine(
                heures,
                jours_absence,
                seuil_hebdo=seuil,
                heures_par_jour=heures_jour,
                coef=coef,
            )

        rtt = surplus
        total += rtt
        detail.append({
            "lundi": lundi,
            "heures": heures or 0,
            "jours_absence": jours_absence,
            "surplus": surplus,
            "rtt": rtt,
        })

    return RttHebdoResult(
        user_id=user_id,
        # On ne tronque plus à l'entier : on conserve les fractions d'heure
        # (arrondi à 2 décimales pour neutraliser les artefacts de calcul flottant).
        # L'arrondi d'affichage se fait dans les templates.
        rtt_calculee=round(total, 2),
        nb_semaines=len(semaines),
        detail=detail,
    )


def maj_rtt_allocations_hebdo(param: ParametrageAnnuel, user_ids: list[int] | None = None) -> list[RttHebdoResult]:
    """Met à jour AllocationConge.rtt_heures_allouees selon le calcul hebdomadaire.

    Le calcul hebdomadaire est désormais le seul mode RTT de l'application.
    """
    if not param:
        return []

    q = AllocationConge.query.filter_by(parametrage_id=param.id)
    if user_ids:
        q = q.filter(AllocationConge.user_id.in_(user_ids))
    allocations = q.all()

    results: list[RttHebdoResult] = []
    for alloc in allocations:
        res = calculer_rtt_hebdo(alloc.user_id, param)
        alloc.rtt_heures_allouees = res.rtt_calculee
        results.append(res)

    db.session.commit()
    return results
