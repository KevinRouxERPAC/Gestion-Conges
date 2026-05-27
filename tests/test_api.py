"""Tests des endpoints API JSON (jours fériés, calcul jours ouvrables)."""
from datetime import date
from models.jour_ferie import JourFerie
from tests.conftest import login


class TestApiAuthentification:
    def test_api_requiert_login(self, client):
        """Sans session, l'API doit rediriger vers /login (302)."""
        resp = client.get("/api/jours-feries")
        assert resp.status_code in (302, 401)


class TestJoursFeries:
    def test_jours_feries_par_defaut(self, client, db_session, users):
        """Sans paramètre, retourne les fériés de l'année courante + suivante (vide si BDD vide)."""
        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-feries")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "feries" in data
        assert isinstance(data["feries"], list)

    def test_jours_feries_pour_annee(self, client, db_session, users):
        """Retourne les fériés correspondant aux années demandées."""
        db_session.session.add(JourFerie(date_ferie=date(2026, 5, 1), libelle="1er mai", annee=2026, auto_genere=True))
        db_session.session.add(JourFerie(date_ferie=date(2027, 1, 1), libelle="Jour de l'An", annee=2027, auto_genere=True))
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-feries?annees=2026")
        assert resp.status_code == 200
        feries = resp.get_json()["feries"]
        assert "2026-05-01" in feries
        assert "2027-01-01" not in feries


class TestJoursOuvrables:
    def test_calcul_simple(self, client, db_session, users):
        """5 jours consécutifs du lundi au vendredi : 5 jours ouvrables."""
        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-ouvrables?debut=2026-06-01&fin=2026-06-05")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valide"] is True
        assert data["jours"] == 5

    def test_calcul_avec_weekend(self, client, db_session, users):
        """Du lundi au dimanche : 5 jours ouvrables (WE exclu)."""
        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-ouvrables?debut=2026-06-01&fin=2026-06-07")
        assert resp.status_code == 200
        assert resp.get_json()["jours"] == 5

    def test_calcul_avec_jour_ferie(self, client, db_session, users):
        """Le 1er mai 2026 (vendredi) férié : du 27/04 au 01/05 → 4 jours ouvrables."""
        db_session.session.add(JourFerie(date_ferie=date(2026, 5, 1), libelle="1er mai", annee=2026, auto_genere=True))
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-ouvrables?debut=2026-04-27&fin=2026-05-01")
        assert resp.status_code == 200
        assert resp.get_json()["jours"] == 4

    def test_fin_avant_debut(self, client, db_session, users):
        """Date de fin avant date de début → 0 jour, valide=False."""
        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-ouvrables?debut=2026-06-10&fin=2026-06-05")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valide"] is False
        assert data["jours"] == 0

    def test_dates_invalides(self, client, db_session, users):
        """Format invalide → 400."""
        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-ouvrables?debut=pas-une-date&fin=2026-06-05")
        assert resp.status_code == 400
