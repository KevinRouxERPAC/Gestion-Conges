from datetime import datetime, timezone

from models import db


class HeuresHebdo(db.Model):
    """Heures réellement travaillées par semaine (saisie RH).

    Sert au calcul RTT hebdomadaire tenant compte des absences : une semaine
    avec une absence (congé, arrêt maladie...) ne doit pas faire perdre de RTT
    au salarié. On stocke le lundi de la semaine ISO (`date_lundi`) pour faciliter
    le filtrage sur l'exercice et le rattachement des absences à la semaine.
    """

    __tablename__ = "heures_hebdo"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Lundi de la semaine ISO concernée.
    date_lundi = db.Column(db.Date, nullable=False)

    heures_travaillees = db.Column(db.Integer, nullable=False, default=0)

    source = db.Column(db.String(30), nullable=False, default="manuel")
    saisi_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    saisi_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date_lundi", name="uq_heures_hebdo_user_lundi"),
    )

    saisi_par = db.relationship("User", foreign_keys=[saisi_par_id])

    def __repr__(self):
        return f"<HeuresHebdo user={self.user_id} semaine_du={self.date_lundi} travaillees={self.heures_travaillees}>"
