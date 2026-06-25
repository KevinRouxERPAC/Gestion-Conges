from datetime import datetime, timezone, date
from functools import wraps

import bcrypt
from services.auth_utils import hash_password, normaliser_role, valider_mot_de_passe
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user

from models import db
from models.conge import Conge
from models.jour_ferie import JourFerie
from models.parametrage import ParametrageAnnuel, AllocationConge
from models.user import User
from models.conge_exceptionnel_type import CongeExceptionnelType
from models.heures_hebdo import HeuresHebdo
from services.solde import (
    calculer_solde,
    get_parametrage_actif,
    generer_allocations_pour_parametrage,
    salaries_a_risque,
    cloturer_exercice_et_reporter,
)
from services.jours_feries import get_jours_feries
from services.format_heures import format_heures_min, format_jours
from services.notifications import notifier_conge_valide, notifier_conge_refuse
from services.export import export_conges_excel, export_conges_equipe_excel, export_conges_pdf
from services.export_comptable import export_compta_cp_rtt_xlsx
from services.audit import log_action
from models.audit_log import AuditLog
import json as _json
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
                "demi_journee_debut": c.demi_journee_debut,
                "demi_journee_fin": c.demi_journee_fin,
                "nb_jours": c.nb_jours_ouvrables or 0,
            })
            conges_exercice_rows.append({
                "salarie": f"{c.utilisateur.prenom} {c.utilisateur.nom}",
                "label": label,
                "jours": c.nb_jours_ouvrables or 0,
                "type": c.type_conge,
                "demi_journee_debut": c.demi_journee_debut,
                "demi_journee_fin": c.demi_journee_fin,
            })

    # Demandes en attente de validation RH (niveau 2, après validation responsable)
    demandes_attente = (
        Conge.query.filter_by(statut="en_attente_rh")
        .order_by(Conge.cree_le.asc())
        .all()
    )

    # Pour chaque demande, prépare la liste des congés chevauchants (autres salariés)
    # afin que le RH visualise les conflits potentiels avant de valider.
    from services.calcul_jours import conges_chevauchant
    conflits_par_conge = {}
    for c in demandes_attente:
        conflits = conges_chevauchant(
            c.date_debut, c.date_fin, exclure_user_id=c.user_id
        )
        conflits_par_conge[c.id] = [
            {
                "salarie": (
                    f"{cc.utilisateur.prenom} {cc.utilisateur.nom}"
                    if cc.utilisateur else "?"
                ),
                "periode": f"{cc.date_debut.strftime('%d/%m')} → {cc.date_fin.strftime('%d/%m')}",
                "type_conge": cc.type_conge,
                "statut": cc.statut,
            }
            for cc in conflits
        ]

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

    # Soldes "à risque" : salariés qui n'ont pas posé leurs CP à l'approche
    # de la fin d'exercice (seuil : 10j restants à moins de 90j de la fin).
    a_risque = salaries_a_risque(jours_min_restants=10, jours_avant_fin=90)

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
        conflits_par_conge=conflits_par_conge,
        a_risque=a_risque,
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

def _traiter_justificatif_conge(conge):
    """Enregistre le fichier uploadé si présent ; vérifie l'obligation selon le type."""
    from services.justificatifs import (
        enregistrer_justificatif,
        verifier_justificatif_obligatoire,
    )

    fichier = request.files.get("justificatif")
    if fichier and fichier.filename:
        err = enregistrer_justificatif(conge, fichier, current_user)
        if err:
            return err
    return verifier_justificatif_obligatoire(conge)


@rh_bp.route("/salarie/<int:user_id>/conge/ajouter", methods=["GET", "POST"])
@rh_required
def ajouter_conge(user_id):
    user = User.query.get_or_404(user_id)
    solde_info = calculer_solde(user.id)
    from services.conges_exceptionnels import get_types_exceptionnels
    types_exceptionnels = get_types_exceptionnels(actifs_only=True)

    if request.method == "POST":
        from services.creer_conge import construire_conge, MODE_RH
        result = construire_conge(
            user,
            request.form,
            mode=MODE_RH,
            statut_initial="valide",
            valide_par=current_user,
        )

        for category, message in result.flashes:
            flash(message, category)

        if not result.success:
            return render_template(
                "rh/ajouter_conge.html",
                salarie=user,
                solde=solde_info,
                types_exceptionnels=types_exceptionnels,
            )

        db.session.add(result.conge)
        db.session.flush()

        err_j = _traiter_justificatif_conge(result.conge)
        if err_j:
            db.session.rollback()
            flash(err_j, "error")
            return render_template(
                "rh/ajouter_conge.html",
                salarie=user,
                solde=solde_info,
                types_exceptionnels=types_exceptionnels,
            )

        db.session.commit()

        # Création directe RH = validation immédiate : on notifie le salarié (B9).
        notifier_conge_valide(result.conge)
        db.session.commit()

        flash(
            f"Congé ajouté : {format_jours(result.conge.nb_jours_ouvrables)} jour(s) ouvrable(s).",
            "success",
        )
        return redirect(url_for("rh.salarie_detail", user_id=user.id))

    return render_template(
        "rh/ajouter_conge.html",
        salarie=user,
        solde=solde_info,
        types_exceptionnels=types_exceptionnels,
    )

