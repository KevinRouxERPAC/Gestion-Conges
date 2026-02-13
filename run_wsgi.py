"""
Point d'entrée WSGI pour déploiement sous IIS (HttpPlatformHandler).
Lance l'application Flask avec le serveur Waitress (compatible Windows).
"""
from app import create_app
from waitress import serve

app = create_app()

if __name__ == "__main__":
    # Port utilisé en interne par HttpPlatformHandler (ne pas exposer sur le pare-feu)
    serve(app, host="127.0.0.1", port=5050)
