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
from services.delegation import (
    delegataires_de,
    peut_valider_pour,
    subordonnes_effectifs,
    suppleants_de,
)
from models.delegation import Delegation

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
    # Subordonnés effectifs = directs + ceux des responsables dont je suis suppléant actif.
    subordonnes_actifs = subordonnes_effectifs(current_user)
    subordonne_ids = [u.id for u in subordonnes_actifs]
    demandes_attente = (
        Conge.query.filter(Conge.user_id.in_(subordonne_ids), Conge.statut == "en_attente_responsable")
        .order_by(Conge.cree_le.asc()).all()
    ) if subordonne_ids else []

    # Conflits équipe : pour chaque demande, qui d'autre dans l'équipe est absent
    # sur la période ? Restreint au périmètre de subordonnés effectifs.
    from services.calcul_jours import conges_chevauchant
    conflits_par_conge = {}
    for c in demandes_attente:
        if not subordonne_ids:
            conflits_par_conge[c.id] = []
            continue
        conflits = conges_chevauchant(
            c.date_debut, c.date_fin, exclure_user_id=c.user_id
        )
        # On ne garde que les collègues du périmètre du responsable.
        conflits_filtres = [cc for cc in conflits if cc.user_id in subordonne_ids]
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
            for cc in conflits_filtres
        ]

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
        conflits_par_conge=conflits_par_conge,
        subordonnes=subordonnes_actifs,
        calendar_events=calendar_events,
    )

def _valider_un_conge_n1(conge):
    """Valide niveau 1 (responsable) un congé. Retourne (ok, message).
    Ne commit pas : caller décide.

    Accepte le responsable direct OU un suppléant actif.
    """
    if conge.statut != "en_attente_responsable":
        return False, f"Conge #{conge.id} : statut {conge.statut}, ignoré."
    u = conge.utilisateur
    if not u or not peut_valider_pour(current_user, u):
        return False, f"Conge #{conge.id} : vous n'êtes pas habilité à valider pour ce salarié."

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
    notifier_rh_demande_transmise(conge)
    return True, None


@responsable_bp.route("/conge/<int:conge_id>/valider", methods=["POST"])
@responsable_required
def valider_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    ok, err = _valider_un_conge_n1(conge)
    if not ok:
        flash(err or "Validation impossible.", "warning")
        return redirect(url_for("responsable.dashboard"))
    db.session.commit()
    flash("Demande validée. Transmise aux RH.", "success")
    return redirect(url_for("responsable.dashboard"))


@responsable_bp.route("/conges/valider-lots", methods=["POST"])
@responsable_required
def valider_lots():
    """Validation niveau 1 par lots."""
    ids = request.form.getlist("conge_ids")
    if not ids:
        flash("Aucun congé sélectionné.", "warning")
        return redirect(url_for("responsable.dashboard"))
    nb_ok = 0
    erreurs = []
    for cid in ids:
        try:
            conge = Conge.query.get(int(cid))
        except (ValueError, TypeError):
            continue
        if not conge:
            continue
        ok, err = _valider_un_conge_n1(conge)
        if ok:
            nb_ok += 1
        elif err:
            erreurs.append(err)
    db.session.commit()
    if nb_ok:
        flash(f"{nb_ok} demande(s) validée(s) et transmise(s) aux RH.", "success")
    for e in erreurs:
        flash(e, "warning")
    return redirect(url_for("responsable.dashboard"))


@responsable_bp.route("/conges/refuser-lots", methods=["POST"])
@responsable_required
def refuser_lots():
    """Refus niveau 1 par lots avec motif commun."""
    ids = request.form.getlist("conge_ids")
    motif = (request.form.get("motif_refus") or "").strip()
    if not ids:
        flash("Aucun congé sélectionné.", "warning")
        return redirect(url_for("responsable.dashboard"))
    if not motif:
        return render_template("responsable/refuser_lots.html", conge_ids=ids)

    nb_ok = 0
    for cid in ids:
        try:
            conge = Conge.query.get(int(cid))
        except (ValueError, TypeError):
            continue
        if not conge or conge.statut != "en_attente_responsable":
            continue
        u = conge.utilisateur
        # Même périmètre que la validation : responsable direct OU suppléant actif.
        if not u or not peut_valider_pour(current_user, u):
            continue
        conge.statut = "refuse"
        conge.valide_par_responsable_id = current_user.id
        conge.valide_par_responsable_le = datetime.now(timezone.utc)
        conge.motif_refus = motif
        log_action(
            "conge.refuser_n1",
            cible_type="conge",
            cible_id=conge.id,
            details={"user_id": conge.user_id, "motif": motif, "lot": True},
        )
        notifier_conge_refuse(conge, motif)
        nb_ok += 1

    db.session.commit()
    flash(f"{nb_ok} demande(s) refusée(s).", "success")
    return redirect(url_for("responsable.dashboard"))

