from models import db
from models.conge import Conge
from models.parametrage import ParametrageAnnuel, AllocationConge


def get_parametrage_actif():
    """Retourne le paramÃ©trage annuel actif."""
    return ParametrageAnnuel.query.filter_by(actif=True).first()


def get_allocation(user_id, parametrage_id=None):
    """Retourne l'allocation de congÃ©s d'un utilisateur pour le paramÃ©trage donnÃ©."""
    if parametrage_id is None:
        param = get_parametrage_actif()
        if param is None:
            return None
        parametrage_id = param.id

    return AllocationConge.query.filter_by(
        user_id=user_id,
        parametrage_id=parametrage_id,
    ).first()


def calculer_jours_consommes(user_id, parametrage_id=None):
    """Calcule le nombre total de jours consommÃ©s par un utilisateur pour l'exercice actif."""
    param = None
    if parametrage_id:
        param = ParametrageAnnuel.query.get(parametrage_id)
    else:
        param = get_parametrage_actif()

    if param is None:
        return 0

    from sqlalchemy import func
    result = db.session.query(func.coalesce(func.sum(Conge.nb_jours_ouvrables), 0)).filter(
        Conge.user_id == user_id,
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge.in_(["CP", "Anciennete"]),
        Conge.statut == "valide",
    ).scalar()

    return result


def calculer_solde(user_id, parametrage_id=None):
    """Calcule le solde restant d'un utilisateur.
    Retourne un dict avec total_alloue, total_consomme, solde_restant.
    """
    allocation = get_allocation(user_id, parametrage_id)
    if allocation is None:
        return {"total_alloue": 0, "total_consomme": 0, "solde_restant": 0}

    pid = allocation.parametrage_id
    consomme = calculer_jours_consommes(user_id, pid)
    total = allocation.total_jours

    return {
        "total_alloue": total,
        "jours_conges": allocation.jours_alloues,
        "jours_anciennete": allocation.jours_anciennete,
        "jours_report": allocation.jours_report,
        "total_consomme": consomme,
        "solde_restant": total - consomme,
    }


def verifier_solde_suffisant(user_id, nb_jours, conge_id_exclu=None):
    """VÃ©rifie si le solde est suffisant pour poser nb_jours de congÃ©s.
    Si conge_id_exclu est fourni, le congÃ© correspondant est exclu du calcul des jours consommÃ©s.
    """
    solde_info = calculer_solde(user_id)
    solde_actuel = solde_info["solde_restant"]

    if conge_id_exclu:
        from models.conge import Conge
        conge_exclu = Conge.query.get(conge_id_exclu)
        if conge_exclu and conge_exclu.statut == "valide":
            solde_actuel += conge_exclu.nb_jours_ouvrables

    return solde_actuel >= nb_jours
