import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "Gh3InTZ80Q5mYfkmZiVWIVoRewwJ0ISDrsXsqdMjxPk=")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "gestion_conges.db")
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
