from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func

from models import db
from models.conge import Conge
from models.interessement_regle import InteressementRegle
from models.user import User


@dataclass(frozen=True)
class InteressementDetailLigne:
    type_absence: str
    jours: int
    points_par_jour: float
    impact_points: float


@dataclass(frozen=True)
class InteressementResult:
    user_id: int
    nom: str
    prenom: str
    actif: bool
    base_points: int
    total_jours_absence: int
    total_malus: float
    points_final: float
    details: list[InteressementDetailLigne]


def calculer_interessement(periode, include_inactifs: bool = False) -> list[InteressementResult]:
    if not periode or not getattr(periode, 'is_valid_dates', False):
        raise ValueError('Periode interessement invalide.')

    start = periode.date_debut
    end = periode.date_fin

    users_q = User.query
    if not include_inactifs:
        users_q = users_q.filter_by(actif=True)
    users = users_q.order_by(User.nom, User.prenom).all()
    user_ids = [u.id for u in users]

    regles_rows = InteressementRegle.query.filter_by(periode_id=periode.id).all()
    regles = {r.type_absence: float(r.points_par_jour or 0.0) for r in regles_rows}

    by_user_type: dict[tuple[int, str], int] = {}
    if user_ids:
        rows = (
            db.session.query(
                Conge.user_id,
                Conge.type_conge,
                func.coalesce(func.sum(Conge.nb_jours_ouvrables), 0),
            )
            .filter(
                Conge.user_id.in_(user_ids),
                Conge.statut == 'valide',
                Conge.date_debut >= start,
                Conge.date_fin <= end,
            )
            .group_by(Conge.user_id, Conge.type_conge)
            .all()
        )
        by_user_type = {(int(uid), str(t)): int(v or 0) for uid, t, v in rows}

    results: list[InteressementResult] = []
    for u in users:
        details: list[InteressementDetailLigne] = []
        total_jours = 0
        total_malus = 0.0

        types = set([t for (uid, t) in by_user_type.keys() if uid == u.id]) | set(regles.keys())
        for t in sorted(types):
            jours = int(by_user_type.get((u.id, t), 0) or 0)
            p = float(regles.get(t, 0.0))
            impact = float(jours) * float(p)
            if jours or p:
                details.append(InteressementDetailLigne(type_absence=t, jours=jours, points_par_jour=p, impact_points=impact))
            total_jours += jours
            total_malus += impact

        points_final = float(periode.base_points) - float(total_malus)
        if points_final < float(periode.plancher_points):
            points_final = float(periode.plancher_points)

        results.append(
            InteressementResult(
                user_id=u.id,
                nom=u.nom,
                prenom=u.prenom,
                actif=bool(u.actif),
                base_points=int(periode.base_points),
                total_jours_absence=int(total_jours),
                total_malus=float(total_malus),
                points_final=float(points_final),
                details=details,
            )
        )

    return results
