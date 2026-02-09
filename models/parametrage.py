from models import db


class ParametrageAnnuel(db.Model):
    __tablename__ = "parametrage_annuel"

    id = db.Column(db.Integer, primary_key=True)
    debut_exercice = db.Column(db.Date, nullable=False)
    fin_exercice = db.Column(db.Date, nullable=False)
    jours_conges_defaut = db.Column(db.Integer, nullable=False, default=25)
    actif = db.Column(db.Boolean, default=True)

    allocations = db.relationship("AllocationConge", backref="parametrage", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Parametrage {self.debut_exercice} - {self.fin_exercice}>"


class AllocationConge(db.Model):
    __tablename__ = "allocations_conges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    parametrage_id = db.Column(db.Integer, db.ForeignKey("parametrage_annuel.id"), nullable=False)
    jours_alloues = db.Column(db.Integer, nullable=False, default=25)
    jours_anciennete = db.Column(db.Integer, nullable=False, default=0)
    jours_report = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (db.UniqueConstraint("user_id", "parametrage_id", name="uq_user_parametrage"),)

    @property
    def total_jours(self):
        return self.jours_alloues + self.jours_anciennete + self.jours_report

    def __repr__(self):
        return f"<Allocation user={self.user_id} jours={self.total_jours}>"
