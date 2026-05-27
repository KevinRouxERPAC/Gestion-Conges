"""Tests de la détection de conflits affichée lors de la validation."""
from datetime import date

from models import db
from models.conge import Conge
from services.calcul_jours import conges_chevauchant
from tests.conftest import login


class TestConflitsService:
    def test_pas_de_conflit_periode_vide(self, db_session):
        assert conges_chevauchant(date(2026, 6, 1), date(2026, 6, 5)) == []

    def test_detecte_chevauchement_partiel(self, db_session, users, parametrage, allocations):
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 3),
            date_fin=date(2026, 6, 10),
            nb_jours_ouvrables=6,
            type_conge="CP",
            statut="valide",
        )
        db.session.add(c)
        db.session.commit()
        # Période 1-7 → chevauchement avec 3-10.
        rows = conges_chevauchant(date(2026, 6, 1), date(2026, 6, 7))
        assert len(rows) == 1
        assert rows[0].id == c.id

    def test_exclure_user(self, db_session, users, parametrage, allocations):
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 3),
            date_fin=date(2026, 6, 10),
            nb_jours_ouvrables=6,
            type_conge="CP",
            statut="valide",
        )
        db.session.add(c)
        db.session.commit()
        # En excluant le user, plus rien.
        rows = conges_chevauchant(
            date(2026, 6, 1), date(2026, 6, 7),
            exclure_user_id=users["salarie"].id,
        )
        assert rows == []


class TestDashboardAffiche:
    def test_dashboard_rh_montre_conflits(self, client, db_session, users, parametrage, allocations):
        # Un autre congé validé qui chevauche la demande.
        autre = Conge(
            user_id=users["salarie_sans_resp"].id,
            date_debut=date(2026, 6, 4),
            date_fin=date(2026, 6, 6),
            nb_jours_ouvrables=3,
            type_conge="CP",
            statut="valide",
        )
        # La demande en attente RH.
        demande = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 10),
            nb_jours_ouvrables=8,
            type_conge="CP",
            statut="en_attente_rh",
        )
        db.session.add_all([autre, demande])
        db.session.commit()

        login(client, "rh1", "rh123")
        resp = client.get("/rh/dashboard")
        assert resp.status_code == 200
        # Le nom du collègue absent apparaît dans la section conflits.
        assert "absent".encode("utf-8") in resp.data
        assert users["salarie_sans_resp"].nom.encode("utf-8") in resp.data
