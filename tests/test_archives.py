"""Tests de l'archivage des congés anciens (FR53)."""
from datetime import date

from tests.conftest import login

from models.conge import Conge


def _conge(db_session, user_id, debut, fin, statut="valide", jours=2):
    c = Conge(
        user_id=user_id,
        date_debut=debut,
        date_fin=fin,
        nb_jours_ouvrables=jours,
        type_conge="CP",
        statut=statut,
    )
    db_session.session.add(c)
    db_session.session.commit()
    return c


class TestArchivage:
    def test_acces_reserve_rh(self, client, users):
        login(client, "jean1", "jean123")
        resp = client.get("/rh/archives", follow_redirects=True)
        # Redirigé vers login (accès refusé) -> la page d'archives n'est pas rendue.
        assert b"Archivage des cong\xc3\xa9s anciens" not in resp.data

    def test_page_affiche_compteur(self, client, db_session, users, parametrage):
        _conge(db_session, users["salarie"].id, date(2025, 12, 1), date(2025, 12, 5))
        login(client, "rh1", "rh123")
        resp = client.get("/rh/archives")
        assert resp.status_code == 200
        assert b"archivable" in resp.data

    def test_archiver_anciens(self, client, db_session, users, parametrage):
        ancien = _conge(db_session, users["salarie"].id, date(2025, 12, 1), date(2025, 12, 5))
        recent = _conge(db_session, users["salarie"].id, date(2026, 6, 1), date(2026, 6, 5))
        en_attente = _conge(
            db_session, users["salarie"].id, date(2025, 1, 1), date(2025, 1, 3),
            statut="en_attente_rh",
        )

        login(client, "rh1", "rh123")
        resp = client.post(
            "/rh/archives",
            data={"action": "archiver", "date_cutoff": "2026-01-01"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        assert Conge.query.get(ancien.id).archive is True
        assert Conge.query.get(recent.id).archive is False
        # Une demande en attente n'est jamais archivée, même ancienne.
        assert Conge.query.get(en_attente.id).archive is False

    def test_conge_archive_exclu_de_accueil(self, client, db_session, users, parametrage):
        archive = _conge(db_session, users["salarie"].id, date(2025, 11, 1), date(2025, 11, 5))
        archive.archive = True
        db_session.session.commit()

        login(client, "jean1", "jean123")
        resp = client.get("/salarie/accueil")
        assert resp.status_code == 200
        assert b"01/11/2025" not in resp.data

    def test_desarchiver(self, client, db_session, users, parametrage):
        c = _conge(db_session, users["salarie"].id, date(2025, 11, 1), date(2025, 11, 5))
        c.archive = True
        db_session.session.commit()

        login(client, "rh1", "rh123")
        resp = client.post(
            "/rh/archives",
            data={"action": "desarchiver"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert Conge.query.get(c.id).archive is False
