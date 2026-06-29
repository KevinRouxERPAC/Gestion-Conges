import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY non défini. Définissez la variable d'environnement SECRET_KEY "
            "(ex: dans web.config ou .env). Générez-en une avec : python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    # timeout=15 : SQLite attend jusqu'à 15 s si la base est verrouillée (écritures concurrentes multi-utilisateurs)
    # Surcharge possible via env var SQLALCHEMY_DATABASE_URI (utile pour migrations Alembic
    # et tests pointant sur une BDD temporaire).
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI") or (
        "sqlite:///" + os.path.join(BASE_DIR, "gestion_conges.db") + "?timeout=15"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes en secondes

    # Schéma d’URL (http ou https). En HTTPS derrière IIS, mettre PREFERRED_URL_SCHEME=https dans web.config.
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")

    # Durcissement du cookie de session :
    # - HttpOnly : inaccessible au JavaScript (atténue le vol de session via XSS).
    # - SameSite=Lax : le cookie n'est pas envoyé sur les requêtes cross-site (anti-CSRF en profondeur).
    # - Secure : cookie transmis uniquement en HTTPS. Indexé sur PREFERRED_URL_SCHEME
    #   pour ne pas casser le dev en HTTP (où le navigateur refuserait un cookie Secure).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PREFERRED_URL_SCHEME == "https"

    # SMTP pour les notifications (validation/refus de congés)
    # Exemple : MAIL_SERVER=smtp.gmail.com MAIL_PORT=587 MAIL_USE_TLS=true
    #           MAIL_USERNAME=xxx MAIL_PASSWORD=xxx MAIL_DEFAULT_SENDER=conges@erpac.local
    # En dev sans SMTP : MAIL_SUPPRESS_SEND=true (les emails sont logués, pas envoyés)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 25))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "false").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "conges@erpac.local")
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"
    # Adresse mail entreprise RH : reçoit un email à chaque nouvelle demande de congé (optionnel)
    MAIL_RH = os.environ.get("MAIL_RH", "").strip() or None

    # Justificatifs d'absence (stockage hors web-root)
    JUSTIFICATIFS_DIR = os.environ.get("JUSTIFICATIFS_DIR") or os.path.join(BASE_DIR, "instance", "justificatifs")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 5 Mo

    # -------------------------------------------------------------------------
    # Connexion ERP lecture seule (SILOG/Cegid PMI, SQL Server).
    # Désactivé par défaut : l'app fonctionne sans l'ERP.
    # Activer via ERP_DB_ENABLED=true + renseigner les variables ci-dessous
    # (dans web.config sur IIS, jamais dans le dépôt Git).
    # -------------------------------------------------------------------------
    ERP_DB_ENABLED = os.environ.get("ERP_DB_ENABLED", "false").lower() == "true"
    ERP_DB_SERVER = os.environ.get("ERP_DB_SERVER", "")
    ERP_DB_DATABASE = os.environ.get("ERP_DB_DATABASE", "PMI")
    ERP_DB_USER = os.environ.get("ERP_DB_USER", "")
    ERP_DB_PASSWORD = os.environ.get("ERP_DB_PASSWORD", "")
    ERP_DB_DRIVER = os.environ.get("ERP_DB_DRIVER", "ODBC Driver 18 for SQL Server")
    ERP_DB_ENCRYPT = os.environ.get("ERP_DB_ENCRYPT", "yes")
    ERP_DB_TRUST_CERT = os.environ.get("ERP_DB_TRUST_CERT", "yes")
    ERP_DB_TIMEOUT = int(os.environ.get("ERP_DB_TIMEOUT", "10"))
    # Planification in-app de la synchro automatique (APScheduler).
    # Jour : mon/tue/wed/thu/fri/sat/sun. Défaut : vendredi 17h30.
    ERP_SYNC_JOUR = os.environ.get("ERP_SYNC_JOUR", "fri")
    ERP_SYNC_HEURE = int(os.environ.get("ERP_SYNC_HEURE", "17"))
    ERP_SYNC_MINUTE = int(os.environ.get("ERP_SYNC_MINUTE", "30"))

    # Web Push (notifications hors du site, sans donnée personnelle)
    # Clés : placer vapid_private.pem dans le répertoire de l'app (ou VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY en env).
    # Important : pour que la notification s'affiche chez l'utilisateur (même onglet fermé), le site doit être
    # servi en HTTPS. En HTTP, le serveur peut envoyer le push mais le navigateur ne l'affiche pas (contexte non sécurisé).
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
