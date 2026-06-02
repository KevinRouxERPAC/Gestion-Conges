from models import db


class ParametrageAnnuel(db.Model):
    __tablename__ = "parametrage_annuel"

    id = db.Column(db.Integer, primary_key=True)
    debut_exercice = db.Column(db.Date, nullable=False)
    fin_exercice = db.Column(db.Date, nullable=False)
    jours_conges_defaut = db.Column(db.Integer, nullable=False, default=25)

    # RTT hebdomadaire (cf. services/rtt_hebdo.py).
    rtt_seuil_hebdo = db.Column(db.Integer, nullable=False, default=35)
    rtt_heures_par_jour_absence = db.Column(db.Integer, nullable=False, default=7)
    rtt_coef_surplus = db.Column(db.Float, nullable=False, default=0.0)

    actif = db.Column(db.Boolean, default=True)

    allocations = db.relationship("AllocationConge", backref="parametrage", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Parametrage {self.debut_exercice} - {self.fin_exercice}>"


class AllocationConge(db.Model):
    __tablename__ = "allocations_conges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    parametrage_id = db.Column(db.Integer, db.ForeignKey("parametrage_annuel.id"), nullable=False)

    # CP (en jours)
    jours_alloues = db.Column(db.Integer, nullable=False, default=25)
    jours_anciennete = db.Column(db.Integer, nullable=False, default=0)
    jours_report = db.Column(db.Integer, nullable=False, default=0)

    # RTT (en heures)
    rtt_heures_allouees = db.Column(db.Integer, nullable=False, default=0)
    rtt_heures_reportees = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (db.UniqueConstraint("user_id", "parametrage_id", name="uq_user_parametrage"),)

    @property
    def total_jours(self):
        return self.jours_alloues + self.jours_anciennete + self.jours_report

    @property
    def total_rtt_heures(self):
        return self.rtt_heures_allouees + self.rtt_heures_reportees

    def __repr__(self):
        return f"<Allocation user={self.user_id} jours={self.total_jours} rtt_heures={self.total_rtt_heures}>"
