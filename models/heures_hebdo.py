from datetime import datetime, timezone

from models import db


class HeuresHebdoSaisie(db.Model):
    __tablename__ = "heures_hebdo_saisies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    annee_iso = db.Column(db.Integer, nullable=False)
    semaine_iso = db.Column(db.Integer, nullable=False)  # 1..53

    heures_prevues = db.Column(db.Float, nullable=False, default=34.65)
    heures_travaillees = db.Column(db.Float, nullable=False, default=0.0)
    heures_sup = db.Column(db.Float, nullable=False, default=0.0)
    heures_trajet = db.Column(db.Float, nullable=False, default=0.0)
    heures_absence = db.Column(db.Float, nullable=False, default=0.0)

    # Indicateur qu'il s'agit d'une semaine marquée RTT côté RH (information de suivi)
    is_semaine_rtt = db.Column(db.Boolean, nullable=False, default=False)

    statut = db.Column(db.String(20), nullable=False, default="brouillon")  # brouillon|valide
    saisi_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    saisi_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    valide_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    valide_le = db.Column(db.DateTime, nullable=True)

    saisi_par = db.relationship("User", foreign_keys=[saisi_par_id])
    valide_par = db.relationship("User", foreign_keys=[valide_par_id])

    __table_args__ = (
        db.UniqueConstraint("user_id", "annee_iso", "semaine_iso", name="uq_heures_hebdo_user_annee_semaine"),
    )


class HeuresHebdoVerrou(db.Model):
    __tablename__ = "heures_hebdo_verrous"

    id = db.Column(db.Integer, primary_key=True)
    annee_iso = db.Column(db.Integer, nullable=False)
    semaine_iso = db.Column(db.Integer, nullable=False)
    verrouille = db.Column(db.Boolean, nullable=False, default=False)
    valide_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    valide_le = db.Column(db.DateTime, nullable=True)

    valide_par = db.relationship("User", foreign_keys=[valide_par_id])

    __table_args__ = (
        db.UniqueConstraint("annee_iso", "semaine_iso", name="uq_heures_hebdo_verrou_annee_semaine"),
    )
