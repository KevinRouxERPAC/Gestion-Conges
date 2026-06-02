from datetime import datetime, timezone

from models import db


class Justificatif(db.Model):
    """Pièce jointe liée à une absence (certificat médical, acte, etc.)."""

    __tablename__ = "justificatifs"

    id = db.Column(db.Integer, primary_key=True)
    conge_id = db.Column(db.Integer, db.ForeignKey("conges.id"), nullable=False, unique=True)
    nom_fichier = db.Column(db.String(255), nullable=False)
    nom_stockage = db.Column(db.String(255), nullable=False, unique=True)
    mime_type = db.Column(db.String(100), nullable=False)
    taille_octets = db.Column(db.Integer, nullable=False)
    upload_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    upload_le = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    conge = db.relationship(
        "Conge",
        backref=db.backref("justificatif", uselist=False, cascade="all, delete-orphan"),
    )
    upload_par = db.relationship("User", foreign_keys=[upload_par_id])

    def __repr__(self):
        return f"<Justificatif conge={self.conge_id} {self.nom_fichier}>"
