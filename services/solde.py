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


_STATUTS_EN_ATTENTE = ("en_attente_responsable", "en_attente_rh")


def calculer_jours_cps_consommes(user_id, parametrage_id=None):
    """Calcule le nombre de jours consommés (CP + Ancienneté) pour l'exercice actif (validés uniquement)."""
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


def calculer_jours_cps_en_attente(user_id, parametrage_id=None):
    """Jours CP/Ancienneté en attente de validation (responsable ou RH) pour l'exercice actif."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    result = db.session.query(func.coalesce(func.sum(Conge.nb_jours_ouvrables), 0)).filter(
        Conge.user_id == user_id,
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge.in_(["CP", "Anciennete"]),
        Conge.statut.in_(_STATUTS_EN_ATTENTE),
    ).scalar()

    return result


def calculer_heures_rtt_consommes(user_id, parametrage_id=None):
    """Calcule le nombre d'heures RTT consommées pour l'exercice actif (validés uniquement)."""
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


def calculer_heures_rtt_en_attente(user_id, parametrage_id=None):
    """Heures RTT en attente de validation (responsable ou RH) pour l'exercice actif."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    result = db.session.query(func.coalesce(func.sum(Conge.nb_heures_rtt), 0)).filter(
        Conge.user_id == user_id,
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge == "RTT",
        Conge.statut.in_(_STATUTS_EN_ATTENTE),
    ).scalar()

    return result


