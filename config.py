import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _load_dotenv_if_present():
    """
    Charge un fichier .env minimal (KEY=VALUE) s'il existe.
    Objectif: faciliter le démarrage en local sans dépendance externe.
    Ne surcharge jamais les variables déjà définies dans l'environnement.
    """
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if not k:
                    continue
                os.environ.setdefault(k, v)
    except OSError:
        # Si le fichier n'est pas lisible, on retombe sur les variables env.
        return


class Config:
    BASE_DIR = BASE_DIR
    _load_dotenv_if_present()
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    if not SECRET_KEY:
        _is_dev = (
            os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
            or os.environ.get("FLASK_ENV", "").lower() == "development"
            or os.environ.get("ENV", "").lower() == "development"
            or os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
        )
        if _is_dev:
            # Clé de secours pour démarrer en local. À remplacer dès que possible.
            SECRET_KEY = "dev-secret-key-change-me"
        else:
            raise RuntimeError(
                "SECRET_KEY non défini. Définissez la variable d'environnement SECRET_KEY "
                "(ex: dans web.config ou .env). Générez-en une avec : python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
    # Base de données. Par défaut : SQLite locale (adapté petite équipe, timeout=15 pour les écritures concurrentes).
    # Pour PostgreSQL : DATABASE_URL=postgresql://user:pass@host/dbname
    _SQLITE_DEFAULT = "sqlite:///" + os.path.join(BASE_DIR, "gestion_conges.db") + "?timeout=15"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _SQLITE_DEFAULT)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes en secondes

    # Schéma d’URL (http ou https). En HTTPS derrière IIS, mettre PREFERRED_URL_SCHEME=https dans web.config.
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")

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

    # Web Push (notifications hors du site, sans donnée personnelle)
    # Clés : placer vapid_private.pem dans le répertoire de l'app (ou VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY en env).
    # Important : pour que la notification s'affiche chez l'utilisateur (même onglet fermé), le site doit être
    # servi en HTTPS. En HTTP, le serveur peut envoyer le push mais le navigateur ne l'affiche pas (contexte non sécurisé).
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
