"""Blueprint des notifications in-app et Web Push."""
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from models import db
from models.notification import Notification
from models.push_subscription import PushSubscription
from services.notifications import compter_non_lues

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/count")
@login_required
def count():
    """Compteur JSON pour mise à jour du badge sans recharger la page."""
    return jsonify({"count": compter_non_lues(current_user.id)})


@notifications_bp.route("/")
@login_required
def liste():
    """Liste des notifications de l'utilisateur connecté."""
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.cree_le.desc())
        .limit(100)
        .all()
    )
    return render_template("notifications/liste.html", notifications=notifications)


@notifications_bp.route("/<int:notification_id>/voir")
@login_required
def voir(notification_id):
    """Ouvre une notification : marque comme lue et redirige (RH → page salarié, salarié → mes congés)."""
    notif = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    notif.lue = True
    db.session.commit()
    if notif.conge_id and notif.conge:
        if current_user.role == "rh":
            return redirect(url_for("rh.salarie_detail", user_id=notif.conge.user_id))
        return redirect(url_for("salarie.accueil"))
    return redirect(url_for("notifications.liste"))


@notifications_bp.route("/<int:notification_id>/lire", methods=["POST"])
@login_required
def marquer_lue(notification_id):
    """Marque une notification comme lue (si elle appartient à l'utilisateur)."""
    notif = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    notif.lue = True
    db.session.commit()
    if request.referrer and "notifications" in (request.referrer or ""):
        return redirect(url_for("notifications.liste"))
    return redirect(request.referrer or url_for("salarie.accueil" if current_user.role == "salarie" else "rh.dashboard"))


@notifications_bp.route("/tout-lire", methods=["POST"])
@login_required
def tout_marquer_lues():
    """Marque toutes les notifications de l'utilisateur comme lues."""
    Notification.query.filter_by(user_id=current_user.id, lue=False).update({"lue": True})
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.liste"))


@notifications_bp.route("/vapid-public")
def vapid_public():
    """Clé publique VAPID pour l'abonnement Web Push (côté navigateur). Si env vide, dérivée de vapid_private.pem."""
    from flask import current_app
    import os
    key = current_app.config.get("VAPID_PUBLIC_KEY") or ""
    if not key.strip():
        base_dir = current_app.config.get("BASE_DIR") or os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        pem_path = os.path.join(base_dir, "vapid_private.pem")
        if os.path.isfile(pem_path):
            try:
                from vapid import Vapid01
            except ImportError:
                from py_vapid import Vapid01
            from cryptography.hazmat.primitives import serialization
            try:
                from py_vapid.utils import b64urlencode
            except ImportError:
                from vapid.utils import b64urlencode
            v = Vapid01.from_file(pem_path)
            pub_bytes = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
            key = b64urlencode(pub_bytes)
            if isinstance(key, bytes):
                key = key.decode("ascii")
    return jsonify({"vapid_public_key": key})


@notifications_bp.route("/push-subscribe", methods=["POST"])
@login_required
def push_subscribe():
    """Enregistre l'abonnement Web Push du navigateur pour l'utilisateur connecté."""
    data = request.get_json()
    if not data or "endpoint" not in data or "keys" not in data:
        return jsonify({"ok": False, "error": "Données d'abonnement invalides"}), 400
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh") or keys.get("p256dh")
    auth = keys.get("auth")
    if not p256dh or not auth:
        return jsonify({"ok": False, "error": "Clés p256dh et auth requises"}), 400
    endpoint = data["endpoint"].strip()
    existing = PushSubscription.query.filter_by(user_id=current_user.id, endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        db.session.commit()
    else:
        db.session.add(PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
        ))
        db.session.commit()
    return jsonify({"ok": True})
