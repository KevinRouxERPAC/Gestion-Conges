"""Envoi de notifications Web Push (hors du site, sans donnée personnelle)."""
import json
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# Compatibilité cryptography >= 42 : pywebpush passe la courbe en classe au lieu d'instance.
# On patche generate_private_key pour accepter les deux (évite "curve must be an EllipticCurve instance").
def _patch_ec_for_pywebpush():
    import cryptography.hazmat.primitives.asymmetric.ec as _ec
    if getattr(_ec.generate_private_key, "_erpac_curve_patch", False):
        return
    _orig = _ec.generate_private_key
    def _patched(curve, backend):
        if isinstance(curve, type):
            curve = curve()
        return _orig(curve, backend)
    _patched._erpac_curve_patch = True
    _ec.generate_private_key = _patched


_patch_ec_for_pywebpush()

# Import après le patch pour que pywebpush utilise generate_private_key corrigé
try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = Exception


def _vapid_private_key():
    """Retourne la clé privée VAPID (chemin fichier ou contenu PEM). Si env vide, tente vapid_private.pem dans BASE_DIR."""
    import os
    base_dir = current_app.config.get("BASE_DIR") or os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    key = (current_app.config.get("VAPID_PRIVATE_KEY") or "").strip()
    if not key:
        default_path = os.path.join(base_dir, "vapid_private.pem")
        if os.path.isfile(default_path):
            return default_path
        return None
    # Si ça ressemble à un chemin de fichier (sans \n), retourner le chemin pour que pywebpush charge le PEM
    if "\n" not in key and len(key) < 500:
        path = key if os.path.isabs(key) else os.path.join(base_dir, key)
        if os.path.isfile(path):
            return path
    return key


def envoyer_push_user(user_id: int, titre: str, message: str, url: str = None):
    """
    Envoie une notification Web Push à tous les abonnements de l'utilisateur.
    Ne fait rien si VAPID non configuré ou aucune subscription.
    """
    from models.push_subscription import PushSubscription

    private_key = _vapid_private_key()
    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
    if not private_key:
        logger.debug("Web Push: pas de clé VAPID (user_id=%s)", user_id)
        return

    if not subscriptions:
        logger.warning("Web Push: aucun abonnement pour user_id=%s (le salarié doit cliquer « Activer les alertes » dans ce navigateur)", user_id)
        return

    logger.info("Web Push: envoi à user_id=%s (%d abonnement(s))", user_id, len(subscriptions))
    payload = json.dumps({"title": titre, "body": message, "url": url or "/notifications/"})
    vapid_claims = {"sub": "mailto:conges@erpac.local"}

    if webpush is None:
        logger.warning("pywebpush non installé, Web Push désactivé.")
        return

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub.to_subscription_info(),
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=vapid_claims,
            )
            logger.info("Web Push: notification envoyée avec succès pour user_id=%s", user_id)
        except WebPushException as e:
            # 410 Gone / 404 = subscription expirée, on peut la supprimer
            if getattr(e, "response", None) and getattr(e.response, "status_code", None) in (410, 404):
                from models import db
                db.session.delete(sub)
                db.session.commit()
                logger.info("Abonnement push expiré supprimé pour user_id=%s", user_id)
            else:
                logger.exception("Erreur Web Push user_id=%s: %s", user_id, e)
        except Exception as e:
            logger.exception("Erreur Web Push user_id=%s: %s", user_id, e)
