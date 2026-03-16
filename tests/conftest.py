"""Configuration de test : app Flask avec SQLite en mémoire."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")

from app import create_app
from models import db as _db


@pytest.fixture(scope="session")
def app():
    """Crée l'application Flask pour les tests (SQLite in-memory)."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "MAIL_SUPPRESS_SEND": True,
        "SERVER_NAME": "localhost",
    })

    with app.app_context():
        _db.drop_all()
        _db.create_all()

    yield app


@pytest.fixture(autouse=True)
def db_session(app):
    """Chaque test s'exécute dans une transaction annulée à la fin."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def _hash():
    """Utilitaire pour hasher un mot de passe."""
    import bcrypt
    def _h(password):
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return _h


@pytest.fixture()
def users(db_session, _hash):
    """Crée un jeu d'utilisateurs : rh, responsable, salarié."""
    from models.user import User

    rh = User(nom="Admin", prenom="RH", identifiant="rh1", mot_de_passe_hash=_hash("rh123"), role="rh", actif=True)
    responsable = User(nom="Chef", prenom="Resp", identifiant="resp1", mot_de_passe_hash=_hash("resp123"), role="responsable", actif=True)
    db_session.session.add_all([rh, responsable])
    db_session.session.flush()

    salarie = User(nom="Dupont", prenom="Jean", identifiant="jean1", mot_de_passe_hash=_hash("jean123"), role="salarie", actif=True, responsable_id=responsable.id)
    salarie_sans_resp = User(nom="Martin", prenom="Paul", identifiant="paul1", mot_de_passe_hash=_hash("paul123"), role="salarie", actif=True)
    db_session.session.add_all([salarie, salarie_sans_resp])
    db_session.session.commit()

    return {"rh": rh, "responsable": responsable, "salarie": salarie, "salarie_sans_resp": salarie_sans_resp}


@pytest.fixture()
def parametrage(db_session):
    """Crée un paramétrage annuel actif."""
    from datetime import date
    from models.parametrage import ParametrageAnnuel

    p = ParametrageAnnuel(
        debut_exercice=date(2026, 1, 1),
        fin_exercice=date(2026, 12, 31),
        jours_conges_defaut=25,
        rtt_heures_defaut=14,
        actif=True,
    )
    db_session.session.add(p)
    db_session.session.commit()
    return p


@pytest.fixture()
def allocations(db_session, users, parametrage):
    """Crée les allocations CP et RTT pour les salariés."""
    from models.parametrage import AllocationConge

    allocs = {}
    for key in ("salarie", "salarie_sans_resp"):
        a = AllocationConge(
            user_id=users[key].id,
            parametrage_id=parametrage.id,
            jours_alloues=25,
            jours_anciennete=2,
            jours_report=0,
            rtt_heures_allouees=14,
            rtt_heures_reportees=0,
        )
        db_session.session.add(a)
        allocs[key] = a
    db_session.session.commit()
    return allocs


def login(client, identifiant, mot_de_passe):
    """Helper pour se connecter."""
    return client.post("/login", data={"identifiant": identifiant, "mot_de_passe": mot_de_passe}, follow_redirects=True)
