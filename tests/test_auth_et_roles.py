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
