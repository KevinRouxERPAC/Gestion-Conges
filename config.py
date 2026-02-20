import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get("SECRET_KEY", "Gh3InTZ80Q5mYfkmZiVWIVoRewwJ0ISDrsXsqdMjxPk=")
    # timeout=15 : SQLite attend jusqu'à 15 s si la base est verrouillée (écritures concurrentes multi-utilisateurs)
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "gestion_conges.db") + "?timeout=15"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes en secondes

    # Application en HTTP uniquement (pas de HTTPS, pas de redirection vers HTTPS)
    PREFERRED_URL_SCHEME = "http"

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

    # Web Push (notifications hors du site, sans donnée personnelle)
    # Clés : placer vapid_private.pem dans le répertoire de l'app (ou VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY en env).
    # Important : pour que la notification s'affiche chez l'utilisateur (même onglet fermé), le site doit être
    # servi en HTTPS. En HTTP, le serveur peut envoyer le push mais le navigateur ne l'affiche pas (contexte non sécurisé).
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
