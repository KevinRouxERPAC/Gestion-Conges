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
    """Notifie le salarié que sa demande de congé a été validée (in-app + Web Push, sans email pour conformité RGPD)."""
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
    """Notifie le salarié que sa demande de congé a été refusée (in-app + Web Push, sans email pour conformité RGPD)."""
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


def notifier_responsable_nouvelle_demande(conge):
    """Notifie le responsable hiérarchique du salarié qu'une nouvelle demande de congé est en attente (validation niveau 1)."""
    u = conge.utilisateur
    if not u or not u.responsable_id:
        return
    responsable_id = u.responsable_id
    nom_salarie = f"{u.prenom} {u.nom}"
    periode = f"{conge.date_debut.strftime('%d/%m/%Y')} - {conge.date_fin.strftime('%d/%m/%Y')}"
    titre = "Demande de congé à valider"
    message = f"{nom_salarie} a déposé une demande de congé {conge.type_conge} : {periode} ({conge.nb_jours_ouvrables} jour(s)). Validez pour la transmettre aux RH."
    creer_notification(
        user_id=responsable_id,
        type_notif="nouvelle_demande_conge_responsable",
        titre=titre,
        message=message,
        conge_id=conge.id,
    )


def notifier_rh_demande_transmise(conge):
    """Notifie les RH qu'une demande a été validée par le responsable et est en attente de validation niveau 2."""
    rh_users = User.query.filter(db.func.lower(User.role) == "rh", User.actif == True).all()
    if not rh_users:
        logger.warning("notifier_rh_demande_transmise: aucun utilisateur RH actif")
        return
    u = conge.utilisateur
    nom_salarie = f"{u.prenom} {u.nom}" if u else "Un salarié"
    periode = f"{conge.date_debut.strftime('%d/%m/%Y')} - {conge.date_fin.strftime('%d/%m/%Y')}"
    titre = "Demande de congé transmise par le responsable"
    message = f"{nom_salarie} : demande de congé {conge.type_conge} ({periode}, {conge.nb_jours_ouvrables} j) validée par le responsable. À valider en niveau 2."
    for rh in rh_users:
        creer_notification(
            user_id=rh.id,
            type_notif="demande_transmise_rh",
            titre=titre,
            message=message,
            conge_id=conge.id,
        )
    try:
        from flask import current_app
        if current_app.config.get("MAIL_RH"):
            from services.email import envoyer_notification_rh_nouvelle_demande
            envoyer_notification_rh_nouvelle_demande(
                nom_salarie=nom_salarie,
                periode=periode,
                nb_jours=conge.nb_jours_ouvrables,
                type_conge=conge.type_conge or "CP",
            )
    except Exception as e:
        logger.warning("Email RH (demande transmise) non envoyé: %s", e)


def notifier_rh_nouvelle_demande(conge):
    """Notifie tous les utilisateurs RH (in-app + Web Push) et envoie un email à la boîte RH entreprise si MAIL_RH est configuré."""
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
    # Email vers la boîte mail entreprise RH (adresse configurée, pas de donnée personnelle employé)
    try:
        from flask import current_app
        if current_app.config.get("MAIL_RH"):
            from services.email import envoyer_notification_rh_nouvelle_demande
            envoyer_notification_rh_nouvelle_demande(
                nom_salarie=nom_salarie,
                periode=periode,
                nb_jours=conge.nb_jours_ouvrables,
                type_conge=conge.type_conge or "CP",
            )
    except Exception as e:
        logger.warning("Email RH (nouvelle demande) non envoyé: %s", e)


def compter_non_lues(user_id: int) -> int:
    """Retourne le nombre de notifications non lues pour un utilisateur."""
    return Notification.query.filter_by(user_id=user_id, lue=False).count()
