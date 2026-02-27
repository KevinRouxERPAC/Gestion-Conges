"""Abonnement Web Push par utilisateur (aucune donnée personnelle, juste endpoint + clés)."""
from datetime import datetime, timezone
from models import db


class PushSubscription(db.Model):
    """Abonnement push navigateur pour un utilisateur (plusieurs appareils/navigateurs possibles)."""
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.String(255), nullable=False)  # clé publique client
    auth = db.Column(db.String(255), nullable=False)
    cree_le = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    utilisateur = db.relationship("User", backref=db.backref("push_subscriptions", lazy="dynamic", cascade="all, delete-orphan"))

    # Un même endpoint par utilisateur = une seule entrée (évite doublons si re-souscription)
    __table_args__ = (db.UniqueConstraint("user_id", "endpoint", name="uq_push_user_endpoint"),)

    def to_subscription_info(self):
        """Format attendu par pywebpush."""
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }
