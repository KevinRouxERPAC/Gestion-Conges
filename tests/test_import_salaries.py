"""Tests de l'import en masse de salariés depuis CSV/Excel."""
import io
from openpyxl import Workbook

from models.user import User
from services.import_salaries import parse_csv, sync_users
from services.auth_utils import hash_password
from tests.conftest import login


CSV_BASIC = (
    "nom;prenom;email;role;actif\n"
    "Dupont;Marie;marie.dupont@example.com;salarie;oui\n"
    "Martin;Paul;;responsable;oui\n"
    "Bernard;Sophie;;rh;non\n"
)


class TestParseCSV:
    def test_parse_basique(self):
        rows = parse_csv(CSV_BASIC.encode("utf-8"))
        assert len(rows) == 3
        assert rows[0]["nom"] == "Dupont"
        assert rows[0]["prenom"] == "Marie"
        assert rows[0]["role"] == "salarie"
        assert rows[0]["actif"] is True
        # Identifiant auto-généré.
        assert rows[0]["identifiant"]

    def test_role_responsable_reconnu(self):
        rows = parse_csv(CSV_BASIC.encode("utf-8"))
        assert rows[1]["role"] == "responsable"

    def test_role_rh_reconnu(self):
        rows = parse_csv(CSV_BASIC.encode("utf-8"))
        assert rows[2]["role"] == "rh"
        assert rows[2]["actif"] is False

    def test_identifiants_uniques(self):
        # Deux salariés avec le même prénom+nom doivent avoir des identifiants distincts.
        csv = "nom;prenom\nDupont;Marie\nDupont;Marie\n"
        rows = parse_csv(csv.encode("utf-8"))
        assert len(rows) == 2
        assert rows[0]["identifiant"] != rows[1]["identifiant"]


class TestSyncUsers:
    def test_creation(self, db_session):
        rows = parse_csv(CSV_BASIC.encode("utf-8"))
        created, updated, errors = sync_users(rows, "motdepasse-solide", hash_password)
        assert created == 3
        assert updated == 0
        assert errors == []
        db_session.session.commit()
        assert User.query.count() >= 3

    def test_mdp_trop_court_refuse(self, db_session):
        rows = parse_csv(CSV_BASIC.encode("utf-8"))
        created, updated, errors = sync_users(rows, "court", hash_password)
        assert created == 0
        assert len(errors) >= 1

    def test_mise_a_jour(self, db_session, users):
        # 'jean1' existe déjà. On le réimporte avec un nouveau nom.
        csv = "identifiant;nom;prenom\njean1;NouveauNom;Jean\n"
        rows = parse_csv(csv.encode("utf-8"))
        created, updated, errors = sync_users(rows, "motdepasse-solide", hash_password)
        db_session.session.commit()
        assert updated == 1
        assert created == 0
        u = User.query.filter_by(identifiant="jean1").first()
        assert u.nom == "NouveauNom"


class TestRouteImport:
    def test_acces_rh_seulement(self, client, db_session, users):
        login(client, "jean1", "jean123")
        resp = client.get("/rh/salaries/importer", follow_redirects=False)
        assert resp.status_code == 302

    def test_dry_run_ne_persiste_pas(self, client, db_session, users):
        login(client, "rh1", "rh123")
        nb_avant = User.query.count()
        data = {
            "default_password": "motdepasse-solide",
            "dry_run": "on",
            "fichier": (io.BytesIO(CSV_BASIC.encode("utf-8")), "test.csv"),
        }
        resp = client.post("/rh/salaries/importer", data=data,
                           content_type="multipart/form-data")
        assert resp.status_code == 200
        # Affichage de l'aperçu.
        assert b"Aper" in resp.data
        # Aucun user créé.
        assert User.query.count() == nb_avant

    def test_import_excel(self, client, db_session, users):
        wb = Workbook()
        ws = wb.active
        ws.append(["nom", "prenom", "role"])
        ws.append(["TestImport", "Excel", "salarie"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        login(client, "rh1", "rh123")
        data = {
            "default_password": "motdepasse-solide",
            "fichier": (buf, "test.xlsx"),
        }
        resp = client.post("/rh/salaries/importer", data=data,
                           content_type="multipart/form-data",
                           follow_redirects=True)
        assert resp.status_code == 200
        u = User.query.filter_by(nom="TestImport").first()
        assert u is not None
        assert u.role == "salarie"
