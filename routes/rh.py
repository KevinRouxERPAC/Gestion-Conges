from datetime import datetime, timezone, date
from functools import wraps

import bcrypt
from services.auth_utils import hash_password
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user

from models import db
from models.conge import Conge
from models.jour_ferie import JourFerie
from models.parametrage import ParametrageAnnuel, AllocationConge
from models.user import User
from models.conge_exceptionnel_type import CongeExceptionnelType
from models.heures_payees import HeuresPayees
from services.calcul_jours import compter_jours_ouvrables, detecter_chevauchement
from services.solde import (
    calculer_solde,
    get_parametrage_actif,
    verifier_solde_suffisant,
    verifier_solde_rtt_suffisant,
    generer_allocations_pour_parametrage,
)
from services.jours_feries import get_jours_feries
from services.notifications import notifier_conge_valide, notifier_conge_refuse
from services.export import export_conges_excel, export_conges_equipe_excel, export_conges_pdf
from services.export_comptable import export_compta_cp_rtt_xlsx
from services.heures_rtt import maj_rtt_allocations_depuis_heures
from models.interessement_periode import InteressementPeriode
from models.interessement_regle import InteressementRegle
from services.interessement import calculer_interessement
from services.export_interessement import export_interessement_xlsx

rh_bp = Blueprint("rh", __name__)


