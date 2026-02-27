from datetime import date, datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from models import db
from models.conge import Conge
from models.user import User
from services.solde import calculer_solde, get_parametrage_actif
from services.calcul_jours import compter_jours_ouvrables, detecter_chevauchement
from services.solde import verifier_solde_suffisant
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
        try:
            date_debut = datetime.strptime(request.form["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(request.form["date_fin"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            flash("Dates invalides.", "error")
            return render_template("salarie/demander_conge.html", solde=solde_info)

        if date_fin < date_debut:
            flash("La date de fin doit être postérieure à la date de début.", "error")
            return render_template("salarie/demander_conge.html", solde=solde_info)

        type_conge = request.form.get("type_conge", "").strip()
        if type_conge not in {"CP", "RTT", "Sans solde"}:
            flash("Merci de sélectionner un type de congé.", "error")
            return render_template("salarie/demander_conge.html", solde=solde_info)

        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la période sélectionnée.", "error")
            return render_template("salarie/demander_conge.html", solde=solde_info)

        chevauchement = detecter_chevauchement(current_user.id, date_debut, date_fin)
        if chevauchement:
            flash(
                f"Chevauchement avec un congé existant ({chevauchement.date_debut.strftime('%d/%m/%Y')} - "
                f"{chevauchement.date_fin.strftime('%d/%m/%Y')}).",
                "error",
            )
            return render_template("salarie/demander_conge.html", solde=solde_info)

        if type_conge in ("CP", "Anciennete"):
            if not verifier_solde_suffisant(current_user.id, nb_jours):
                flash(
                    f"Solde insuffisant. Reste {solde_info['solde_restant']} jour(s), vous en demandez {nb_jours}.",
                    "error",
                )
                return render_template("salarie/demander_conge.html", solde=solde_info)

        # Validation 2 niveaux : si le salarié a un responsable, en attente responsable sinon directement en attente RH
        statut_initial = "en_attente_responsable" if current_user.responsable_id else "en_attente_rh"
        conge = Conge(
            user_id=current_user.id,
            date_debut=date_debut,
            date_fin=date_fin,
            nb_jours_ouvrables=nb_jours,
            type_conge=type_conge,
            commentaire=commentaire,
            statut=statut_initial,
        )
        db.session.add(conge)
        db.session.commit()

        from services.notifications import notifier_responsable_nouvelle_demande, notifier_rh_nouvelle_demande
        if current_user.responsable_id:
            notifier_responsable_nouvelle_demande(conge)
        else:
            notifier_rh_nouvelle_demande(conge)
        db.session.commit()

        if current_user.responsable_id:
            flash("Demande de congé envoyée à votre responsable. Après sa validation, elle sera transmise aux RH.", "success")
        else:
            flash("Demande de congé envoyée. Elle sera traitée par les RH.", "success")
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

    events = []
    for c in conges_annee:
        salarie_nom = ""
        if voir_tous and c.utilisateur:
            salarie_nom = f"{c.utilisateur.prenom} {c.utilisateur.nom}"
        events.append({
            "start": c.date_debut.isoformat(),
            "end": c.date_fin.isoformat(),
            "type": c.type_conge,
            "statut": c.statut,
            "label": f"{c.date_debut.strftime('%d/%m/%Y')} → {c.date_fin.strftime('%d/%m/%Y')}",
            "jours": c.nb_jours_ouvrables,
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
