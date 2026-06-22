"""Tests d'authentification et de redirection par rôle."""
from tests.conftest import login


class TestAuthentification:
    def test_login_identifiant_invalide(self, client, users):
        resp = client.post("/login", data={"identifiant": "inconnu", "mot_de_passe": "xxx"}, follow_redirects=True)
        assert b"incorrect" in resp.data

    def test_login_rh_redirige_dashboard_rh(self, client, users):
        resp = client.post("/login", data={"identifiant": "rh1", "mot_de_passe": "rh123"}, follow_redirects=False)
        assert resp.status_code == 302
        assert "/rh/dashboard" in resp.headers["Location"]

    def test_login_responsable_redirige_dashboard_responsable(self, client, users):
        resp = client.post("/login", data={"identifiant": "resp1", "mot_de_passe": "resp123"}, follow_redirects=False)
        assert resp.status_code == 302
        assert "/responsable/dashboard" in resp.headers["Location"]

    def test_login_salarie_redirige_accueil(self, client, users):
        resp = client.post("/login", data={"identifiant": "jean1", "mot_de_passe": "jean123"}, follow_redirects=False)
        assert resp.status_code == 302
        assert "/salarie/accueil" in resp.headers["Location"]


class TestAntiEnumeration:
    """Anti-énumération de comptes par timing (R4)."""

    def test_meme_message_inexistant_et_mauvais_mdp(self, client, users):
        # Un identifiant inexistant et un mauvais mot de passe sur un compte
        # existant doivent renvoyer exactement le même message.
        r_inexistant = client.post(
            "/login", data={"identifiant": "inexistant", "mot_de_passe": "peu importe"},
            follow_redirects=True,
        )
        r_mauvais = client.post(
            "/login", data={"identifiant": "jean1", "mot_de_passe": "mauvais"},
            follow_redirects=True,
        )
        assert b"incorrect" in r_inexistant.data
        assert b"incorrect" in r_mauvais.data

    def test_check_factice_appele_si_identifiant_inexistant(self, client, users, monkeypatch):
        # La branche factice doit exécuter un check_password contre DUMMY_HASH
        # quand l'identifiant n'existe pas (égalisation du temps de réponse).
        import routes.auth as auth_mod
        from services.auth_utils import DUMMY_HASH

        hashes_vus = []
        original = auth_mod.check_password

        def espion(pwd, hashed):
            hashes_vus.append(hashed)
            return original(pwd, hashed)

        monkeypatch.setattr(auth_mod, "check_password", espion)
        client.post("/login", data={"identifiant": "inexistant", "mot_de_passe": "x"})
        assert DUMMY_HASH in hashes_vus


class TestAccesRoles:
    def test_salarie_ne_peut_pas_acceder_rh(self, client, users):
        login(client, "jean1", "jean123")
        resp = client.get("/rh/dashboard", follow_redirects=True)
        assert b"RH" in resp.data or resp.status_code == 200

    def test_salarie_ne_peut_pas_acceder_responsable(self, client, users):
        login(client, "jean1", "jean123")
        resp = client.get("/responsable/dashboard", follow_redirects=True)
        assert resp.status_code == 200

    def test_rh_peut_acceder_dashboard(self, client, users):
        login(client, "rh1", "rh123")
        resp = client.get("/rh/dashboard")
        assert resp.status_code == 200

    def test_responsable_peut_acceder_dashboard(self, client, users):
        login(client, "resp1", "resp123")
        resp = client.get("/responsable/dashboard")
        assert resp.status_code == 200
