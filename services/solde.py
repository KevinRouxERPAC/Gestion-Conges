from models import db
from models.conge import Conge
from models.parametrage import ParametrageAnnuel, AllocationConge
from services.consommation import (
    somme_consommation,
    _num,
    STATUT_VALIDE,
    STATUTS_EN_ATTENTE,
    TYPES_CP,
    TYPE_RTT,
)


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
    """Calcule le nombre de jours consommés (CP + Ancienneté) pour l'exercice actif (validés uniquement)."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    return somme_consommation(
        colonne=Conge.nb_jours_ouvrables,
        date_debut_min=param.debut_exercice,
        date_fin_max=param.fin_exercice,
        statuts=STATUT_VALIDE,
        types=TYPES_CP,
        user_id=user_id,
    )


def calculer_jours_cps_en_attente(user_id, parametrage_id=None):
    """Jours CP/Ancienneté en attente de validation (responsable ou RH) pour l'exercice actif."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    return somme_consommation(
        colonne=Conge.nb_jours_ouvrables,
        date_debut_min=param.debut_exercice,
        date_fin_max=param.fin_exercice,
        statuts=STATUTS_EN_ATTENTE,
        types=TYPES_CP,
        user_id=user_id,
    )


def calculer_heures_rtt_consommes(user_id, parametrage_id=None):
    """Calcule le nombre d'heures RTT consommées pour l'exercice actif (validés uniquement)."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    return somme_consommation(
        colonne=Conge.nb_heures_rtt,
        date_debut_min=param.debut_exercice,
        date_fin_max=param.fin_exercice,
        statuts=STATUT_VALIDE,
        types=TYPE_RTT,
        user_id=user_id,
    )


def calculer_heures_rtt_en_attente(user_id, parametrage_id=None):
    """Heures RTT en attente de validation (responsable ou RH) pour l'exercice actif."""
    param = _get_param(parametrage_id)
    if param is None:
        return 0

    return somme_consommation(
        colonne=Conge.nb_heures_rtt,
        date_debut_min=param.debut_exercice,
        date_fin_max=param.fin_exercice,
        statuts=STATUTS_EN_ATTENTE,
        types=TYPE_RTT,
        user_id=user_id,
    )


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
        # RTT (heures, décimales) — normalisées (_num : entier si rond, sinon
        # float arrondi) pour un affichage propre (pas de « 14.0 ») et des
        # valeurs d'input valides.
        "rtt_heures_allouees": _num(allocation.rtt_heures_allouees),
        "rtt_heures_reportees": _num(allocation.rtt_heures_reportees),
        "rtt_total_alloue": _num(rtt_total),
        "rtt_total_consomme": _num(rtt_consomme),
        "rtt_solde_restant": _num(rtt_total - rtt_consomme),
        "rtt_en_attente": _num(rtt_en_attente),
        "rtt_solde_projete": _num(rtt_total - rtt_consomme - rtt_en_attente),
    }


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
                # RTT calculé en hebdomadaire : aucune allocation forfaitaire au départ.
                rtt_heures_allouees=0,
            )
            db.session.add(alloc)

        alloc.jours_report = int(cp_a_reporter)
        # RTT en heures décimales : on ne tronque plus à l'entier (cf. R3).
        alloc.rtt_heures_reportees = round(float(rtt_a_reporter), 2)
        total_cp_reporte += int(cp_a_reporter)
        total_rtt_reporte += round(float(rtt_a_reporter), 2)

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
        # Le RTT n'est plus alloué par forfait : il est calculé depuis les heures
        # hebdomadaires saisies (cf. recalcul ci-dessous). On préserve la valeur
        # existante (recalculée) et on initialise à 0 pour les nouveaux salariés.
        allocation.rtt_heures_allouees = allocation.rtt_heures_allouees or 0
        allocation.rtt_heures_reportees = allocation.rtt_heures_reportees or 0

    db.session.commit()

    # Recalcule le RTT hebdomadaire (seul mode supporté) à partir des heures déjà
    # saisies, pour refléter immédiatement les droits acquis.
    from services.rtt_hebdo import maj_rtt_allocations_hebdo
    maj_rtt_allocations_hebdo(param)
