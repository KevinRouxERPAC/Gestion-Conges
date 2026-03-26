from datetime import datetime

from models import db
from models.conge_exceptionnel_type import CongeExceptionnelType
from models.interessement_periode import InteressementPeriode
from models.interessement_regle import InteressementRegle


def handle_types_exceptionnels_action(form) -> tuple[str, str]:
    action = form.get("action")

    if action == "create":
        code = (form.get("code") or "").strip().upper()
        libelle = (form.get("libelle") or "").strip()
        unite = (form.get("unite") or "jours").strip() or "jours"
        plafond_str = (form.get("plafond_annuel") or "").strip()
        plafond = None
        if plafond_str:
            try:
                plafond = int(plafond_str)
            except ValueError:
                plafond = None

        if not code or not libelle or unite not in ("jours", "heures"):
            return "error", "Données invalides."

        existing = CongeExceptionnelType.query.filter_by(code=code).first()
        if existing:
            return "error", "Un type avec ce code existe déjà."

        t = CongeExceptionnelType(code=code, libelle=libelle, unite=unite, plafond_annuel=plafond, actif=True)
        db.session.add(t)
        db.session.commit()
        return "success", "Type ajouté."

    if action == "update":
        try:
            type_id = int(form.get("type_id") or "0")
        except ValueError:
            type_id = 0

        t = CongeExceptionnelType.query.get(type_id)
        if not t:
            return "error", "Type introuvable."

        libelle = (form.get("libelle") or "").strip()
        unite = (form.get("unite") or "jours").strip() or "jours"
        plafond_str = (form.get("plafond_annuel") or "").strip()
        plafond = None
        if plafond_str:
            try:
                plafond = int(plafond_str)
            except ValueError:
                plafond = None

        if not libelle or unite not in ("jours", "heures"):
            return "error", "Données invalides."

        t.libelle = libelle
        t.unite = unite
        t.plafond_annuel = plafond
        db.session.commit()
        return "success", "Type mis à jour."

    if action == "toggle":
        try:
            type_id = int(form.get("type_id") or "0")
        except ValueError:
            type_id = 0

        t = CongeExceptionnelType.query.get(type_id)
        if not t:
            return "error", "Type introuvable."

        t.actif = not bool(t.actif)
        db.session.commit()
        return "success", "Statut mis à jour."

    return "warning", "Action inconnue."


def handle_interessement_action(form, *, periode_id: int | None = None) -> tuple[str, str]:
    action = form.get("action", "")

    if action == "create_periode":
        libelle = (form.get("libelle") or "").strip()
        date_debut_str = (form.get("date_debut") or "").strip()
        date_fin_str = (form.get("date_fin") or "").strip()
        base_points_str = (form.get("base_points") or "100").strip()
        plancher_str = (form.get("plancher_points") or "0").strip()

        if not libelle or not date_debut_str or not date_fin_str:
            return "error", "Libellé, date de début et date de fin sont obligatoires."

        try:
            d_debut = datetime.strptime(date_debut_str, "%Y-%m-%d").date()
            d_fin = datetime.strptime(date_fin_str, "%Y-%m-%d").date()
        except ValueError:
            return "error", "Format de date invalide."

        if d_fin < d_debut:
            return "error", "La date de fin doit être postérieure à la date de début."

        try:
            base_points = int(base_points_str)
            plancher_points = int(plancher_str)
        except ValueError:
            return "error", "Base et plancher doivent être des entiers."

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
        return "success", "Période créée."

    if action == "toggle_periode":
        try:
            pid = int(form.get("periode_id") or "0")
        except ValueError:
            pid = 0
        p = InteressementPeriode.query.get(pid)
        if p:
            p.actif = not p.actif
            db.session.commit()
            return "success", "Statut mis à jour."
        return "warning", "Période introuvable."

    if action == "delete_periode":
        try:
            pid = int(form.get("periode_id") or "0")
        except ValueError:
            pid = 0
        p = InteressementPeriode.query.get(pid)
        if p:
            db.session.delete(p)
            db.session.commit()
            return "success", "Période supprimée."
        return "warning", "Période introuvable."

    if action == "add_regle":
        if not periode_id:
            return "error", "Période introuvable."
        type_absence = (form.get("type_absence") or "").strip()
        ppj_str = (form.get("points_par_jour") or "0").strip()

        if not type_absence:
            return "error", "Type d’absence obligatoire."

        existing = InteressementRegle.query.filter_by(periode_id=periode_id, type_absence=type_absence).first()
        if existing:
            return "error", "Une règle existe déjà pour ce type d’absence."

        try:
            ppj = float(ppj_str)
        except ValueError:
            ppj = 0.0

        r = InteressementRegle(periode_id=periode_id, type_absence=type_absence, points_par_jour=ppj)
        db.session.add(r)
        db.session.commit()
        return "success", "Règle ajoutée."

    if action == "update_regles":
        if not periode_id:
            return "error", "Période introuvable."
        regles = InteressementRegle.query.filter_by(periode_id=periode_id).all()
        for r in regles:
            ppj_str = (form.get(f"ppj_{r.id}") or "").strip()
            if ppj_str:
                try:
                    r.points_par_jour = float(ppj_str)
                except ValueError:
                    pass
        db.session.commit()
        return "success", "Règles mises à jour."

    if action == "delete_regle":
        if not periode_id:
            return "error", "Période introuvable."
        try:
            rid = int(form.get("regle_id") or "0")
        except ValueError:
            rid = 0
        r = InteressementRegle.query.get(rid)
        if r and r.periode_id == periode_id:
            db.session.delete(r)
            db.session.commit()
            return "success", "Règle supprimée."
        return "warning", "Règle introuvable."

    return "warning", "Action inconnue."
