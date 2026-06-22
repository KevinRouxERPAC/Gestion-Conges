"""Tests de la saisie RTT au quart d'heure et de l'affichage « H h MM »."""
from models.conge import Conge
from services.format_heures import format_heures_min, est_multiple_quart
from tests.conftest import login


class TestFormatHeuresMin:
    def test_heure_pleine(self):
        assert format_heures_min(7) == "7 h"
        assert format_heures_min(7.0) == "7 h"

    def test_quarts(self):
        assert format_heures_min(5.25) == "5 h 15"
        assert format_heures_min(5.5) == "5 h 30"
        assert format_heures_min(5.75) == "5 h 45"
        assert format_heures_min(0.25) == "0 h 15"

    def test_zero_et_none(self):
        assert format_heures_min(0) == "0 h"
        assert format_heures_min(None) == "0 h"

    def test_negatif(self):
        # Report de déficit RTT : le signe est conservé.
        assert format_heures_min(-2.5) == "-2 h 30"

    def test_decimale_non_quart_arrondie_minute(self):
        # 16,1 h = 16 h 06 (acquisition hebdomadaire décimale)
        assert format_heures_min(16.1) == "16 h 06"


class TestEstMultipleQuart:
    def test_multiples_valides(self):
        for v in (0.25, 0.5, 0.75, 1, 5.25, 7.0, 14):
            assert est_multiple_quart(v) is True

    def test_non_multiples(self):
        for v in (0.1, 5.10, 5.3, 0.2):
            assert est_multiple_quart(v) is False


class TestSaisieRttQuartHeure:
    def test_rtt_quart_heure_accepte(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/conge/ajouter", data={
            "date_debut": "2026-05-04",
            "date_fin": "2026-05-04",
            "type_conge": "RTT",
            "nb_heures_rtt": "5.25",
        }, follow_redirects=True)
        assert resp.status_code == 200
        conge = Conge.query.filter_by(user_id=users["salarie"].id, type_conge="RTT").first()
        assert conge is not None
        assert conge.nb_heures_rtt == 5.25

    def test_rtt_virgule_francaise_acceptee(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        client.post(f"/rh/salarie/{users['salarie'].id}/conge/ajouter", data={
            "date_debut": "2026-05-04",
            "date_fin": "2026-05-04",
            "type_conge": "RTT",
            "nb_heures_rtt": "5,75",
        }, follow_redirects=True)
        conge = Conge.query.filter_by(user_id=users["salarie"].id, type_conge="RTT").first()
        assert conge is not None
        assert conge.nb_heures_rtt == 5.75

    def test_rtt_non_multiple_quart_rejete(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/conge/ajouter", data={
            "date_debut": "2026-05-04",
            "date_fin": "2026-05-04",
            "type_conge": "RTT",
            "nb_heures_rtt": "5.10",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Aucun congé créé (saisie rejetée) et message d'erreur affiché.
        assert Conge.query.filter_by(user_id=users["salarie"].id, type_conge="RTT").first() is None
        assert "multiple de 0,25" in resp.get_data(as_text=True)
