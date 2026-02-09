from models import db


class JourFerie(db.Model):
    __tablename__ = "jours_feries"

    id = db.Column(db.Integer, primary_key=True)
    date_ferie = db.Column(db.Date, nullable=False)
    libelle = db.Column(db.String(100), nullable=False)
    annee = db.Column(db.Integer, nullable=False)
    auto_genere = db.Column(db.Boolean, default=True)

    __table_args__ = (db.UniqueConstraint("date_ferie", name="uq_date_ferie"),)

    def __repr__(self):
        return f"<JourFerie {self.libelle} ({self.date_ferie})>"
