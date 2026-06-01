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
    rtt_calculee: int
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

    Les heures travaillées proviennent de HeuresHebdo (saisie RH par semaine) ;
    les absences sont déduites des congés validés. Seules les semaines avec des
    heures saisies génèrent du RTT.
    """
    seuil = SEUIL_HEBDO_DEFAUT
    heures_jour = HEURES_PAR_JOUR_DEFAUT
    coef = _coef_param(param)

    # Absences par semaine (lundi -> total jours d'absence).
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

    total = 0.0
    detail = []
    for r in rows:
        lundi = r.date_lundi
        jours_absence = absences_semaine.get(lundi, 0.0)
        rtt = calculer_rtt_semaine(
            r.heures_travaillees or 0,
            jours_absence,
            seuil_hebdo=seuil,
            heures_par_jour=heures_jour,
            coef=coef,
        )
        total += rtt
        detail.append({
            "lundi": lundi,
            "heures": r.heures_travaillees or 0,
            "jours_absence": jours_absence,
            "rtt": rtt,
        })

    return RttHebdoResult(
        user_id=user_id,
        rtt_calculee=int(round(total)),
        nb_semaines=len(rows),
        detail=detail,
    )


def maj_rtt_allocations_hebdo(param: ParametrageAnnuel, user_ids: list[int] | None = None) -> list[RttHebdoResult]:
    """Met à jour AllocationConge.rtt_heures_allouees selon le calcul hebdomadaire.

    Ne s'applique que si le mode RTT du paramétrage est 'hebdo'.
    """
    if not param or getattr(param, "rtt_calc_mode", "fixe") != "hebdo":
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
