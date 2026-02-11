"""
Service d'envoi d'emails pour les notifications (validation/refus de congés).
Utilise smtplib (sans dépendance externe).
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def _get_config():
    """Récupère la config mail depuis l'app Flask."""
    return {
        "server": current_app.config.get("MAIL_SERVER", "localhost"),
        "port": current_app.config.get("MAIL_PORT", 25),
        "use_tls": current_app.config.get("MAIL_USE_TLS", False),
        "use_ssl": current_app.config.get("MAIL_USE_SSL", False),
        "username": current_app.config.get("MAIL_USERNAME", ""),
        "password": current_app.config.get("MAIL_PASSWORD", ""),
        "default_sender": current_app.config.get("MAIL_DEFAULT_SENDER", "conges@erpac.local"),
        "suppress": current_app.config.get("MAIL_SUPPRESS_SEND", False),
    }


def send_email(to_email: str, subject: str, body_text: str, body_html: str = None) -> bool:
    """
    Envoie un email.
    Retourne True si envoyé ou si MAIL_SUPPRESS_SEND (mode dev), False en cas d'erreur.
    """
    if not to_email or not to_email.strip():
        current_app.logger.debug("Email non envoyé : pas d'adresse destinataire")
        return False

    to_email = to_email.strip()
    config = _get_config()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["default_sender"]
    msg["To"] = to_email

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    if config["suppress"]:
        current_app.logger.info(
            f"[MAIL SUPPRESSED] To: {to_email} | Subject: {subject} | Body: {body_text[:100]}..."
        )
        return True

    try:
        if config["use_ssl"]:
            server = smtplib.SMTP_SSL(config["server"], config["port"])
        else:
            server = smtplib.SMTP(config["server"], config["port"])
            if config["use_tls"]:
                server.starttls()

        if config["username"] and config["password"]:
            server.login(config["username"], config["password"])

        server.sendmail(config["default_sender"], [to_email], msg.as_string())
        server.quit()
        current_app.logger.info(f"Email envoyé à {to_email}: {subject}")
        return True
    except Exception as e:
        current_app.logger.warning(f"Échec envoi email à {to_email}: {e}")
        return False


def envoyer_notification_validation(prenom: str, email: str, date_debut, date_fin, nb_jours: int, type_conge: str):
    """Notification au salarié : sa demande de congé a été validée."""
    subject = "ERPAC Congés - Demande validée"
    body_text = f"""Bonjour {prenom},

Votre demande de congé a été validée par les RH.

Détails :
- Période : {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}
- Nombre de jours : {nb_jours}
- Type : {type_conge}

Vous pouvez consulter votre solde et historique sur l'application Gestion des Congés.

Cordialement,
L'équipe ERPAC
"""
    body_html = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Bonjour {prenom},</p>
    <p>Votre demande de congé a été <strong style="color: #008C3A;">validée</strong> par les RH.</p>
    <table style="border-collapse: collapse; margin: 20px 0;">
        <tr><td style="padding: 5px 15px 5px 0;"><strong>Période :</strong></td><td>{date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}</td></tr>
        <tr><td style="padding: 5px 15px 5px 0;"><strong>Jours :</strong></td><td>{nb_jours}</td></tr>
        <tr><td style="padding: 5px 15px 5px 0;"><strong>Type :</strong></td><td>{type_conge}</td></tr>
    </table>
    <p>Cordialement,<br>L'équipe ERPAC</p>
</body>
</html>
"""
    return send_email(email, subject, body_text, body_html)


def envoyer_notification_refus(prenom: str, email: str, date_debut, date_fin, nb_jours: int, type_conge: str, motif: str):
    """Notification au salarié : sa demande de congé a été refusée."""
    subject = "ERPAC Congés - Demande refusée"
    body_text = f"""Bonjour {prenom},

Votre demande de congé a été refusée par les RH.

Détails de la demande :
- Période : {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}
- Nombre de jours : {nb_jours}
- Type : {type_conge}

Motif du refus :
{motif}

Pour toute question, contactez les ressources humaines.

Cordialement,
L'équipe ERPAC
"""
    body_html = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Bonjour {prenom},</p>
    <p>Votre demande de congé a été <strong style="color: #dc2626;">refusée</strong> par les RH.</p>
    <table style="border-collapse: collapse; margin: 20px 0;">
        <tr><td style="padding: 5px 15px 5px 0;"><strong>Période :</strong></td><td>{date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}</td></tr>
        <tr><td style="padding: 5px 15px 5px 0;"><strong>Jours :</strong></td><td>{nb_jours}</td></tr>
        <tr><td style="padding: 5px 15px 5px 0;"><strong>Type :</strong></td><td>{type_conge}</td></tr>
    </table>
    <p><strong>Motif du refus :</strong></p>
    <p style="background: #fef2f2; padding: 10px; border-left: 4px solid #dc2626;">{motif}</p>
    <p>Pour toute question, contactez les ressources humaines.</p>
    <p>Cordialement,<br>L'équipe ERPAC</p>
</body>
</html>
"""
    return send_email(email, subject, body_text, body_html)
