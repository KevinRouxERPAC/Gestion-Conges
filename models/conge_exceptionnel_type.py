from models import db


class CongeExceptionnelType(db.Model):
    __tablename__ = "conges_exceptionnels_types"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), nullable=False, unique=True)  # ex: "MARIAGE"
    libelle = db.Column(db.String(120), nullable=False)  # ex: "Mariage"
    unite = db.Column(db.String(10), nullable=False, default="jours")  # "jours" | "heures"
    plafond_annuel = db.Column(db.Integer, nullable=True)  # en jours ou heures selon unite
    actif = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<CongeExceptionnelType {self.code} ({self.unite}) actif={self.actif}>"

