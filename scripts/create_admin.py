#!/usr/bin/env python3
"""
Créer le premier utilisateur RH (admin) quand la base est vide.
À lancer une fois après le premier déploiement.

Usage (depuis la racine du projet) :
  python scripts/create_admin.py
  # ou avec le venv :
  venv/bin/python scripts/create_admin.py

Les variables d'environnement optionnelles :
  ADMIN_IDENTIFIANT  identifiant de connexion (défaut : admin)
  ADMIN_NOM          nom (défaut : Admin)
  ADMIN_PRENOM       prénom (défaut : Gestion)
Le mot de passe est demandé au clavier (non affiché).
"""
import os
import sys

# S'assurer que la racine du projet est dans le path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db
from models.user import User


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main():
    app = create_app()
    with app.app_context():
        if User.query.filter_by(role="rh").first():
            print("Un utilisateur RH existe déjà. Aucune action.")
            return

        identifiant = os.environ.get("ADMIN_IDENTIFIANT", "admin").strip()
        nom = os.environ.get("ADMIN_NOM", "Admin").strip()
        prenom = os.environ.get("ADMIN_PRENOM", "Gestion").strip()

        if User.query.filter_by(identifiant=identifiant).first():
            print(f"L'identifiant '{identifiant}' existe déjà. Changez ADMIN_IDENTIFIANT ou créez l'utilisateur depuis l'interface RH.")
            return

        try:
            getpass = __import__("getpass").getpass
        except Exception:
            getpass = lambda p: input(p + " (visible) ")

        mot_de_passe = getpass("Mot de passe pour le compte RH : ")
        if not mot_de_passe or len(mot_de_passe) < 5:
            print("Le mot de passe doit faire au moins 5 caractères.")
            sys.exit(1)

        user = User(
            nom=nom,
            prenom=prenom,
            identifiant=identifiant,
            mot_de_passe_hash=hash_password(mot_de_passe),
            role="rh",
            actif=True,
        )
        db.session.add(user)
        db.session.commit()
        print(f"Compte RH créé : {identifiant} ({prenom} {nom}). Vous pouvez vous connecter.")


if __name__ == "__main__":
    main()
