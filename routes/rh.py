from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from models import db
from models.user import User
from models.conge import Conge
from models.parametrage import ParametrageAnnuel, AllocationConge
from models.jour_ferie import JourFerie
from services.calcul_jours import compter_jours_ouvrables, detecter_chevauchement
from services.solde import calculer_solde, get_parametrage_actif, verifier_solde_suffisant
from services.jours_feries import get_jours_feries

rh_bp = Blueprint("rh", __name__)


def rh_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "rh":
            flash("AccÃ¨s rÃ©servÃ© aux gestionnaires RH.", "error")
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
            Conge.date_debut <= datetime.today().date(),
            Conge.date_fin >= datetime.today().date(),
        ).count()
        salaries_data.append({
            "user": s,
            "solde": solde_info,
            "conges_en_cours": conges_en_cours,
        })

    # Stats
    total_salaries = len(salaries)
    total_en_conge = sum(1 for s in salaries_data if s["conges_en_cours"] > 0)

    return render_template(
        "rh/dashboard.html",
        salaries_data=salaries_data,
        total_salaries=total_salaries,
        total_en_conge=total_en_conge,
        parametrage=param,
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
            flash("La date de fin doit Ãªtre postÃ©rieure Ã  la date de dÃ©but.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        type_conge = request.form.get("type_conge", "CP")
        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la pÃ©riode sÃ©lectionnÃ©e.", "error")
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        chevauchement = detecter_chevauchement(user.id, date_debut, date_fin)
        if chevauchement:
            flash(
                f"Chevauchement dÃ©tectÃ© avec le congÃ© du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
                f"au {chevauchement.date_fin.strftime('%d/%m/%Y')}.",
                "error",
            )
            return render_template("rh/ajouter_conge.html", salarie=user, solde=solde_info)

        if type_conge in ("CP", "Anciennete"):
            if not verifier_solde_suffisant(user.id, nb_jours):
                flash(
                    f"Solde insuffisant. {solde_info['solde_restant']} jour(s) restant(s), "
                    f"{nb_jours} jour(s) demandÃ©(s).",
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
        )
        db.session.add(conge)
        db.session.commit()

        flash(f"CongÃ© ajoutÃ© : {nb_jours} jour(s) ouvrable(s).", "success")
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
            flash("La date de fin doit Ãªtre postÃ©rieure Ã  la date de dÃ©but.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)

        type_conge = request.form.get("type_conge", conge.type_conge)
        commentaire = request.form.get("commentaire", "").strip()

        nb_jours = compter_jours_ouvrables(date_debut, date_fin)
        if nb_jours == 0:
            flash("Aucun jour ouvrable dans la pÃ©riode sÃ©lectionnÃ©e.", "error")
            return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)

        chevauchement = detecter_chevauchement(user.id, date_debut, date_fin, conge_id_exclu=conge.id)
        if chevauchement:
            flash(
                f"Chevauchement dÃ©tectÃ© avec le congÃ© du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
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

        flash("CongÃ© modifiÃ© avec succÃ¨s.", "success")
        return redirect(url_for("rh.salarie_detail", user_id=user.id))

    return render_template("rh/modifier_conge.html", conge=conge, salarie=user, solde=solde_info)


@rh_bp.route("/conge/<int:conge_id>/supprimer", methods=["POST"])
@rh_required
def supprimer_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    user_id = conge.user_id
    db.session.delete(conge)
    db.session.commit()
    flash("CongÃ© supprimÃ©.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=user_id))


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
                flash("DonnÃ©es invalides.", "error")
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
            flash("ParamÃ©trage enregistrÃ©.", "success")
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
                flash(f"{count} jour(s) fÃ©riÃ©(s) ajoutÃ©(s).", "success")
            return redirect(url_for("rh.parametrage"))

        elif action == "ajouter_ferie":
            try:
                date_f = datetime.strptime(request.form["date_ferie"], "%Y-%m-%d").date()
                libelle = request.form.get("libelle_ferie", "").strip()
                if not libelle:
                    libelle = "Jour fÃ©riÃ© personnalisÃ©"
            except (ValueError, KeyError):
                flash("Date invalide.", "error")
                return redirect(url_for("rh.parametrage"))

            existing = JourFerie.query.filter_by(date_ferie=date_f).first()
            if existing:
                flash("Ce jour fÃ©riÃ© existe dÃ©jÃ .", "warning")
            else:
                jf = JourFerie(date_ferie=date_f, libelle=libelle, annee=date_f.year, auto_genere=False)
                db.session.add(jf)
                db.session.commit()
                flash("Jour fÃ©riÃ© ajoutÃ©.", "success")
            return redirect(url_for("rh.parametrage"))

        elif action == "supprimer_ferie":
            ferie_id = request.form.get("ferie_id")
            if ferie_id:
                jf = JourFerie.query.get(int(ferie_id))
                if jf:
                    db.session.delete(jf)
                    db.session.commit()
                    flash("Jour fÃ©riÃ© supprimÃ©.", "success")
            return redirect(url_for("rh.parametrage"))

    return render_template("rh/parametrage.html", parametrage=param, jours_feries=jours_feries_list)


@rh_bp.route("/salarie/<int:user_id>/allocation", methods=["POST"])
@rh_required
def modifier_allocation(user_id):
    user = User.query.get_or_404(user_id)
    param = get_parametrage_actif()
    if not param:
        flash("Aucun paramÃ©trage actif. Configurez d'abord le paramÃ©trage annuel.", "error")
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
    flash("Allocation mise Ã  jour.", "success")
    return redirect(url_for("rh.salarie_detail", user_id=user_id))
