import logging
import os
import sys
from datetime import timedelta
from flask import Flask, redirect, url_for, Response, send_from_directory
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from models import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
_log = logging.getLogger(__name__)

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
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


