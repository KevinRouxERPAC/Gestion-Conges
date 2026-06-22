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

from sqlalchemy import func, or_

from models import db
from models.conge import Conge
from services.calcul_jours import compter_jours_ouvrables_avec_demi

STATUT_VALIDE = "valide"
STATUTS_EN_ATTENTE = ("en_attente_responsable", "en_attente_rh")

# Types décomptés sur le solde CP (les deux puisent dans la même enveloppe jours).
TYPES_CP = ("CP", "Anciennete")
TYPE_RTT = ("RTT",)


def _num(val):
    """Normalise une somme : 0 si None, int si entier, float arrondi sinon.

    L'arrondi à 2 décimales neutralise les artefacts de calcul flottant
    (ex. 16.0999999) tout en préservant les demi-journées (0,5) et les
    fractions d'heure RTT (ex. 16,1).
    """
    if val is None:
        return 0
    f = float(val)
    return int(f) if f.is_integer() else round(f, 2)


def _prorata_fenetre(conge, colonne_key, date_debut_min, date_fin_max):
    """Part de la valeur d'un congé *à cheval* tombant dans [min, max].

    Le prorata se fait au prorata des jours ouvrables réellement contenus dans la
    fenêtre, rapportés au total des jours ouvrables du congé. Appliqué tel quel à
    la valeur sommée (jours ou heures), il garantit l'invariant : la somme des
    parts de deux exercices adjacents égale la valeur totale du congé.

    Les demi-journées de bordure du congé ne s'appliquent qu'à la part qui les
    contient (l'autre bordure tombe sur une coupure de jour plein).
    """
    valeur = getattr(conge, colonne_key, None)
    if not valeur:
        return 0.0

    jours_total = compter_jours_ouvrables_avec_demi(
        conge.date_debut, conge.date_fin, conge.demi_journee_debut, conge.demi_journee_fin
    )
    if jours_total <= 0:
        return 0.0

    part_debut = max(conge.date_debut, date_debut_min)
    part_fin = min(conge.date_fin, date_fin_max)
    # La demi-journée de bordure ne compte que si la vraie bordure est dans la fenêtre.
    demi_debut = conge.demi_journee_debut if conge.date_debut >= date_debut_min else None
    demi_fin = conge.demi_journee_fin if conge.date_fin <= date_fin_max else None
    jours_fenetre = compter_jours_ouvrables_avec_demi(part_debut, part_fin, demi_debut, demi_fin)

    return float(valeur) * jours_fenetre / jours_total


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

    Sémantique des bornes (IMPORTANT) :
        Un congé est décompté pour sa part de jours ouvrables réellement contenue
        dans la fenêtre ``[date_debut_min, date_fin_max]`` :
        - les congés *entièrement contenus* sont sommés tels quels (chemin SQL
          agrégé, rapide) ;
        - les congés *à cheval* sur une borne sont décomptés **au prorata** des
          jours ouvrables tombant dans la fenêtre (calcul Python, cf.
          ``_prorata_fenetre``).
        Conséquences concrètes :
        - un congé qui chevauche la fin d'exercice (ex. 30/12 → 03/01) est réparti
          entre les deux exercices ; la somme des deux parts égale le total (aucun
          jour perdu ni compté deux fois) ;
        - dans l'export comptable « à une date » (``date_fin_max`` = date d'arrêté),
          un congé en cours est compté pour sa partie déjà écoulée à cette date.
        Cette règle de prorata est centralisée ici (et nulle part ailleurs) pour
        garantir la cohérence inter-écrans.

    Returns:
        Un nombre si ``group_by`` est ``None``, sinon un dict agrégé.
    """
    if isinstance(statuts, str):
        statuts = (statuts,)

    # Filtres communs aux deux chemins (SQL agrégé + prorata Python).
    def _appliquer_filtres_communs(q):
        q = q.filter(Conge.statut.in_(tuple(statuts)))
        if types is not None:
            q = q.filter(Conge.type_conge.in_(tuple(types)))
        if user_id is not None:
            q = q.filter(Conge.user_id == user_id)
        if user_ids is not None:
            q = q.filter(Conge.user_id.in_(tuple(user_ids)))
        if conge_id_exclu is not None:
            q = q.filter(Conge.id != conge_id_exclu)
        return q

    total_expr = func.coalesce(func.sum(colonne), 0)

    if group_by == "user":
        select_cols = (Conge.user_id, total_expr)
    elif group_by == "user_type":
        select_cols = (Conge.user_id, Conge.type_conge, total_expr)
    else:
        select_cols = (total_expr,)

    # --- Chemin 1 : congés entièrement contenus (agrégat SQL rapide). ---
    q = _appliquer_filtres_communs(
        db.session.query(*select_cols).filter(
            Conge.date_debut >= date_debut_min,
            Conge.date_fin <= date_fin_max,
        )
    )

    # --- Chemin 2 : congés à cheval sur une borne (prorata Python). ---
    # Chevauchent la fenêtre sans y être entièrement contenus.
    colonne_key = colonne.key
    q_frontiere = _appliquer_filtres_communs(
        db.session.query(Conge).filter(
            Conge.date_debut <= date_fin_max,
            Conge.date_fin >= date_debut_min,
            or_(Conge.date_debut < date_debut_min, Conge.date_fin > date_fin_max),
        )
    )

    if group_by == "user":
        res = {int(uid): _num(val) for uid, val in q.group_by(Conge.user_id).all()}
        for c in q_frontiere.all():
            part = _prorata_fenetre(c, colonne_key, date_debut_min, date_fin_max)
            if part:
                res[c.user_id] = _num((res.get(c.user_id, 0) or 0) + part)
        return res

    if group_by == "user_type":
        rows = q.group_by(Conge.user_id, Conge.type_conge).all()
        res = {(int(uid), str(t)): _num(val) for uid, t, val in rows}
        for c in q_frontiere.all():
            part = _prorata_fenetre(c, colonne_key, date_debut_min, date_fin_max)
            if part:
                cle = (c.user_id, c.type_conge)
                res[cle] = _num((res.get(cle, 0) or 0) + part)
        return res

    total = float(q.scalar() or 0)
    for c in q_frontiere.all():
        total += _prorata_fenetre(c, colonne_key, date_debut_min, date_fin_max)
    return _num(total)
