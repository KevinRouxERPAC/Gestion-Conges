"""Tests spécifiques au rôle Responsable : calendrier équipe + ajout congé subordonné."""
from datetime import date
from models.conge import Conge
from tests.conftest import login


class TestDashboardResponsable:
    def test_dashboard_contient_calendrier(self, client, db_session, users, parametrage, allocations):
        """Le dashboard responsable doit contenir le calendrier FullCalendar."""
        login(client, "resp1", "resp123")
        resp = client.get("/responsable/dashboard")
        assert resp.status_code == 200
        assert b"calendar-responsable" in resp.data
        assert b"fullcalendar" in resp.data.lower() or b"FullCalendar" in resp.data

    def test_dashboard_liste_subordonnes(self, client, db_session, users, parametrage, allocations):
        """Le dashboard doit lister les subordonnés avec un bouton + Congé."""
        login(client, "resp1", "resp123")
        resp = client.get("/responsable/dashboard")
        assert resp.status_code == 200
        assert b"Dupont" in resp.data
        assert b"+ Cong" in resp.data  # "+ Congé" encodé


class TestAjoutCongeParResponsable:
    def test_ajouter_conge_pour_subordonne(self, client, db_session, users, parametrage, allocations):
        """Le responsable peut créer un congé pour un subordonné."""
        login(client, "resp1", "resp123")
        resp = client.post(
            f"/responsable/subordonn%C3%A9/{users['salarie'].id}/conge/ajouter",
            data={
                "date_debut": "2026-06-01",
                "date_fin": "2026-06-05",
                "type_conge": "CP",
                "commentaire": "Posé par le responsable",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        conge = Conge.query.filter_by(user_id=users["salarie"].id).first()
        assert conge is not None
        assert conge.statut == "en_attente_rh"
        assert conge.valide_par_responsable_id == users["responsable"].id

    def test_ajouter_rtt_pour_subordonne(self, client, db_session, users, parametrage, allocations):
        """Le responsable peut créer un RTT (heures) pour un subordonné."""
        login(client, "resp1", "resp123")
        resp = client.post(
            f"/responsable/subordonn%C3%A9/{users['salarie'].id}/conge/ajouter",
            data={
                "date_debut": "2026-05-04",
                "date_fin": "2026-05-04",
                "type_conge": "RTT",
                "nb_heures_rtt": "4",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        conge = Conge.query.filter_by(user_id=users["salarie"].id, type_conge="RTT").first()
        assert conge is not None
        assert conge.nb_heures_rtt == 4

    def test_ne_peut_pas_ajouter_pour_non_subordonne(self, client, db_session, users, parametrage, allocations):
        """Le responsable ne peut pas ajouter un congé pour un salarié qui n'est pas son subordonné."""
        login(client, "resp1", "resp123")
        resp = client.get(
            f"/responsable/subordonn%C3%A9/{users['salarie_sans_resp'].id}/conge/ajouter",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"pas dans votre" in resp.data or b"quipe" in resp.data

    def test_solde_insuffisant_bloque(self, client, db_session, users, parametrage, allocations):
        """Ajout refusé si solde CP insuffisant."""
        login(client, "resp1", "resp123")
        resp = client.post(
            f"/responsable/subordonn%C3%A9/{users['salarie'].id}/conge/ajouter",
            data={
                "date_debut": "2026-01-05",
                "date_fin": "2026-02-28",
                "type_conge": "CP",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"insuffisant" in resp.data
