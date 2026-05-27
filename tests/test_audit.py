"""Tests du journal d'audit (services/audit.py + hooks dans les routes)."""
import json
from datetime import date

from models.audit_log import AuditLog
from models.conge import Conge
from tests.conftest import login


class TestServiceAudit:
    def test_log_action_basique(self, db_session, users, client):
        """log_action ajoute une entrée à la session ; commit par le caller."""
        # On se connecte pour avoir un current_user.
        login(client, "rh1", "rh123")

        with client.session_transaction():
            pass  # active la session

        # Appel direct du service nécessite un contexte applicatif et un acteur.
        # Plus pratique : appeler une route qui utilise log_action et vérifier en BDD.
        # Voir TestHooksRoutes ci-dessous pour le scénario complet.


class TestHooksRoutes:
    def test_validation_logue_action(self, client, db_session, users, parametrage, allocations):
        """La validation d'un congé par RH écrit une entrée 'conge.valider'."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_rh",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/conge/{conge.id}/valider", follow_redirects=True)
        assert resp.status_code == 200

        log = AuditLog.query.filter_by(action="conge.valider", cible_id=conge.id).first()
        assert log is not None
        assert log.acteur_id == users["rh"].id
        assert log.acteur_role == "rh"
        details = json.loads(log.details)
        assert details["user_id"] == users["salarie"].id
        assert details["nb_jours"] == 5

    def test_refus_logue_action(self, client, db_session, users, parametrage, allocations):
        """Le refus d'un congé écrit une entrée 'conge.refuser' avec le motif."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_rh",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.post(
            f"/rh/conge/{conge.id}/refuser",
            data={"motif_refus": "Période surchargée"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        log = AuditLog.query.filter_by(action="conge.refuser", cible_id=conge.id).first()
        assert log is not None
        details = json.loads(log.details)
        assert details["motif"] == "Période surchargée"

    def test_creation_salarie_loguee(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.post("/rh/salarie/nouveau", data={
            "nom": "Nouveau",
            "prenom": "Test",
            "identifiant": "audit_test",
            "mot_de_passe": "motdepasse-solide",
            "role": "salarie",
        }, follow_redirects=True)
        assert resp.status_code == 200

        log = AuditLog.query.filter_by(action="salarie.creer").order_by(AuditLog.id.desc()).first()
        assert log is not None
        details = json.loads(log.details)
        assert details["identifiant"] == "audit_test"

    def test_modification_allocation_loguee(self, client, db_session, users, parametrage, allocations):
        """Modifier une allocation écrit avant/après."""
        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/salarie/{users['salarie'].id}/allocation", data={
            "jours_alloues": "30",
            "jours_anciennete": "5",
            "jours_report": "0",
            "rtt_heures_allouees": "20",
            "rtt_heures_reportees": "0",
        }, follow_redirects=True)
        assert resp.status_code == 200

        log = AuditLog.query.filter_by(action="allocation.modifier").order_by(AuditLog.id.desc()).first()
        assert log is not None
        details = json.loads(log.details)
        assert details["avant"]["jours_alloues"] == 25
        assert details["apres"]["jours_alloues"] == 30


class TestPageAuditLog:
    def test_acces_rh_seulement(self, client, db_session, users):
        # Sans login : redirection
        resp = client.get("/rh/audit-log")
        assert resp.status_code in (302, 401)

        # Salarié : accès refusé
        login(client, "jean1", "jean123")
        resp = client.get("/rh/audit-log", follow_redirects=False)
        assert resp.status_code == 302

    def test_page_audit_affiche_entries(self, client, db_session, users, parametrage, allocations):
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_rh",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "rh1", "rh123")
        client.post(f"/rh/conge/{conge.id}/valider", follow_redirects=True)

        resp = client.get("/rh/audit-log")
        assert resp.status_code == 200
        assert b"conge.valider" in resp.data
