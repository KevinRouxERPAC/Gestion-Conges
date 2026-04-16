from datetime import date, timedelta
from models import db
from models.conge import Conge
from models.parametrage import ParametrageAnnuel, AllocationConge
from sqlalchemy import func


def _shift_exercice(param: ParametrageAnnuel) -> tuple[date, date]:
    """
    Calcule les dates du prochain exercice à partir d'un paramétrage existant.
    On conserve la même durée (fin - début) et on démarre le lendemain de la fin.
    """
    duree = param.fin_exercice - param.debut_exercice
    debut = param.fin_exercice + timedelta(days=1)
    fin = debut + duree
    return debut, fin


def _ensure_exercice_actif(today: date | None = None) -> ParametrageAnnuel | None:
    """
    Garantit qu'un exercice actif est pertinent par rapport à la date du jour.
    Si l'exercice actif est terminé (today > fin_exercice), un nouvel exercice est créé
    avec les mêmes paramètres par défaut, activé, l'ancien est désactivé, et les allocations
    CP/RTT sont générées/mises à jour.
    """
    if today is None:
        today = date.today()

    param = ParametrageAnnuel.query.filter_by(actif=True).first()
    if not param:
        return None

    if today <= param.fin_exercice:
        return param

    # L'exercice actif est terminé : créer le suivant si absent, basculer actif, générer allocations.
    new_debut, new_fin = _shift_exercice(param)

    existing = (
        ParametrageAnnuel.query.filter_by(debut_exercice=new_debut, fin_exercice=new_fin).first()
    )
    if existing:
        new_param = existing
    else:
        new_param = ParametrageAnnuel(
            debut_exercice=new_debut,
            fin_exercice=new_fin,
            jours_conges_defaut=param.jours_conges_defaut,
            rtt_heures_defaut=param.rtt_heures_defaut,
            rtt_calc_mode=param.rtt_calc_mode,
            rtt_heures_reference=param.rtt_heures_reference,
            rtt_coef_surplus=param.rtt_coef_surplus,
            actif=False,  # on active après commit + verrouillage ci-dessous
        )
        db.session.add(new_param)
        db.session.flush()

    # Un seul exercice actif.
    ParametrageAnnuel.query.update({ParametrageAnnuel.actif: False})
    new_param.actif = True
    db.session.commit()

    # Générer allocations pour le nouvel exercice (idempotent).
    generer_allocations_pour_parametrage(new_param)
    return new_param


def get_parametrage_actif(today: date | None = None):
    """Retourne le paramétrage annuel actif."""
    return _ensure_exercice_actif(today=today)


def get_allocation(user_id, parametrage_id=None):
    """Retourne l'allocation de congés d'un utilisateur pour le paramétrage donné."""
    if parametrage_id is None:
        param = get_parametrage_actif()
        if param is None:
            return None
        parametrage_id = param.id

    return AllocationConge.query.filter_by(
        user_id=user_id,
        parametrage_id=parametrage_id,
    ).first()


def _get_param(parametrage_id):
    if parametrage_id:
        return ParametrageAnnuel.query.get(parametrage_id)
    return get_parametrage_actif()


def _get_parametrage_precedent(param: ParametrageAnnuel):
    """Retourne l'exercice précédent le plus récent par date de fin."""
    if not param:
        return None
    return (
        ParametrageAnnuel.query
        .filter(
            ParametrageAnnuel.id != param.id,
            ParametrageAnnuel.fin_exercice < param.debut_exercice,
        )
        .order_by(ParametrageAnnuel.fin_exercice.desc())
        .first()
    )


def _repartir_consommation_cp_anciennete(total_consomme, jours_conges, jours_anciennete, jours_report=0):
    """Répartit la consommation en priorisant CP (incluant report) puis ancienneté."""
    cp_disponibles = (jours_conges or 0) + (jours_report or 0)
    anciennete_disponible = jours_anciennete or 0
    total = total_consomme or 0

    cp_consomme = min(total, cp_disponibles)
    anciennete_consomme = min(max(total - cp_consomme, 0), anciennete_disponible)

    return {
        "cp_disponibles": cp_disponibles,
        "cp_consomme": cp_consomme,
        "cp_restant": cp_disponibles - cp_consomme,
        "anciennete_disponible": anciennete_disponible,
        "anciennete_consomme": anciennete_consomme,
        "anciennete_restante": anciennete_disponible - anciennete_consomme,
    }


