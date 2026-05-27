import os
import sys
from datetime import timedelta
from flask import Flask, redirect, url_for, Response, send_from_directory
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from models import db

csrf = CSRFProtect()
migrate = Migrate()
# Rate limiter : protège /login contre le brute force. Storage en mémoire
# suffisant pour un déploiement single-process (Waitress/Gunicorn 1 worker).
# Pour multi-worker, basculer storage_uri vers Redis.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],  # pas de limite globale, application ciblée
    storage_uri="memory://",
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(seconds=app.config["PERMANENT_SESSION_LIFETIME"])
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Init extensions
    db.init_app(app)
    csrf.init_app(app)
    # Migrations Alembic via Flask-Migrate. Dossier "migrations/" à la racine.
    # Commandes : flask db migrate -m "..."  /  flask db upgrade  /  flask db stamp head
    migrate.init_app(app, db)
    # Rate limiter (désactivé en tests via app.config["RATELIMIT_ENABLED"] = False).
    limiter.init_app(app)

    # Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = u"Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.rh import rh_bp
    from routes.salarie import salarie_bp
    from routes.responsable import responsable_bp
    from routes.notifications import notifications_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(rh_bp, url_prefix="/rh")
    app.register_blueprint(salarie_bp, url_prefix="/salarie")
    app.register_blueprint(responsable_bp, url_prefix="/responsable")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.context_processor
    def inject_now():
        from datetime import datetime as _dt
        return {"now": _dt.now}

    @app.template_filter("nb_jours")
    def _format_nb_jours(valeur):
        """Affiche un nombre de jours en français (`1,5` au lieu de `1.5`).
        Retire les zéros inutiles : 2.0 → "2", 1.5 → "1,5".
        """
        if valeur is None:
            return "0"
        try:
            v = float(valeur)
        except (TypeError, ValueError):
            return str(valeur)
        if v == int(v):
            return str(int(v))
        # 1 décimale suffit (demi-journées uniquement).
        return f"{v:.1f}".replace(".", ",")

    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        if current_user.is_authenticated:
            from services.notifications import compter_non_lues
            return {"notifications_non_lues": compter_non_lues(current_user.id)}
        return {"notifications_non_lues": 0}

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/favicon.ico")
    def favicon():
        return Response(status=204)

    @app.route("/sw.js")
    def service_worker():
        return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")

    @app.after_request
    def no_hsts(response):
        if app.config.get("PREFERRED_URL_SCHEME") != "https":
            response.headers.pop("Strict-Transport-Security", None)
        return response

    @app.after_request
    def security_headers(response):
        """Pose les en-têtes de sécurité par défaut sur toutes les réponses HTML.

        Politique adaptée à un intranet :
        - default-src 'self' : tout doit venir du même domaine.
        - 'unsafe-inline' sur script-src + style-src : compromis pour rester
          compatible avec Alpine.js et les <script>/style inline existants.
          Une refactorisation pour utiliser des nonces serait préférable, mais
          le risque XSS reste limité grâce à l'échappement Jinja + CSRF.
        - frame-ancestors 'none' : remplace X-Frame-Options DENY.
        - HSTS uniquement si PREFERRED_URL_SCHEME=https (cf. no_hsts ci-dessus).
        """
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        if app.config.get("PREFERRED_URL_SCHEME") == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=15552000; includeSubDomains"
            )
        return response

    # Schéma de base : laissé pour les environnements de test (SQLite in-memory) et
    # le tout premier démarrage en l'absence de fichier de BDD. En production,
    # les évolutions de schéma doivent passer par Alembic : `flask db upgrade`.
    # Les anciens scripts scripts/migrations/migrate_*.py sont conservés pour
    # référence historique mais ne sont plus rejoués automatiquement.
    #
    # Variable d'env SKIP_DB_CREATE_ALL=1 : utilisée lors de la génération
    # autogen d'une migration Alembic pour partir d'une base vide.
    if os.environ.get("SKIP_DB_CREATE_ALL") != "1":
        with app.app_context():
            db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)


