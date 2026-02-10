import bcrypt
import time
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
    # region agent log
    try:
        timestamp_ms = int(time.time() * 1000)
        log_line = (
            '{"id":"log_%d_login_entry",'
            '"timestamp":%d,'
            '"location":"routes/auth.py:login",'
            '"message":"login route called",'
            '"data":{"method":"%s","path":"/login"},'
            '"runId":"initial","hypothesisId":"H1"}\n'
        ) % (timestamp_ms, timestamp_ms, request.method)
        with open(r"c:\Users\kevin\ERPAC\ERPAC\Gestion_Conges\Application\.cursor\debug.log", "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass
    # endregion
    if current_user.is_authenticated:
        if current_user.role == "rh":
            return redirect(url_for("rh.dashboard"))
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
            return redirect(url_for("salarie.accueil"))
        else:
            # region agent log
            try:
                timestamp_ms = int(time.time() * 1000)
                log_line = (
                    '{"id":"log_%d_login_failed",'
                    '"timestamp":%d,'
                    '"location":"routes/auth.py:login",'
                    '"message":"login failed or user not found",'
                    '"data":{"identifiant_present":%s},'
                    '"runId":"initial","hypothesisId":"H2"}\n'
                ) % (timestamp_ms, timestamp_ms, "true" if bool(identifiant) else "false")
                with open(r"c:\Users\kevin\ERPAC\ERPAC\Gestion_Conges\Application\.cursor\debug.log", "a", encoding="utf-8") as f:
                    f.write(log_line)
            except Exception:
                pass
            # endregion
            flash("Identifiant ou mot de passe incorrect.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("auth.login"))
