"""Tests des délégations : suppléant actif peut valider niveau 1."""
from datetime import date, timedelta

import pytest

from models import db
from models.audit_log import AuditLog
from models.conge import Conge
from models.delegation import Delegation
from models.notification import Notification
from models.user import User
from services.delegation import peut_valider_pour, suppleants_de, delegataires_de
from tests.conftest import login


@pytest.fixture
def suppleant(db_session, users, _hash):
    """Crée un 2e responsable, candidat suppléant."""
    s = User(
        nom="Suppléant",
        prenom="Bob",
        identifiant="suppleant1",
        mot_de_passe_hash=_hash("suppl123"),
        role="responsable",
        actif=True,
    )
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def delegation_active(db_session, users, suppleant):
    today = date.today()
    d = Delegation(
        responsable_id=users["responsable"].id,
        suppleant_id=suppleant.id,
        date_debut=today,
        date_fin=today + timedelta(days=14),
    )
    db.session.add(d)
    db.session.commit()
    return d


class TestServiceDelegation:
    def test_suppleants_de(self, db_session, users, suppleant, delegation_active):
        ids = suppleants_de(users["responsable"].id)
        assert suppleant.id in ids

    def test_delegataires_de(self, db_session, users, suppleant, delegation_active):
        ids = delegataires_de(suppleant.id)
        assert users["responsable"].id in ids

    def test_peut_valider_responsable_direct(self, db_session, users):
        # Le responsable direct peut toujours valider.
        assert peut_valider_pour(users["responsable"], users["salarie"]) is True

    def test_peut_valider_suppleant_actif(self, db_session, users, suppleant, delegation_active):
        # Le suppléant peut valider pour le subordonné du responsable.
        assert peut_valider_pour(suppleant, users["salarie"]) is True

    def test_ne_peut_pas_valider_sans_delegation(self, db_session, users, suppleant):
        # Sans délégation : non.
        assert peut_valider_pour(suppleant, users["salarie"]) is False

    def test_delegation_passee_inactive(self, db_session, users, suppleant):
        # Délégation déjà terminée hier.
        today = date.today()
        d = Delegation(
            responsable_id=users["responsable"].id,
            suppleant_id=suppleant.id,
            date_debut=today - timedelta(days=10),
            date_fin=today - timedelta(days=1),
        )
        db.session.add(d)
        db.session.commit()
        assert peut_valider_pour(suppleant, users["salarie"]) is False


class TestSuppleantValide:
    def test_suppleant_voit_demande_dans_dashboard(self, client, db_session, users, suppleant, delegation_active):
        # Demande en attente_responsable pour un subordonné du responsable principal.
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 9, 1),
            date_fin=date(2026, 9, 3),
            nb_jours_ouvrables=3,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db.session.add(c)
        db.session.commit()

        login(client, "suppleant1", "suppl123")
        resp = client.get("/responsable/dashboard")
        assert resp.status_code == 200
        # Le nom du subordonné est visible dans le dashboard du suppléant.
        assert users["salarie"].nom.encode("utf-8") in resp.data

    def test_suppleant_peut_valider(self, client, db_session, users, suppleant, delegation_active):
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 9, 1),
            date_fin=date(2026, 9, 3),
            nb_jours_ouvrables=3,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db.session.add(c)
        db.session.commit()

        login(client, "suppleant1", "suppl123")
        resp = client.post(f"/responsable/conge/{c.id}/valider", follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(c)
        assert c.statut == "en_attente_rh"
        # Audit a tracé le suppléant comme acteur.
        log = AuditLog.query.filter_by(action="conge.valider_n1", cible_id=c.id).first()
        assert log is not None
        assert log.acteur_id == suppleant.id


class TestSuppleantRefuseLots:
    def test_suppleant_peut_refuser_par_lots(self, client, db_session, users, suppleant, delegation_active):
        """Régression : le refus par lots ignorait les délégations (filtre direct
        sur responsable_id), donc un suppléant ne pouvait pas refuser par lots."""
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 9, 1),
            date_fin=date(2026, 9, 3),
            nb_jours_ouvrables=3,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db.session.add(c)
        db.session.commit()

        login(client, "suppleant1", "suppl123")
        resp = client.post(
            "/responsable/conges/refuser-lots",
            data={"conge_ids": [str(c.id)], "motif_refus": "Indisponibilité équipe"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        db.session.refresh(c)
        assert c.statut == "refuse"
        assert c.motif_refus == "Indisponibilité équipe"


class TestNotificationSuppleant:
    def test_demande_notifie_responsable_et_suppleant(self, client, db_session, users, suppleant, delegation_active):
        login(client, "jean1", "jean123")
        resp = client.post("/salarie/demander-conge", data={
            "date_debut": "2026-09-01",
            "date_fin": "2026-09-03",
            "type_conge": "CP",
        }, follow_redirects=True)
        assert resp.status_code == 200

        # Responsable et suppléant ont chacun une notification.
        for uid in (users["responsable"].id, suppleant.id):
            n = Notification.query.filter_by(
                user_id=uid, type="nouvelle_demande_conge_responsable"
            ).first()
            assert n is not None, f"Pas de notif pour user_id={uid}"


class TestPageDelegations:
    def test_creation_delegation(self, client, db_session, users, suppleant):
        login(client, "resp1", "resp123")
        today = date.today()
        fin = today + timedelta(days=7)
        resp = client.post("/responsable/delegations", data={
            "action": "create",
            "suppleant_id": str(suppleant.id),
            "date_debut": today.isoformat(),
            "date_fin": fin.isoformat(),
        }, follow_redirects=True)
        assert resp.status_code == 200
        d = Delegation.query.filter_by(
            responsable_id=users["responsable"].id, suppleant_id=suppleant.id
        ).first()
        assert d is not None

    def test_suppression_delegation(self, client, db_session, users, suppleant, delegation_active):
        login(client, "resp1", "resp123")
        resp = client.post("/responsable/delegations", data={
            "action": "delete",
            "delegation_id": str(delegation_active.id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert Delegation.query.get(delegation_active.id) is None

    def test_ne_peut_pas_se_designer_soi_meme(self, client, db_session, users):
        login(client, "resp1", "resp123")
        today = date.today()
        resp = client.post("/responsable/delegations", data={
            "action": "create",
            "suppleant_id": str(users["responsable"].id),
            "date_debut": today.isoformat(),
            "date_fin": (today + timedelta(days=5)).isoformat(),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert Delegation.query.filter_by(responsable_id=users["responsable"].id).count() == 0
