"""Service de notifications in-app + Web Push (hors du site, sans donnée personnelle)."""
import logging
from models import db
from models.notification import Notification
from models.user import User

logger = logging.getLogger(__name__)


def creer_notification(user_id: int, type_notif: str, titre: str, message: str, conge_id: int = None):
    """Crée une notification pour un utilisateur et envoie un Web Push si abonné."""
    n = Notification(
        user_id=user_id,
        type=type_notif,
        titre=titre,
        message=message,
        conge_id=conge_id,
    )
    db.session.add(n)
    db.session.flush()
    try:
        from services.webpush import envoyer_push_user
        envoyer_push_user(user_id, titre, message, url="/notifications/")
    except Exception as e:
        logger.warning("Web Push non envoyé pour user_id=%s: %s", user_id, e)


def notifier_conge_valide(conge):
    """Notifie le salarié que sa demande de congé a été validée."""
    u = conge.utilisateur
    if not u:
        return
    periode = f"{conge.date_debut.strftime('%d/%m/%Y')} - {conge.date_fin.strftime('%d/%m/%Y')}"
    message = f"Votre demande de congé ({conge.type_conge}) du {periode} ({conge.nb_jours_ouvrables} jour(s)) a été validée."
    creer_notification(
        user_id=conge.user_id,
        type_notif="conge_valide",
        titre="Demande de congé validée",
        message=message,
        conge_id=conge.id,
    )


def notifier_conge_refuse(conge, motif: str):
    """Notifie le salarié que sa demande de congé a été refusée."""
    u = conge.utilisateur
    if not u:
        return
    periode = f"{conge.date_debut.strftime('%d/%m/%Y')} - {conge.date_fin.strftime('%d/%m/%Y')}"
    message = f"Votre demande de congé ({conge.type_conge}) du {periode} ({conge.nb_jours_ouvrables} jour(s)) a été refusée."
    if motif:
        message += f" Motif : {motif}"
    creer_notification(
        user_id=conge.user_id,
        type_notif="conge_refuse",
        titre="Demande de congé refusée",
        message=message,
        conge_id=conge.id,
    )


def notifier_rh_nouvelle_demande(conge):
    """Notifie tous les utilisateurs RH qu'un salarié a déposé une demande de congé."""
    rh_users = User.query.filter(db.func.lower(User.role) == "rh", User.actif == True).all()
    if not rh_users:
        logger.warning("notifier_rh_nouvelle_demande: aucun utilisateur RH actif trouvé")
        return
    logger.info("notifier_rh_nouvelle_demande: envoi à %d RH (conge_id=%s)", len(rh_users), conge.id)
    u = conge.utilisateur
    nom_salarie = f"{u.prenom} {u.nom}" if u else "Un salarié"
    periode = f"{conge.date_debut.strftime('%d/%m/%Y')} - {conge.date_fin.strftime('%d/%m/%Y')}"
    titre = "Nouvelle demande de congé"
    message = f"{nom_salarie} a déposé une demande de congé {conge.type_conge} : {periode} ({conge.nb_jours_ouvrables} jour(s))."
    for rh in rh_users:
        creer_notification(
            user_id=rh.id,
            type_notif="nouvelle_demande_conge",
            titre=titre,
            message=message,
            conge_id=conge.id,
        )


def compter_non_lues(user_id: int) -> int:
    """Retourne le nombre de notifications non lues pour un utilisateur."""
    return Notification.query.filter_by(user_id=user_id, lue=False).count()
