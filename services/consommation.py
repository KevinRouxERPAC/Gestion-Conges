"""Source de vérité unique pour le calcul de consommation des congés (NFR9).

Toute somme de consommation (jours CP, heures RTT, jours/heures exceptionnels)
DOIT passer par ce module. Objectif : 0 écart entre l'écran salarié, l'export
comptable et l'intéressement pour un même salarié/exercice.

Auparavant cette logique était réécrite dans 4 fichiers distincts (solde,
conges_exceptionnels, export_comptable, interessement), avec des bornes
temporelles et des filtres de statut divergents. Cette primitive centralise la
règle : « somme d'une colonne des congés d'un périmètre, sur une fenêtre de
dates, pour un ensemble de statuts et de types ».
"""

from sqlalchemy import func

from models import db
from models.conge import Conge

STATUT_VALIDE = "valide"
STATUTS_EN_ATTENTE = ("en_attente_responsable", "en_attente_rh")

# Types décomptés sur le solde CP (les deux puisent dans la même enveloppe jours).
TYPES_CP = ("CP", "Anciennete")
TYPE_RTT = ("RTT",)


def _num(val):
    """Normalise une somme SQL : 0 si None, int si entier, float sinon (demi-journées)."""
    if val is None:
        return 0
    f = float(val)
    return int(f) if f.is_integer() else f


def somme_consommation(
    *,
    colonne,
    date_debut_min,
    date_fin_max,
    statuts,
    types=None,
    user_id=None,
    user_ids=None,
    conge_id_exclu=None,
    group_by=None,
):
    """Somme une colonne de `Conge` selon un périmètre commun à tous les calculs.

    Args:
        colonne : colonne à sommer (ex. ``Conge.nb_jours_ouvrables``).
        date_debut_min : borne basse incluse sur ``date_debut``.
        date_fin_max : borne haute incluse sur ``date_fin`` (fin d'exercice ou date d'arrêté).
        statuts : statut ou itérable de statuts à inclure.
        types : itérable de ``type_conge`` à inclure ; ``None`` = tous les types.
        user_id : restreint à un salarié.
        user_ids : restreint à un ensemble de salariés (pour les agrégats groupés).
        conge_id_exclu : exclut un congé (utile pour re-vérifier un plafond hors congé courant).
        group_by : ``None`` (scalaire), ``"user"`` (dict user_id→valeur) ou
            ``"user_type"`` (dict (user_id, type)→valeur).

    Returns:
        Un nombre si ``group_by`` est ``None``, sinon un dict agrégé.
    """
    if isinstance(statuts, str):
        statuts = (statuts,)

    total_expr = func.coalesce(func.sum(colonne), 0)

    if group_by == "user":
        select_cols = (Conge.user_id, total_expr)
    elif group_by == "user_type":
        select_cols = (Conge.user_id, Conge.type_conge, total_expr)
    else:
        select_cols = (total_expr,)

    q = db.session.query(*select_cols).filter(
        Conge.date_debut >= date_debut_min,
        Conge.date_fin <= date_fin_max,
        Conge.statut.in_(tuple(statuts)),
    )

    if types is not None:
        q = q.filter(Conge.type_conge.in_(tuple(types)))
    if user_id is not None:
        q = q.filter(Conge.user_id == user_id)
    if user_ids is not None:
        q = q.filter(Conge.user_id.in_(tuple(user_ids)))
    if conge_id_exclu is not None:
        q = q.filter(Conge.id != conge_id_exclu)

    if group_by == "user":
        return {int(uid): _num(val) for uid, val in q.group_by(Conge.user_id).all()}
    if group_by == "user_type":
        rows = q.group_by(Conge.user_id, Conge.type_conge).all()
        return {(int(uid), str(t)): _num(val) for uid, t, val in rows}

    return _num(q.scalar())
