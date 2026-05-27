"""Service d'écriture des entrées d'audit.

Le service ne `commit` jamais : il ajoute à la session en cours. C'est la route
qui appelle `db.session.commit()` après son propre traitement, ce qui garantit
que l'audit log et la modification métier vivent (ou tombent) ensemble dans la
même transaction.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from flask_login import current_user

from models import db
from models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    action: str,
    *,
    cible_type: Optional[str] = None,
    cible_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Ajoute une entrée d'audit à la session courante.

    Args:
        action: identifiant de l'action ("salarie.create", "conge.valider", ...).
            Convention : "<scope>.<verbe>" en snake_case.
        cible_type: type métier de l'entité touchée (ex. "user", "conge").
        cible_id: clé primaire de l'entité.
        details: dict sérialisable, conservé en JSON. Mettez le minimum utile à
            une investigation (avant/après pour les modifications, motif pour
            les refus, etc.). Ne mettez pas de mots de passe ni d'autres secrets.

    L'acteur est récupéré depuis `current_user` si disponible. Si l'appel est
    fait hors contexte requête (ex. script), `acteur_id` est laissé NULL.
    """
    acteur_id = None
    acteur_role = None
    try:
        if current_user and current_user.is_authenticated:
            acteur_id = current_user.id
            acteur_role = current_user.role
    except Exception:
        # current_user peut échouer en dehors d'une requête.
        pass

    details_json = None
    if details is not None:
        try:
            details_json = json.dumps(details, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            logger.warning("audit: details non sérialisables pour action=%s : %s", action, e)
            details_json = json.dumps({"_warning": "details_non_serialisables"})

    entry = AuditLog(
        acteur_id=acteur_id,
        acteur_role=acteur_role,
        action=action,
        cible_type=cible_type,
        cible_id=cible_id,
        details=details_json,
    )
    db.session.add(entry)
