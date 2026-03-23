from datetime import datetime, timezone
from models import db


class Conge(db.Model):
    __tablename__ = "conges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)
    nb_jours_ouvrables = db.Column(db.Integer, nullable=False)
    type_conge = db.Column(db.String(50), nullable=False, default="CP")  # CP, RTT, Sans solde, Maladie, Anciennete
    # Pour RTT uniquement : nombre d'heures consommées (sinon NULL)
    nb_heures_rtt = db.Column(db.Integer, nullable=True)
    nb_heures_exceptionnelles = db.Column(db.Integer, nullable=True)
    commentaire = db.Column(db.Text, nullable=True)
    cree_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    modifie_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Workflow validation 2 niveaux : en_attente_responsable → en_attente_rh → valide | refuse
    statut = db.Column(db.String(30), nullable=False, default="valide")  # en_attente_responsable, en_attente_rh, valide, refuse
    valide_par_responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    valide_par_responsable_le = db.Column(db.DateTime, nullable=True)
    valide_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # RH (validation niveau 2)
    valide_le = db.Column(db.DateTime, nullable=True)
    motif_refus = db.Column(db.Text, nullable=True)

    valide_par_responsable = db.relationship("User", foreign_keys=[valide_par_responsable_id])
    valide_par = db.relationship("User", foreign_keys=[valide_par_id])

    def __repr__(self):
        return f"<Conge {self.date_debut} - {self.date_fin} ({self.nb_jours_ouvrables}j) [{self.statut}]>"
