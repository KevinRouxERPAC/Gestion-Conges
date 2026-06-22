"""Gestion sécurisée des justificatifs liés aux absences."""
from __future__ import annotations

import os
import uuid
from typing import Optional

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from models import db
from models.conge import Conge
from models.justificatif import Justificatif
from models.user import User
from services.audit import log_action
from services.conges_exceptionnels import get_type_exceptionnel, parse_code

ALLOWED_MIMES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
ALLOWED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})


def _storage_dir() -> str:
    path = current_app.config.get("JUSTIFICATIFS_DIR") or os.path.join(
        current_app.config["BASE_DIR"], "instance", "justificatifs"
    )
    os.makedirs(path, exist_ok=True)
    return path


def _detect_mime(content: bytes) -> Optional[str]:
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def justificatif_requis_pour_type(type_conge: str) -> bool:
    """Maladie toujours requis ; EXC selon le flag sur CongeExceptionnelType."""
    if type_conge == "Maladie":
        return True
    code = parse_code(type_conge or "")
    if not code:
        return False
    exc_type = get_type_exceptionnel(code)
    return bool(exc_type and exc_type.justificatif_requis)


def a_justificatif(conge: Conge) -> bool:
    return conge.justificatif is not None


def peut_televerser_justificatif(user: User) -> bool:
    return user.role == "rh"


def peut_consulter_justificatif(user: User, conge: Conge) -> bool:
    if user.role == "rh":
        return True
    return user.role == "salarie" and conge.user_id == user.id


def chemin_stockage(nom_stockage: str) -> str:
    return os.path.join(_storage_dir(), nom_stockage)


def enregistrer_justificatif(conge: Conge, fichier: FileStorage, acteur: User) -> Optional[str]:
    """Enregistre ou remplace le justificatif d'un congé. Retourne un message d'erreur ou None."""
    if not peut_televerser_justificatif(acteur):
        return "Vous n'êtes pas autorisé à déposer un justificatif."

    if not fichier or not fichier.filename:
        return "Aucun fichier sélectionné."

    content = fichier.read()
    if not content:
        return "Le fichier est vide."

    max_size = int(current_app.config.get("MAX_CONTENT_LENGTH") or 5 * 1024 * 1024)
    if len(content) > max_size:
        return f"Fichier trop volumineux (max {max_size // (1024 * 1024)} Mo)."

    mime = _detect_mime(content)
    if mime not in ALLOWED_MIMES:
        return "Format non autorisé. Formats acceptés : PDF, JPEG, PNG."

    ext = os.path.splitext(secure_filename(fichier.filename) or "")[1].lower()
    if ext == ".jpeg":
        ext = ".jpg"
    if ext not in ALLOWED_EXTENSIONS:
        return "Extension non autorisée. Formats acceptés : PDF, JPEG, PNG."

    expected_ext = ALLOWED_MIMES[mime]
    if ext != expected_ext and not (ext == ".jpg" and mime == "image/jpeg"):
        return "Le contenu du fichier ne correspond pas à son extension."

    nom_original = secure_filename(fichier.filename) or f"justificatif{expected_ext}"
    nom_stockage = f"{uuid.uuid4().hex}{expected_ext}"
    full_path = chemin_stockage(nom_stockage)

    with open(full_path, "wb") as fh:
        fh.write(content)

    existing = conge.justificatif
    if existing:
        _supprimer_fichier(existing.nom_stockage)
        existing.nom_fichier = nom_original
        existing.nom_stockage = nom_stockage
        existing.mime_type = mime
        existing.taille_octets = len(content)
        existing.upload_par_id = acteur.id
        action = "justificatif.remplacer"
    else:
        # On lie l'objet via la relation (conge=conge) plutôt que par conge_id :
        # le backref `conge.justificatif` est ainsi peuplé immédiatement en mémoire.
        # Indispensable car la route appelle verifier_justificatif_obligatoire()
        # juste après, dans la même transaction (avant tout flush/commit) ; avec
        # conge_id seul, la relation serait restée en cache à None et la
        # vérification aurait rejeté à tort un justificatif pourtant fourni.
        db.session.add(
            Justificatif(
                conge=conge,
                nom_fichier=nom_original,
                nom_stockage=nom_stockage,
                mime_type=mime,
                taille_octets=len(content),
                upload_par_id=acteur.id,
            )
        )
        action = "justificatif.upload"

    log_action(
        action,
        cible_type="conge",
        cible_id=conge.id,
        details={
            "user_id": conge.user_id,
            "type_conge": conge.type_conge,
            "nom_fichier": nom_original,
            "taille_octets": len(content),
            "mime_type": mime,
        },
    )
    return None


def _supprimer_fichier(nom_stockage: str) -> None:
    path = chemin_stockage(nom_stockage)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            current_app.logger.warning("Impossible de supprimer le justificatif %s", nom_stockage)


def supprimer_justificatif(conge: Conge, acteur: User) -> Optional[str]:
    if not peut_televerser_justificatif(acteur):
        return "Vous n'êtes pas autorisé à supprimer un justificatif."
    j = conge.justificatif
    if not j:
        return None
    _supprimer_fichier(j.nom_stockage)
    log_action(
        "justificatif.supprimer",
        cible_type="conge",
        cible_id=conge.id,
        details={"user_id": conge.user_id, "nom_fichier": j.nom_fichier},
    )
    db.session.delete(j)
    return None


def verifier_justificatif_obligatoire(conge: Conge) -> Optional[str]:
    if justificatif_requis_pour_type(conge.type_conge) and not a_justificatif(conge):
        return "Un justificatif est obligatoire pour ce type d'absence."
    return None
