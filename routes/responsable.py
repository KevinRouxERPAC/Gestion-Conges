# Blueprint Responsable - validation niveau 1 + calendrier équipe + ajout congé subordonné
from datetime import datetime, timezone, date
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db
from models.conge import Conge
from models.user import User
from services.notifications import notifier_rh_demande_transmise, notifier_conge_refuse, notifier_rh_nouvelle_demande
from services.solde import calculer_solde, verifier_solde_suffisant, verifier_solde_rtt_suffisant
from services.calcul_jours import compter_jours_ouvrables, detecter_chevauchement

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
        demandes_attente=demandes_attente,
        subordonnes=current_user.subordonnes,
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
        conge.valide_par_id = current_user.id
        conge.valide_le = datetime.now(timezone.utc)
        conge.motif_refus = motif
        db.session.commit()
        notifier_conge_refuse(conge, motif)
        db.session.commit()
        flash("Demande refusée.", "success")
        return redirect(url_for("responsable.dashboard"))
    return render_template("responsable/refuser_conge.html", conge=conge)


@responsable_bp.route("/subordonné/<int:user_id>/conge/ajouter", methods=["GET", "POST"])
@responsable_required
def ajouter_conge_subordonne(user_id):
    """Le responsable crée un congé pour un de ses subordonnés (envoyé directement en attente RH)."""
    user = User.query.get_or_404(user_id)
    if user.responsable_id != current_user.id:
        flash("Ce salarié n'est pas dans votre équipe.", "error")
        return redirect(url_for("responsable.dashboard"))

    solde_info = calculer_solde(user.id)

    if request.method == "POST":
        try:
            date_debut = datetime.strptime(request.form["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(request.form["date_fin"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            flash("Dates invalides.", "error")
            return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)

        if date_fin < date_debut:
            flash("La date de fin doit être postérieure à la date de début.", "error")
            return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)

        type_conge = request.form.get("type_conge", "CP")
        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la période sélectionnée.", "error")
            return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)

        chevauchement = detecter_chevauchement(user.id, date_debut, date_fin)
        if chevauchement:
            flash(
                f"Chevauchement détecté avec le congé du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
                f"au {chevauchement.date_fin.strftime('%d/%m/%Y')}.",
                "error",
            )
            return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)

        nb_heures_rtt = None

        if type_conge in ("CP", "Anciennete"):
            if not verifier_solde_suffisant(user.id, nb_jours):
                flash(
                    f"Solde CP insuffisant. {solde_info['solde_restant']} jour(s) restant(s), "
                    f"{nb_jours} jour(s) demandé(s).",
                    "error",
                )
                return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)
        elif type_conge == "RTT":
            try:
                nb_heures_rtt_val = int(request.form.get("nb_heures_rtt", "0"))
            except ValueError:
                nb_heures_rtt_val = 0
            if nb_heures_rtt_val <= 0:
                flash("Merci de saisir un nombre d'heures RTT valide (>= 1).", "error")
                return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)
            if not verifier_solde_rtt_suffisant(user.id, nb_heures_rtt_val):
                solde_rtt = solde_info.get("rtt_solde_restant", 0)
                flash(
                    f"Solde RTT insuffisant. {solde_rtt} heure(s) restante(s), "
                    f"{nb_heures_rtt_val} heure(s) demandée(s).",
                    "error",
                )
                return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)
            nb_heures_rtt = nb_heures_rtt_val

        conge = Conge(
            user_id=user.id,
            date_debut=date_debut,
            date_fin=date_fin,
            nb_jours_ouvrables=nb_jours,
            type_conge=type_conge,
            commentaire=commentaire,
            statut="en_attente_rh",
            valide_par_responsable_id=current_user.id,
            valide_par_responsable_le=datetime.now(timezone.utc),
            nb_heures_rtt=nb_heures_rtt,
        )
        db.session.add(conge)
        db.session.commit()

        notifier_rh_nouvelle_demande(conge)
        db.session.commit()

        flash(f"Congé créé pour {user.prenom} {user.nom} et transmis aux RH.", "success")
        return redirect(url_for("responsable.dashboard"))

    return render_template("responsable/ajouter_conge.html", salarie=user, solde=solde_info)
