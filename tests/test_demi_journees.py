"""Tests des demi-journées (matin / après-midi)."""
from datetime import date

import pytest

from models.conge import Conge
from models.jour_ferie import JourFerie
from services.calcul_jours import compter_jours_ouvrables_avec_demi
from tests.conftest import login


class TestCompterDemiJournees:
    def test_journee_complete_mono(self, db_session):
        # 1 jour ouvré, sans demi-journée → 1
        assert compter_jours_ouvrables_avec_demi(date(2026, 6, 1), date(2026, 6, 1)) == 1.0

    def test_demi_matin_mono(self, db_session):
        assert compter_jours_ouvrables_avec_demi(date(2026, 6, 1), date(2026, 6, 1), "matin") == 0.5

    def test_demi_apres_midi_mono(self, db_session):
        assert compter_jours_ouvrables_avec_demi(date(2026, 6, 1), date(2026, 6, 1), "apres_midi") == 0.5

    def test_apres_midi_sur_multi_jours(self, db_session):
        # 5 jours (lundi à vendredi), commençant après-midi → 4,5
        assert (
            compter_jours_ouvrables_avec_demi(date(2026, 6, 1), date(2026, 6, 5), "apres_midi") == 4.5
        )

    def test_matin_fin_sur_multi_jours(self, db_session):
        # 5 jours, finissant le matin → 4,5
        assert (
            compter_jours_ouvrables_avec_demi(date(2026, 6, 1), date(2026, 6, 5), None, "matin") == 4.5
        )

    def test_apres_midi_et_matin_fin(self, db_session):
        # Commence après-midi, finit matin → 5 - 1 = 4
        assert (
            compter_jours_ouvrables_avec_demi(date(2026, 6, 1), date(2026, 6, 5), "apres_midi", "matin") == 4.0
        )

    def test_demi_matin_sur_jour_ferie(self, db_session):
        # Si la matinée tombe sur un jour férié, elle ne compte pas (0).
        db_session.session.add(JourFerie(date_ferie=date(2026, 5, 1), libelle="1er mai", annee=2026, auto_genere=True))
        db_session.session.commit()
        assert compter_jours_ouvrables_avec_demi(date(2026, 5, 1), date(2026, 5, 1), "matin") == 0.0

    def test_demi_sur_weekend_zero(self, db_session):
        # Samedi : 0 même avec demi-journée.
        assert compter_jours_ouvrables_avec_demi(date(2026, 6, 6), date(2026, 6, 6), "matin") == 0.0

    def test_multi_jours_apres_midi_premier_ferie(self, db_session):
        # 5 jours, jour 1 férié, "apres_midi" sur le jour férié → ne soustrait pas 0,5
        # 5 jours brut, jour 1 férié → 4 ouvrables. apres_midi sur férié = pas de modif.
        db_session.session.add(JourFerie(date_ferie=date(2026, 6, 1), libelle="ferié", annee=2026, auto_genere=True))
        db_session.session.commit()
        assert (
            compter_jours_ouvrables_avec_demi(date(2026, 6, 1), date(2026, 6, 5), "apres_midi") == 4.0
        )


class TestDemandeAvecDemiJournee:
    def test_salarie_pose_un_apres_midi(self, client, db_session, users, parametrage, allocations):
        """Un salarié pose une demi-journée d'après-midi en RTT → conge créé avec 0,5 j."""
        login(client, "jean1", "jean123")
        resp = client.post("/salarie/demander-conge", data={
            "date_debut": "2026-06-01",
            "date_fin": "2026-06-01",
            "type_conge": "RTT",
            "nb_heures_rtt": "4",
            "demi_journee_debut": "apres_midi",
        }, follow_redirects=True)
        assert resp.status_code == 200
        conge = Conge.query.filter_by(user_id=users["salarie"].id).first()
        assert conge is not None
        assert conge.nb_jours_ouvrables == 0.5
        assert conge.demi_journee_debut == "apres_midi"
        assert conge.type_conge == "RTT"

    def test_demi_journee_cp_refusee(self, client, db_session, users, parametrage, allocations):
        """Règle métier : une demi-journée n'est pas autorisée pour un CP."""
        login(client, "jean1", "jean123")
        resp = client.post("/salarie/demander-conge", data={
            "date_debut": "2026-06-01",
            "date_fin": "2026-06-01",
            "type_conge": "CP",
            "demi_journee_debut": "apres_midi",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Aucun congé ne doit avoir été créé.
        assert Conge.query.filter_by(user_id=users["salarie"].id).count() == 0

    def test_rh_pose_demi_journee_finale(self, client, db_session, users, parametrage, allocations):
        """RH crée un RTT de 5 jours qui finit le matin du vendredi → 4,5 j."""
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/conge/ajouter", data={
            "date_debut": "2026-06-01",
            "date_fin": "2026-06-05",
            "type_conge": "RTT",
            "nb_heures_rtt": "30",
            "demi_journee_fin": "matin",
        }, follow_redirects=True)
        assert resp.status_code == 200
        conge = Conge.query.filter_by(user_id=users["salarie"].id, type_conge="RTT").first()
        assert conge is not None
        assert conge.nb_jours_ouvrables == 4.5
        assert conge.demi_journee_fin == "matin"
        assert conge.statut == "valide"


class TestApiDemiJournees:
    def test_api_demi_journee(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.get("/api/jours-ouvrables?debut=2026-06-01&fin=2026-06-05&demi_debut=apres_midi&demi_fin=matin")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valide"] is True
        assert data["jours"] == 4.0
