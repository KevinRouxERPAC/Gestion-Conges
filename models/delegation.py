"""Délégation temporaire d'un responsable vers un suppléant.

Cas d'usage : un responsable part en congé. Pour ne pas bloquer la validation
des demandes de ses subordonnés, il désigne un suppléant pendant une période
donnée. Le suppléant voit les demandes en attente et peut valider/refuser au
même titre que le responsable.
"""
from datetime import date as date_cls, datetime, timezone

from models import db


class Delegation(db.Model):
    __tablename__ = "delegations"

    id = db.Column(db.Integer, primary_key=True)
    responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    suppleant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)
    cree_le = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # Acteur qui a créé la délégation (responsable lui-même ou RH).
    cree_par_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    responsable = db.relationship("User", foreign_keys=[responsable_id])
    suppleant = db.relationship("User", foreign_keys=[suppleant_id])
    cree_par = db.relationship("User", foreign_keys=[cree_par_id])

    @property
    def active(self) -> bool:
        today = date_cls.today()
        return self.date_debut <= today <= self.date_fin

    def __repr__(self):
        return (
            f"<Delegation resp={self.responsable_id} suppleant={self.suppleant_id} "
            f"{self.date_debut}→{self.date_fin}>"
        )
