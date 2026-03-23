from datetime import datetime, timezone

from models import db


class InteressementRegle(db.Model):
    __tablename__ = 'interessement_regles'

    id = db.Column(db.Integer, primary_key=True)
    periode_id = db.Column(db.Integer, db.ForeignKey('interessement_periodes.id'), nullable=False)

    # Type d'absence (ex: CP, RTT, Maladie, Sans solde, Anciennete, EXC:CODE)
    type_absence = db.Column(db.String(50), nullable=False)

    # Pondération par jour ouvrable (malus si positif)
    points_par_jour = db.Column(db.Float, nullable=False, default=0.0)

    cree_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    modifie_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    periode = db.relationship('InteressementPeriode', backref=db.backref('regles', lazy=True, cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('periode_id', 'type_absence', name='uq_interessement_periode_type'),
    )

    def __repr__(self):
        return f'InteressementRegle(id={self.id}, periode_id={self.periode_id}, type_absence={self.type_absence!r}, points_par_jour={self.points_par_jour})'
