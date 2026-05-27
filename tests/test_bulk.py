"""Tests des validations / refus par lots (RH et responsable)."""
from datetime import date

from models.audit_log import AuditLog
from models.conge import Conge
from tests.conftest import login


def _creer_demandes_rh(db_session, user_id, n=3, statut="en_attente_rh"):
    ids = []
    for i in range(n):
        c = Conge(
            user_id=user_id,
            date_debut=date(2026, 6, 1 + i * 7),
            date_fin=date(2026, 6, 3 + i * 7),
            nb_jours_ouvrables=3,
            type_conge="CP",
            statut=statut,
        )
        db_session.session.add(c)
    db_session.session.commit()
    return [c.id for c in Conge.query.filter_by(user_id=user_id, statut=statut).all()]


class TestRhBulk:
    def test_valider_lots(self, client, db_session, users, parametrage, allocations):
        ids = _creer_demandes_rh(db_session, users["salarie"].id, n=3)
        login(client, "rh1", "rh123")
        resp = client.post("/rh/conges/valider-lots", data={
            "conge_ids": [str(i) for i in ids],
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Tous validés.
        for cid in ids:
            assert Conge.query.get(cid).statut == "valide"
        # Audit : 3 entrées conge.valider.
        assert AuditLog.query.filter_by(action="conge.valider").count() == 3

    def test_valider_lots_vide(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.post("/rh/conges/valider-lots", data={}, follow_redirects=True)
        assert resp.status_code == 200
        assert "Aucun".encode("utf-8") in resp.data

    def test_refuser_lots_sans_motif_redirige_page_motif(self, client, db_session, users, parametrage, allocations):
        ids = _creer_demandes_rh(db_session, users["salarie"].id, n=2)
        login(client, "rh1", "rh123")
        resp = client.post("/rh/conges/refuser-lots", data={
            "conge_ids": [str(i) for i in ids],
        })
        # On obtient la page de saisie du motif (pas une redirection).
        assert resp.status_code == 200
        assert b"Motif de refus" in resp.data
        # Aucun congé n'a été refusé.
        for cid in ids:
            assert Conge.query.get(cid).statut == "en_attente_rh"

    def test_refuser_lots_avec_motif(self, client, db_session, users, parametrage, allocations):
        ids = _creer_demandes_rh(db_session, users["salarie"].id, n=2)
        login(client, "rh1", "rh123")
        resp = client.post("/rh/conges/refuser-lots", data={
            "conge_ids": [str(i) for i in ids],
            "motif_refus": "Effectifs trop réduits cette semaine.",
        }, follow_redirects=True)
        assert resp.status_code == 200
        for cid in ids:
            c = Conge.query.get(cid)
            assert c.statut == "refuse"
            assert c.motif_refus == "Effectifs trop réduits cette semaine."
        # Audit : 2 entrées de refus avec marqueur lot.
        refusals = AuditLog.query.filter_by(action="conge.refuser").all()
        assert len(refusals) == 2


class TestResponsableBulk:
    def test_valider_lots_n1(self, client, db_session, users, parametrage, allocations):
        # Crée 2 demandes en attente_responsable pour le subordonné.
        for i in range(2):
            c = Conge(
                user_id=users["salarie"].id,
                date_debut=date(2026, 7, 1 + i * 7),
                date_fin=date(2026, 7, 3 + i * 7),
                nb_jours_ouvrables=3,
                type_conge="CP",
                statut="en_attente_responsable",
            )
            db_session.session.add(c)
        db_session.session.commit()
        ids = [c.id for c in Conge.query.filter_by(statut="en_attente_responsable").all()]

        login(client, "resp1", "resp123")
        resp = client.post("/responsable/conges/valider-lots", data={
            "conge_ids": [str(i) for i in ids],
        }, follow_redirects=True)
        assert resp.status_code == 200
        for cid in ids:
            assert Conge.query.get(cid).statut == "en_attente_rh"

    def test_valider_lots_n1_ignore_non_subordonnes(self, client, db_session, users, parametrage, allocations):
        # Demande d'un salarié SANS responsable assigné → ne doit pas être validable.
        c = Conge(
            user_id=users["salarie_sans_resp"].id,
            date_debut=date(2026, 8, 1),
            date_fin=date(2026, 8, 3),
            nb_jours_ouvrables=3,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db_session.session.add(c)
        db_session.session.commit()

        login(client, "resp1", "resp123")
        resp = client.post("/responsable/conges/valider-lots", data={
            "conge_ids": [str(c.id)],
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Pas modifié.
        assert Conge.query.get(c.id).statut == "en_attente_responsable"
