from models import db
from models.conge import Conge
from models.parametrage import ParametrageAnnuel, AllocationConge
from sqlalchemy import func


def get_parametrage_actif():
    """Retourne le paramétrage annuel actif."""
    return ParametrageAnnuel.query.filter_by(actif=True).first()


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
            "rtt_heures_allouees": 0,
            "rtt_heures_reportees": 0,
            "rtt_total_alloue": 0,
            "rtt_total_consomme": 0,
            "rtt_solde_restant": 0,
        }

    pid = allocation.parametrage_id

    cp_consomme = calculer_jours_cps_consommes(user_id, pid)
    cp_total = allocation.total_jours

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


def generer_allocations_pour_parametrage(param: ParametrageAnnuel):
    """Crée ou met à jour les allocations de congés (CP + RTT) pour tous les salariés actifs."""
    from models.user import User

    salaries = User.query.filter_by(actif=True).all()
    for s in salaries:
        allocation = AllocationConge.query.filter_by(
            user_id=s.id,
            parametrage_id=param.id,
        ).first()
        if not allocation:
            allocation = AllocationConge(
                user_id=s.id,
                parametrage_id=param.id,
            )
            db.session.add(allocation)

        allocation.jours_alloues = param.jours_conges_defaut
        allocation.jours_anciennete = allocation.jours_anciennete or 0
        allocation.jours_report = allocation.jours_report or 0
        allocation.rtt_heures_allouees = param.rtt_heures_defaut
        allocation.rtt_heures_reportees = allocation.rtt_heures_reportees or 0

    db.session.commit()
