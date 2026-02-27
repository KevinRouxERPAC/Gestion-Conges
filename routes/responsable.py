# Blueprint Responsable - validation niveau 1
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db
from models.conge import Conge
from models.user import User
from services.notifications import notifier_rh_demande_transmise, notifier_conge_refuse

responsable_bp = Blueprint("responsable", __name__)

def responsable_required(f):
    @wraps(f)
    @login_required
    def dec(*args, **kwargs):
        if current_user.role != "responsable":
            flash("Accès réservé aux responsables.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return dec

@responsable_bp.route("/dashboard")
@responsable_required
def dashboard():
    subordonne_ids = [u.id for u in current_user.subordonnes if u.actif]
    demandes_attente = (Conge.query.filter(Conge.user_id.in_(subordonne_ids), Conge.statut == "en_attente_responsable").order_by(Conge.cree_le.asc()).all()) if subordonne_ids else []
    return render_template("responsable/dashboard.html", demandes_attente=demandes_attente, subordonnes=current_user.subordonnes)

@responsable_bp.route("/conge/<int:conge_id>/valider", methods=["POST"])
@responsable_required
def valider_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    if conge.statut != "en_attente_responsable":
        flash("Cette demande n'est pas en attente de votre validation.", "warning")
        return redirect(url_for("responsable.dashboard"))
    u = conge.utilisateur
    if not u or u.responsable_id != current_user.id:
        flash("Vous n'êtes pas le responsable de ce salarié.", "error")
        return redirect(url_for("responsable.dashboard"))
    conge.statut = "en_attente_rh"
    conge.valide_par_responsable_id = current_user.id
    conge.valide_par_responsable_le = datetime.now(timezone.utc)()
    db.session.commit()
    notifier_rh_demande_transmise(conge)
    db.session.commit()
    flash("Demande validée. Transmise aux RH.", "success")
    return redirect(url_for("responsable.dashboard"))

@responsable_bp.route("/conge/<int:conge_id>/refuser", methods=["GET", "POST"])
@responsable_required
def refuser_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    if conge.statut != "en_attente_responsable":
        flash("Cette demande n'est pas en attente.", "warning")
        return redirect(url_for("responsable.dashboard"))
    u = conge.utilisateur
    if not u or u.responsable_id != current_user.id:
        flash("Vous n'êtes pas le responsable de ce salarié.", "error")
        return redirect(url_for("responsable.dashboard"))
    if request.method == "POST":
        motif = request.form.get("motif_refus", "").strip()
        if not motif:
            flash("Le motif de refus est obligatoire.", "error")
            return render_template("responsable/refuser_conge.html", conge=conge)
        conge.statut = "refuse"
        conge.valide_par_responsable_id = current_user.id
        conge.valide_par_responsable_le = datetime.now(timezone.utc)()
        conge.valide_par_id = current_user.id
        conge.valide_le = datetime.now(timezone.utc)()
        conge.motif_refus = motif
        db.session.commit()
        notifier_conge_refuse(conge, motif)
        db.session.commit()
        flash("Demande refusée.", "success")
        return redirect(url_for("responsable.dashboard"))
    return render_template("responsable/refuser_conge.html", conge=conge)
