"""Calcul RTT hebdomadaire tenant compte des absences (points 7 + 9).

Règle métier : le RTT provient des heures travaillées au-delà d'un seuil hebdomadaire
(par défaut 35 h). Une absence dans la semaine (congé, arrêt maladie...) ne doit PAS
faire perdre de RTT au salarié : on réduit donc le seuil au prorata des jours d'absence.

Exemple : seuil 35 h, 1 jour d'absence (7 h) -> seuil ajusté 28 h. Si le salarié a
travaillé 28 h cette semaine-là, RTT = max(0, 28 - 28) = 0 (aucun RTT enlevé). S'il a
travaillé 31 h, RTT = 3 h.

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

# Valeurs par défaut (modifiables ultérieurement via paramétrage si besoin).
SEUIL_HEBDO_DEFAUT = 35
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
    return surplus * float(coef)


def _coef_param(param: ParametrageAnnuel) -> float:
    """Coefficient de conversion surplus -> RTT. 1.0 par défaut (surplus = RTT)."""
    coef = float(getattr(param, "rtt_coef_surplus", 0.0) or 0.0)
    return coef if coef > 0 else 1.0


def seuil_hebdo_param(param: ParametrageAnnuel | None) -> float:
    """Seuil hebdomadaire RTT depuis le paramétrage actif, sinon constante par défaut."""
    if param is not None:
        val = getattr(param, "rtt_seuil_hebdo", None)
        if val is not None and int(val) > 0:
            return float(val)
    return float(SEUIL_HEBDO_DEFAUT)


def heures_par_jour_absence_param(param: ParametrageAnnuel | None) -> float:
    """Heures déduites du seuil par jour d'absence, depuis le paramétrage ou défaut."""
    if param is not None:
        val = getattr(param, "rtt_heures_par_jour_absence", None)
        if val is not None and int(val) > 0:
            return float(val)
    return float(HEURES_PAR_JOUR_DEFAUT)


def rtt_acquis_par_semaine_param(param: ParametrageAnnuel | None) -> float:
    """RTT acquis automatiquement par semaine (ex. 0,35 h). 0 si non configuré."""
    if param is not None:
        val = getattr(param, "rtt_acquis_par_semaine", None)
        if val is not None:
            try:
                return max(0.0, float(val))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _semaines_exercice(param: ParametrageAnnuel) -> list:
    """Liste des lundis (semaines ISO) couvrant l'exercice [debut, fin]."""
    lundi = _lundi(param.debut_exercice)
    fin = param.fin_exercice
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
    non travaillé, ce qui justifie de réduire le seuil hebdomadaire).
    """
    debut = param.debut_exercice
    fin = param.fin_exercice
    feries = get_dates_feries_set(debut, fin)

    conges = (
        Conge.query.filter(
            Conge.user_id == user_id,
            Conge.statut == "valide",
            Conge.date_debut <= fin,
            Conge.date_fin >= debut,
        ).all()
    )

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


def jours_absence_semaine(user_id: int, lundi: date) -> float:
    """Nombre de jours ouvrables d'absence (congés validés) sur la semaine du `lundi`.

    Utilisé par l'écran de saisie hebdomadaire pour afficher le contexte d'absence.
    """
    lundi = _lundi(lundi)
    dimanche = lundi + timedelta(days=6)
    feries = get_dates_feries_set(lundi, dimanche)
    conges = (
        Conge.query.filter(
            Conge.user_id == user_id,
            Conge.statut == "valide",
            Conge.date_debut <= dimanche,
            Conge.date_fin >= lundi,
        ).all()
    )
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


def calculer_rtt_hebdo(user_id: int, param: ParametrageAnnuel) -> RttHebdoResult:
    """Agrège le RTT hebdomadaire d'un salarié sur l'exercice.

    Deux composantes, additionnées par semaine :
    - Base automatique : ``rtt_acquis_par_semaine`` (ex. 0,35 h) acquis pour chaque
      semaine de l'exercice, proratisé selon les absences (semaine entièrement en
      congé → 0). Indépendant de toute saisie d'heures.
    - Heures supplémentaires : surplus des heures travaillées (HeuresHebdo)
      au-delà du seuil hebdomadaire ajusté.

    Si aucune base n'est configurée (0), on conserve le comportement historique :
    seules les semaines avec des heures saisies génèrent du RTT.
    """
    seuil = seuil_hebdo_param(param)
    heures_jour = heures_par_jour_absence_param(param)
    coef = _coef_param(param)
    base_hebdo = rtt_acquis_par_semaine_param(param)

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
            HeuresHebdo.date_lundi <= param.fin_exercice,
        ).all()
    )
    heures_par_lundi = {r.date_lundi: (r.heures_travaillees or 0) for r in rows}

    # Avec une base hebdomadaire, on parcourt toutes les semaines de l'exercice
    # (acquisition automatique). Sinon, uniquement les semaines saisies.
    if base_hebdo > 0:
        semaines = _semaines_exercice(param)
    else:
        semaines = sorted(heures_par_lundi.keys())

    total = 0.0
    detail = []
    for lundi in semaines:
        jours_absence = absences_semaine.get(lundi, 0.0)
        # Présence de la semaine sur 5 jours ouvrables de référence, bornée [0,1].
        presence = max(0.0, min(1.0, (5.0 - jours_absence) / 5.0))
        base = base_hebdo * presence

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

        rtt = base + surplus
        total += rtt
        detail.append({
            "lundi": lundi,
            "heures": heures or 0,
            "jours_absence": jours_absence,
            "base": round(base, 2),
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
