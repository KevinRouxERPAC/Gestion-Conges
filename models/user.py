from flask_login import UserMixin
from models import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    identifiant = db.Column(db.String(100), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="salarie")  # "rh", "salarie" ou "responsable"
    actif = db.Column(db.Boolean, default=True)
    date_embauche = db.Column(db.Date, nullable=True)
    email = db.Column(db.String(120), nullable=True)  # pour les notifications
    responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # responsable hiérarchique (pour validation niveau 1)

    responsable = db.relationship("User", remote_side="User.id", foreign_keys=[responsable_id], backref="subordonnes")

    conges = db.relationship(
        "Conge",
        foreign_keys="Conge.user_id",
        backref="utilisateur",
        lazy=True,
        cascade="all, delete-orphan",
    )
    allocations = db.relationship("AllocationConge", backref="utilisateur", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.prenom} {self.nom} ({self.role})>"