@rh_bp.route("/conge/<int:conge_id>/modifier", methods=["GET", "POST"])
@rh_required
def modifier_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    user = conge.utilisateur
    solde_info = calculer_solde(user.id)
    from services.conges_exceptionnels import get_types_exceptionnels
    types_exceptionnels = get_types_exceptionnels(actifs_only=True)

    if request.method == "POST":
        from services.creer_conge import construire_conge, MODE_RH
        # On capture l'état "avant" pour l'audit et la notification de modification.
        avant = {
            "type_conge": conge.type_conge,
            "date_debut": str(conge.date_debut),
            "date_fin": str(conge.date_fin),
            "nb_jours_ouvrables": conge.nb_jours_ouvrables,
            "nb_heures_rtt": conge.nb_heures_rtt,
        }
        ancien_type = conge.type_conge
        result = construire_conge(
            user,
            request.form,
            mode=MODE_RH,
            statut_initial=conge.statut,
            conge_existant=conge,
        )

        for category, message in result.flashes:
            flash(message, category)

        if not result.success:
            return render_template(
                "rh/modifier_conge.html",
                conge=conge,
                salarie=user,
                solde=solde_info,
                types_exceptionnels=types_exceptionnels,
            )

        apres = {
            "type_conge": conge.type_conge,
            "date_debut": str(conge.date_debut),
            "date_fin": str(conge.date_fin),
            "nb_jours_ouvrables": conge.nb_jours_ouvrables,
            "nb_heures_rtt": conge.nb_heures_rtt,
        }
        a_change = avant != apres
        log_action(
            "conge.modifier",
            cible_type="conge",
            cible_id=conge.id,
            details={"user_id": user.id, "avant": avant, "apres": apres},
        )

        err_j = _traiter_justificatif_conge(conge)
        if err_j:
            db.session.rollback()
            flash(err_j, "error")
            return render_template(
                "rh/modifier_conge.html",
                conge=conge,
                salarie=user,
                solde=solde_info,
                types_exceptionnels=types_exceptionnels,
            )

        db.session.commit()

        # Informe le salarié de la modification (en particulier d'un changement de type).
        if a_change:
            from services.notifications import notifier_conge_modifie
            notifier_conge_modifie(conge, ancien_type=ancien_type)
            db.session.commit()

        flash("Congé modifié avec succès.", "success")
        return redirect(url_for("rh.salarie_detail", user_id=user.id))

    return render_template(
        "rh/modifier_conge.html",
        conge=conge,
        salarie=user,
        solde=solde_info,
        types_exceptionnels=types_exceptionnels,
    )


@rh_bp.route("/conge/<int:conge_id>/justificatif")
@login_required
def telecharger_justificatif(conge_id):
    """Téléchargement protégé : RH ou salarié concerné uniquement."""
    from flask import abort, send_file
    from services.justificatifs import peut_consulter_justificatif, chemin_stockage

    conge = Conge.query.get_or_404(conge_id)
    if not peut_consulter_justificatif(current_user, conge):
        abort(403)

    j = conge.justificatif
    if not j:
        abort(404)

    log_action(
        "justificatif.download",
        cible_type="conge",
        cible_id=conge.id,
        details={"user_id": conge.user_id, "nom_fichier": j.nom_fichier},
    )
    db.session.commit()

    return send_file(
        chemin_stockage(j.nom_stockage),
        mimetype=j.mime_type,
        as_attachment=True,
        download_name=j.nom_fichier,
    )


