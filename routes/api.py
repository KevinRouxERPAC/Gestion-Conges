"""Endpoints JSON internes (consommés par le JS de l'app, pas exposés publiquement)."""
from datetime import date
from flask import Blueprint, jsonify, request
from flask_login import login_required

from models.jour_ferie import JourFerie
from services.calcul_jours import compter_jours_ouvrables_avec_demi

api_bp = Blueprint("api", __name__)


@api_bp.route("/jours-feries")
@login_required
def jours_feries():
    """Retourne les dates fériées (format ISO) pour les années passées en query
    string (`annees=2026,2027`). Par défaut : année courante + suivante.

    Le client doit gérer un cache court (HTTP no-store : c'est suffisamment rare
    pour ne pas justifier un cache côté serveur).
    """
    annees_param = (request.args.get("annees") or "").strip()
    if annees_param:
        try:
            annees = [int(x.strip()) for x in annees_param.split(",") if x.strip()]
        except ValueError:
            return jsonify({"error": "Paramètre 'annees' invalide"}), 400
    else:
        today = date.today()
        annees = [today.year, today.year + 1]

    if not annees:
        return jsonify({"feries": []})

    rows = JourFerie.query.filter(JourFerie.annee.in_(annees)).all()
    feries = [r.date_ferie.isoformat() for r in rows]
    return jsonify({"feries": feries})


@api_bp.route("/jours-ouvrables")
@login_required
def jours_ouvrables():
    """Calcule le nombre de jours ouvrables entre deux dates (incluses), côté serveur.

    Permet au formulaire de confirmer le décompte sans dupliquer la logique
    métier en JS (le JS peut faire un calcul local rapide, et confirmer ici).
    """
    debut_str = (request.args.get("debut") or "").strip()
    fin_str = (request.args.get("fin") or "").strip()
    if not debut_str or not fin_str:
        return jsonify({"error": "Paramètres 'debut' et 'fin' requis (AAAA-MM-JJ)"}), 400
    try:
        from datetime import datetime as _dt
        debut = _dt.strptime(debut_str, "%Y-%m-%d").date()
        fin = _dt.strptime(fin_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Format de date invalide"}), 400

    if fin < debut:
        return jsonify({"jours": 0, "valide": False, "raison": "Date de fin avant date de début"})

    demi_debut = (request.args.get("demi_debut") or "").strip().lower() or None
    demi_fin = (request.args.get("demi_fin") or "").strip().lower() or None
    if demi_debut not in (None, "matin", "apres_midi"):
        demi_debut = None
    if demi_fin not in (None, "matin", "apres_midi"):
        demi_fin = None

    nb = compter_jours_ouvrables_avec_demi(debut, fin, demi_debut, demi_fin)
    return jsonify({"jours": nb, "valide": True})
