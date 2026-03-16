"""Tests des fonctionnalités RH : CRUD utilisateurs, ajout/modification congés, allocations."""
from datetime import date
from models.conge import Conge
from models.user import User
from models.parametrage import AllocationConge
from tests.conftest import login


class TestGestionUtilisateurs:
    def test_creer_salarie(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.post("/rh/salarie/nouveau", data={
            "nom": "Nouveau",
            "prenom": "Test",
            "identifiant": "nouveau1",
            "mot_de_passe": "test123",
            "role": "salarie",
            "responsable_id": str(users["responsable"].id),
        }, follow_redirects=True)
        assert resp.status_code == 200

        u = User.query.filter_by(identifiant="nouveau1").first()
        assert u is not None
        assert u.nom == "Nouveau"
        assert u.role == "salarie"
        assert u.responsable_id == users["responsable"].id

    def test_modifier_salarie(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/modifier", data={
            "nom": "DupontModif",
            "prenom": "JeanModif",
            "identifiant": "jean1",
            "role": "salarie",
            "actif": "on",
            "responsable_id": "",
        }, follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(users["salarie"])
        assert users["salarie"].nom == "DupontModif"
        assert users["salarie"].responsable_id is None

    def test_desactiver_salarie(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/statut", data={
            "actif": "off",
        }, follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(users["salarie"])
        assert users["salarie"].actif is False


class TestAjoutCongeRH:
    def test_ajouter_conge_cp(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/conge/ajouter", data={
            "date_debut": "2026-06-01",
            "date_fin": "2026-06-05",
            "type_conge": "CP",
            "commentaire": "Test RH",
        }, follow_redirects=True)
        assert resp.status_code == 200

        conge = Conge.query.filter_by(user_id=users["salarie"].id).first()
        assert conge is not None
        assert conge.statut == "valide"
        assert conge.type_conge == "CP"

    def test_ajouter_conge_rtt_heures(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/conge/ajouter", data={
            "date_debut": "2026-05-04",
            "date_fin": "2026-05-04",
            "type_conge": "RTT",
            "nb_heures_rtt": "4",
        }, follow_redirects=True)
        assert resp.status_code == 200

        conge = Conge.query.filter_by(user_id=users["salarie"].id, type_conge="RTT").first()
        assert conge is not None
        assert conge.nb_heures_rtt == 4

    def test_ajouter_conge_solde_insuffisant(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/conge/ajouter", data={
            "date_debut": "2026-01-05",
            "date_fin": "2026-02-28",
            "type_conge": "CP",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"insuffisant" in resp.data


class TestModificationAllocation:
    def test_modifier_allocation_cp_et_rtt(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/allocation", data={
            "jours_alloues": "30",
            "jours_anciennete": "3",
            "jours_report": "5",
            "rtt_heures_allouees": "20",
            "rtt_heures_reportees": "4",
        }, follow_redirects=True)
        assert resp.status_code == 200

        a = AllocationConge.query.filter_by(user_id=users["salarie"].id, parametrage_id=parametrage.id).first()
        assert a.jours_alloues == 30
        assert a.jours_anciennete == 3
        assert a.jours_report == 5
        assert a.rtt_heures_allouees == 20
        assert a.rtt_heures_reportees == 4


class TestValidationCongeRH:
    def test_validation_verifie_solde(self, client, db_session, users, parametrage, allocations):
        """La validation RH vérifie aussi le solde CP."""
        for i in range(3):
            c = Conge(
                user_id=users["salarie"].id,
                date_debut=date(2026, 3 + i, 2),
                date_fin=date(2026, 3 + i, 13),
                nb_jours_ouvrables=10,
                type_conge="CP",
                statut="valide",
            )
            db_session.session.add(c)
        db_session.session.commit()

        conge_test = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 9, 1),
            date_fin=date(2026, 9, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_rh",
        )
        db_session.session.add(conge_test)
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/conge/{conge_test.id}/valider", follow_redirects=True)
        assert resp.status_code == 200
        assert b"insuffisant" in resp.data

        db_session.session.refresh(conge_test)
        assert conge_test.statut == "en_attente_rh"
