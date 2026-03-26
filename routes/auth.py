import time

from services.auth_utils import check_password
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)

_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 900  # 15 minutes
_login_attempts = {}  # {ip: [timestamp, timestamp, ...]}


def _is_locked(ip):
    attempts = _login_attempts.get(ip, [])
    cutoff = time.time() - _LOCKOUT_SECONDS
    recent = [t for t in attempts if t > cutoff]
    _login_attempts[ip] = recent
    return len(recent) >= _MAX_ATTEMPTS


def _record_failure(ip):
    _login_attempts.setdefault(ip, []).append(time.time())


def _clear_attempts(ip):
    _login_attempts.pop(ip, None)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "rh":
            return redirect(url_for("rh.dashboard"))
        if current_user.role == "responsable":
            return redirect(url_for("responsable.dashboard"))
        return redirect(url_for("salarie.accueil"))

    if request.method == "POST":
        ip = request.remote_addr or "unknown"

        if _is_locked(ip):
            flash("Trop de tentatives. Réessayez dans quelques minutes.", "error")
            return render_template("auth/login.html")

        identifiant = request.form.get("identifiant", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")

        user = User.query.filter_by(identifiant=identifiant, actif=True).first()

        if user and check_password(mot_de_passe, user.mot_de_passe_hash):
            _clear_attempts(ip)
            login_user(user)
            session.permanent = True
            flash("Connexion réussie.", "success")
            if user.role == "rh":
                return redirect(url_for("rh.dashboard"))
            if user.role == "responsable":
                return redirect(url_for("responsable.dashboard"))
            return redirect(url_for("salarie.accueil"))
        else:
            _record_failure(ip)
            flash("Identifiant ou mot de passe incorrect.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("auth.login"))
