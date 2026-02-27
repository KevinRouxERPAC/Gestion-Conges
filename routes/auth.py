import bcrypt
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password, hashed):
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


@auth_bp.route("/login", methods=["GET", "POST"])
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
