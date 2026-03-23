from datetime import date, datetime, timezone

from models import db


class InteressementPeriode(db.Model):
    __tablename__ = 'interessement_periodes'

    id = db.Column(db.Integer, primary_key=True)
    libelle = db.Column(db.String(120), nullable=False)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)

    base_points = db.Column(db.Integer, nullable=False, default=100)
    plancher_points = db.Column(db.Integer, nullable=False, default=0)

    actif = db.Column(db.Boolean, nullable=False, default=False)
    cree_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    modifie_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'InteressementPeriode(id={self.id}, libelle={self.libelle!r}, debut={self.date_debut}, fin={self.date_fin}, actif={self.actif})'

    @property
    def is_valid_dates(self) -> bool:
        if not isinstance(self.date_debut, date) or not isinstance(self.date_fin, date):
            return False
        return self.date_fin >= self.date_debut
