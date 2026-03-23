from datetime import datetime, timezone

from models import db


class HeuresPayees(db.Model):
    __tablename__ = "heures_payees"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    annee = db.Column(db.Integer, nullable=False)
    mois = db.Column(db.Integer, nullable=False)  # 1..12

    heures_payees = db.Column(db.Integer, nullable=False, default=0)
    heures_trajet = db.Column(db.Integer, nullable=False, default=0)
    heures_travaillees = db.Column(db.Integer, nullable=False, default=0)

    source = db.Column(db.String(30), nullable=False, default="manuel")
    saisi_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    saisi_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "annee", "mois", name="uq_heures_user_annee_mois"),
    )

    saisi_par = db.relationship("User", foreign_keys=[saisi_par_id])

    def __repr__(self):
        return f"<HeuresPayees user={self.user_id} {self.mois:02d}/{self.annee} payees={self.heures_payees}>"
