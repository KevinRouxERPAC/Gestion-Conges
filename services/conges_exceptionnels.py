from sqlalchemy import func

from models import db
from models.conge import Conge
from models.parametrage import ParametrageAnnuel
from models.conge_exceptionnel_type import CongeExceptionnelType


EXC_PREFIX = "EXC:"


def get_types_exceptionnels(actifs_only: bool = True):
    q = CongeExceptionnelType.query
    if actifs_only:
        q = q.filter_by(actif=True)
    return q.order_by(CongeExceptionnelType.libelle.asc()).all()


def get_type_exceptionnel(code: str):
    return CongeExceptionnelType.query.filter_by(code=code).first()


def parse_code(type_conge: str):
    if not type_conge:
        return None
    if not type_conge.startswith(EXC_PREFIX):
        return None
    return type_conge[len(EXC_PREFIX):].strip() or None


def _get_param(parametrage_id):
    if parametrage_id:
        return ParametrageAnnuel.query.get(parametrage_id)
    return ParametrageAnnuel.query.filter_by(actif=True).first()


def calculer_consommation(user_id: int, code: str, unite: str, parametrage_id=None, conge_id_exclu=None) -> int:
    param = _get_param(parametrage_id)
    if param is None:
        return 0
    type_value = f"{EXC_PREFIX}{code}"
    q = db.session.query(func.coalesce(func.sum(Conge.nb_jours_ouvrables), 0))
    if unite == "heures":
        q = db.session.query(func.coalesce(func.sum(Conge.nb_heures_exceptionnelles), 0))
    q = q.filter(
        Conge.user_id == user_id,
        Conge.date_debut >= param.debut_exercice,
        Conge.date_fin <= param.fin_exercice,
        Conge.type_conge == type_value,
        Conge.statut == "valide",
    )
    if conge_id_exclu:
        q = q.filter(Conge.id != conge_id_exclu)
    return int(q.scalar() or 0)


def verifier_plafond(user_id: int, t: CongeExceptionnelType, quantite: int, parametrage_id=None, conge_id_exclu=None) -> bool:
    if t.plafond_annuel is None:
        return True
    consomme = calculer_consommation(user_id, t.code, t.unite, parametrage_id=parametrage_id, conge_id_exclu=conge_id_exclu)
    return (consomme + quantite) <= int(t.plafond_annuel)


