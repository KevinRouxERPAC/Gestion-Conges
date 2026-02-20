"""
Point d'entrée WSGI pour déploiement (IIS HttpPlatformHandler ou tests en mode production).
Lance l'application Flask avec Waitress (compatible Windows, multi-requêtes).

Lancer en local pour tester comme en production :
  python run_wsgi.py

Pour tester avec deux utilisateurs (RH + salarié) :
  - Onglet 1 : ouvrez http://127.0.0.1:5000 (ou le port affiché), connectez-vous en RH.
  - Onglet 2 : ouvrez une fenêtre de navigation privée (Ctrl+Shift+N) ou un autre
    navigateur, allez sur la même URL, connectez-vous en salarié.
  Les deux sessions restent indépendantes.
"""
import os

# Sous IIS, le répertoire de travail doit être la racine du projet (DB, config, vapid_private.pem, etc.)
_script_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _script_dir:
    os.chdir(_script_dir)

from app import create_app
from waitress import serve

app = create_app()

if __name__ == "__main__":
    # IIS transmet le port via HTTP_PLATFORM_PORT ; sinon PORT ou 5000 par défaut
    port = int(os.environ.get("HTTP_PLATFORM_PORT", os.environ.get("PORT", "5000")))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Waitress (production) : http://{host}:{port}")
    print("Pour deux utilisateurs : un onglet normal (RH) + un onglet navigation privée (salarié).")
    serve(app, host=host, port=port, threads=6)
