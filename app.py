import logging
import os
import sys
import json
from datetime import timedelta
from flask import Flask, redirect, url_for, Response, send_from_directory, request
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from models import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
_log = logging.getLogger(__name__)

csrf = CSRFProtect()

# region agent log (debug-a810eb)
_AGENT_DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "debug-a810eb.log")


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict):
    try:
        try:
            os.makedirs(os.path.dirname(_AGENT_DEBUG_LOG_PATH), exist_ok=True)
        except Exception:
            pass
        payload = {
            "sessionId": "a810eb",
            "runId": os.environ.get("AGENT_DEBUG_RUN_ID", "pre-fix"),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(__import__("time").time() * 1000),
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        try:
            _log.error("[agent-log] Echec ecriture %s", _AGENT_DEBUG_LOG_PATH, exc_info=True)
        except Exception:
            pass
        pass


# endregion agent log (debug-a810eb)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    app.permanent_session_lifetime = timedelta(seconds=app.config["PERMANENT_SESSION_LIFETIME"])
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    # region agent log (debug-a810eb)
    _agent_log(
        "H0",
        "app.py:create_app",
        "Flask app created (ProxyFix enabled)",
        {
            "preferredUrlScheme": app.config.get("PREFERRED_URL_SCHEME"),
            "sessionCookieSecure": bool(app.config.get("SESSION_COOKIE_SECURE")),
        },
    )
    # endregion agent log (debug-a810eb)

    # Init extensions
    db.init_app(app)
    csrf.init_app(app)

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(rh_bp, url_prefix="/rh")
    app.register_blueprint(salarie_bp, url_prefix="/salarie")
    app.register_blueprint(responsable_bp, url_prefix="/responsable")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")

    @app.url_defaults
    def static_cache_bust(endpoint, values):
        if endpoint != "static":
            return
        filename = values.get("filename")
        if not filename:
            return
        filepath = os.path.join(app.static_folder, filename)
        try:
            values["v"] = int(os.path.getmtime(filepath))
        except OSError:
            pass

    @app.context_processor
    def inject_now():
        from datetime import datetime as _dt
        return {"now": _dt.now}

    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        if current_user.is_authenticated:
            from services.notifications import compter_non_lues
            return {"notifications_non_lues": compter_non_lues(current_user.id)}
        return {"notifications_non_lues": 0}

    # region agent log (debug-a810eb)
    @app.before_request
    def _agent_before_request_log():
        # Hypothèses:
        # H1: la requête n'arrive pas à Flask (=> aucun log)
        # H2: proto/host mal interprétés derrière IIS (X-Forwarded-Proto/Host)
        # H3: redirections/boucles (Location)
        _agent_log(
            "H2",
            "app.py:before_request",
            "Incoming request",
            {
                "method": request.method,
                "path": request.path,
                "url": request.url,
                "scheme": request.scheme,
                "host": request.host,
                "remoteAddr": request.remote_addr,
                "xForwardedProto": request.headers.get("X-Forwarded-Proto"),
                "xForwardedHost": request.headers.get("X-Forwarded-Host"),
                "xForwardedFor": request.headers.get("X-Forwarded-For"),
                "forwarded": request.headers.get("Forwarded"),
                "userAgent": request.headers.get("User-Agent"),
            },
        )

    # endregion agent log (debug-a810eb)

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
        # region agent log (debug-a810eb)
        _agent_log(
            "H3",
            "app.py:after_request",
            "Response sent",
            {
                "status": int(getattr(response, "status_code", 0) or 0),
                "path": request.path if request else None,
                "locationHeader": response.headers.get("Location"),
                "hasSetCookie": "Set-Cookie" in response.headers,
            },
        )
        # endregion agent log (debug-a810eb)
        return response

    @app.errorhandler(404)
    def page_not_found(e):
        from flask import render_template
        return render_template("erreur.html", code=404,
                               titre="Page introuvable",
                               message="La page demandée n'existe pas ou a été déplacée."), 404

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("erreur.html", code=403,
                               titre="Accès refusé",
                               message="Vous n'avez pas les droits pour accéder à cette ressource."), 403

    @app.errorhandler(500)
    def internal_error(e):
        from flask import render_template
        db.session.rollback()
        return render_template("erreur.html", code=500,
                               titre="Erreur interne",
                               message="Une erreur inattendue s'est produite. Veuillez réessayer ou contacter l'administrateur."), 500

    # Create tables
    with app.app_context():
        db.create_all()
        _migrations_dir = os.path.join(os.path.dirname(__file__), "scripts", "migrations")
        if _migrations_dir not in sys.path:
            sys.path.insert(0, _migrations_dir)
        _migrations = (
            "migrate_conges_statut", "migrate_user_email", "migrate_validation_2_niveaux",
            "migrate_rtt_columns", "migrate_conges_exceptionnels", "migrate_heures_payees",
            "migrate_rtt_calc_heures", "migrate_interessement", "migrate_heures_hebdo",
        )
        for mig in _migrations:
            try:
                __import__(mig).migrate()
            except Exception:
                _log.error("Migration %s echouee :", mig, exc_info=True)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)


