from datetime import datetime
from models import db


class Notification(db.Model):
    """Notification in-app (sans email) : validation/refus de congé pour le salarié, nouvelle demande pour les RH."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # conge_valide, conge_refuse, nouvelle_demande_conge
    titre = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    lue = db.Column(db.Boolean, default=False, nullable=False)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    conge_id = db.Column(db.Integer, db.ForeignKey("conges.id"), nullable=True)

    utilisateur = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))
    conge = db.relationship("Conge", backref="notifications", foreign_keys=[conge_id])

    def __repr__(self):
        return f"<Notification {self.type} pour user={self.user_id} lue={self.lue}>"
