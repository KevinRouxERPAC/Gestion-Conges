import bcrypt
from services.auth_utils import hash_password, check_password, valider_mot_de_passe
from services.audit import log_action
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db
from models.user import User
from app import limiter

auth_bp = Blueprint("auth", __name__)


def _accueil_par_role(user):
    """URL d'accueil correspondant au rôle de l'utilisateur."""
    if user.role == "rh":
        return url_for("rh.dashboard")
    if user.role == "responsable":
        return url_for("responsable.dashboard")
    return url_for("salarie.accueil")



@auth_bp.route("/login", methods=["GET", "POST"])
# Protection contre le brute force : 10 tentatives/min/IP, 50/heure/IP.
# Les GET (affichage de la page) ne consomment pas le quota.
@limiter.limit("10 per minute; 50 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "rh":
            return redirect(url_for("rh.dashboard"))
        if current_user.role == "responsable":
            return redirect(url_for("responsable.dashboard"))
        return redirect(url_for("salarie.accueil"))

    if request.method == "POST":
        identifiant = request.form.get("identifiant", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")

        user = User.query.filter_by(identifiant=identifiant, actif=True).first()

        if user and check_password(mot_de_passe, user.mot_de_passe_hash):
            login_user(user)
            session.permanent = True
            flash("Connexion réussie.", "success")
            if user.role == "rh":
                return redirect(url_for("rh.dashboard"))
            if user.role == "responsable":
                return redirect(url_for("responsable.dashboard"))
            return redirect(url_for("salarie.accueil"))
        else:
            flash("Identifiant ou mot de passe incorrect.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/changer-mot-de-passe", methods=["GET", "POST"])
@login_required
def changer_mot_de_passe():
    """Changement de mot de passe en self-service (tous rôles).

    L'utilisateur doit confirmer son mot de passe actuel. Le nouveau mot de passe
    suit la politique commune (`valider_mot_de_passe`) et doit être différent de
    l'ancien. Aucune réinitialisation par email n'est possible (RGPD : pas
    d'email salarié) : l'oubli total reste géré par les RH via la fiche salarié.
    """
    if request.method == "POST":
        actuel = request.form.get("mot_de_passe_actuel", "")
        nouveau = request.form.get("nouveau_mot_de_passe", "")
        confirmation = request.form.get("confirmation_mot_de_passe", "")

        if not check_password(actuel, current_user.mot_de_passe_hash):
            flash("Mot de passe actuel incorrect.", "error")
            return render_template("auth/changer_mot_de_passe.html")

        if nouveau != confirmation:
            flash("La confirmation ne correspond pas au nouveau mot de passe.", "error")
            return render_template("auth/changer_mot_de_passe.html")

        err_pwd = valider_mot_de_passe(nouveau)
        if err_pwd:
            flash(err_pwd, "error")
            return render_template("auth/changer_mot_de_passe.html")

        if check_password(nouveau, current_user.mot_de_passe_hash):
            flash("Le nouveau mot de passe doit être différent de l'actuel.", "error")
            return render_template("auth/changer_mot_de_passe.html")

        user = User.query.get(current_user.id)
        user.mot_de_passe_hash = hash_password(nouveau)
        log_action("compte.changer_mdp", cible_type="user", cible_id=user.id)
        db.session.commit()
        flash("Mot de passe mis à jour.", "success")
        return redirect(url_for("auth.changer_mot_de_passe"))

    return render_template("auth/changer_mot_de_passe.html")
