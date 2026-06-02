"""Tests du changement de mot de passe en self-service (auth.changer_mot_de_passe)."""
from models.user import User
from services.auth_utils import check_password
from tests.conftest import login


class TestChangerMotDePasse:
    def test_acces_requiert_authentification(self, client, db_session):
        """Un visiteur non connecté est redirigé vers le login."""
        resp = client.get("/changer-mot-de-passe", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert "/login" in resp.headers.get("Location", "")

    def test_page_accessible_connecte(self, client, db_session, users):
        login(client, "jean1", "jean123")
        resp = client.get("/changer-mot-de-passe")
        assert resp.status_code == 200

    def test_changement_succes(self, client, db_session, users):
        """Le mot de passe est mis à jour et permet une nouvelle connexion."""
        login(client, "jean1", "jean123")
        resp = client.post("/changer-mot-de-passe", data={
            "mot_de_passe_actuel": "jean123",
            "nouveau_mot_de_passe": "nouveau-mdp-solide",
            "confirmation_mot_de_passe": "nouveau-mdp-solide",
        }, follow_redirects=True)
        assert resp.status_code == 200

        u = User.query.filter_by(identifiant="jean1").first()
        assert check_password("nouveau-mdp-solide", u.mot_de_passe_hash)
        assert not check_password("jean123", u.mot_de_passe_hash)

    def test_mauvais_mot_de_passe_actuel_refuse(self, client, db_session, users):
        login(client, "jean1", "jean123")
        client.post("/changer-mot-de-passe", data={
            "mot_de_passe_actuel": "mauvais",
            "nouveau_mot_de_passe": "nouveau-mdp-solide",
            "confirmation_mot_de_passe": "nouveau-mdp-solide",
        }, follow_redirects=True)
        u = User.query.filter_by(identifiant="jean1").first()
        assert check_password("jean123", u.mot_de_passe_hash)

    def test_confirmation_differente_refuse(self, client, db_session, users):
        login(client, "jean1", "jean123")
        client.post("/changer-mot-de-passe", data={
            "mot_de_passe_actuel": "jean123",
            "nouveau_mot_de_passe": "nouveau-mdp-solide",
            "confirmation_mot_de_passe": "pas-pareil-du-tout",
        }, follow_redirects=True)
        u = User.query.filter_by(identifiant="jean1").first()
        assert check_password("jean123", u.mot_de_passe_hash)

    def test_nouveau_trop_court_refuse(self, client, db_session, users):
        login(client, "jean1", "jean123")
        client.post("/changer-mot-de-passe", data={
            "mot_de_passe_actuel": "jean123",
            "nouveau_mot_de_passe": "court",
            "confirmation_mot_de_passe": "court",
        }, follow_redirects=True)
        u = User.query.filter_by(identifiant="jean1").first()
        assert check_password("jean123", u.mot_de_passe_hash)

    def test_nouveau_identique_a_lancien_refuse(self, client, db_session, users):
        login(client, "jean1", "jean123")
        client.post("/changer-mot-de-passe", data={
            "mot_de_passe_actuel": "jean123",
            "nouveau_mot_de_passe": "jean123",
            "confirmation_mot_de_passe": "jean123",
        }, follow_redirects=True)
        u = User.query.filter_by(identifiant="jean1").first()
        assert check_password("jean123", u.mot_de_passe_hash)
