from datetime import datetime, date
from functools import wraps

import bcrypt
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user

from models import db
from models.conge import Conge
from models.jour_ferie import JourFerie
from models.parametrage import ParametrageAnnuel, AllocationConge
from models.user import User
from services.calcul_jours import compter_jours_ouvrables, detecter_chevauchement
from services.solde import calculer_solde, get_parametrage_actif, verifier_solde_suffisant
from services.jours_feries import get_jours_feries
from services.email import envoyer_notification_validation, envoyer_notification_refus
from services.export import export_conges_excel, export_conges_equipe_excel, export_conges_pdf

rh_bp = Blueprint("rh", __name__)


def hash_password(password: str) -> str:
    """Hasher un mot de passe pour création / modification côté RH."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


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
    if param:
        conges_exercice = Conge.query.filter(
            Conge.statut == "valide",
            Conge.date_debut <= param.fin_exercice,
            Conge.date_fin >= param.debut_exercice,
        ).all()
        for c in conges_exercice:
            if c.utilisateur is None:
                continue
            calendar_events.append({
                "start": c.date_debut.isoformat(),
                "end": c.date_fin.isoformat(),
                "user": f"{c.utilisateur.prenom} {c.utilisateur.nom}",
                "type_conge": c.type_conge,
            })

    # Demandes en attente de validation
    demandes_attente = (
        Conge.query.filter_by(statut="en_attente")
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
        demandes_attente=demandes_attente,
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

    if request.method == "POST":
        try:
            date_debut = datetime.strptime(request.form["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(request.form["date_fin"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            flash("Dates invalides.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        if date_fin < date_debut:
            flash("La date de fin doit être postérieure à la date de début.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        type_conge = request.form.get("type_conge", "CP")
        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la période sélectionnée.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        chevauchement = detecter_chevauchement(user.id, date_debut, date_fin)
        if chevauchement:
            flash(
                f"Chevauchement détecté avec le congé du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
                f"au {chevauchement.date_fin.strftime('%d/%m/%Y')}.",
                "error",
            )
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        if type_conge in ("CP", "Anciennete"):
            if not verifier_solde_suffisant(user.id, nb_jours):
                flash(
                    f"Solde insuffisant. {solde_info['solde_restant']} jour(s) restant(s), "
                    f"{nb_jours} jour(s) demandé(s).",
                    "error",
                )
                return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        conge = Conge(
            user_id=user.id,
            date_debut=date_debut,
            date_fin=date_fin,
            nb_jours_ouvrables=nb_jours,
            type_conge=type_conge,
            commentaire=commentaire,
            statut="valide",
            valide_par_id=current_user.id,
            valide_le=datetime.utcnow(),
        )
        db.session.add(conge)
        db.session.commit()

        flash(f"Congé ajouté : {nb_jours} jour(s) ouvrable(s).", "success")
        return redirect(url_for("rh.salarie_detail", user_id=user.id))

    return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)


@rh_bp.route("/conge/<int:conge_id>/modifier", methods=["GET", "POST"])
@rh_required
def modifier_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    user = conge.utilisateur
    solde_info = calculer_solde(user.id)

    if request.method == "POST":
        try:
            date_debut = datetime.strptime(request.form["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(request.form["date_fin"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            flash("Dates invalides.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)

        if date_fin < date_debut:
            flash("La date de fin doit être postérieure à la date de début.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)

        type_conge = request.form.get("type_conge", conge.type_conge)
        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la période sélectionnée.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)

        chevauchement = detecter_chevauchement(user.id, date_debut, date_fin, conge_id_exclu=conge.id)
        if chevauchement:
            flash(
                f"Chevauchement détecté avec le congé du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
                f"au {chevauchement.date_fin.strftime('%d/%m/%Y')}.",
                "error",
            )
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)

        if type_conge in ("CP", "Anciennete"):
            if not verifier_solde_suffisant(user.id, nb_jours, conge_id_exclu=conge.id):
                flash("Solde insuffisant pour cette modification.", "error")
                return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)

        conge.date_debut = date_debut
        conge.date_fin = date_fin
        conge.nb_jours_ouvrables = nb_jours
        conge.type_conge = type_conge
        conge.commentaire = commentaire
        db.session.commit()

        flash("Congé modifié avec succès.", "success")
        return redirect(url_for("rh.salarie_detail", user_id=user.id))

    return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)


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
    if conge.statut != "en_attente":
        flash("Ce congé n'est pas en attente de validation.", "warning")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    if conge.type_conge in ("CP", "Anciennete"):
        if not verifier_solde_suffisant(conge.user_id, conge.nb_jours_ouvrables):
            flash("Solde insuffisant pour valider ce congé.", "error")
            return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    conge.statut = "valide"
    conge.valide_par_id = current_user.id
    conge.valide_le = datetime.utcnow()
    conge.motif_refus = None
    db.session.commit()

    # Notification email
    user = conge.utilisateur
    if user and getattr(user, "email", None) and user.email:
        envoyer_notification_validation(
            prenom=user.prenom,
            email=user.email,
            date_debut=conge.date_debut,
            date_fin=conge.date_fin,
            nb_jours=conge.nb_jours_ouvrables,
            type_conge=conge.type_conge,
        )

    flash("Demande de congé validée.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))


@rh_bp.route("/conge/<int:conge_id>/refuser", methods=["GET", "POST"])
@rh_required
def refuser_conge(conge_id):
    """Refuser une demande de congé avec motif obligatoire."""
    conge = Conge.query.get_or_404(conge_id)
    if conge.statut != "en_attente":
        flash("Ce congé n'est pas en attente de validation.", "warning")
        return redirect(url_for("rh.salarie_detail", user_id=conge.user_id))

    if request.method == "POST":
        motif = request.form.get("motif_refus", "").strip()
        if not motif:
            flash("Le motif de refus est obligatoire.", "error")
            return render_template("rh/refuser_conge.html", conge=conge)

        conge.statut = "refuse"
        conge.valide_par_id = current_user.id
        conge.valide_le = datetime.utcnow()
        conge.motif_refus = motif
        db.session.commit()

        # Notification email
        user = conge.utilisateur
        if user and getattr(user, "email", None) and user.email:
            envoyer_notification_refus(
                prenom=user.prenom,
                email=user.email,
                date_debut=conge.date_debut,
                date_fin=conge.date_fin,
                nb_jours=conge.nb_jours_ouvrables,
                type_conge=conge.type_conge,
                motif=motif,
            )

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
            except (ValueError, KeyError):
                flash("Données invalides.", "error")
                return redirect(url_for("rh.parametrage"))

            if param is None:
                param = ParametrageAnnuel(
                    debut_exercice=debut,
                    fin_exercice=fin,
                    jours_conges_defaut=jours_defaut,
                    actif=True,
                )
                db.session.add(param)
            else:
                param.debut_exercice = debut
                param.fin_exercice = fin
                param.jours_conges_defaut = jours_defaut

            db.session.commit()
            flash("Paramétrage enregistré.", "success")
            return redirect(url_for("rh.parametrage"))

        elif action == "charger_feries":
            if param:
                annees = set()
                annees.add(param.debut_exercice.year)
                annees.add(param.fin_exercice.year)
                count = 0
                for annee in annees:
                    feries = get_jours_feries(annee)
                    for date_f, libelle in feries:
                        existing = JourFerie.query.filter_by(date_ferie=date_f).first()
                        if not existing:
                            jf = JourFerie(date_ferie=date_f, libelle=libelle, annee=annee, auto_genere=True)
                            db.session.add(jf)
                            count += 1
                db.session.commit()
                flash(f"{count} jour(s) férié(s) ajouté(s).", "success")
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
                jf = JourFerie.query.get(int(ferie_id))
                if jf:
                    db.session.delete(jf)
                    db.session.commit()
                    flash("Jour férié supprimé.", "success")
            return redirect(url_for("rh.parametrage"))

    return render_template("rh/parametrage.html", parametrage=param, jours_feries=jours_feries_list)


@rh_bp.route("/salarie/<int:user_id>/email", methods=["POST"])
@rh_required
def modifier_email(user_id):
    """Mise à jour de l'email du salarié pour les notifications."""
    user = User.query.get_or_404(user_id)
    email = request.form.get("email", "").strip() or None
    user.email = email if email else None
    db.session.commit()
    flash("Email mis à jour." if email else "Email supprimé.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=user_id))


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

        user = User(
            nom=nom,
            prenom=prenom,
            identifiant=identifiant,
            mot_de_passe_hash=hash_password(mot_de_passe),
            role=role,
            actif=True,
            date_embauche=date_embauche,
        )
        db.session.add(user)
        db.session.commit()

        flash("Salarié créé avec succès.", "success")
        return redirect(url_for("rh.liste_salaries"))

    return render_template("rh/salarie_form.html", salarie=None, mode="create")


@rh_bp.route("/salarie/<int:user_id>/modifier", methods=["GET", "POST"])
@rh_required
def modifier_salarie(user_id):
    """Modification d'un salarié existant côté RH."""
    user = User.query.get_or_404(user_id)

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
            return render_template("rh/salarie_form.html", salarie=user, mode="edit")

        existing = User.query.filter(
            User.identifiant == identifiant,
            User.id != user.id,
        ).first()
        if existing:
            flash("Un autre utilisateur utilise déjà cet identifiant.", "error")
            return render_template("rh/salarie_form.html", salarie=user, mode="edit")

        date_embauche = None
        if date_embauche_str:
            try:
                date_embauche = datetime.strptime(date_embauche_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Date d'embauche invalide.", "error")
                return render_template("rh/salarie_form.html", salarie=user, mode="edit")

        user.nom = nom
        user.prenom = prenom
        user.identifiant = identifiant
        user.role = role
        user.date_embauche = date_embauche
        user.actif = actif_str == "on"

        if mot_de_passe:
            user.mot_de_passe_hash = hash_password(mot_de_passe)

        db.session.commit()
        flash("Salarié mis à jour.", "success")
        return redirect(url_for("rh.liste_salaries"))

    return render_template("rh/salarie_form.html", salarie=user, mode="edit")
