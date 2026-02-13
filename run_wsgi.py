"""
Point d'entrée WSGI pour déploiement sous IIS (HttpPlatformHandler).
Lance l'application Flask avec le serveur Waitress (compatible Windows).
"""
import os

from app import create_app
from waitress import serve

app = create_app()

if __name__ == "__main__":
    # IIS HttpPlatformHandler transmet le port via HTTP_PLATFORM_PORT
    port = int(os.environ.get("HTTP_PLATFORM_PORT", os.environ.get("PORT", "5050")))
    serve(app, host="127.0.0.1", port=port)
