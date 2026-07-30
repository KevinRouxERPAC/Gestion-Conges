import os
import sys
import secrets
import logging
from datetime import timedelta
from flask import Flask, redirect, url_for, Response, send_from_directory, g
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

    @app.before_request
    def _generer_csp_nonce():
        # Nonce unique par requête, partagé entre l'en-tête CSP (script-src) et les
        # scripts inline des templates ({{ csp_nonce }}). Permet de retirer
        # 'unsafe-inline' de script-src sans casser les scripts inline légitimes.
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_csp_nonce():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.context_processor
    def inject_now():
        from datetime import datetime as _dt
        return {"now": _dt.now}

    @app.template_filter("nb_jours")
    def _format_nb_jours(valeur):
        """Affiche un nombre de jours en français (`1,5` au lieu de `1.5`).
        Retire les zéros inutiles : 2.0 → "2", 1.5 → "1,5".

        S'appuie sur services.format_heures.format_jours pour que templates et
        messages flash appliquent exactement la même règle de formatage.
        """
        from services.format_heures import format_jours
        return format_jours(valeur)

    @app.template_filter("nb_heures")
    def _format_nb_heures(valeur):
        """Affiche un nombre d'heures au centième, sans unité (ex. 16,10)."""
        from services.format_heures import format_heures_cent
        return format_heures_cent(valeur)

    @app.template_filter("nb_heures_cent")
    def _format_nb_heures_cent(valeur):
        """Alias de ``nb_heures`` : centième d'heure sans unité."""
        from services.format_heures import format_heures_cent
        return format_heures_cent(valeur)

    @app.template_filter("heures_min")
    def _format_heures_min(valeur):
        """Affiche une durée en centièmes d'heure avec unité (ex. 5,25 h)."""
        from services.format_heures import format_heures_min
        return format_heures_min(valeur)

    @app.template_filter("libelle_exceptionnel")
    def _libelle_exceptionnel(code):
        """Résout le libellé d'un type exceptionnel depuis son code (ex. MARIAGE → "Mariage").

        Mise en cache par requête (flask.g) pour éviter un N+1 lors de l'affichage
        d'une liste de congés. Retombe sur le code si le type est introuvable.
        """
        if not code:
            return code
        from flask import g
        cache = getattr(g, "_exc_libelles", None)
        if cache is None:
            from services.conges_exceptionnels import get_types_exceptionnels
            cache = {t.code: t.libelle for t in get_types_exceptionnels(actifs_only=False)}
            g._exc_libelles = cache
        return cache.get(code, code)

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
        - script-src 'self' 'nonce-…' 'unsafe-eval' : plus de 'unsafe-inline'.
          Les scripts inline légitimes portent le nonce de la requête
          ({{ csp_nonce }}), les gestionnaires inline on*= ont été remplacés par
          des écouteurs délégués (static/js/app.js). 'unsafe-eval' reste requis
          car Alpine.js v3 (build standard) et FullCalendar compilent leurs
          expressions via `new Function(...)` ; le retirer nécessiterait la
          migration vers Alpine CSP build (chantier séparé).
        - style-src garde 'unsafe-inline' : FullCalendar et quelques composants
          injectent des styles inline ; durcissement à traiter à part.
        - Google Fonts (fonts.googleapis.com + fonts.gstatic.com) autorisé
          pour la feuille de style et les fichiers de police (Inter).
        - frame-ancestors 'none' : remplace X-Frame-Options DENY.
        - HSTS uniquement si PREFERRED_URL_SCHEME=https (cf. no_hsts ci-dessus).
        """
        nonce = getattr(g, "csp_nonce", "")
        script_src = (
            f"script-src 'self' 'nonce-{nonce}' 'unsafe-eval'; "
            if nonce
            else "script-src 'self' 'unsafe-eval'; "
        )
        csp = (
            "default-src 'self'; "
            + script_src
            + "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
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

    # Schéma de base : en production (SKIP_DB_CREATE_ALL=1), les évolutions passent
    # par Alembic (`flask db upgrade`). Au démarrage on valide le schéma et on
    # protège chaque commit (rollback automatique en cas d'erreur SQL).
    from services.db_safety import DbSaveError, preparer_base_au_demarrage

    preparer_base_au_demarrage(app)

    @app.errorhandler(DbSaveError)
    def _handle_db_save_error(exc: DbSaveError):
        from flask import flash, jsonify, redirect, request, url_for

        logger = logging.getLogger(__name__)
        logger.warning("Enregistrement refusé : %s", exc.message, exc_info=exc.original)

        if request.path.startswith("/api/"):
            return jsonify({"error": exc.message}), 409

        flash(exc.message, "error")
        referrer = request.referrer
        if referrer and referrer.startswith(request.host_url):
            return redirect(referrer)
        if request.blueprint == "rh":
            return redirect(url_for("rh.dashboard"))
        return redirect(url_for("auth.login"))

    @app.teardown_request
    def _rollback_session_si_erreur(exc):
        if exc is not None:
            db.session.rollback()

    # ------------------------------------------------------------------ #
    # Commande CLI : flask sync-erp-heures [--semaine AAAASS]             #
    # Destinée à être appelée par le Planificateur de tâches Windows      #
    # chaque vendredi (ou manuellement).                                  #
    # ------------------------------------------------------------------ #
    import click

    @app.cli.command("sync-erp-heures")
    @click.option(
        "--semaine",
        default=None,
        metavar="AAAASS",
        help="Semaine à importer (ex. 202624). Défaut : semaine précédente.",
    )
    @click.option(
        "--no-rtt",
        is_flag=True,
        default=False,
        help="Importe les heures sans recalculer les RTT.",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Aperçu : n'écrit rien en base, affiche le diff qui serait importé.",
    )
    def cmd_sync_erp_heures(semaine, no_rtt, dry_run):
        """Importe les heures hebdomadaires depuis l'ERP (SILOG/Cegid PMI)."""
        from services.erp.sync_heures import synchroniser_semaine
        from services.erp.connexion import ErpNonConfigureError

        try:
            rapport = synchroniser_semaine(
                semaine_erp=semaine,
                recalculer_rtt=not no_rtt,
                dry_run=dry_run,
            )
        except ErpNonConfigureError as e:
            click.echo(f"[ERREUR] {e}", err=True)
            raise SystemExit(1)
        except Exception as e:
            click.echo(f"[ERREUR] {e}", err=True)
            raise SystemExit(1)

        mode = "APERÇU" if dry_run else "IMPORT"
        click.echo(f"[{mode}] Semaine ERP : {rapport.semaine_erp} (lundi {rapport.date_lundi})")
        click.echo(f"  Heures importées     : {rapport.nb_importes}")
        click.echo(f"  Sans matricule app   : {rapport.nb_skipped_sans_user}")
        click.echo(f"  RTT recalculé        : {'oui' if rapport.rtt_recalcule else 'non'}")
        if dry_run and rapport.preview:
            click.echo(f"  --- Aperçu ({len(rapport.preview)} ligne(s)) ---")
            for p in rapport.preview:
                ancienne = p.get("ancienne_valeur")
                ancienne_str = f"{ancienne} h" if ancienne is not None else "(nouveau)"
                click.echo(
                    f"    matricule={p['matricule']} user={p['user_id']} "
                    f"{ancienne_str} → {p['heures_erp']} h [{p['action']}]"
                )
        for w in rapport.avertissements:
            click.echo(f"  [!] {w}")

    @app.cli.command("backup-db")
    @click.option("--forcer", is_flag=True, help="Ignore l'intervalle minimum entre sauvegardes.")
    @click.option("--raison", default="manuel-cli", help="Libellé de la sauvegarde.")
    def cmd_backup_db(forcer, raison):
        """Sauvegarde la base SQLite dans le dossier backup/."""
        from services.db_backup import sauvegarder_base

        info = sauvegarder_base(raison, forcer=forcer)
        if info is None:
            click.echo("Aucune sauvegarde effectuée (pas de fichier SQLite ou intervalle non écoulé).")
            raise SystemExit(1)
        click.echo(f"Sauvegarde : {info.chemin} ({info.taille_octets} octets, users={info.users})")

    @app.cli.command("list-db-backups")
    def cmd_list_db_backups():
        """Liste les sauvegardes disponibles dans backup/."""
        from services.db_backup import lister_sauvegardes

        sauvegardes = lister_sauvegardes()
        if not sauvegardes:
            click.echo("Aucune sauvegarde.")
            return
        for s in sauvegardes:
            click.echo(
                f"{s.cree_le:%Y-%m-%d %H:%M}  {s.raison:16}  "
                f"{s.taille_octets:>8} o  users={s.users if s.users is not None else '?'}"
                f"  {s.chemin.name}"
            )

    @app.cli.command("envoyer-rappels")
    def cmd_envoyer_rappels():
        """Envoie les rappels automatiques (demandes en attente, fin d'exercice).

        À planifier une fois par jour (ex. via le Planificateur de tâches Windows
        ou APScheduler).
        """
        from services.rappels import envoyer_rappels
        bilan = envoyer_rappels()
        click.echo(
            f"Rappels envoyés : {bilan['en_attente']} demande(s) en attente, "
            f"{bilan['fin_exercice']} rappel(s) fin d'exercice."
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)