def calculer_solde(user_id, parametrage_id=None):
    """Calcule les soldes restants d'un utilisateur pour CP (jours) et RTT (heures).

    Inclut les demandes en attente pour transparence (clés *_en_attente). Le solde
    autorisé peut être négatif : c'est un avertissement, pas un blocage.
    """
    allocation = get_allocation(user_id, parametrage_id)
    if allocation is None:
        return {
            "total_alloue": 0,
            "jours_conges": 0,
            "jours_anciennete": 0,
            "jours_report": 0,
            "total_consomme": 0,
            "solde_restant": 0,
            "cp_en_attente": 0,
            "solde_projete": 0,
            "rtt_heures_allouees": 0,
            "rtt_heures_reportees": 0,
            "rtt_total_alloue": 0,
            "rtt_total_consomme": 0,
            "rtt_solde_restant": 0,
            "rtt_en_attente": 0,
            "rtt_solde_projete": 0,
        }

    pid = allocation.parametrage_id

    cp_consomme = calculer_jours_cps_consommes(user_id, pid)
    cp_en_attente = calculer_jours_cps_en_attente(user_id, pid)
    cp_total = allocation.total_jours

    rtt_total = allocation.total_rtt_heures
    rtt_consomme = calculer_heures_rtt_consommes(user_id, pid)
    rtt_en_attente = calculer_heures_rtt_en_attente(user_id, pid)

    return {
        # CP (jours) - clés compatibles avec l'existant
        "total_alloue": cp_total,
        "jours_conges": allocation.jours_alloues,
        "jours_anciennete": allocation.jours_anciennete,
        "jours_report": allocation.jours_report,
        "total_consomme": cp_consomme,
        "solde_restant": cp_total - cp_consomme,
        "cp_en_attente": cp_en_attente,
        "solde_projete": cp_total - cp_consomme - cp_en_attente,
        # RTT (heures)
        "rtt_heures_allouees": allocation.rtt_heures_allouees,
        "rtt_heures_reportees": allocation.rtt_heures_reportees,
        "rtt_total_alloue": rtt_total,
        "rtt_total_consomme": rtt_consomme,
        "rtt_solde_restant": rtt_total - rtt_consomme,
        "rtt_en_attente": rtt_en_attente,
        "rtt_solde_projete": rtt_total - rtt_consomme - rtt_en_attente,
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


def salaries_a_risque(jours_min_restants=10, jours_avant_fin=90):
    """Liste les salariés actifs qui ont encore beaucoup de CP à poser près de la fin d'exercice.

    Args:
        jours_min_restants : seuil au-delà duquel un salarié est considéré "à risque".
        jours_avant_fin : fenêtre en jours avant la fin d'exercice où on déclenche l'alerte.

    Retourne : liste de dicts {user, solde_restant, solde_projete, jours_avant_fin_exercice}.
    Vide si l'exercice est à plus de jours_avant_fin de sa fin, ou si pas de paramétrage actif.
    """
    from datetime import date as _date
    from models.user import User

    param = get_parametrage_actif()
    if param is None:
        return []

    today = _date.today()
    delta_fin = (param.fin_exercice - today).days
    if delta_fin > jours_avant_fin or delta_fin < 0:
        return []

    salaries = User.query.filter_by(actif=True).order_by(User.nom, User.prenom).all()
    a_risque = []
    for s in salaries:
        info = calculer_solde(s.id)
        if info["solde_restant"] >= jours_min_restants:
            a_risque.append({
                "user": s,
                "solde_restant": info["solde_restant"],
                "solde_projete": info.get("solde_projete", info["solde_restant"]),
                "jours_avant_fin_exercice": delta_fin,
            })
    return a_risque


def cloturer_exercice_et_reporter(
    nouveau_param: ParametrageAnnuel,
    report_max_jours=None,
    report_max_heures_rtt=None,
):
    """Clôture l'exercice actif courant et crée les allocations du nouveau,
    en reportant le solde restant (CP et RTT) selon les plafonds.

    Args:
        nouveau_param : ParametrageAnnuel déjà persisté pour le prochain exercice
            (actif=True). L'ancien paramétrage actif sera désactivé.
        report_max_jours : plafond de report CP. None = pas de plafond (report intégral).
        report_max_heures_rtt : idem pour RTT.

    Retourne un dict {nb_salaries, report_cp_total, report_rtt_total}.
    """
    from models.user import User

    ancien = ParametrageAnnuel.query.filter(
        ParametrageAnnuel.actif == True,
        ParametrageAnnuel.id != nouveau_param.id,
    ).first()

    salaries = User.query.filter_by(actif=True).all()
    total_cp_reporte = 0
    total_rtt_reporte = 0

    for s in salaries:
        # Solde restant avant clôture (basé sur l'ancien paramétrage si présent,
        # sinon le calcul retourne 0 ou utilise l'allocation courante).
        # Un solde négatif (déficit) est désormais reporté tel quel sur l'exercice
        # suivant (report négatif), au lieu d'être écrêté à 0.
        solde_info = calculer_solde(s.id, parametrage_id=ancien.id if ancien else None)
        cp_restant = solde_info.get("solde_restant", 0)
        rtt_restant = solde_info.get("rtt_solde_restant", 0)

        # Le plafond ne s'applique qu'au report positif : un déficit passe tel quel.
        cp_a_reporter = (
            min(cp_restant, report_max_jours) if report_max_jours is not None else cp_restant
        )
        rtt_a_reporter = (
            min(rtt_restant, report_max_heures_rtt)
            if report_max_heures_rtt is not None
            else rtt_restant
        )

        alloc = AllocationConge.query.filter_by(
            user_id=s.id, parametrage_id=nouveau_param.id
        ).first()
        if not alloc:
            alloc = AllocationConge(
                user_id=s.id,
                parametrage_id=nouveau_param.id,
                jours_alloues=nouveau_param.jours_conges_defaut,
                jours_anciennete=0,
                rtt_heures_allouees=nouveau_param.rtt_heures_defaut,
            )
            db.session.add(alloc)

        alloc.jours_report = int(cp_a_reporter)
        alloc.rtt_heures_reportees = int(rtt_a_reporter)
        total_cp_reporte += int(cp_a_reporter)
        total_rtt_reporte += int(rtt_a_reporter)

    if ancien:
        ancien.actif = False
    nouveau_param.actif = True

    return {
        "nb_salaries": len(salaries),
        "report_cp_total": total_cp_reporte,
        "report_rtt_total": total_rtt_reporte,
    }


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