def calculer_jours_cps_consommes(user_id, parametrage_id=None):
    """Calcule le nombre de jours consommés (CP + Ancienneté) pour l'exercice actif."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    result = db.session.query(func.coalesce(func.sum(Conge.nb_jours_ouvrables), 0)).filter(
        Conge.user_id == user_id,
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge.in_(["CP", "Anciennete"]),
        Conge.statut == "valide",
    ).scalar()

    return result


def calculer_heures_rtt_consommes(user_id, parametrage_id=None):
    """Calcule le nombre d'heures RTT consommées pour l'exercice actif."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    result = db.session.query(func.coalesce(func.sum(Conge.nb_heures_rtt), 0)).filter(
        Conge.user_id == user_id,
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge == "RTT",
        Conge.statut == "valide",
    ).scalar()

    return result


def calculer_solde(user_id, parametrage_id=None):
    """Calcule les soldes restant d'un utilisateur pour CP (jours) et RTT (heures)."""
    allocation = get_allocation(user_id, parametrage_id)
    if allocation is None:
        return {
            "total_alloue": 0,
            "jours_conges": 0,
            "jours_anciennete": 0,
            "jours_report": 0,
            "total_consomme": 0,
            "solde_restant": 0,
            "cp_restant": 0,
            "cp_consomme": 0,
            "anciennete_restante": 0,
            "anciennete_consommee": 0,
            "rtt_heures_allouees": 0,
            "rtt_heures_reportees": 0,
            "rtt_total_alloue": 0,
            "rtt_total_consomme": 0,
            "rtt_solde_restant": 0,
        }

    pid = allocation.parametrage_id

    cp_consomme = calculer_jours_cps_consommes(user_id, pid)
    cp_total = allocation.total_jours
    repartition_cp = _repartir_consommation_cp_anciennete(
        total_consomme=cp_consomme,
        jours_conges=allocation.jours_alloues,
        jours_anciennete=allocation.jours_anciennete,
        jours_report=allocation.jours_report,
    )

    rtt_total = allocation.total_rtt_heures
    rtt_consomme = calculer_heures_rtt_consommes(user_id, pid)

    return {
        # CP (jours) - clés compatibles avec l'existant
        "total_alloue": cp_total,
        "jours_conges": allocation.jours_alloues,
        "jours_anciennete": allocation.jours_anciennete,
        "jours_report": allocation.jours_report,
        "total_consomme": cp_consomme,
        "solde_restant": cp_total - cp_consomme,
        "cp_restant": repartition_cp["cp_restant"],
        "cp_consomme": repartition_cp["cp_consomme"],
        "anciennete_restante": repartition_cp["anciennete_restante"],
        "anciennete_consommee": repartition_cp["anciennete_consomme"],
        # RTT (heures)
        "rtt_heures_allouees": allocation.rtt_heures_allouees,
        "rtt_heures_reportees": allocation.rtt_heures_reportees,
        "rtt_total_alloue": rtt_total,
        "rtt_total_consomme": rtt_consomme,
        "rtt_solde_restant": rtt_total - rtt_consomme,
    }


def verifier_solde_suffisant(user_id, nb_jours, conge_id_exclu=None):
    """Vérifie si le solde CP est suffisant pour poser nb_jours de congés."""
    solde_info = calculer_solde(user_id)
    solde_actuel = solde_info["solde_restant"]

    if conge_id_exclu:
        conge_exclu = Conge.query.get(conge_id_exclu)
        if conge_exclu and conge_exclu.statut == "valide" and conge_exclu.type_conge in ("CP", "Anciennete"):
            solde_actuel += conge_exclu.nb_jours_ouvrables

    return solde_actuel >= nb_jours


def verifier_solde_rtt_suffisant(user_id, nb_heures, conge_id_exclu=None):
    """Vérifie si le solde RTT (en heures) est suffisant."""
    solde_info = calculer_solde(user_id)
    solde_actuel = solde_info["rtt_solde_restant"]

    if conge_id_exclu:
        conge_exclu = Conge.query.get(conge_id_exclu)
        if conge_exclu and conge_exclu.statut == "valide" and conge_exclu.type_conge == "RTT":
            solde_actuel += conge_exclu.nb_heures_rtt or 0

    return solde_actuel >= nb_heures


