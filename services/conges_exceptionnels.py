from models import db
from models.conge import Conge
from models.parametrage import ParametrageAnnuel
from models.conge_exceptionnel_type import CongeExceptionnelType
from services.consommation import somme_consommation, STATUT_VALIDE


EXC_PREFIX = "EXC:"

# Types de congés exceptionnels par défaut (barème indicatif courant en France,
# modifiable ensuite par les RH). Unité en jours sauf indication contraire.
TYPES_PAR_DEFAUT = [
    ("MARIAGE_PACS", "Mariage / PACS du salarié", "jours", 4, True),
    ("MARIAGE_ENFANT", "Mariage d'un enfant", "jours", 1, True),
    ("NAISSANCE_ADOPTION", "Naissance ou adoption", "jours", 3, True),
    ("DECES_CONJOINT", "Décès du conjoint / partenaire", "jours", 3, True),
    ("DECES_ENFANT", "Décès d'un enfant", "jours", 5, True),
    ("DECES_PARENT", "Décès d'un parent", "jours", 3, True),
    ("ENFANT_MALADE", "Enfant malade", "jours", 3, True),
    ("DEMENAGEMENT", "Déménagement", "jours", 1, False),
]


def creer_types_par_defaut() -> int:
    """Crée les types de congés exceptionnels par défaut s'ils n'existent pas déjà.

    Idempotent : les types déjà présents (par code) ne sont pas dupliqués.
    Retourne le nombre de types effectivement créés.
    """
    crees = 0
    for code, libelle, unite, plafond, justificatif_requis in TYPES_PAR_DEFAUT:
        if CongeExceptionnelType.query.filter_by(code=code).first():
            continue
        db.session.add(
            CongeExceptionnelType(
                code=code,
                libelle=libelle,
                unite=unite,
                plafond_annuel=plafond,
                justificatif_requis=justificatif_requis,
                actif=True,
            )
        )
        crees += 1
    if crees:
        db.session.commit()
    return crees


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


def calculer_consommation(user_id: int, code: str, unite: str, parametrage_id=None, conge_id_exclu=None):
    """Somme la consommation exceptionnelle validée pour l'exercice.

    Retour : int pour l'unité "heures", float pour l'unité "jours" (qui peut
    contenir des demi-journées, ex. 0,5). On ne tronque pas les jours, sinon
    le plafond serait appliqué de façon trop permissive.
    """
    param = _get_param(parametrage_id)
    if param is None:
        return 0
    type_value = f"{EXC_PREFIX}{code}"
    colonne = Conge.nb_heures_exceptionnelles if unite == "heures" else Conge.nb_jours_ouvrables
    total = somme_consommation(
        colonne=colonne,
        date_debut_min=param.debut_exercice,
        date_fin_max=param.fin_exercice,
        statuts=STATUT_VALIDE,
        types=(type_value,),
        user_id=user_id,
        conge_id_exclu=conge_id_exclu,
    )
    return int(total) if unite == "heures" else float(total)


def verifier_plafond(user_id: int, t: CongeExceptionnelType, quantite, parametrage_id=None, conge_id_exclu=None) -> bool:
    if t.plafond_annuel is None:
        return True
    consomme = calculer_consommation(user_id, t.code, t.unite, parametrage_id=parametrage_id, conge_id_exclu=conge_id_exclu)
    return (consomme + quantite) <= float(t.plafond_annuel)


