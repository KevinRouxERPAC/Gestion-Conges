from __future__ import annotations

from dataclasses import dataclass

from models.conge import Conge
from models.user import User
from services.consommation import somme_consommation, STATUT_VALIDE

TYPE_MALADIE = "Maladie"


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
    jours_maladie: int
    total_malus: float
    points_final: float
    part_euros: float | None
    details: list[InteressementDetailLigne]


def calculer_interessement(periode, include_inactifs: bool = False) -> list[InteressementResult]:
    """Calcule l'intéressement : seuls les arrêts maladie réduisent les points.

    Chaque salarié part de ``base_points``. Chaque jour de Maladie validé dans la
    période retire ``malus_maladie_par_jour`` points. Le montant total est réparti
    au prorata des points finaux (plancher appliqué si configuré).
    """
    if not periode or not getattr(periode, "is_valid_dates", False):
        raise ValueError("Periode interessement invalide.")

    start = periode.date_debut
    end = periode.date_fin
    malus_par_jour = float(getattr(periode, "malus_maladie_par_jour", None) or 5.0)

    users_q = User.query
    if not include_inactifs:
        users_q = users_q.filter_by(actif=True)
    # L'intéressement est une prime réservée aux salariés : les gestionnaires RH
    # et les responsables (qui valident/administrent) n'en sont pas bénéficiaires.
    users_q = users_q.filter_by(role="salarie")
    users = users_q.order_by(User.nom, User.prenom).all()
    user_ids = [u.id for u in users]

    jours_maladie_par_user: dict[int, int] = {}
    if user_ids:
        by_user_type = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=start,
            date_fin_max=end,
            statuts=STATUT_VALIDE,
            types=(TYPE_MALADIE,),
            user_ids=user_ids,
            group_by="user",
        )
        jours_maladie_par_user = {int(uid): int(val or 0) for uid, val in by_user_type.items()}

    results: list[InteressementResult] = []
    for u in users:
        jours_maladie = int(jours_maladie_par_user.get(u.id, 0) or 0)
        total_malus = float(jours_maladie) * malus_par_jour
        points_final = float(periode.base_points) - total_malus
        if points_final < float(periode.plancher_points):
            points_final = float(periode.plancher_points)

        details: list[InteressementDetailLigne] = []
        if jours_maladie or malus_par_jour:
            details.append(
                InteressementDetailLigne(
                    type_absence=TYPE_MALADIE,
                    jours=jours_maladie,
                    points_par_jour=malus_par_jour,
                    impact_points=total_malus,
                )
            )

        results.append(
            InteressementResult(
                user_id=u.id,
                nom=u.nom,
                prenom=u.prenom,
                actif=bool(u.actif),
                base_points=int(periode.base_points),
                jours_maladie=jours_maladie,
                total_malus=float(total_malus),
                points_final=float(points_final),
                part_euros=None,
                details=details,
            )
        )

    _repartir_montant_total(results, periode)
    return results


def _repartir_montant_total(results: list[InteressementResult], periode) -> None:
    """Répartit ``periode.montant_total_euros`` au prorata des points finaux."""
    montant = float(periode.montant_total_euros or 0)
    if montant <= 0 or not results:
        return

    somme_points = sum(r.points_final for r in results)
    if somme_points <= 0:
        return

    parts_bruts = [r.points_final * montant / somme_points for r in results]
    parts_arrondies = [round(p, 2) for p in parts_bruts]

    reliquat = round(montant - sum(parts_arrondies), 2)
    if abs(reliquat) >= 0.01 and len(results) > 0:
        idx_max = max(range(len(results)), key=lambda i: results[i].points_final)
        parts_arrondies[idx_max] = round(parts_arrondies[idx_max] + reliquat, 2)

    for r, part in zip(results, parts_arrondies):
        object.__setattr__(r, "part_euros", float(part))