def calculer_soldes_batch(user_ids, parametrage_id=None):
    """Calcule les soldes de tous les user_ids en 3 requêtes au lieu de N*4."""
    param = _get_param(parametrage_id)
    empty = {
        "total_alloue": 0, "jours_conges": 0, "jours_anciennete": 0,
        "jours_report": 0, "total_consomme": 0, "solde_restant": 0,
        "cp_restant": 0, "cp_consomme": 0, "anciennete_restante": 0, "anciennete_consommee": 0,
        "rtt_heures_allouees": 0, "rtt_heures_reportees": 0,
        "rtt_total_alloue": 0, "rtt_total_consomme": 0, "rtt_solde_restant": 0,
    }
    if not param or not user_ids:
        return {uid: dict(empty) for uid in user_ids}

    allocations = AllocationConge.query.filter(
        AllocationConge.user_id.in_(user_ids),
        AllocationConge.parametrage_id == param.id,
    ).all()
    alloc_by_user = {a.user_id: a for a in allocations}

    cp_rows = db.session.query(
        Conge.user_id,
        func.coalesce(func.sum(Conge.nb_jours_ouvrables), 0),
    ).filter(
        Conge.user_id.in_(user_ids),
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge.in_(["CP", "Anciennete"]),
        Conge.statut == "valide",
    ).group_by(Conge.user_id).all()
    cp_by_user = {uid: float(v) for uid, v in cp_rows}

    rtt_rows = db.session.query(
        Conge.user_id,
        func.coalesce(func.sum(Conge.nb_heures_rtt), 0),
    ).filter(
        Conge.user_id.in_(user_ids),
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge == "RTT",
        Conge.statut == "valide",
    ).group_by(Conge.user_id).all()
    rtt_by_user = {uid: float(v) for uid, v in rtt_rows}

    result = {}
    for uid in user_ids:
        alloc = alloc_by_user.get(uid)
        if not alloc:
            result[uid] = dict(empty)
            continue
        cp_total = alloc.total_jours
        cp_consomme = cp_by_user.get(uid, 0)
        repartition_cp = _repartir_consommation_cp_anciennete(
            total_consomme=cp_consomme,
            jours_conges=alloc.jours_alloues,
            jours_anciennete=alloc.jours_anciennete,
            jours_report=alloc.jours_report,
        )
        rtt_total = alloc.total_rtt_heures
        rtt_consomme = rtt_by_user.get(uid, 0)
        result[uid] = {
            "total_alloue": cp_total,
            "jours_conges": alloc.jours_alloues,
            "jours_anciennete": alloc.jours_anciennete,
            "jours_report": alloc.jours_report,
            "total_consomme": cp_consomme,
            "solde_restant": cp_total - cp_consomme,
            "cp_restant": repartition_cp["cp_restant"],
            "cp_consomme": repartition_cp["cp_consomme"],
            "anciennete_restante": repartition_cp["anciennete_restante"],
            "anciennete_consommee": repartition_cp["anciennete_consomme"],
            "rtt_heures_allouees": alloc.rtt_heures_allouees,
            "rtt_heures_reportees": alloc.rtt_heures_reportees,
            "rtt_total_alloue": rtt_total,
            "rtt_total_consomme": rtt_consomme,
            "rtt_solde_restant": rtt_total - rtt_consomme,
        }
    return result


def generer_allocations_pour_parametrage(param: ParametrageAnnuel):
    """Crée ou met à jour les allocations de congés (CP + RTT) pour tous les salariés actifs."""
    from models.user import User

    salaries = User.query.filter_by(actif=True).all()
    param_precedent = _get_parametrage_precedent(param)

    for s in salaries:
        allocation = AllocationConge.query.filter_by(
            user_id=s.id,
            parametrage_id=param.id,
        ).first()

        report_cp_anticipe = 0
        report_rtt_anticipe = 0
        if param_precedent:
            solde_precedent = calculer_solde(s.id, parametrage_id=param_precedent.id)
            report_cp_anticipe = min(0, int(solde_precedent.get("solde_restant", 0) or 0))
            report_rtt_anticipe = min(0, float(solde_precedent.get("rtt_solde_restant", 0) or 0))

        if not allocation:
            allocation = AllocationConge(
                user_id=s.id,
                parametrage_id=param.id,
            )
            db.session.add(allocation)

        allocation.jours_alloues = param.jours_conges_defaut
        allocation.jours_anciennete = allocation.jours_anciennete or 0
        # Le report doit refléter le solde réel de l'exercice précédent.
        # On le recalcule même si l'allocation existe déjà (cas "nouvel exercice" re-paramétré).
        allocation.jours_report = report_cp_anticipe
        allocation.rtt_heures_allouees = param.rtt_heures_defaut
        allocation.rtt_heures_reportees = report_rtt_anticipe

    db.session.commit()
