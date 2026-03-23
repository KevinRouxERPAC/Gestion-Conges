from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func

from models import db
from models.heures_payees import HeuresPayees
from models.parametrage import AllocationConge, ParametrageAnnuel


@dataclass(frozen=True)
class RttCalcResult:
    user_id: int
    heures_travaillees: int
    reference: int
    coef: float
    rtt_calculee: int


def _sum_heures_travaillees_sur_exercice(user_id: int, param: ParametrageAnnuel) -> int:
    """Somme des heures_travaillees sur l'exercice (filtre annee/mois)."""
    start = param.debut_exercice
    end = param.fin_exercice
    start_key = start.year * 100 + start.month
    end_key = end.year * 100 + end.month

    key_expr = (HeuresPayees.annee * 100) + HeuresPayees.mois
    total = (
        db.session.query(func.coalesce(func.sum(HeuresPayees.heures_travaillees), 0))
        .filter(HeuresPayees.user_id == user_id)
        .filter(key_expr >= start_key)
        .filter(key_expr <= end_key)
        .scalar()
    )
    try:
        return int(total or 0)
    except Exception:
        return 0


def calculer_rtt_depuis_heures(user_id: int, param: ParametrageAnnuel) -> RttCalcResult:
    heures = _sum_heures_travaillees_sur_exercice(user_id, param)
    ref = int(getattr(param, "rtt_heures_reference", 0) or 0)
    coef = float(getattr(param, "rtt_coef_surplus", 0.0) or 0.0)

    surplus = max(0, heures - ref)
    rtt = int(round(surplus * coef)) if coef > 0 else 0

    return RttCalcResult(
        user_id=user_id,
        heures_travaillees=heures,
        reference=ref,
        coef=coef,
        rtt_calculee=rtt,
    )


def maj_rtt_allocations_depuis_heures(param: ParametrageAnnuel, user_ids: list[int] | None = None) -> list[RttCalcResult]:
    """Met à jour AllocationConge.rtt_heures_allouees selon le paramétrage.

    - Si mode != "heures": ne modifie rien.
    - Si mode == "heures": calcule et applique sur les allocations de l'exercice.
    """
    if not param or getattr(param, "rtt_calc_mode", "fixe") != "heures":
        return []

    q = AllocationConge.query.filter_by(parametrage_id=param.id)
    if user_ids:
        q = q.filter(AllocationConge.user_id.in_(user_ids))
    allocations = q.all()

    results: list[RttCalcResult] = []
    for alloc in allocations:
        res = calculer_rtt_depuis_heures(alloc.user_id, param)
        alloc.rtt_heures_allouees = res.rtt_calculee
        results.append(res)

    db.session.commit()
    return results