@rh_bp.route("/conge/<int:conge_id>/justificatif/supprimer", methods=["POST"])
@rh_required
def supprimer_justificatif_route(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    from services.justificatifs import supprimer_justificatif

    err = supprimer_justificatif(conge, current_user)
    if err:
        flash(err, "error")
    else:
        db.session.commit()
        flash("Justificatif supprimé.", "success")
    return redirect(url_for("rh.modifier_conge", conge_id=conge.id))


@rh_bp.route("/conge/<int:conge_id>/supprimer", methods=["POST"])
@rh_required
def supprimer_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    user_id = conge.user_id
    from services.justificatifs import supprimer_justificatif
    supprimer_justificatif(conge, current_user)
    log_action(
        "conge.supprimer",
        cible_type="conge",
        cible_id=conge.id,
        details={
            "user_id": user_id,
            "type_conge": conge.type_conge,
            "nb_jours": conge.nb_jours_ouvrables,
            "periode": f"{conge.date_debut} → {conge.date_fin}",
            "statut": conge.statut,
        },
    )
    db.session.delete(conge)
    db.session.commit()
    flash("Congé supprimé.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=user_id))

def _valider_un_conge_rh(conge):
    """Applique la validation niveau 2 (RH) à un congé. Retourne (ok, message).

    Effectue les contrôles bloquants (plafond exceptionnel), pose le statut,
    écrit l'audit et empile la notification salarié. Ne commit pas : le caller
    décide.
    """
    if conge.statut != "en_attente_rh":
        return False, f"Conge #{conge.id} : statut {conge.statut}, ignoré."

    from services.conges_exceptionnels import parse_code, get_type_exceptionnel, verifier_plafond
    from services.justificatifs import verifier_justificatif_obligatoire

    err_j = verifier_justificatif_obligatoire(conge)
    if err_j:
        return False, err_j

    exc_code = parse_code(conge.type_conge)
    if exc_code:
        exc_type = get_type_exceptionnel(exc_code)
        if exc_type and exc_type.plafond_annuel is not None:
            quantite = (
                conge.nb_heures_exceptionnelles or 0
                if exc_type.unite == "heures"
                else conge.nb_jours_ouvrables or 0
            )
            if not verifier_plafond(conge.user_id, exc_type, quantite, conge_id_exclu=conge.id):
                return False, (
                    f"Conge #{conge.id} : plafond annuel dépassé pour « {exc_type.libelle} »."
                )

    conge.statut = "valide"
    conge.valide_par_id = current_user.id
    conge.valide_le = datetime.now(timezone.utc)
    conge.motif_refus = None
    log_action(
        "conge.valider",
        cible_type="conge",
        cible_id=conge.id,
        details={
            "user_id": conge.user_id,
            "type_conge": conge.type_conge,
            "nb_jours": conge.nb_jours_ouvrables,
            "periode": f"{conge.date_debut} → {conge.date_fin}",
        },
    )
    notifier_conge_valide(conge)
    return True, None


@rh_bp.route("/conge/<int:conge_id>/valider", methods=["POST"])
@rh_required
def valider_conge(conge_id):
    """Valider une demande de congé en attente. Solde CP/RTT peut être négatif (informatif).
    Pour un congé exceptionnel, on re-vérifie le plafond car la consommation peut avoir bougé
    entre la soumission et la validation RH.
    """
    conge = Conge.query.get_or_404(conge_id)
    if conge.statut != "en_attente_rh":
        flash("Ce congé n'est pas en attente de validation RH.", "warning")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    # Warnings de solde négatif (informatifs).
    if conge.type_conge in ("CP", "Anciennete"):
        solde_info = calculer_solde(conge.user_id)
        solde_apres = solde_info["solde_restant"] - (conge.nb_jours_ouvrables or 0)
        if solde_apres < 0:
            flash(f"Validation effectuée. Solde CP négatif : {format_jours(solde_apres)} jour(s).", "warning")
    elif conge.type_conge == "RTT":
        solde_info = calculer_solde(conge.user_id)
        rtt_apres = solde_info.get("rtt_solde_restant", 0) - (conge.nb_heures_rtt or 0)
        if rtt_apres < 0:
            flash(f"Validation effectuée. Solde RTT négatif : {format_heures_min(rtt_apres)}.", "warning")

    ok, err = _valider_un_conge_rh(conge)
    if not ok:
        flash(err or "Validation impossible.", "error")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    db.session.commit()

    flash("Demande de congé validée.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))


@rh_bp.route("/conges/valider-lots", methods=["POST"])
@rh_required
def valider_lots():
    """Validation par lots : reçoit conge_ids[] et applique pour chaque demande en attente RH."""
    ids = request.form.getlist("conge_ids")
    if not ids:
        flash("Aucun congé sélectionné.", "warning")
        return redirect(url_for("rh.dashboard"))

    # Chargement en une seule requête (au lieu d'un get() par identifiant).
    ids_int = []
    for cid in ids:
        try:
            ids_int.append(int(cid))
        except (ValueError, TypeError):
            continue
    conges = Conge.query.filter(Conge.id.in_(ids_int)).all() if ids_int else []

    nb_ok = 0
    erreurs = []
    for conge in conges:
        ok, err = _valider_un_conge_rh(conge)
        if ok:
            nb_ok += 1
        elif err:
            erreurs.append(err)

    db.session.commit()
    if nb_ok:
        flash(f"{nb_ok} demande(s) validée(s).", "success")
    for e in erreurs:
        flash(e, "warning")
    return redirect(url_for("rh.dashboard"))

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
        log_action(
            "conge.refuser",
            cible_type="conge",
            cible_id=conge.id,
            details={"user_id": conge.user_id, "motif": motif},
        )
        db.session.commit()

        notifier_conge_refuse(conge, motif)
        db.session.commit()

        flash("Demande de congé refusée.", "success")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    return render_template("rh/refuser_conge.html", conge=conge)


@rh_bp.route("/conges/refuser-lots", methods=["POST"])
@rh_required
def refuser_lots():
    """Refus par lots : conge_ids[] + motif_refus commun à toutes les demandes.

    Si le motif est absent, on rebascule sur une page de saisie groupée
    (le RH a coché les demandes puis cliqué "Refuser la sélection").
    """
    ids = request.form.getlist("conge_ids")
    motif = (request.form.get("motif_refus") or "").strip()
    if not ids:
        flash("Aucun congé sélectionné.", "warning")
        return redirect(url_for("rh.dashboard"))
    if not motif:
        # Page de saisie groupée du motif.
        return render_template("rh/refuser_lots.html", conge_ids=ids)

    ids_int = []
    for cid in ids:
        try:
            ids_int.append(int(cid))
        except (ValueError, TypeError):
            continue
    conges = Conge.query.filter(Conge.id.in_(ids_int)).all() if ids_int else []

    nb_ok = 0
    for conge in conges:
        if conge.statut != "en_attente_rh":
            continue
        conge.statut = "refuse"
        conge.valide_par_id = current_user.id
        conge.valide_le = datetime.now(timezone.utc)
        conge.motif_refus = motif
        log_action(
            "conge.refuser",
            cible_type="conge",
            cible_id=conge.id,
            details={"user_id": conge.user_id, "motif": motif, "lot": True},
        )
        notifier_conge_refuse(conge, motif)
        nb_ok += 1

    db.session.commit()
    flash(f"{nb_ok} demande(s) refusée(s) avec le même motif.", "success")
    return redirect(url_for("rh.dashboard"))


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
                rtt_seuil_hebdo = int(request.form.get("rtt_seuil_hebdo") or 35)
                rtt_heures_par_jour = int(request.form.get("rtt_heures_par_jour_absence") or 7)
                rtt_coef_surplus = float((request.form.get('rtt_coef_surplus') or '0').replace(',', '.').strip() or '0')
                rtt_acquis_par_semaine = float((request.form.get('rtt_acquis_par_semaine') or '0').replace(',', '.').strip() or '0')
                if rtt_seuil_hebdo <= 0 or rtt_heures_par_jour <= 0:
                    raise ValueError("seuil RTT invalide")
                if rtt_acquis_par_semaine < 0:
                    raise ValueError("RTT acquis par semaine invalide")
            except (ValueError, KeyError):
                flash("Données invalides.", "error")
                return redirect(url_for("rh.parametrage"))

            if param is None:
                param = ParametrageAnnuel(
                    debut_exercice=debut,
                    fin_exercice=fin,
                    jours_conges_defaut=jours_defaut,
                    rtt_seuil_hebdo=rtt_seuil_hebdo,
                    rtt_heures_par_jour_absence=rtt_heures_par_jour,
                    rtt_coef_surplus=rtt_coef_surplus,
                    rtt_acquis_par_semaine=rtt_acquis_par_semaine,
                    actif=True,
                )
                db.session.add(param)
            else:
                param.debut_exercice = debut
                param.fin_exercice = fin
                param.jours_conges_defaut = jours_defaut
                param.rtt_seuil_hebdo = rtt_seuil_hebdo
                param.rtt_heures_par_jour_absence = rtt_heures_par_jour
                param.rtt_coef_surplus = rtt_coef_surplus
                param.rtt_acquis_par_semaine = rtt_acquis_par_semaine

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


@rh_bp.route("/cloture-exercice", methods=["GET", "POST"])
@rh_required
def cloture_exercice():
    """Clôture l'exercice actif et démarre le suivant avec report automatique des soldes."""
    ancien = get_parametrage_actif()
    if not ancien:
        flash("Aucun exercice actif. Configurez d'abord le paramétrage.", "error")
        return redirect(url_for("rh.parametrage"))

    if request.method == "POST":
        try:
            debut = datetime.strptime(request.form["debut_exercice"], "%Y-%m-%d").date()
            fin = datetime.strptime(request.form["fin_exercice"], "%Y-%m-%d").date()
            jours_defaut = int(request.form["jours_conges_defaut"])
        except (ValueError, KeyError):
            flash("Données du nouvel exercice invalides.", "error")
            return redirect(url_for("rh.cloture_exercice"))

        if fin <= debut:
            flash("La date de fin doit être postérieure à la date de début.", "error")
            return redirect(url_for("rh.cloture_exercice"))

        plafond_cp_str = (request.form.get("plafond_report_cp") or "").strip()
        plafond_rtt_str = (request.form.get("plafond_report_rtt") or "").strip()
        try:
            plafond_cp = int(plafond_cp_str) if plafond_cp_str else None
            plafond_rtt = int(plafond_rtt_str) if plafond_rtt_str else None
        except ValueError:
            flash("Plafonds de report invalides.", "error")
            return redirect(url_for("rh.cloture_exercice"))

        nouveau = ParametrageAnnuel(
            debut_exercice=debut,
            fin_exercice=fin,
            jours_conges_defaut=jours_defaut,
            rtt_seuil_hebdo=ancien.rtt_seuil_hebdo,
            rtt_heures_par_jour_absence=ancien.rtt_heures_par_jour_absence,
            rtt_coef_surplus=ancien.rtt_coef_surplus,
            rtt_acquis_par_semaine=ancien.rtt_acquis_par_semaine,
            actif=False,
        )
        db.session.add(nouveau)
        db.session.flush()

        try:
            res = cloturer_exercice_et_reporter(
                nouveau,
                report_max_jours=plafond_cp,
                report_max_heures_rtt=plafond_rtt,
            )
        except Exception:
            db.session.rollback()
            flash("Erreur lors de la clôture. Aucune modification n'a été appliquée.", "error")
            return redirect(url_for("rh.cloture_exercice"))

        log_action(
            "exercice.cloturer",
            cible_type="parametrage",
            cible_id=nouveau.id,
            details={
                "ancien_id": ancien.id,
                "ancien_periode": f"{ancien.debut_exercice} → {ancien.fin_exercice}",
                "nouveau_periode": f"{debut} → {fin}",
                "plafond_report_cp": plafond_cp,
                "plafond_report_rtt": plafond_rtt,
                "report_cp_total": res["report_cp_total"],
                "report_rtt_total": res["report_rtt_total"],
                "nb_salaries": res["nb_salaries"],
            },
        )
        db.session.commit()

        flash(
            f"Exercice clôturé. {res['nb_salaries']} salarié(s) traité(s) : "
            f"{res['report_cp_total']} j CP et {res['report_rtt_total']} h RTT reportés.",
            "success",
        )
        return redirect(url_for("rh.dashboard"))

    # Prévisualisation : combien va être reporté ?
    salaries = User.query.filter_by(actif=True).order_by(User.nom, User.prenom).all()
    apercu = []
    for s in salaries:
        info = calculer_solde(s.id)
        apercu.append({
            "user": s,
            "cp_restant": info.get("solde_restant", 0),
            "rtt_restant": info.get("rtt_solde_restant", 0),
        })

    return render_template("rh/cloture_exercice.html", ancien=ancien, apercu=apercu)

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

    avant = {
        "jours_alloues": allocation.jours_alloues,
        "jours_anciennete": allocation.jours_anciennete,
        "jours_report": allocation.jours_report,
        "rtt_heures_allouees": allocation.rtt_heures_allouees,
        "rtt_heures_reportees": allocation.rtt_heures_reportees,
    }
    try:
        allocation.jours_alloues = int(request.form.get("jours_alloues", param.jours_conges_defaut))
        allocation.jours_anciennete = int(request.form.get("jours_anciennete", 0))
        allocation.jours_report = int(request.form.get("jours_report", 0))
        # RTT en heures décimales (cf. R3) : on accepte les fractions (et la virgule).
        allocation.rtt_heures_allouees = float((request.form.get("rtt_heures_allouees", "0") or "0").replace(",", "."))
        allocation.rtt_heures_reportees = float((request.form.get("rtt_heures_reportees", "0") or "0").replace(",", "."))
    except ValueError:
        flash("Valeurs invalides.", "error")
        return redirect(url_for("rh.salarie_detail", user_id=user_id))

    apres = {
        "jours_alloues": allocation.jours_alloues,
        "jours_anciennete": allocation.jours_anciennete,
        "jours_report": allocation.jours_report,
        "rtt_heures_allouees": allocation.rtt_heures_allouees,
        "rtt_heures_reportees": allocation.rtt_heures_reportees,
    }
    log_action(
        "allocation.modifier",
        cible_type="allocation",
        cible_id=allocation.id,
        details={"user_id": user_id, "avant": avant, "apres": apres},
    )
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
    actif_avant = user.actif
    user.actif = actif_str == "on"
    log_action(
        "salarie.statut",
        cible_type="user",
        cible_id=user.id,
        details={"actif_avant": actif_avant, "actif_apres": user.actif},
    )
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

@rh_bp.route("/salaries/importer", methods=["GET", "POST"])
@rh_required
def importer_salaries():
    """Import en masse de salariés depuis un fichier CSV ou Excel.

    Clé d'unicité : identifiant. Création si absent, mise à jour si présent.
    """
    from services.import_salaries import parse_csv, parse_excel, sync_users

    if request.method == "POST":
        f = request.files.get("fichier")
        default_password = request.form.get("default_password", "")
        dry_run = request.form.get("dry_run") == "on"

        if not f or not f.filename:
            flash("Aucun fichier sélectionné.", "error")
            return redirect(url_for("rh.importer_salaries"))

        content = f.read()
        filename = f.filename.lower()
        try:
            if filename.endswith(".csv"):
                rows = parse_csv(content)
            elif filename.endswith(".xlsx") or filename.endswith(".xlsm"):
                rows = parse_excel(content)
            else:
                flash("Format non supporté. Utilisez CSV ou XLSX.", "error")
                return redirect(url_for("rh.importer_salaries"))
        except Exception as e:
            flash(f"Erreur lors de la lecture du fichier : {e}", "error")
            return redirect(url_for("rh.importer_salaries"))

        if not rows:
            flash("Aucune ligne exploitable trouvée. Vérifiez les en-têtes NOM / PRENOM.", "error")
            return redirect(url_for("rh.importer_salaries"))

        if dry_run:
            # Aperçu sans persistance.
            return render_template(
                "rh/import_salaries.html",
                preview=rows,
                preview_count=len(rows),
            )

        created, updated, errors = sync_users(rows, default_password, hash_password)

        log_action(
            "salaries.import",
            cible_type="user",
            details={
                "fichier": f.filename,
                "lignes_traitees": len(rows),
                "crees": created,
                "mis_a_jour": updated,
                "erreurs": len(errors),
            },
        )
        db.session.commit()

        msg = f"Import terminé : {created} créé(s), {updated} mis à jour."
        if errors:
            msg += f" {len(errors)} erreur(s)."
        flash(msg, "success" if not errors else "warning")
        for e in errors[:10]:
            flash(e, "warning")
        return redirect(url_for("rh.liste_salaries"))

    return render_template("rh/import_salaries.html", preview=None)


@rh_bp.route("/salarie/nouveau", methods=["GET", "POST"])
@rh_required
def creer_salarie():
    """Création d'un nouveau salarié côté RH."""
    responsables = User.query.filter(User.role.in_(["responsable", "rh"]), User.actif == True).order_by(User.nom, User.prenom).all()

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        identifiant = request.form.get("identifiant", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")
        role = normaliser_role(request.form.get("role", "salarie"))
        date_embauche_str = request.form.get("date_embauche", "").strip()

        def _reafficher_formulaire():
            return render_template("rh/salarie_form.html", salarie=None, mode="create", responsables=responsables)

        if not nom or not prenom or not identifiant or not mot_de_passe:
            flash("Nom, prénom, identifiant et mot de passe sont obligatoires.", "error")
            return _reafficher_formulaire()

        if role is None:
            flash("Rôle invalide.", "error")
            return _reafficher_formulaire()

        err_pwd = valider_mot_de_passe(mot_de_passe)
        if err_pwd:
            flash(err_pwd, "error")
            return _reafficher_formulaire()

        existing = User.query.filter_by(identifiant=identifiant).first()
        if existing:
            flash("Un utilisateur avec cet identifiant existe déjà.", "error")
            return _reafficher_formulaire()

        date_embauche = None
        if date_embauche_str:
            try:
                date_embauche = datetime.strptime(date_embauche_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Date d'embauche invalide.", "error")
                return _reafficher_formulaire()

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
        db.session.flush()
        log_action(
            "salarie.creer",
            cible_type="user",
            cible_id=user.id,
            details={
                "identifiant": user.identifiant,
                "nom": user.nom,
                "prenom": user.prenom,
                "role": user.role,
                "responsable_id": user.responsable_id,
            },
        )
        db.session.commit()

        flash("Salarié créé avec succès.", "success")
        return redirect(url_for("rh.liste_salaries"))

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
        role = normaliser_role(request.form.get("role", "salarie"))
        date_embauche_str = request.form.get("date_embauche", "").strip()
        actif_str = request.form.get("actif", "off")

        if not nom or not prenom or not identifiant:
            flash("Nom, prénom et identifiant sont obligatoires.", "error")
            return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)

        if role is None:
            flash("Rôle invalide.", "error")
            return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)

        if mot_de_passe:
            err_pwd = valider_mot_de_passe(mot_de_passe)
            if err_pwd:
                flash(err_pwd, "error")
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

        # Garde-fou anti lock-out : on n'autorise pas le retrait du dernier accès RH
        # actif, ni qu'un RH se retire à lui-même son accès (changement de rôle ou
        # désactivation) — sinon plus personne ne peut administrer l'application.
        etait_rh_actif = user.role == "rh" and user.actif
        sera_rh_actif = role == "rh" and actif_str == "on"
        if etait_rh_actif and not sera_rh_actif:
            if user.id == current_user.id:
                flash(
                    "Vous ne pouvez pas retirer votre propre accès RH. "
                    "Demandez à un autre gestionnaire RH de le faire.",
                    "error",
                )
                return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)
            autres_rh_actifs = User.query.filter(
                User.role == "rh", User.actif == True, User.id != user.id
            ).count()
            if autres_rh_actifs == 0:
                flash("Il doit rester au moins un gestionnaire RH actif.", "error")
                return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)

        avant = {
            "nom": user.nom,
            "prenom": user.prenom,
            "identifiant": user.identifiant,
            "role": user.role,
            "actif": user.actif,
            "responsable_id": user.responsable_id,
        }
        user.nom = nom
        user.prenom = prenom
        user.identifiant = identifiant
        user.role = role
        user.date_embauche = date_embauche
        user.actif = actif_str == "on"
        mdp_modifie = bool(mot_de_passe)
        if mot_de_passe:
            user.mot_de_passe_hash = hash_password(mot_de_passe)
        r_id = request.form.get("responsable_id", "").strip()
        user.responsable_id = int(r_id) if r_id else None
        apres = {
            "nom": user.nom,
            "prenom": user.prenom,
            "identifiant": user.identifiant,
            "role": user.role,
            "actif": user.actif,
            "responsable_id": user.responsable_id,
        }
        log_action(
            "salarie.modifier",
            cible_type="user",
            cible_id=user.id,
            details={"avant": avant, "apres": apres, "mdp_modifie": mdp_modifie},
        )
        db.session.commit()
        flash("Salarié mis à jour.", "success")
        return redirect(url_for("rh.liste_salaries"))

    return render_template("rh/salarie_form.html", salarie=user, mode="edit", responsables=responsables)



def _parse_plafond(raw):
    """Parse le plafond annuel d'un type exceptionnel.

    Retourne (valeur, erreur) :
    - ("", None) absent → (None, None) : pas de plafond.
    - entier positif → (int, None).
    - saisie non vide invalide → (None, message) pour éviter de SUPPRIMER
      silencieusement le plafond sur une faute de frappe.
    """
    plafond_str = (raw or "").strip()
    if not plafond_str:
        return None, None
    try:
        valeur = int(plafond_str)
    except ValueError:
        return None, "Plafond annuel invalide (entier attendu)."
    if valeur < 0:
        return None, "Plafond annuel invalide (doit être positif)."
    return valeur, None


@rh_bp.route("/types-exceptionnels", methods=["GET", "POST"])
@rh_required
def types_exceptionnels():
    from services.conges_exceptionnels import get_types_exceptionnels, creer_types_par_defaut

    if request.method == "POST":
        action = request.form.get("action")

        if action == "seed_defaults":
            nb = creer_types_par_defaut()
            if nb:
                flash(f"{nb} type(s) de congés exceptionnels par défaut ajouté(s).", "success")
            else:
                flash("Les types par défaut existent déjà.", "info")
            return redirect(url_for("rh.types_exceptionnels"))

        if action == "create":
            code = (request.form.get("code") or "").strip().upper()
            libelle = (request.form.get("libelle") or "").strip()
            unite = (request.form.get("unite") or "jours").strip() or "jours"

            justificatif_requis = request.form.get("justificatif_requis") == "on"

            if not code or not libelle or unite not in ("jours", "heures"):
                flash("Données invalides.", "error")
                return redirect(url_for("rh.types_exceptionnels"))
            if len(code) > 30 or len(libelle) > 120:
                flash("Code (max 30) ou libellé (max 120) trop long.", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            plafond, plafond_err = _parse_plafond(request.form.get("plafond_annuel"))
            if plafond_err:
                flash(plafond_err, "error")
                return redirect(url_for("rh.types_exceptionnels"))

            existing = CongeExceptionnelType.query.filter_by(code=code).first()
            if existing:
                flash("Un type avec ce code existe déjà.", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            t = CongeExceptionnelType(
                code=code,
                libelle=libelle,
                unite=unite,
                plafond_annuel=plafond,
                justificatif_requis=justificatif_requis,
                actif=True,
            )
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

            if not libelle or unite not in ("jours", "heures"):
                flash("Données invalides.", "error")
                return redirect(url_for("rh.types_exceptionnels"))
            if len(libelle) > 120:
                flash("Libellé trop long (max 120).", "error")
                return redirect(url_for("rh.types_exceptionnels"))

            plafond, plafond_err = _parse_plafond(request.form.get("plafond_annuel"))
            if plafond_err:
                flash(plafond_err, "error")
                return redirect(url_for("rh.types_exceptionnels"))

            t.libelle = libelle
            t.unite = unite
            t.plafond_annuel = plafond
            t.justificatif_requis = request.form.get("justificatif_requis") == "on"
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




@rh_bp.route("/heures-hebdo", methods=["GET", "POST"])
@rh_required
def heures_hebdo():
    """Saisie hebdomadaire des heures travaillées + recalcul RTT (mode 'hebdo').

    Le RTT tient compte des absences de la semaine : une absence réduit le seuil
    hebdomadaire pour ne pas pénaliser le salarié (cf. services/rtt_hebdo.py).
    """
    from datetime import timedelta
    from services.rtt_hebdo import (
        jours_absence_semaine,
        maj_rtt_allocations_hebdo,
        _lundi,
        seuil_hebdo_param,
        heures_par_jour_absence_param,
    )

    param = get_parametrage_actif()
    if not param:
        flash("Aucun paramétrage actif. Configurez d'abord l'exercice.", "error")
        return redirect(url_for("rh.parametrage"))

    lundi_str = (request.values.get("lundi") or "").strip()
    if lundi_str:
        try:
            ref = datetime.strptime(lundi_str, "%Y-%m-%d").date()
        except ValueError:
            ref = date.today()
    else:
        ref = date.today()
    lundi = _lundi(ref)

    salaries = User.query.filter_by(actif=True).order_by(User.nom).all()

    if request.method == "POST":
        action = (request.form.get("action") or "save").strip() or "save"
        saved_user_ids = []

        for s in salaries:
            hw_str = (request.form.get(f"u{s.id}_heures") or "").strip()
            if hw_str == "":
                continue
            try:
                heures = int(hw_str)
            except ValueError:
                flash(f"Valeur invalide pour {s.prenom} {s.nom}.", "error")
                return redirect(url_for("rh.heures_hebdo", lundi=lundi.isoformat()))

            row = HeuresHebdo.query.filter_by(user_id=s.id, date_lundi=lundi).first()
            if not row:
                row = HeuresHebdo(user_id=s.id, date_lundi=lundi)
                db.session.add(row)
            row.heures_travaillees = max(0, heures)
            row.source = "manuel"
            row.saisi_par_id = current_user.id
            saved_user_ids.append(s.id)

        db.session.commit()
        flash("Heures hebdomadaires enregistrées." if saved_user_ids else "Aucune donnée à enregistrer.",
              "success" if saved_user_ids else "info")

        if action == "save_recalc":
            try:
                res = maj_rtt_allocations_hebdo(param)
                flash(f"RTT recalculées pour {len(res)} salarié(s).", "success")
            except Exception:
                db.session.rollback()
                flash("Erreur lors du recalcul RTT. Consultez les logs serveur.", "error")

        return redirect(url_for("rh.heures_hebdo", lundi=lundi.isoformat()))

    existing = HeuresHebdo.query.filter_by(date_lundi=lundi).all()
    by_user = {e.user_id: e for e in existing}
    absences = {s.id: jours_absence_semaine(s.id, lundi) for s in salaries}

    return render_template(
        "rh/heures_hebdo.html",
        parametrage=param,
        lundi=lundi,
        lundi_prec=(lundi - timedelta(days=7)),
        lundi_suiv=(lundi + timedelta(days=7)),
        dimanche=(lundi + timedelta(days=6)),
        salaries=salaries,
        heures_by_user=by_user,
        absences=absences,
        seuil_hebdo=seuil_hebdo_param(param),
        heures_par_jour=heures_par_jour_absence_param(param),
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


@rh_bp.route("/audit-log")
@rh_required
def audit_log():
    """Journal des actions RH/responsable (création/modification/suppression/validation/refus)."""
    PAGE_SIZE = 100

    # Filtres
    action_filter = (request.args.get("action") or "").strip()
    acteur_filter = (request.args.get("acteur") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action.like(f"{action_filter}%"))
    if acteur_filter:
        try:
            query = query.filter(AuditLog.acteur_id == int(acteur_filter))
        except ValueError:
            pass

    total = query.count()
    entries = (
        query.order_by(AuditLog.cree_le.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    # Décodage JSON des détails pour affichage lisible.
    entries_view = []
    for e in entries:
        try:
            details = _json.loads(e.details) if e.details else None
        except (TypeError, ValueError):
            details = {"_raw": e.details}
        entries_view.append({"row": e, "details": details})

    # Liste d'acteurs pour le filtre (déduplique côté Python pour ne pas alourdir SQL).
    acteurs = (
        User.query.filter(User.id.in_(db.session.query(AuditLog.acteur_id).distinct()))
        .order_by(User.nom, User.prenom)
        .all()
    )

    return render_template(
        "rh/audit_log.html",
        entries=entries_view,
        total=total,
        page=page,
        page_size=PAGE_SIZE,
        has_next=(page * PAGE_SIZE) < total,
        has_prev=page > 1,
        action_filter=action_filter,
        acteur_filter=acteur_filter,
        acteurs=acteurs,
    )


# Statuts de congés éligibles à l'archivage (les demandes en attente sont exclues).
_STATUTS_ARCHIVABLES = ("valide", "refuse", "annule")


def _parse_date_cutoff(value, defaut):
    if not value:
        return defaut
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return defaut


@rh_bp.route("/archives", methods=["GET", "POST"])
@rh_required
def archives():
    """Archivage des congés anciens (FR53).

    Le RH choisit une date d'arrêté : tous les congés traités (validés, refusés,
    annulés) dont la date de fin est antérieure ou égale à cette date sont
    archivés. Les congés archivés sont conservés (audit) mais retirés des listes
    courantes. Une demande encore en attente n'est jamais archivée.
    """
    param = get_parametrage_actif()
    defaut_cutoff = param.debut_exercice if param else date.today()

    if request.method == "POST":
        cutoff = _parse_date_cutoff(request.form.get("date_cutoff"), defaut_cutoff)
        action = request.form.get("action", "archiver")

        if action == "desarchiver":
            conges = Conge.query.filter(Conge.archive == True).all()
            for c in conges:
                c.archive = False
            nb = len(conges)
            log_action("conge.desarchiver", details={"nb": nb})
            db.session.commit()
            flash(f"{nb} congé(s) désarchivé(s).", "success")
            return redirect(url_for("rh.archives"))

        conges = Conge.query.filter(
            Conge.archive == False,
            Conge.statut.in_(_STATUTS_ARCHIVABLES),
            Conge.date_fin <= cutoff,
        ).all()
        for c in conges:
            c.archive = True
        nb = len(conges)
        log_action(
            "conge.archiver",
            details={"nb": nb, "date_cutoff": cutoff.isoformat()},
        )
        db.session.commit()
        flash(f"{nb} congé(s) archivé(s) (date de fin ≤ {cutoff.strftime('%d/%m/%Y')}).", "success")
        return redirect(url_for("rh.archives"))

    cutoff = _parse_date_cutoff(request.args.get("date_cutoff"), defaut_cutoff)
    nb_archivables = Conge.query.filter(
        Conge.archive == False,
        Conge.statut.in_(_STATUTS_ARCHIVABLES),
        Conge.date_fin <= cutoff,
    ).count()
    nb_archives = Conge.query.filter(Conge.archive == True).count()

    return render_template(
        "rh/archives.html",
        date_cutoff=cutoff,
        nb_archivables=nb_archivables,
        nb_archives=nb_archives,
    )

