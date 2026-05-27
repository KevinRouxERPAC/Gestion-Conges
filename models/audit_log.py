"""Trace des actions sensibles (RH, responsable) pour audit et débogage."""
from datetime import datetime, timezone

from models import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    cree_le = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    # Acteur qui a effectué l'action. Nullable pour supporter une action système
    # (ex. script de tâche planifiée) ou un acteur supprimé après coup.
    acteur_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    acteur_role = db.Column(db.String(20), nullable=True)  # snapshot du rôle au moment T
    # Action structurée : "scope.verbe", ex. "salarie.create", "conge.valider".
    action = db.Column(db.String(80), nullable=False, index=True)
    # Cible facultative (entité touchée).
    cible_type = db.Column(db.String(40), nullable=True)
    cible_id = db.Column(db.Integer, nullable=True, index=True)
    # Détail libre (JSON sérialisé sous forme de string, par simplicité SQLite).
    details = db.Column(db.Text, nullable=True)

    acteur = db.relationship("User", foreign_keys=[acteur_id])

    def __repr__(self):
        return f"<AuditLog {self.cree_le} {self.action} acteur={self.acteur_id} cible={self.cible_type}/{self.cible_id}>"
