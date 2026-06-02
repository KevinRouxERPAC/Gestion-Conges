from datetime import date, datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from models import db
from models.conge import Conge
from models.user import User
from services.solde import calculer_solde, get_allocation, get_parametrage_actif
from services.export import export_conges_excel, export_conges_pdf

salarie_bp = Blueprint("salarie", __name__)


@salarie_bp.route("/demander-conge", methods=["GET", "POST"])
@login_required
def demander_conge():
    """Le salarié soumet une demande de congé (validation 2 niveaux : responsable puis RH)."""
    if current_user.role == "rh":
        flash("Les RH ajoutent les congés directement depuis le profil du salarié.", "info")
        return redirect(url_for("rh.dashboard"))

    solde_info = calculer_solde(current_user.id)

    if request.method == "POST":
        from services.creer_conge import construire_conge, MODE_SALARIE
        statut_initial = "en_attente_responsable" if current_user.responsable_id else "en_attente_rh"
        result = construire_conge(
            current_user,
            request.form,
            mode=MODE_SALARIE,
            statut_initial=statut_initial,
        )

        for category, message in result.flashes:
            flash(message, category)

        if not result.success:
            return render_template("salarie/demander_conge.html", solde=solde_info)

        db.session.add(result.conge)
        db.session.commit()

        from services.notifications import (
            notifier_responsable_nouvelle_demande,
            notifier_rh_nouvelle_demande,
        )
        if current_user.responsable_id:
            notifier_responsable_nouvelle_demande(result.conge)
            flash(
                "Demande de congé envoyée à votre responsable. Après sa validation, elle sera transmise aux RH.",
                "success",
            )
        else:
            notifier_rh_nouvelle_demande(result.conge)
            flash("Demande de congé envoyée. Elle sera traitée par les RH.", "success")
        db.session.commit()

        return redirect(url_for("salarie.accueil"))

    return render_template("salarie/demander_conge.html", solde=solde_info)


@salarie_bp.route("/accueil")
@login_required
def accueil():
    solde_info = calculer_solde(current_user.id)
    param = get_parametrage_actif()

    conges = Conge.query.filter_by(user_id=current_user.id).order_by(Conge.date_debut.desc()).all()

    return render_template(
        "salarie/accueil.html",
        solde=solde_info,
        conges=conges,
        parametrage=param,
    )



@salarie_bp.route("/conge/<int:conge_id>/annuler", methods=["POST"])
@login_required
def annuler_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    if conge.user_id != current_user.id:
        flash("Vous ne pouvez annuler que vos propres demandes.", "error")
        return redirect(url_for("salarie.accueil"))
    if conge.statut not in ("en_attente_responsable", "en_attente_rh"):
        flash("Seules les demandes en attente peuvent être annulées.", "warning")
        return redirect(url_for("salarie.accueil"))
    conge.statut = "annule"
    db.session.commit()
    flash("Demande de congé annulée.", "success")
    return redirect(url_for("salarie.accueil"))