def rh_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "rh":
            flash("Accès réservé aux gestionnaires RH.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

@rh_bp.route("/dashboard")
@rh_required
def dashboard():
    salaries = User.query.filter_by(actif=True).order_by(User.nom).all()
    param = get_parametrage_actif()

    salaries_data = []
    for s in salaries:
        solde_info = calculer_solde(s.id)
        conges_en_cours = Conge.query.filter(
            Conge.user_id == s.id,
            Conge.statut == "valide",
            Conge.date_debut <= datetime.today().date(),
            Conge.date_fin >= datetime.today().date(),
        ).count()
        salaries_data.append({
            "user": s,
            "solde": solde_info,
            "conges_en_cours": conges_en_cours,
        })

    # Données pour les graphiques (solde restant par salarié)
    chart_labels = []
    chart_soldes_restants = []
    for item in salaries_data:
        user = item["user"]
        solde = item["solde"]
        chart_labels.append(f"{user.prenom} {user.nom}")
        chart_soldes_restants.append(solde.get("solde_restant", 0))

    # Données pour le calendrier (tous les congés de l'exercice actif)
    calendar_events = []
    conges_exercice_rows = []
    if param:
        conges_exercice = Conge.query.filter(
            Conge.statut == "valide",
            Conge.date_debut <= param.fin_exercice,
            Conge.date_fin >= param.debut_exercice,
        ).all()
        for c in conges_exercice:
            if c.utilisateur is None:
                continue
            label = f"{c.date_debut.strftime('%d/%m/%Y')} → {c.date_fin.strftime('%d/%m/%Y')}"
            calendar_events.append({
                "start": c.date_debut.isoformat(),
                "end": c.date_fin.isoformat(),
                "user": f"{c.utilisateur.prenom} {c.utilisateur.nom}",
                "type_conge": c.type_conge,
            })
            conges_exercice_rows.append({
                "salarie": f"{c.utilisateur.prenom} {c.utilisateur.nom}",
                "label": label,
                "jours": c.nb_jours_ouvrables or 0,
                "type": c.type_conge,
            })

    # Demandes en attente de validation RH (niveau 2, après validation responsable)
    demandes_attente = (
        Conge.query.filter_by(statut="en_attente_rh")
        .order_by(Conge.cree_le.asc())
        .all()
    )

    # Salariés inactifs (pour le tableau en dessous)
    salaries_inactifs = User.query.filter_by(actif=False).order_by(User.nom).all()
    salaries_data_inactifs = []
    for s in salaries_inactifs:
        solde_info = calculer_solde(s.id)
        salaries_data_inactifs.append({"user": s, "solde": solde_info})

    # Stats
    total_salaries = len(salaries)
    total_en_conge = sum(1 for s in salaries_data if s["conges_en_cours"] > 0)

    today = date.today()
    compta_31_03 = None
    compta_30_09 = None
    if param:
        year = param.fin_exercice.year
        compta_31_03 = date(year, 3, 31)
        compta_30_09 = date(year, 9, 30)

    return render_template(
        "rh/dashboard.html",
        salaries_data=salaries_data,
        salaries_data_inactifs=salaries_data_inactifs,
        total_salaries=total_salaries,
        total_en_conge=total_en_conge,
        parametrage=param,
        chart_labels=chart_labels,
        chart_soldes_restants=chart_soldes_restants,
        calendar_events=calendar_events,
        conges_exercice_rows=conges_exercice_rows,
        demandes_attente=demandes_attente,
        today=today,
        compta_31_03=compta_31_03,
        compta_30_09=compta_30_09,
    )

@rh_bp.route("/salarie/<int:user_id>")
@rh_required
def salarie_detail(user_id):
    user = User.query.get_or_404(user_id)
    solde_info = calculer_solde(user.id)
    param = get_parametrage_actif()

    conges = Conge.query.filter_by(user_id=user.id).order_by(Conge.date_debut.desc()).all()

    return render_template(
        "rh/salarie_detail.html",
        salarie=user,
        solde=solde_info,
        conges=conges,
        parametrage=param,
    )

@rh_bp.route("/salarie/<int:user_id>/conge/ajouter", methods=["GET", "POST"])
@rh_required
def ajouter_conge(user_id):
    user = User.query.get_or_404(user_id)
    solde_info = calculer_solde(user.id)
    from services.conges_exceptionnels import (
        get_types_exceptionnels,
        parse_code,
        get_type_exceptionnel,
        verifier_plafond,
    )
    types_exceptionnels = get_types_exceptionnels(actifs_only=True)

    if request.method == "POST":
        try:
            date_debut = datetime.strptime(request.form["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(request.form["date_fin"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            flash("Dates invalides.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        if date_fin < date_debut:
            flash("La date de fin doit être postérieure à la date de début.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        type_conge = request.form.get("type_conge", "CP")
        exc_code = parse_code(type_conge)
        exc_type = None

        types_standards = {"CP", "Anciennete", "RTT", "Sans solde", "Maladie"}
        if type_conge not in types_standards and not exc_code:
            flash("Merci de sélectionner un type de congé valide.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        if exc_code:
            exc_type = get_type_exceptionnel(exc_code)
            if not exc_type or not exc_type.actif:
                flash("Type de congé exceptionnel invalide.", "error")
                return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la période sélectionnée.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        chevauchement = detecter_chevauchement(user.id, date_debut, date_fin)
        if chevauchement:
            flash(
                f"Chevauchement détecté avec le congé du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
                f"au {chevauchement.date_fin.strftime('%d/%m/%Y')}.",
                "error",
            )
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        nb_heures_rtt = None
        nb_heures_exceptionnelles = None

        if type_conge in ("CP", "Anciennete"):
            if not verifier_solde_suffisant(user.id, nb_jours):
                flash(
                    f"Solde CP insuffisant. {solde_info['solde_restant']} jour(s) restant(s), "
                    f"{nb_jours} jour(s) demandé(s).",
                    "error",
                )
                return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)
        elif type_conge == "RTT":
            try:
                nb_heures_rtt_val = int(request.form.get("nb_heures_rtt", "0"))
            except ValueError:
                nb_heures_rtt_val = 0
            if nb_heures_rtt_val <= 0:
                flash("Merci de saisir un nombre d'heures RTT valide (>= 1).", "error")
                return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

            if not verifier_solde_rtt_suffisant(user.id, nb_heures_rtt_val):
                solde_rtt = solde_info.get("rtt_solde_restant", 0)
                flash(
                    f"Solde RTT insuffisant. {solde_rtt} heure(s) restant(s), "
                    f"{nb_heures_rtt_val} heure(s) demandé(s).",
                    "error",
                )
                return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

            nb_heures_rtt = nb_heures_rtt_val
        elif exc_code and exc_type:
            nb_heures_exceptionnelles = None
            if exc_type.unite == "heures":
                try:
                    nb_heures_exceptionnelles = int(request.form.get("nb_heures_exceptionnelles", "0"))
                except ValueError:
                    nb_heures_exceptionnelles = 0
                if nb_heures_exceptionnelles <= 0:
                    flash("Merci de saisir un nombre d'heures valide.", "error")
                    return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)
                quantite = nb_heures_exceptionnelles
            else:
                quantite = nb_jours

            if not verifier_plafond(user.id, exc_type, quantite):
                flash(f"Plafond dépassé pour le congé exceptionnel « {exc_type.libelle} ».", "error")
                return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        conge = Conge(
            user_id=user.id,
            date_debut=date_debut,
            date_fin=date_fin,
            nb_jours_ouvrables=nb_jours,
            type_conge=type_conge,
            commentaire=commentaire,
            statut="valide",
            valide_par_id=current_user.id,
            valide_le=datetime.now(timezone.utc),
            nb_heures_rtt=nb_heures_rtt,
            nb_heures_exceptionnelles=nb_heures_exceptionnelles if exc_code else None,
        )
        db.session.add(conge)
        db.session.commit()

        flash(f"Congé ajouté : {nb_jours} jour(s) ouvrable(s).", "success")
        return redirect(url_for("rh.salarie_detail", user_id=user.id))

    return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

@rh_bp.route("/conge/<int:conge_id>/modifier", methods=["GET", "POST"])
@rh_required
def modifier_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    user = conge.utilisateur
    solde_info = calculer_solde(user.id)
    from services.conges_exceptionnels import (
        get_types_exceptionnels,
        parse_code,
        get_type_exceptionnel,
        verifier_plafond,
    )
    types_exceptionnels = get_types_exceptionnels(actifs_only=True)

    if request.method == "POST":
        try:
            date_debut = datetime.strptime(request.form["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(request.form["date_fin"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            flash("Dates invalides.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        if date_fin < date_debut:
            flash("La date de fin doit être postérieure à la date de début.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        type_conge = request.form.get("type_conge", conge.type_conge)
        exc_code = parse_code(type_conge)
        exc_type = None
        if exc_code:
            exc_type = get_type_exceptionnel(exc_code)
            if not exc_type or not exc_type.actif:
                flash("Type de congé exceptionnel invalide.", "error")
                return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la période sélectionnée.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        chevauchement = detecter_chevauchement(user.id, date_debut, date_fin, conge_id_exclu=conge.id)
        if chevauchement:
            flash(
                f"Chevauchement détecté avec le congé du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
                f"au {chevauchement.date_fin.strftime('%d/%m/%Y')}.",
                "error",
            )
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        nb_heures_rtt = None
        nb_heures_exceptionnelles = None

        if type_conge in ("CP", "Anciennete"):
            if not verifier_solde_suffisant(user.id, nb_jours, conge_id_exclu=conge.id):
                flash("Solde CP insuffisant pour cette modification.", "error")
                return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)
        elif type_conge == "RTT":
            try:
                nb_heures_rtt_val = int(request.form.get("nb_heures_rtt", str(conge.nb_heures_rtt or 0)))
            except ValueError:
                nb_heures_rtt_val = 0
            if nb_heures_rtt_val <= 0:
                flash("Merci de saisir un nombre d'heures RTT valide (>= 1).", "error")
                return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

            if not verifier_solde_rtt_suffisant(user.id, nb_heures_rtt_val, conge_id_exclu=conge.id):
                solde_rtt = solde_info.get("rtt_solde_restant", 0)
                flash(
                    f"Solde RTT insuffisant pour cette modification. {solde_rtt} heure(s) restant(s), "
                    f"{nb_heures_rtt_val} heure(s) demandé(s).",
                    "error",
                )
                return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

            nb_heures_rtt = nb_heures_rtt_val
        elif exc_code and exc_type:
            if exc_type.unite == "heures":
                try:
                    nb_heures_exceptionnelles = int(request.form.get("nb_heures_exceptionnelles", str(conge.nb_heures_exceptionnelles or 0)))
                except ValueError:
                    nb_heures_exceptionnelles = 0
                if nb_heures_exceptionnelles <= 0:
                    flash("Merci de saisir un nombre d'heures valide.", "error")
                    return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)
                quantite = nb_heures_exceptionnelles
            else:
                quantite = nb_jours

            if not verifier_plafond(user.id, exc_type, quantite, conge_id_exclu=conge.id):
                flash(f"Plafond dépassé pour le congé exceptionnel « {exc_type.libelle} ».", "error")
                return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

        conge.date_debut = date_debut
        conge.date_fin = date_fin
        conge.nb_jours_ouvrables = nb_jours
        conge.type_conge = type_conge
        conge.commentaire = commentaire
        conge.nb_heures_rtt = nb_heures_rtt
        conge.nb_heures_exceptionnelles = nb_heures_exceptionnelles
        db.session.commit()

        flash("Congé modifié avec succès.", "success")
        return redirect(url_for("rh.salarie_detail", user_id=user.id))

    return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info, types_exceptionnels=types_exceptionnels)

@rh_bp.route("/conge/<int:conge_id>/supprimer", methods=["POST"])
@rh_required
def supprimer_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    user_id = conge.user_id
    db.session.delete(conge)
    db.session.commit()
    flash("Congé supprimé.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=user_id))

@rh_bp.route("/conge/<int:conge_id>/valider", methods=["POST"])
@rh_required
def valider_conge(conge_id):
    """Valider une demande de congé en attente."""
    conge = Conge.query.get_or_404(conge_id)
    if conge.statut != "en_attente_rh":
        flash("Ce congé n'est pas en attente de validation RH.", "warning")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    if conge.type_conge in ("CP", "Anciennete"):
        if not verifier_solde_suffisant(conge.user_id, conge.nb_jours_ouvrables):
            flash("Solde CP insuffisant pour valider ce congé.", "error")
            return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))
    elif conge.type_conge == "RTT":
        if not verifier_solde_rtt_suffisant(conge.user_id, conge.nb_heures_rtt or 0):
            flash("Solde RTT insuffisant pour valider ce congé.", "error")
            return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    conge.statut = "valide"
    conge.valide_par_id = current_user.id
    conge.valide_le = datetime.now(timezone.utc)
    conge.motif_refus = None
    db.session.commit()

    notifier_conge_valide(conge)
    db.session.commit()

    flash("Demande de congé validée.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

@rh_bp.route("/conge/<int:conge_id>/refuser", methods=["GET", "POST"])
@rh_required
def refuser_conge(conge_id):
    """Refuser une demande de congé avec motif obligatoire (validation niveau 2 - RH)."""
    conge = Conge.query.get_or_404(conge_id)
    if conge.statut != "en_attente_rh":
        flash("Ce congé n'est pas en attente de validation RH.", "warning")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    if request.method == "POST":
        motif = request.form.get("motif_refus", "").strip()
        if not motif:
            flash("Le motif de refus est obligatoire.", "error")
            return render_template("rh/refuser_conge.html", conge=conge)

        conge.statut = "refuse"
        conge.valide_par_id = current_user.id
        conge.valide_le = datetime.now(timezone.utc)
        conge.motif_refus = motif
        db.session.commit()

        notifier_conge_refuse(conge, motif)
        db.session.commit()

        flash("Demande de congé refusée.", "success")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    return render_template("rh/refuser_conge.html", conge=conge)

@rh_bp.route("/parametrage", methods=["GET", "POST"])
@rh_required
def parametrage():
    param = get_parametrage_actif()
    jours_feries_list = []
    if param:
        annee_debut = param.debut_exercice.year
        annee_fin = param.fin_exercice.year
        jours_feries_list = JourFerie.query.filter(
            JourFerie.annee.in_([annee_debut, annee_fin])
        ).order_by(JourFerie.date_ferie).all()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_parametrage":
            try:
                debut = datetime.strptime(request.form["debut_exercice"], "%Y-%m-%d").date()
                fin = datetime.strptime(request.form["fin_exercice"], "%Y-%m-%d").date()
                jours_defaut = int(request.form["jours_conges_defaut"])
                rtt_heures_defaut = int(request.form['rtt_heures_defaut'])
                rtt_calc_mode = (request.form.get('rtt_calc_mode') or 'fixe').strip() or 'fixe'
                if rtt_calc_mode not in ('fixe', 'heures'):
                    rtt_calc_mode = 'fixe'
                rtt_heures_reference = int((request.form.get('rtt_heures_reference') or '0').strip() or '0')
                rtt_coef_surplus = float((request.form.get('rtt_coef_surplus') or '0').replace(',', '.').strip() or '0')
            except (ValueError, KeyError):
                flash("Données invalides.", "error")
                return redirect(url_for("rh.parametrage"))

            if param is None:
                param = ParametrageAnnuel(
                    debut_exercice=debut,
                    fin_exercice=fin,
                    jours_conges_defaut=jours_defaut,
                    rtt_heures_defaut=rtt_heures_defaut,
                    rtt_calc_mode=rtt_calc_mode,
                    rtt_heures_reference=rtt_heures_reference,
                    rtt_coef_surplus=rtt_coef_surplus,
                    actif=True,
                )
                db.session.add(param)
            else:
                param.debut_exercice = debut
                param.fin_exercice = fin
                param.jours_conges_defaut = jours_defaut
                param.rtt_heures_defaut = rtt_heures_defaut
                param.rtt_calc_mode = rtt_calc_mode
                param.rtt_heures_reference = rtt_heures_reference
                param.rtt_coef_surplus = rtt_coef_surplus

            db.session.commit()
            flash("Paramétrage enregistré.", "success")
            return redirect(url_for("rh.parametrage"))
        elif action == "generer_allocations":
            if not param:
                flash("Aucun paramétrage actif. Configurez d'abord l'exercice.", "error")
                return redirect(url_for("rh.parametrage"))
            generer_allocations_pour_parametrage(param)
            flash("Allocations CP et RTT générées/mises à jour pour tous les salariés actifs.", "success")
            return redirect(url_for("rh.parametrage"))

        elif action == "charger_feries":
            if not param:
                flash(
                    "Avant de charger les jours fériés, merci d'indiquer les dates de début et de fin de l'exercice puis d'enregistrer.",
                    "error",
                )
                return redirect(url_for("rh.parametrage"))

            annees = {param.debut_exercice.year, param.fin_exercice.year}
            count_added = 0
            count_updated = 0

            try:
                for annee in annees:
                    feries = get_jours_feries(annee)
                    for date_f, libelle in feries:
                        existing = JourFerie.query.filter_by(date_ferie=date_f).first()
                        if not existing:
                            jf = JourFerie(date_ferie=date_f, libelle=libelle, annee=annee, auto_genere=True)
                            db.session.add(jf)
                            count_added += 1
                        elif existing.auto_genere:
                            existing.libelle = libelle
                            count_updated += 1

                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Erreur lors du chargement des jours fériés. Consultez les logs serveur.", "error")
                return redirect(url_for("rh.parametrage"))

            if count_added or count_updated:
                msg = []
                if count_added:
                    msg.append(f"{count_added} jour(s) férié(s) ajouté(s)")
                if count_updated:
                    msg.append(f"{count_updated} libellé(s) mis à jour")
                flash(". ".join(msg) + ".", "success")
            return redirect(url_for("rh.parametrage"))

        elif action == "ajouter_ferie":
            try:
                date_f = datetime.strptime(request.form["date_ferie"], "%Y-%m-%d").date()
                libelle = request.form.get("libelle_ferie", "").strip()
                if not libelle:
                    libelle = "Jour férié personnalisé"
            except (ValueError, KeyError):
                flash("Date invalide.", "error")
                return redirect(url_for("rh.parametrage"))

            existing = JourFerie.query.filter_by(date_ferie=date_f).first()
            if existing:
                flash("Ce jour férié existe déjà.", "warning")
            else:
                jf = JourFerie(date_ferie=date_f, libelle=libelle, annee=date_f.year, auto_genere=False)
                db.session.add(jf)
                db.session.commit()
                flash("Jour férié ajouté.", "success")
            return redirect(url_for("rh.parametrage"))

        elif action == "supprimer_ferie":
            ferie_id = request.form.get("ferie_id")
            if ferie_id:
                try:
                    ferie_id_int = int(ferie_id)
                except (ValueError, TypeError):
                    flash("Identifiant invalide.", "error")
                    return redirect(url_for("rh.parametrage"))
                jf = JourFerie.query.get(ferie_id_int)
                if jf:
                    db.session.delete(jf)
                    db.session.commit()
                    flash("Jour férié supprimé.", "success")
            return redirect(url_for("rh.parametrage"))

    return render_template("rh/parametrage.html", parametrage=param, jours_feries=jours_feries_list)

@rh_bp.route("/salarie/<int:user_id>/allocation", methods=["POST"])
@rh_required
def modifier_allocation(user_id):
    user = User.query.get_or_404(user_id)
    param = get_parametrage_actif()
    if not param:
        flash("Aucun paramétrage actif. Configurez d'abord le paramétrage annuel.", "error")
        return redirect(url_for("rh.salarie_detail", user_id=user_id))

    allocation = AllocationConge.query.filter_by(user_id=user_id, parametrage_id=param.id).first()
    if not allocation:
        allocation = AllocationConge(user_id=user_id, parametrage_id=param.id)
        db.session.add(allocation)

    try:
        allocation.jours_alloues = int(request.form.get("jours_alloues", param.jours_conges_defaut))
        allocation.jours_anciennete = int(request.form.get("jours_anciennete", 0))
        allocation.jours_report = int(request.form.get("jours_report", 0))
        allocation.rtt_heures_allouees = int(request.form.get("rtt_heures_allouees", param.rtt_heures_defaut))
        allocation.rtt_heures_reportees = int(request.form.get("rtt_heures_reportees", 0))
    except ValueError:
        flash("Valeurs invalides.", "error")
        return redirect(url_for("rh.salarie_detail", user_id=user_id))

    db.session.commit()
    flash("Allocation mise à jour.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=user_id))

@rh_bp.route("/salarie/<int:user_id>/statut", methods=["POST"])
@rh_required
def modifier_statut_salarie(user_id):
    """Modification du statut actif/inactif du salarié."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas modifier votre propre statut.", "error")
        return redirect(url_for("rh.salarie_detail", user_id=user_id))

    actif_str = request.form.get("actif", "off")
    user.actif = actif_str == "on"
    db.session.commit()
    flash("Statut du salarié mis à jour.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=user_id))

@rh_bp.route("/salaries")
@rh_required
def liste_salaries():
    """Liste complète des salariés pour gestion RH."""
    salaries = User.query.order_by(User.nom, User.prenom).all()
    return render_template("rh/salaries.html", salaries=salaries)

@rh_bp.route("/export/equipe/excel")
@rh_required
def export_equipe_excel():
    """Export Excel de tous les congés de l'équipe."""
    param = get_parametrage_actif()
    salaries = User.query.filter_by(actif=True).order_by(User.nom, User.prenom).all()
    users_with_conges = []
    for s in salaries:
        q = Conge.query.filter_by(user_id=s.id).order_by(Conge.date_debut.desc())
        if param:
            q = q.filter(
                Conge.date_debut <= param.fin_exercice,
                Conge.date_fin >= param.debut_exercice,
            )
        conges = q.all()
        users_with_conges.append({"user": s, "conges": conges})
    buffer = export_conges_equipe_excel(users_with_conges)
    filename = f"conges_equipe_{date.today().strftime('%Y%m%d')}.xlsx"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@rh_bp.route("/export/compta")
@rh_required
def export_compta():
    """Export Excel comptable CP/RTT à une date donnée."""
    param = get_parametrage_actif()
    if not param:
        flash("Aucun paramétrage actif. Configurez d'abord l'exercice.", "error")
        return redirect(url_for("rh.dashboard"))

    date_str = (request.args.get("date") or "").strip()
    include_inactifs = (request.args.get("include_inactifs") or "0").strip() == "1"

    as_of = date.today()
    if date_str:
        try:
            as_of = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Date invalide (format attendu : AAAA-MM-JJ).", "error")
            return redirect(url_for("rh.dashboard"))

    buffer = export_compta_cp_rtt_xlsx(param, as_of, include_inactifs=include_inactifs)
    filename = f"export_comptable_cp_rtt_{as_of.strftime('%Y%m%d')}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@rh_bp.route("/salarie/<int:user_id>/export/excel")
@rh_required
def export_salarie_excel(user_id):
    """Export Excel des congés d'un salarié."""
    user = User.query.get_or_404(user_id)
    conges = Conge.query.filter_by(user_id=user.id).order_by(Conge.date_debut.desc()).all()
    buffer = export_conges_excel(conges, user.nom, user.prenom)
    filename = f"conges_{user.prenom}_{user.nom}_{date.today().strftime('%Y%m%d')}.xlsx"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@rh_bp.route("/salarie/<int:user_id>/export/pdf")
@rh_required
def export_salarie_pdf(user_id):
    """Export PDF des congés d'un salarié."""
    user = User.query.get_or_404(user_id)
    conges = Conge.query.filter_by(user_id=user.id).order_by(Conge.date_debut.desc()).all()
    solde_info = calculer_solde(user.id)
    buffer = export_conges_pdf(conges, solde_info, user.nom, user.prenom)
    filename = f"conges_{user.prenom}_{user.nom}_{date.today().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

@rh_bp.route("/salarie/nouveau", methods=["GET", "POST"])
@rh_required
def creer_salarie():
    """Création d'un nouveau salarié côté RH."""
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        identifiant = request.form.get("identifiant", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")
        role = request.form.get("role", "salarie").strip() or "salarie"
        date_embauche_str = request.form.get("date_embauche", "").strip()

        if not nom or not prenom or not identifiant or not mot_de_passe:
            flash("Nom, prénom, identifiant et mot de passe sont obligatoires.", "error")
            return render_template("rh/salarie_form.html", salarie=None, mode="create")

        existing = User.query.filter_by(identifiant=identifiant).first()
        if existing:
            flash("Un utilisateur avec cet identifiant existe déjà.", "error")
            return render_template("rh/salarie_form.html", salarie=None, mode="create")

        date_embauche = None
        if date_embauche_str:
            try:
                date_embauche = datetime.strptime(date_embauche_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Date d'embauche invalide.", "error")
                return render_template("rh/salarie_form.html", salarie=None, mode="create")

        r_id = request.form.get("responsable_id", "").strip()
        user = User(
            nom=nom,
            prenom=prenom,
            identifiant=identifiant,
            mot_de_passe_hash=hash_password(mot_de_passe),
            role=role,
            actif=True,
            date_embauche=date_embauche,
            responsable_id=int(r_id) if r_id else None,
        )
        db.session.add(user)
        db.session.commit()

        flash("Salarié créé avec succès.", "success")
        return redirect(url_for("rh.liste_salaries"))

    responsables = User.query.filter(User.role.in_(["responsable", "rh"]), User.actif == True).order_by(User.nom, User.prenom).all()
    return render_template("rh/salarie_form.html", salarie=None, mode="create", responsables=responsables)


@rh_bp.route("/salarie/<int:user_id>/modifier", methods=["GET", "POST"])
@rh_required
def modifier_salarie(user_id):
    """Modification d'un salarié existant côté RH."""
    user = User.query.get_or_404(user_id)
    responsables = User.query.filter(User.role.in_(["responsable", "rh"]), User.actif == True).order_by(User.nom, User.prenom).all()

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        identifiant = request.form.get("identifiant", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")
        role = request.form.get("role", "salarie").strip() or "salarie"
        date_embauche_str = request.form.get("date_embauche", "").strip()
        actif_str = request.form.get("actif", "off")

        if not nom or not prenom or not identifiant:
            flash("Nom, prénom et identifiant sont obligatoires.", "error")
            return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)

        existing = User.query.filter(
            User.identifiant == identifiant,
            User.id != user.id,
        ).first()
        if existing:
            flash("Un autre utilisateur utilise déjà cet identifiant.", "error")
            return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)

        date_embauche = None
        if date_embauche_str:
            try:
                date_embauche = datetime.strptime(date_embauche_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Date d'embauche invalide.", "error")
                return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)

        user.nom = nom
        user.prenom = prenom
        user.identifiant = identifiant
        user.role = role
        user.date_embauche = date_embauche
        user.actif = actif_str == "on"
        if mot_de_passe:
            user.mot_de_passe_hash = hash_password(mot_de_passe)
        r_id = request.form.get("responsable_id", "").strip()
        user.responsable_id = int(r_id) if r_id else None
        db.session.commit()
        flash("Salarié mis à jour.", "success")
        return redirect(url_for("rh.liste_salaries"))

    return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)



@rh_bp.route("/types-exceptionnels", methods=["GET", "POST"])
@rh_required
def types_exceptionnels():
    from services.conges_exceptionnels import get_types_exceptionnels

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            code = (request.form.get("code") or "").strip().upper()
            libelle = (request.form.get("libelle") or "").strip()
            unite = (request.form.get("unite") or "jours").strip() or "jours"
            plafond_str = (request.form.get("plafond_annuel") or "").strip()
            plafond = None
            if plafond_str:
                try:
                    plafond = int(plafond_str)
                except ValueError:
                    plafond = None

            if not code or not libelle or unite not in ("jours", "heures"):
                flash("Données invalides.", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            existing = CongeExceptionnelType.query.filter_by(code=code).first()
            if existing:
                flash("Un type avec ce code existe déjà.", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            t = CongeExceptionnelType(code=code, libelle=libelle, unite=unite, plafond_annuel=plafond, actif=True)
            db.session.add(t)
            db.session.commit()
            flash("Type ajouté.", "success")
            return redirect(url_for("rh.types_exceptionnels"))

        if action == "update":
            try:
                type_id = int(request.form.get("type_id") or "0")
            except ValueError:
                type_id = 0

            t = CongeExceptionnelType.query.get(type_id)
            if not t:
                flash("Type introuvable.", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            libelle = (request.form.get("libelle") or "").strip()
            unite = (request.form.get("unite") or "jours").strip() or "jours"
            plafond_str = (request.form.get("plafond_annuel") or "").strip()
            plafond = None
            if plafond_str:
                try:
                    plafond = int(plafond_str)
                except ValueError:
                    plafond = None

            if not libelle or unite not in ("jours", "heures"):
                flash("Données invalides.", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            t.libelle = libelle
            t.unite = unite
            t.plafond_annuel = plafond
            db.session.commit()
            flash("Type mis à jour.", "success")
            return redirect(url_for("rh.types_exceptionnels"))

        if action == "toggle":
            try:
                type_id = int(request.form.get("type_id") or "0")
            except ValueError:
                type_id = 0

            t = CongeExceptionnelType.query.get(type_id)
            if not t:
                flash("Type introuvable.", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            t.actif = not bool(t.actif)
            db.session.commit()
            flash("Statut mis à jour.", "success")
            return redirect(url_for("rh.types_exceptionnels"))

    types = get_types_exceptionnels(actifs_only=False)
    return render_template("rh/types_exceptionnels.html", types=types)




@rh_bp.route("/heures", methods=["GET", "POST"])
@rh_required
def heures():
    """Saisie mensuelle des heures (trajet/travaillées/payées) et recalcul RTT optionnel."""
    from services.solde import get_parametrage_actif

    param = get_parametrage_actif()
    if not param:
        flash("Aucun paramétrage actif. Configurez d'abord l'exercice.", "error")
        return redirect(url_for("rh.parametrage"))

    try:
        annee = int(request.values.get("annee") or date.today().year)
    except ValueError:
        annee = date.today().year
    try:
        mois = int(request.values.get("mois") or date.today().month)
    except ValueError:
        mois = date.today().month
    if mois < 1 or mois > 12:
        mois = date.today().month

    salaries = User.query.filter_by(actif=True).order_by(User.nom).all()

    if request.method == "POST":
        action = (request.form.get("action") or "save").strip() or "save"
        saved_user_ids = []

        for s in salaries:
            prefix = f"u{s.id}_"
            hp_str = (request.form.get(prefix + "heures_payees") or "").strip()
            ht_str = (request.form.get(prefix + "heures_trajet") or "").strip()
            hw_str = (request.form.get(prefix + "heures_travaillees") or "").strip()

            # Si rien saisi pour ce salarié, on ignore.
            if not (hp_str or ht_str or hw_str):
                continue

            try:
                heures_payees = int(hp_str or 0)
                heures_trajet = int(ht_str or 0)
                heures_travaillees = int(hw_str or 0)
            except ValueError:
                flash(f"Valeurs invalides pour {s.prenom} {s.nom}.", "error")
                return redirect(url_for("rh.heures", annee=annee, mois=mois))

            row = HeuresPayees.query.filter_by(user_id=s.id, annee=annee, mois=mois).first()
            if not row:
                row = HeuresPayees(user_id=s.id, annee=annee, mois=mois)
                db.session.add(row)

            row.heures_payees = max(0, heures_payees)
            row.heures_trajet = max(0, heures_trajet)
            row.heures_travaillees = max(0, heures_travaillees)
            row.source = "manuel"
            row.saisi_par_id = current_user.id
            saved_user_ids.append(s.id)

        db.session.commit()

        if saved_user_ids:
            flash("Heures enregistrées.", "success")
        else:
            flash("Aucune donnée à enregistrer.", "info")

        if action == "save_recalc":
            try:
                res = maj_rtt_allocations_depuis_heures(param, user_ids=saved_user_ids)
                if res:
                    flash(f"RTT recalculées pour {len(res)} salarié(s).", "success")
                else:
                    flash("RTT non recalculées (mode RTT = fixe ou paramétrage manquant).", "warning")
            except Exception:
                db.session.rollback()
                flash("Erreur lors du recalcul RTT. Consultez les logs serveur.", "error")

        return redirect(url_for("rh.heures", annee=annee, mois=mois))

    existing = HeuresPayees.query.filter_by(annee=annee, mois=mois).all()
    by_user = {e.user_id: e for e in existing}

    return render_template(
        "rh/heures.html",
        parametrage=param,
        annee=annee,
        mois=mois,
        salaries=salaries,
        heures_by_user=by_user,
    )


@rh_bp.route("/interessement", methods=["GET", "POST"])
@rh_required
def interessement():
    """Gestion des périodes et règles d’intéressement."""
    periodes = InteressementPeriode.query.order_by(InteressementPeriode.date_debut.desc()).all()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "create_periode":
            libelle = (request.form.get("libelle") or "").strip()
            date_debut_str = (request.form.get("date_debut") or "").strip()
            date_fin_str = (request.form.get("date_fin") or "").strip()
            base_points_str = (request.form.get("base_points") or "100").strip()
            plancher_str = (request.form.get("plancher_points") or "0").strip()

            if not libelle or not date_debut_str or not date_fin_str:
                flash("Libellé, date de début et date de fin sont obligatoires.", "error")
                return redirect(url_for("rh.interessement"))

            try:
                d_debut = datetime.strptime(date_debut_str, "%Y-%m-%d").date()
                d_fin = datetime.strptime(date_fin_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Format de date invalide.", "error")
                return redirect(url_for("rh.interessement"))

            if d_fin < d_debut:
                flash("La date de fin doit être postérieure à la date de début.", "error")
                return redirect(url_for("rh.interessement"))

            try:
                base_points = int(base_points_str)
                plancher_points = int(plancher_str)
            except ValueError:
                flash("Base et plancher doivent être des entiers.", "error")
                return redirect(url_for("rh.interessement"))

            p = InteressementPeriode(
                libelle=libelle,
                date_debut=d_debut,
                date_fin=d_fin,
                base_points=base_points,
                plancher_points=plancher_points,
                actif=False,
            )
            db.session.add(p)
            db.session.commit()
            flash("Période créée.", "success")
            return redirect(url_for("rh.interessement"))

        if action == "toggle_periode":
            try:
                pid = int(request.form.get("periode_id") or "0")
            except ValueError:
                pid = 0
            p = InteressementPeriode.query.get(pid)
            if p:
                p.actif = not p.actif
                db.session.commit()
                flash("Statut mis à jour.", "success")
            return redirect(url_for("rh.interessement"))

        if action == "delete_periode":
            try:
                pid = int(request.form.get("periode_id") or "0")
            except ValueError:
                pid = 0
            p = InteressementPeriode.query.get(pid)
            if p:
                db.session.delete(p)
                db.session.commit()
                flash("Période supprimée.", "success")
            return redirect(url_for("rh.interessement"))

    return render_template("rh/interessement.html", periodes=periodes)


@rh_bp.route("/interessement/<int:periode_id>/regles", methods=["GET", "POST"])
@rh_required
def interessement_regles(periode_id):
    """Gestion des règles de pondération pour une période d’intéressement."""
    periode = InteressementPeriode.query.get_or_404(periode_id)
    regles = InteressementRegle.query.filter_by(periode_id=periode.id).order_by(InteressementRegle.type_absence).all()

    types_conge_disponibles = ["CP", "Anciennete", "RTT", "Sans solde", "Maladie"]
    from services.conges_exceptionnels import get_types_exceptionnels
    for t in get_types_exceptionnels(actifs_only=False):
        types_conge_disponibles.append(f"EXC:{t.code}")

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "add_regle":
            type_absence = (request.form.get("type_absence") or "").strip()
            ppj_str = (request.form.get("points_par_jour") or "0").strip()

            if not type_absence:
                flash("Type d’absence obligatoire.", "error")
                return redirect(url_for("rh.interessement_regles", periode_id=periode.id))

            existing = InteressementRegle.query.filter_by(periode_id=periode.id, type_absence=type_absence).first()
            if existing:
                flash("Une règle existe déjà pour ce type d’absence.", "error")
                return redirect(url_for("rh.interessement_regles", periode_id=periode.id))

            try:
                ppj = float(ppj_str)
            except ValueError:
                ppj = 0.0

            r = InteressementRegle(periode_id=periode.id, type_absence=type_absence, points_par_jour=ppj)
            db.session.add(r)
            db.session.commit()
            flash("Règle ajoutée.", "success")
            return redirect(url_for("rh.interessement_regles", periode_id=periode.id))

        if action == "update_regles":
            for r in regles:
                ppj_str = (request.form.get(f"ppj_{r.id}") or "").strip()
                if ppj_str:
                    try:
                        r.points_par_jour = float(ppj_str)
                    except ValueError:
                        pass
            db.session.commit()
            flash("Règles mises à jour.", "success")
            return redirect(url_for("rh.interessement_regles", periode_id=periode.id))

        if action == "delete_regle":
            try:
                rid = int(request.form.get("regle_id") or "0")
            except ValueError:
                rid = 0
            r = InteressementRegle.query.get(rid)
            if r and r.periode_id == periode.id:
                db.session.delete(r)
                db.session.commit()
                flash("Règle supprimée.", "success")
            return redirect(url_for("rh.interessement_regles", periode_id=periode.id))

    return render_template(
        "rh/interessement_regles.html",
        periode=periode,
        regles=regles,
        types_conge_disponibles=types_conge_disponibles,
    )


@rh_bp.route("/interessement/<int:periode_id>/export")
@rh_required
def export_interessement(periode_id):
    """Export Excel du calcul d’intéressement pour une période."""
    periode = InteressementPeriode.query.get_or_404(periode_id)
    include_inactifs = (request.args.get("include_inactifs") or "0").strip() == "1"

    try:
        buffer = export_interessement_xlsx(periode, include_inactifs=include_inactifs)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("rh.interessement"))

    filename = f"interessement_{periode.libelle.replace(' ', '_')}_{periode.date_debut}_{periode.date_fin}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