@responsable_bp.route("/conge/<int:conge_id>/refuser", methods=["GET", "POST"])
@responsable_required
def refuser_conge(conge_id):
    conge = Conge.query.get_or_404(conge_id)
    if conge.statut != "en_attente_responsable":
        flash("Cette demande n'est pas en attente.", "warning")
        return redirect(url_for("responsable.dashboard"))
    u = conge.utilisateur
    if not u or not peut_valider_pour(current_user, u):
        flash("Vous n'êtes pas habilité à refuser pour ce salarié.", "error")
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
    if not peut_valider_pour(current_user, user):
        flash("Ce salarié n'est pas dans votre équipe (directe ou déléguée).", "error")
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


@responsable_bp.route("/delegations", methods=["GET", "POST"])
@responsable_required
def delegations():
    """Gestion des délégations (suppléant temporaire) pour le responsable connecté."""
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create":
            try:
                suppleant_id = int(request.form.get("suppleant_id", "0"))
                d_debut = datetime.strptime(request.form["date_debut"], "%Y-%m-%d").date()
                d_fin = datetime.strptime(request.form["date_fin"], "%Y-%m-%d").date()
            except (ValueError, KeyError, TypeError):
                flash("Données invalides.", "error")
                return redirect(url_for("responsable.delegations"))

            if d_fin < d_debut:
                flash("La date de fin doit être postérieure à la date de début.", "error")
                return redirect(url_for("responsable.delegations"))

            suppleant = User.query.get(suppleant_id)
            if not suppleant or not suppleant.actif:
                flash("Suppléant introuvable.", "error")
                return redirect(url_for("responsable.delegations"))
            if suppleant.id == current_user.id:
                flash("Vous ne pouvez pas vous désigner vous-même comme suppléant.", "error")
                return redirect(url_for("responsable.delegations"))
            if suppleant.role != "responsable":
                flash(
                    "Le suppléant doit être un autre responsable. Les RH valident déjà en niveau 2.",
                    "error",
                )
                return redirect(url_for("responsable.delegations"))

            d = Delegation(
                responsable_id=current_user.id,
                suppleant_id=suppleant.id,
                date_debut=d_debut,
                date_fin=d_fin,
                cree_par_id=current_user.id,
            )
            db.session.add(d)
            db.session.flush()
            log_action(
                "delegation.creer",
                cible_type="delegation",
                cible_id=d.id,
                details={
                    "responsable_id": current_user.id,
                    "suppleant_id": suppleant.id,
                    "periode": f"{d_debut} → {d_fin}",
                },
            )
            db.session.commit()
            flash("Délégation enregistrée.", "success")
            return redirect(url_for("responsable.delegations"))

        if action == "delete":
            try:
                did = int(request.form.get("delegation_id", "0"))
            except (ValueError, TypeError):
                did = 0
            d = Delegation.query.get(did)
            if d and d.responsable_id == current_user.id:
                log_action(
                    "delegation.supprimer",
                    cible_type="delegation",
                    cible_id=d.id,
                    details={
                        "suppleant_id": d.suppleant_id,
                        "periode": f"{d.date_debut} → {d.date_fin}",
                    },
                )
                db.session.delete(d)
                db.session.commit()
                flash("Délégation supprimée.", "success")
            return redirect(url_for("responsable.delegations"))

    sortantes = (
        Delegation.query.filter_by(responsable_id=current_user.id)
        .order_by(Delegation.date_debut.desc())
        .all()
    )
    entrantes = (
        Delegation.query.filter_by(suppleant_id=current_user.id)
        .order_by(Delegation.date_debut.desc())
        .all()
    )
    candidats = (
        User.query.filter(
            User.actif == True,
            User.id != current_user.id,
            User.role == "responsable",
        )
        .order_by(User.nom, User.prenom)
        .all()
    )
    return render_template(
        "responsable/delegations.html",
        sortantes=sortantes,
        entrantes=entrantes,
        candidats=candidats,
        aujourdhui=date.today(),
    )
