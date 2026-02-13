"""
Import / mise a jour des salaries depuis CSV ou Excel.
Cle: identifiant. Creation si absent, mise a jour si present.
"""
import csv
import io
import re
from datetime import datetime
from typing import Callable

from openpyxl import load_workbook

COL_IDENTIFIANT = ("identifiant", "login", "matricule")
COL_NOM = ("nom", "nom_famille", "lastname")
COL_PRENOM = ("prenom", "prenom_usage", "firstname")
COL_EMAIL = ("email", "mail", "courriel")
COL_DATE_EMBAUCHE = ("date_embauche", "date_entree", "embauche")
COL_ROLE = ("role", "type", "profil")
COL_ACTIF = ("actif", "actif_yn", "statut")


def _norm(s):
    if not s:
        return ""
    s = str(s).strip().lower().replace(" ", "_")
    return re.sub(r"_+", "_", s)


def _find_col(headers, candidates):
    for i, h in enumerate(headers):
        n = _norm(h)
        for c in candidates:
            if _norm(c) == n:
                return i
    return None


def _parse_date(val):
    if val is None or (isinstance(val, str) and not val.strip()):
        return None
    if hasattr(val, "date"):
        return val.date()
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_bool(val):
    if val is None:
        return True
    s = str(val).strip().lower()
    if s in ("1", "oui", "yes", "true", "o"):
        return True
    if s in ("0", "non", "no", "false", "n"):
        return False
    return True


def parse_csv(content):
    """Parse un CSV avec en-tete. Retourne liste de dicts."""
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.reader(io.StringIO(text), delimiter=";")
    try:
        first_row = next(reader)
    except StopIteration:
        return []
    if not first_row:
        return []
    if "," in (first_row[0] or "") and ";" not in (first_row[0] or ""):
        reader = csv.reader(io.StringIO(text), delimiter=",")
        first_row = next(reader)
    else:
        reader = csv.reader(io.StringIO(text), delimiter=";")
        first_row = next(reader)
    headers = [str(h).strip() for h in first_row]
    idx_id = _find_col(headers, COL_IDENTIFIANT)
    idx_nom = _find_col(headers, COL_NOM)
    idx_prenom = _find_col(headers, COL_PRENOM)
    if idx_id is None or idx_nom is None or idx_prenom is None:
        return []
    idx_email = _find_col(headers, COL_EMAIL)
    idx_date = _find_col(headers, COL_DATE_EMBAUCHE)
    idx_role = _find_col(headers, COL_ROLE)
    idx_actif = _find_col(headers, COL_ACTIF)

    rows = []
    for row in reader:
        row = list(row)
        if len(row) <= max(idx_id, idx_nom, idx_prenom):
            continue
        identifiant = (row[idx_id] or "").strip()
        nom = (row[idx_nom] or "").strip()
        prenom = (row[idx_prenom] or "").strip()
        if not identifiant or not nom or not prenom:
            continue
        email = (row[idx_email] or "").strip() if idx_email is not None and idx_email < len(row) else ""
        date_embauche = _parse_date(row[idx_date] if idx_date is not None and idx_date < len(row) else None)
        role_raw = (row[idx_role] or "salarie").strip() if idx_role is not None and idx_role < len(row) else "salarie"
        role = "rh" if str(role_raw).lower() in ("rh", "admin") else "salarie"
        actif = _parse_bool(row[idx_actif] if idx_actif is not None and idx_actif < len(row) else True)
        rows.append({
            "identifiant": identifiant,
            "nom": nom,
            "prenom": prenom,
            "email": email or None,
            "date_embauche": date_embauche,
            "role": role,
            "actif": actif,
        })
    return rows


def parse_excel(content):
    """Parse la premiere feuille Excel. Meme structure que parse_csv."""
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        first_row = next(rows_iter)
    except StopIteration:
        return []
    headers = [str(h).strip() if h is not None else "" for h in first_row]
    idx_id = _find_col(headers, COL_IDENTIFIANT)
    idx_nom = _find_col(headers, COL_NOM)
    idx_prenom = _find_col(headers, COL_PRENOM)
    if idx_id is None or idx_nom is None or idx_prenom is None:
        return []
    idx_email = _find_col(headers, COL_EMAIL)
    idx_date = _find_col(headers, COL_DATE_EMBAUCHE)
    idx_role = _find_col(headers, COL_ROLE)
    idx_actif = _find_col(headers, COL_ACTIF)

    rows = []
    for row in rows_iter:
        row = list(row) if row else []
        if len(row) <= max(idx_id, idx_nom, idx_prenom):
            continue
        identifiant = (row[idx_id] or "").strip() if idx_id < len(row) else ""
        nom = (row[idx_nom] or "").strip() if idx_nom < len(row) else ""
        prenom = (row[idx_prenom] or "").strip() if idx_prenom < len(row) else ""
        if not identifiant or not nom or not prenom:
            continue
        email = (row[idx_email] or "").strip() if idx_email is not None and idx_email < len(row) else ""
        date_embauche = _parse_date(row[idx_date] if idx_date is not None and idx_date < len(row) else None)
        role_raw = (row[idx_role] or "salarie")
        role = "rh" if str(role_raw).lower() in ("rh", "admin") else "salarie"
        actif = _parse_bool(row[idx_actif] if idx_actif is not None and idx_actif < len(row) else True)
        rows.append({
            "identifiant": identifiant,
            "nom": nom,
            "prenom": prenom,
            "email": email or None,
            "date_embauche": date_embauche,
            "role": role,
            "actif": actif,
        })
    return rows


def sync_users(rows, default_password, hash_password):
    """
    Cree ou met a jour les utilisateurs. Cle: identifiant.
    Retourne: (created, updated, errors).
    """
    from models.user import User
    from models import db

    created = 0
    updated = 0
    errors = []

    for i, row in enumerate(rows):
        identifiant = (row.get("identifiant") or "").strip()
        nom = (row.get("nom") or "").strip()
        prenom = (row.get("prenom") or "").strip()
        if not identifiant or not nom or not prenom:
            errors.append("Ligne %d: identifiant, nom et prenom obligatoires." % (i + 2))
            continue
        user = User.query.filter_by(identifiant=identifiant).first()
        if user:
            user.nom = nom
            user.prenom = prenom
            user.email = (row.get("email") or "").strip() or None
            user.date_embauche = row.get("date_embauche")
            user.role = (row.get("role") or "salarie").strip() or "salarie"
            if user.role != "rh":
                user.role = "salarie"
            user.actif = row.get("actif", True)
            updated += 1
        else:
            if not default_password or len(default_password) < 6:
                errors.append("Ligne %d (%s): mot de passe par defaut requis (min. 6 car.) pour les nouveaux." % (i + 2, identifiant))
                continue
            new_user = User(
                identifiant=identifiant,
                nom=nom,
                prenom=prenom,
                mot_de_passe_hash=hash_password(default_password),
                role=(row.get("role") or "salarie").strip() or "salarie",
                actif=row.get("actif", True),
                email=(row.get("email") or "").strip() or None,
                date_embauche=row.get("date_embauche"),
            )
            if new_user.role != "rh":
                new_user.role = "salarie"
            db.session.add(new_user)
            created += 1

    return created, updated, errors
