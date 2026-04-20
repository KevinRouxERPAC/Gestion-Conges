from models import db


class ParametrageAnnuel(db.Model):
    __tablename__ = "parametrage_annuel"

    id = db.Column(db.Integer, primary_key=True)
    debut_exercice = db.Column(db.Date, nullable=False)
    fin_exercice = db.Column(db.Date, nullable=False)

    # Période des congés (CP / ancienneté) : 1er juin → 31 mai
    # Distincte de l'exercice comptable (1er avril → 31 mars).
    # Si NULL, on retombe sur debut_exercice / fin_exercice.
    debut_periode_conges = db.Column(db.Date, nullable=True)
    fin_periode_conges = db.Column(db.Date, nullable=True)

    jours_conges_defaut = db.Column(db.Integer, nullable=False, default=25)
    # Nombre d'heures RTT allouées par défaut pour l'exercice (0 si non utilisé)
    rtt_heures_defaut = db.Column(db.Integer, nullable=False, default=0)

    # Lot 4 - Calcul RTT depuis heures (optionnel)
    # Mode: 'fixe' -> rtt_heures_defaut ; 'heures' -> calcul basé sur heures_travaillees
    rtt_calc_mode = db.Column(db.String(10), nullable=False, default="fixe")
    rtt_heures_reference = db.Column(db.Integer, nullable=False, default=0)
    rtt_coef_surplus = db.Column(db.Float, nullable=False, default=0.0)

    actif = db.Column(db.Boolean, default=True)

    allocations = db.relationship("AllocationConge", backref="parametrage", lazy=True, cascade="all, delete-orphan")

    @property
    def periode_conges(self):
        """Bornes de la période CP/ancienneté (fallback sur l'exercice)."""
        debut = self.debut_periode_conges or self.debut_exercice
        fin = self.fin_periode_conges or self.fin_exercice
        return debut, fin

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
