"""Lanceur de l'app sur la base de DEMO pour la vérification fonctionnelle.

Ne PAS utiliser en production. Fixe une base jetable (verif_demo.db), supprime
l'envoi d'e-mails et lance le serveur de dev sur le port 5001.
"""
import os

os.environ.setdefault("SECRET_KEY", "dev-verify")
os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///verif_demo.db")
os.environ.setdefault("MAIL_SUPPRESS_SEND", "true")

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5001, threaded=True)
