import os
import sys
from datetime import timedelta
from flask import Flask, redirect, url_for, Response, send_from_directory
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from models import db

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(seconds=app.config["PERMANENT_SESSION_LIFETIME"])
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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

    # Create tables
    with app.app_context():
        db.create_all()
        _migrations_dir = os.path.join(os.path.dirname(__file__), "scripts", "migrations")
        if _migrations_dir not in sys.path:
            sys.path.insert(0, _migrations_dir)
        for mig in ("migrate_conges_statut", "migrate_user_email", "migrate_validation_2_niveaux"):
            try:
                __import__(mig).migrate()
            except Exception:
                pass

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
