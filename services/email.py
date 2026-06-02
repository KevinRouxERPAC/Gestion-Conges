"""
Service d'envoi d'emails (smtplib, sans dépendance externe).

Conformité RGPD : aucun email n'est envoyé aux salariés (aucune adresse salarié
n'est collectée). Le seul email sortant est le récap hebdomadaire adressé à la
boîte RH entreprise (`MAIL_RH`), via `envoyer_recap_hebdo_rh`. Les notifications
salarié (validation / refus / modification) passent uniquement par l'in-app et le
Web Push (cf. `services/notifications.py`).
"""
import smtplib
from html import escape
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

    server = None
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
        current_app.logger.info(f"Email envoyé à {to_email}: {subject}")
        return True
    except Exception as e:
        current_app.logger.warning(f"Échec envoi email à {to_email}: {e}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


def envoyer_recap_hebdo_rh(demandes: list) -> bool:
    """Envoie un récap hebdomadaire à la boîte RH entreprise (MAIL_RH).

    `demandes` est une liste de dicts contenant :
      - nom_salarie (str)
      - periode (str, ex. "12/05/2026 - 16/05/2026")
      - nb_jours (int)
      - type_conge (str)
      - statut (str : "en_attente_responsable" | "en_attente_rh")
      - age_jours (int, nombre de jours depuis la création de la demande)

    Retourne False si MAIL_RH non configuré ou si la liste est vide (pas d'envoi).
    """
    to = (current_app.config.get("MAIL_RH") or "").strip()
    if not to:
        return False
    if not demandes:
        # Pas d'email si rien à signaler.
        return False

    nb = len(demandes)
    subject = f"ERPAC Conges - Recap hebdomadaire : {nb} demande(s) en attente"

    # Texte brut
    lignes_text = []
    for d in demandes:
        statut_label = "en attente responsable" if d["statut"] == "en_attente_responsable" else "en attente RH"
        lignes_text.append(
            f"- {d['nom_salarie']} | {d['periode']} | {d['nb_jours']} j | "
            f"{d['type_conge']} | {statut_label} | depuis {d['age_jours']} j"
        )
    body_text = (
        f"Bonjour,\n\n"
        f"{nb} demande(s) de conge en attente de validation.\n\n"
        + "\n".join(lignes_text)
        + "\n\nConnectez-vous a l'application pour valider ou refuser.\n\n"
        "Cordialement,\nL'equipe ERPAC\n"
    )

    # HTML
    lignes_html = []
    for d in demandes:
        statut_label = "En attente responsable" if d["statut"] == "en_attente_responsable" else "En attente RH"
        statut_color = "#92400e" if d["statut"] == "en_attente_responsable" else "#9a3412"
        age_color = "#dc2626" if d["age_jours"] >= 7 else "#6b7280"
        lignes_html.append(
            f"<tr>"
            f"<td style='padding:6px 10px; border:1px solid #e5e7eb;'>{escape(d['nom_salarie'])}</td>"
            f"<td style='padding:6px 10px; border:1px solid #e5e7eb;'>{escape(d['periode'])}</td>"
            f"<td style='padding:6px 10px; border:1px solid #e5e7eb; text-align:right;'>{d['nb_jours']} j</td>"
            f"<td style='padding:6px 10px; border:1px solid #e5e7eb;'>{escape(d['type_conge'])}</td>"
            f"<td style='padding:6px 10px; border:1px solid #e5e7eb; color:{statut_color};'>{statut_label}</td>"
            f"<td style='padding:6px 10px; border:1px solid #e5e7eb; color:{age_color};'>{d['age_jours']} j</td>"
            f"</tr>"
        )
    body_html = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Bonjour,</p>
    <p><strong>{nb}</strong> demande(s) de conge en attente de validation.</p>
    <table style="border-collapse: collapse; margin: 20px 0; font-size: 14px;">
        <thead>
            <tr style="background:#008C3A; color:#fff;">
                <th style="padding:6px 10px; border:1px solid #006c2d; text-align:left;">Salarie</th>
                <th style="padding:6px 10px; border:1px solid #006c2d; text-align:left;">Periode</th>
                <th style="padding:6px 10px; border:1px solid #006c2d; text-align:right;">Jours</th>
                <th style="padding:6px 10px; border:1px solid #006c2d; text-align:left;">Type</th>
                <th style="padding:6px 10px; border:1px solid #006c2d; text-align:left;">Statut</th>
                <th style="padding:6px 10px; border:1px solid #006c2d; text-align:left;">Anciennete</th>
            </tr>
        </thead>
        <tbody>
            {''.join(lignes_html)}
        </tbody>
    </table>
    <p style="color:#6b7280; font-size:13px;">Les demandes de plus de 7 jours sont signalees en rouge.</p>
    <p>Connectez-vous a l'application pour valider ou refuser.</p>
    <p>Cordialement,<br>L'equipe ERPAC</p>
</body>
</html>
"""
    return send_email(to, subject, body_text, body_html)
