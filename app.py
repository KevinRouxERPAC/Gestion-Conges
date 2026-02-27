import os
import json
import time
from datetime import timedelta
from flask import Flask, redirect, url_for, Response, send_from_directory
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from models import db

# #region agent log
def _dlog(msg, hypothesis_id, data=None):
    entry = json.dumps({"sessionId": "e6ee59", "timestamp": int(time.time() * 1000), "location": "app.py create_app", "message": msg, "hypothesisId": hypothesis_id, "data": data or {}}) + "\n"
    base = os.path.dirname(os.path.abspath(__file__))
    for log_dir in [os.path.join(base, "logs"), base]:
        try:
            if not os.path.isdir(log_dir) and log_dir != base:
                os.makedirs(log_dir, exist_ok=True)
            p = os.path.join(log_dir, "debug-e6ee59.log") if os.path.isdir(log_dir) else os.path.join(base, "logs", "debug-e6ee59.log")
            if log_dir == base:
                p = os.path.join(base, "debug-e6ee59.log")
            else:
                p = os.path.join(log_dir, "debug-e6ee59.log")
            with open(p, "a", encoding="utf-8") as f:
                f.write(entry)
            break
        except Exception:
            continue
# #endregion

def create_app():
    # #region agent log
    _dlog("create_app entry", "H3", {})
    # #endregion
    app = Flask(__name__)
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(seconds=app.config["PERMANENT_SESSION_LIFETIME"])
    # Derrière IIS (HTTP ou HTTPS) : utiliser X-Forwarded-Proto pour url_for / redirects
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Init extensions
    db.init_app(app)

    # Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
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

    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        if current_user.is_authenticated:
            from services.notifications import compter_non_lues
            return {"notifications_non_lues": compter_non_lues(current_user.id)}
        return {"notifications_non_lues": 0}

    # Root redirect
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    # Évite le 404 favicon dans la console (requête automatique du navigateur)
    @app.route("/favicon.ico")
    def favicon():
        return Response(status=204)

    # Service worker à la racine pour que la portée soit / (requis pour Web Push)
    @app.route("/sw.js")
    def service_worker():
        return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")

    # Ne pas ajouter HSTS si le site est en HTTP ; en HTTPS on laisse le serveur (IIS) le gérer
    @app.after_request
    def no_hsts(response):
        if app.config.get("PREFERRED_URL_SCHEME") != "https":
            response.headers.pop("Strict-Transport-Security", None)
        return response

    # Create tables
    # #region agent log
    _dlog("before app_context", "H3", {})
    # #endregion
    with app.app_context():
        db.create_all()
        # Migrations
        for mig in ("migrate_conges_statut", "migrate_user_email", "migrate_validation_2_niveaux"):
            try:
                __import__(mig).migrate()
            except Exception:
                pass
    # #region agent log
    _dlog("create_app returning", "H3", {})
    # #endregion
    return app


if __name__ == "__main__":
    app = create_app()
    # threaded=True : permet de traiter plusieurs requêtes simultanées (multi-utilisateurs en dev)
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
