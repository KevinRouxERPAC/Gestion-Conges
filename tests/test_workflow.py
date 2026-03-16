"""Tests du workflow de validation 2 niveaux et des notifications."""
from datetime import date
from models.conge import Conge
from models.notification import Notification
from tests.conftest import login


class TestWorkflowAvecResponsable:
    """Salarié avec responsable : en_attente_responsable → en_attente_rh → valide/refuse."""

    def test_demande_conge_statut_initial(self, client, db_session, users, parametrage, allocations):
        """Une demande par un salarié avec responsable doit démarrer en en_attente_responsable."""
        login(client, "jean1", "jean123")
        resp = client.post("/salarie/demander-conge", data={
            "date_debut": "2026-06-01",
            "date_fin": "2026-06-05",
            "type_conge": "CP",
            "commentaire": "Vacances",
        }, follow_redirects=True)
        assert resp.status_code == 200

        conge = Conge.query.filter_by(user_id=users["salarie"].id).first()
        assert conge is not None
        assert conge.statut == "en_attente_responsable"

    def test_responsable_valide_passe_en_attente_rh(self, client, db_session, users, parametrage, allocations):
        """Le responsable valide → statut en_attente_rh + notification RH."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "resp1", "resp123")
        resp = client.post(f"/responsable/conge/{conge.id}/valider", follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(conge)
        assert conge.statut == "en_attente_rh"
        assert conge.valide_par_responsable_id == users["responsable"].id

        notif_rh = Notification.query.filter_by(user_id=users["rh"].id).first()
        assert notif_rh is not None

    def test_responsable_refuse_avec_motif(self, client, db_session, users, parametrage, allocations):
        """Le responsable refuse avec motif obligatoire → statut refuse + notification salarié."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 3),
            nb_jours_ouvrables=3,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "resp1", "resp123")
        resp = client.post(f"/responsable/conge/{conge.id}/refuser", data={
            "motif_refus": "Effectifs insuffisants",
        }, follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(conge)
        assert conge.statut == "refuse"
        assert conge.motif_refus == "Effectifs insuffisants"

        notif_salarie = Notification.query.filter_by(user_id=users["salarie"].id, type="conge_refuse").first()
        assert notif_salarie is not None

    def test_responsable_refuse_sans_motif_echoue(self, client, db_session, users, parametrage, allocations):
        """Le responsable ne peut pas refuser sans motif."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 7, 10),
            date_fin=date(2026, 7, 11),
            nb_jours_ouvrables=2,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "resp1", "resp123")
        resp = client.post(f"/responsable/conge/{conge.id}/refuser", data={
            "motif_refus": "",
        }, follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(conge)
        assert conge.statut == "en_attente_responsable"

    def test_rh_valide_conge(self, client, db_session, users, parametrage, allocations):
        """Les RH valident un congé en en_attente_rh → statut valide + notification salarié."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 8, 3),
            date_fin=date(2026, 8, 7),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_rh",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/conge/{conge.id}/valider", follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(conge)
        assert conge.statut == "valide"
        assert conge.valide_par_id == users["rh"].id

        notif = Notification.query.filter_by(user_id=users["salarie"].id, type="conge_valide").first()
        assert notif is not None

    def test_rh_refuse_conge_avec_motif(self, client, db_session, users, parametrage, allocations):
        """Les RH refusent avec motif → refuse + notification salarié."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 9, 1),
            date_fin=date(2026, 9, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_rh",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.post(f"/rh/conge/{conge.id}/refuser", data={
            "motif_refus": "Budget dépassé",
        }, follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(conge)
        assert conge.statut == "refuse"
        assert conge.motif_refus == "Budget dépassé"


class TestWorkflowSansResponsable:
    """Salarié sans responsable : la demande va directement en en_attente_rh."""

    def test_demande_directe_rh(self, client, db_session, users, parametrage, allocations):
        """Sans responsable, le statut initial est en_attente_rh."""
        login(client, "paul1", "paul123")
        resp = client.post("/salarie/demander-conge", data={
            "date_debut": "2026-06-15",
            "date_fin": "2026-06-20",
            "type_conge": "CP",
        }, follow_redirects=True)
        assert resp.status_code == 200

        conge = Conge.query.filter_by(user_id=users["salarie_sans_resp"].id).first()
        assert conge is not None
        assert conge.statut == "en_attente_rh"


class TestAnnulationConge:
    def test_salarie_annule_demande_en_attente(self, client, db_session, users, parametrage, allocations):
        """Un salarié peut annuler une demande en attente."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 10, 1),
            date_fin=date(2026, 10, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="en_attente_responsable",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "jean1", "jean123")
        resp = client.post(f"/salarie/conge/{conge.id}/annuler", follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(conge)
        assert conge.statut == "annule"

    def test_salarie_ne_peut_annuler_valide(self, client, db_session, users, parametrage, allocations):
        """Un salarié ne peut pas annuler un congé déjà validé."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 11, 1),
            date_fin=date(2026, 11, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        login(client, "jean1", "jean123")
        resp = client.post(f"/salarie/conge/{conge.id}/annuler", follow_redirects=True)
        assert resp.status_code == 200

        db_session.session.refresh(conge)
        assert conge.statut == "valide"
