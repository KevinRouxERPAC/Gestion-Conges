from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models.conge import Conge
from services.solde import calculer_solde, get_parametrage_actif

salarie_bp = Blueprint("salarie", __name__)


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
