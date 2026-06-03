"""Tests du changement de mot de passe self-service (FR52)."""
from tests.conftest import login

from models.user import User
from services.auth_utils import check_password


class TestChangementMotDePasse:
    def test_acces_requiert_authentification(self, client, users):
        resp = client.get("/changer-mot-de-passe", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_changement_reussi(self, client, db_session, users):
        login(client, "jean1", "jean123")
        resp = client.post(
            "/changer-mot-de-passe",
            data={
                "mot_de_passe_actuel": "jean123",
                "nouveau_mot_de_passe": "nouveauPass1",
                "confirmation_mot_de_passe": "nouveauPass1",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        user = User.query.filter_by(identifiant="jean1").first()
        assert check_password("nouveauPass1", user.mot_de_passe_hash)
        assert not check_password("jean123", user.mot_de_passe_hash)

    def test_mot_de_passe_actuel_incorrect(self, client, db_session, users):
        login(client, "jean1", "jean123")
        resp = client.post(
            "/changer-mot-de-passe",
            data={
                "mot_de_passe_actuel": "mauvais",
                "nouveau_mot_de_passe": "nouveauPass1",
                "confirmation_mot_de_passe": "nouveauPass1",
            },
            follow_redirects=True,
        )
        assert "incorrect" in resp.data.decode("utf-8")
        user = User.query.filter_by(identifiant="jean1").first()
        assert check_password("jean123", user.mot_de_passe_hash)

    def test_confirmation_differente(self, client, db_session, users):
        login(client, "jean1", "jean123")
        resp = client.post(
            "/changer-mot-de-passe",
            data={
                "mot_de_passe_actuel": "jean123",
                "nouveau_mot_de_passe": "nouveauPass1",
                "confirmation_mot_de_passe": "autrePass2",
            },
            follow_redirects=True,
        )
        assert "confirmation" in resp.data.decode("utf-8").lower()
        user = User.query.filter_by(identifiant="jean1").first()
        assert check_password("jean123", user.mot_de_passe_hash)

    def test_nouveau_trop_court(self, client, db_session, users):
        login(client, "jean1", "jean123")
        resp = client.post(
            "/changer-mot-de-passe",
            data={
                "mot_de_passe_actuel": "jean123",
                "nouveau_mot_de_passe": "court",
                "confirmation_mot_de_passe": "court",
            },
            follow_redirects=True,
        )
        assert "court" in resp.data.decode("utf-8").lower()
        user = User.query.filter_by(identifiant="jean1").first()
        assert check_password("jean123", user.mot_de_passe_hash)

    def test_nouveau_identique_ancien(self, client, db_session, users):
        login(client, "jean1", "jean123")
        # Le mot de passe seedé (jean123) fait moins de 8 caractères : on définit
        # d'abord un mot de passe valide, puis on tente de le réutiliser à l'identique.
        client.post(
            "/changer-mot-de-passe",
            data={
                "mot_de_passe_actuel": "jean123",
                "nouveau_mot_de_passe": "ValidePass1",
                "confirmation_mot_de_passe": "ValidePass1",
            },
            follow_redirects=True,
        )
        resp = client.post(
            "/changer-mot-de-passe",
            data={
                "mot_de_passe_actuel": "ValidePass1",
                "nouveau_mot_de_passe": "ValidePass1",
                "confirmation_mot_de_passe": "ValidePass1",
            },
            follow_redirects=True,
        )
        assert "différent" in resp.data.decode("utf-8").lower()
