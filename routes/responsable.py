# Blueprint Responsable - validation niveau 1 + calendrier équipe + ajout congé subordonné
from datetime import datetime, timezone, date
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db
from models.conge import Conge
from models.user import User
from services.notifications import notifier_rh_demande_transmise, notifier_conge_refuse, notifier_rh_nouvelle_demande
from services.solde import calculer_solde
from services.audit import log_action

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
    solde_info = calculer_solde(current_user.id)
    subordonnes_actifs = [u for u in current_user.subordonnes if u.actif]
    subordonne_ids = [u.id for u in subordonnes_actifs]
    demandes_attente = (
        Conge.query.filter(Conge.user_id.in_(subordonne_ids), Conge.statut == "en_attente_responsable")
        .order_by(Conge.cree_le.asc()).all()
    ) if subordonne_ids else []

    today = date.today()
    start_of_year = date(today.year, 1, 1)
    end_of_year = date(today.year, 12, 31)

    calendar_events = []
    if subordonne_ids:
        conges_equipe = Conge.query.filter(
            Conge.user_id.in_(subordonne_ids),
            Conge.date_debut <= end_of_year,
            Conge.date_fin >= start_of_year,
            Conge.statut.in_(["valide", "en_attente_responsable", "en_attente_rh"]),
        ).all()
        for c in conges_equipe:
            if c.utilisateur:
                calendar_events.append({
                    "start": c.date_debut.isoformat(),
                    "end": c.date_fin.isoformat(),
                    "user": f"{c.utilisateur.prenom} {c.utilisateur.nom}",
                    "type_conge": c.type_conge,
                    "statut": c.statut,
                })

    return render_template(
        "responsable/dashboard.html",
        solde=solde_info,
        demandes_attente=demandes_attente,
        subordonnes=subordonnes_actifs,
        calendar_events=calendar_events,
    )

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
    conge.valide_par_responsable_le = datetime.now(timezone.utc)
    log_action(
        "conge.valider_n1",
        cible_type="conge",
        cible_id=conge.id,
        details={
            "user_id": conge.user_id,
            "type_conge": conge.type_conge,
            "nb_jours": conge.nb_jours_ouvrables,
            "periode": f"{conge.date_debut} → {conge.date_fin}",
        },
    )
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
        conge.valide_par_responsable_le = datetime.now(timezone.utc)
        conge.motif_refus = motif
        log_action(
            "conge.refuser_n1",
            cible_type="conge",
            cible_id=conge.id,
            details={"user_id": conge.user_id, "motif": motif},
        )
        db.session.commit()
        notifier_conge_refuse(conge, motif)
        db.session.commit()
        flash("Demande refusée.", "success")
        return redirect(url_for("responsable.dashboard"))
    return render_template("responsable/refuser_conge.html", conge=conge)


@responsable_bp.route("/subordonne/<int:user_id>/conge/ajouter", methods=["GET", "POST"])
@responsable_bp.route("/subordonné/<int:user_id>/conge/ajouter", methods=["GET", "POST"])
@responsable_required
def ajouter_conge_subordonne(user_id):
    """Le responsable crée un congé pour un de ses subordonnés (envoyé directement en attente RH)."""
    user = User.query.get_or_404(user_id)
    if user.responsable_id != current_user.id:
        flash("Ce salarié n'est pas dans votre équipe.", "error")
        return redirect(url_for("responsable.dashboard"))

    solde_info = calculer_solde(user.id)
    from services.conges_exceptionnels import get_types_exceptionnels
    types_exceptionnels = get_types_exceptionnels(actifs_only=True)

    if request.method == "POST":
        from services.creer_conge import construire_conge, MODE_RESPONSABLE
        result = construire_conge(
            user,
            request.form,
            mode=MODE_RESPONSABLE,
            statut_initial="en_attente_rh",
            valide_par_responsable=current_user,
        )

        for category, message in result.flashes:
            flash(message, category)

        if not result.success:
            return render_template(
                "responsable/ajouter_conge.html",
                salarie=user,
                solde=solde_info,
                types_exceptionnels=types_exceptionnels,
            )

        db.session.add(result.conge)
        db.session.commit()

        notifier_rh_nouvelle_demande(result.conge)
        db.session.commit()

        flash(f"Congé créé pour {user.prenom} {user.nom} et transmis aux RH.", "success")
        return redirect(url_for("responsable.dashboard"))

    return render_template(
        "responsable/ajouter_conge.html",
        salarie=user,
        solde=solde_info,
        types_exceptionnels=types_exceptionnels,
    )
