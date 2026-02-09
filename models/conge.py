from datetime import datetime
from models import db


class Conge(db.Model):
    __tablename__ = "conges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)
    nb_jours_ouvrables = db.Column(db.Integer, nullable=False)
    type_conge = db.Column(db.String(50), nullable=False, default="CP")  # CP, RTT, Sans solde, Maladie, Anciennete
    commentaire = db.Column(db.Text, nullable=True)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    modifie_le = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Conge {self.date_debut} - {self.date_fin} ({self.nb_jours_ouvrables}j)>"