@salarie_bp.route("/calendrier")
@login_required
def calendrier():
    """Calendrier annuel des congés du salarié, avec navigation entre années."""
    # Année via ?annee=YYYY, sinon année courante ; tous=1 pour voir tous les salariés
    try:
        year = int(request.args.get("annee", date.today().year))
    except (TypeError, ValueError):
        year = date.today().year
    voir_tous = request.args.get("tous") == "1"
    if voir_tous and current_user.role not in ("salarie", "responsable"):
        voir_tous = False
        flash("Option 'tout le monde' réservée aux salariés et responsables.", "warning")

    start_of_year = date(year, 1, 1)
    end_of_year = date(year, 12, 31)

    # Congés de l'année (validés + en attente, pas les refusés)
    if voir_tous:
        conges_annee = (
            Conge.query.join(User, Conge.user_id == User.id)
            .filter(
                User.actif == True,
                Conge.date_debut <= end_of_year,
                Conge.date_fin >= start_of_year,
                Conge.statut.in_(["valide", "en_attente_responsable", "en_attente_rh"]),
            )
            .all()
        )
    else:
        conges_annee = Conge.query.filter(
            Conge.user_id == current_user.id,
            Conge.date_debut <= end_of_year,
            Conge.date_fin >= start_of_year,
            Conge.statut.in_(["valide", "en_attente_responsable", "en_attente_rh"]),
        ).all()

    def _filter_group(type_conge: str) -> str:
        """Groupe de filtrage utilisé par la légende/cases à cocher du calendrier."""
        if not type_conge:
            return "default"
        if type_conge in ("CP", "Anciennete", "RTT", "Sans solde", "Maladie"):
            return type_conge
        if type_conge.startswith("EXC:"):
            return "Exceptionnel"
        return "default"

    events = []
    for c in conges_annee:
        salarie_nom = ""
        if voir_tous and c.utilisateur:
            salarie_nom = f"{c.utilisateur.prenom} {c.utilisateur.nom}"
        events.append({
            "start": c.date_debut.isoformat(),
            "end": c.date_fin.isoformat(),
            "type": c.type_conge,
            "filter_group": _filter_group(c.type_conge),
            "statut": c.statut,
            "label": f"{c.date_debut.strftime('%d/%m/%Y')} → {c.date_fin.strftime('%d/%m/%Y')}",
            "jours": c.nb_jours_ouvrables,
            "heures_rtt": c.nb_heures_rtt,
            "salarie": salarie_nom,
        })

    # Historique récapitulatif par année (validés uniquement)
    tous_conges = Conge.query.filter_by(
        user_id=current_user.id, statut="valide"
    ).all()
    resume_par_annee = {}
    for c in tous_conges:
        annee = c.date_debut.year
        if annee not in resume_par_annee:
            resume_par_annee[annee] = {
                "annee": annee,
                "nb_conges": 0,
                "total_jours": 0,
            }
        resume_par_annee[annee]["nb_conges"] += 1
        resume_par_annee[annee]["total_jours"] += c.nb_jours_ouvrables or 0

    historique = sorted(resume_par_annee.values(), key=lambda x: x["annee"], reverse=True)

    return render_template(
        "salarie/calendrier.html",
        year=year,
        events=events,
        historique=historique,
        voir_tous=voir_tous,
    )


@salarie_bp.route("/export/excel")
@login_required
def export_excel():
    """Export Excel des congés du salarié connecté."""
    if current_user.role == "rh":
        return redirect(url_for("rh.export_equipe_excel"))
    conges = Conge.query.filter_by(user_id=current_user.id).order_by(Conge.date_debut.desc()).all()
    buffer = export_conges_excel(conges, current_user.nom, current_user.prenom)
    filename = f"mes_conges_{current_user.prenom}_{current_user.nom}_{date.today().strftime('%Y%m%d')}.xlsx"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@salarie_bp.route("/export/pdf")
@login_required
def export_pdf():
    """Export PDF des congés du salarié connecté."""
    if current_user.role == "rh":
        return redirect(url_for("rh.dashboard"))
    conges = Conge.query.filter_by(user_id=current_user.id).order_by(Conge.date_debut.desc()).all()
    solde_info = calculer_solde(current_user.id)
    buffer = export_conges_pdf(conges, solde_info, current_user.nom, current_user.prenom)
    filename = f"mes_conges_{current_user.prenom}_{current_user.nom}_{date.today().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


@salarie_bp.route("/heures")
@login_required
def heures():
    """Vue hebdomadaire des heures travaillées et du RTT calculé sur l'exercice.

    Le RTT est calculé semaine par semaine : une absence réduit le seuil
    hebdomadaire pour ne pas pénaliser le salarié (cf. services/rtt_hebdo.py).
    """
    param = get_parametrage_actif()
    allocation = None
    rtt_calc = None
    detail = []

    if param:
        allocation = get_allocation(current_user.id, parametrage_id=param.id)
        from services.rtt_hebdo import calculer_rtt_hebdo
        try:
            rtt_calc = calculer_rtt_hebdo(current_user.id, param)
            # Semaines les plus récentes en premier.
            detail = sorted(rtt_calc.detail, key=lambda d: d["lundi"], reverse=True)
        except Exception:
            rtt_calc = None
            detail = []

    total_heures = sum((d["heures"] or 0) for d in detail)

    return render_template(
        "salarie/heures.html",
        parametrage=param,
        allocation=allocation,
        rtt_calc=rtt_calc,
        detail=detail,
        total_heures=total_heures,
    )





