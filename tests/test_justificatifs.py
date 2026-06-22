"""Tests des justificatifs d'absence (upload RH, download protégé)."""
import io
from datetime import date

import pytest
from werkzeug.datastructures import FileStorage

from models import db
from models.conge import Conge
from models.conge_exceptionnel_type import CongeExceptionnelType
from services.justificatifs import justificatif_requis_pour_type
from tests.conftest import login

PDF_BYTES = b"%PDF-1.4\njustificatif test\n"


def _pdf_file(name="certificat.pdf"):
    return FileStorage(stream=io.BytesIO(PDF_BYTES), filename=name, content_type="application/pdf")


class TestJustificatifRequis:
    def test_maladie_toujours_requis(self):
        assert justificatif_requis_pour_type("Maladie") is True

    def test_cp_non_requis(self):
        assert justificatif_requis_pour_type("CP") is False

    def test_exc_selon_flag(self, db_session):
        t = CongeExceptionnelType(
            code="DECES_PARENT",
            libelle="Décès parent",
            unite="jours",
            plafond_annuel=3,
            justificatif_requis=True,
            actif=True,
        )
        db.session.add(t)
        db.session.commit()
        assert justificatif_requis_pour_type("EXC:DECES_PARENT") is True


class TestUploadRh:
    def test_ajouter_maladie_sans_fichier_refuse(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.post(
            f"/rh/salarie/{users['salarie'].id}/conge/ajouter",
            data={
                "date_debut": "2026-06-10",
                "date_fin": "2026-06-12",
                "type_conge": "Maladie",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert Conge.query.filter_by(user_id=users["salarie"].id, type_conge="Maladie").count() == 0

    def test_ajouter_maladie_avec_pdf_ok(self, app, db_session, users, parametrage):
        """Enregistrement RH : congé Maladie + justificatif (logique métier)."""
        from flask_login import login_user
        from services.creer_conge import construire_conge, MODE_RH
        from services.justificatifs import enregistrer_justificatif

        with app.test_request_context():
            login_user(users["rh"])
            result = construire_conge(
                users["salarie"],
                {
                    "date_debut": "2026-08-10",
                    "date_fin": "2026-08-12",
                    "type_conge": "Maladie",
                },
                mode=MODE_RH,
                statut_initial="valide",
                valide_par=users["rh"],
            )
            assert result.success, result.flashes
            db.session.add(result.conge)
            db.session.flush()
            err = enregistrer_justificatif(result.conge, _pdf_file(), users["rh"])
            assert err is None
            db.session.commit()

        conge = Conge.query.filter_by(user_id=users["salarie"].id, type_conge="Maladie").first()
        assert conge is not None
        assert conge.justificatif is not None
        assert conge.justificatif.nom_fichier == "certificat.pdf"

    def test_ajouter_maladie_avec_pdf_via_route_cree_le_conge(self, client, db_session, users, parametrage):
        """Régression : l'ajout RH d'un congé Maladie AVEC justificatif valide, via la
        route complète, doit créer le congé.

        La route enregistre le justificatif puis appelle verifier_justificatif_obligatoire()
        dans la même requête (avant tout flush). Si la relation conge.justificatif n'est
        pas peuplée en mémoire, la vérification rejette à tort un justificatif pourtant
        fourni et le congé n'est jamais créé (rollback)."""
        login(client, "rh1", "rh123")
        resp = client.post(
            f"/rh/salarie/{users['salarie'].id}/conge/ajouter",
            data={
                "date_debut": "2026-08-10",
                "date_fin": "2026-08-10",
                "type_conge": "Maladie",
                "justificatif": (io.BytesIO(PDF_BYTES), "certificat.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        conge = Conge.query.filter_by(user_id=users["salarie"].id, type_conge="Maladie").first()
        assert conge is not None, "Le congé Maladie avec justificatif valide doit être créé"
        assert conge.justificatif is not None
        assert conge.justificatif.nom_fichier == "certificat.pdf"

    def test_fichier_invalide_refuse(self, client, db_session, users):
        login(client, "rh1", "rh123")
        client.post(
            f"/rh/salarie/{users['salarie'].id}/conge/ajouter",
            data={
                "date_debut": "2026-06-10",
                "date_fin": "2026-06-10",
                "type_conge": "Maladie",
                "justificatif": (io.BytesIO(b"not a pdf"), "fake.pdf"),
            },
            follow_redirects=True,
        )
        assert Conge.query.filter_by(user_id=users["salarie"].id, type_conge="Maladie").count() == 0


class TestDownloadAcces:
    @pytest.fixture()
    def conge_maladie_avec_justificatif(self, db_session, users):
        from services.justificatifs import enregistrer_justificatif

        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 3),
            nb_jours_ouvrables=3,
            type_conge="Maladie",
            statut="valide",
        )
        db.session.add(c)
        db.session.flush()

        class FakeFile:
            filename = "arret.pdf"

            def read(self):
                return PDF_BYTES

        err = enregistrer_justificatif(c, FakeFile(), users["rh"])
        assert err is None
        db.session.commit()
        return c

    def test_rh_peut_telecharger(self, client, db_session, users, conge_maladie_avec_justificatif):
        login(client, "rh1", "rh123")
        resp = client.get(f"/rh/conge/{conge_maladie_avec_justificatif.id}/justificatif")
        assert resp.status_code == 200
        assert resp.data.startswith(b"%PDF")

    def test_salarie_propre_conge_ok(self, client, db_session, users, conge_maladie_avec_justificatif):
        login(client, "jean1", "jean123")
        resp = client.get(f"/rh/conge/{conge_maladie_avec_justificatif.id}/justificatif")
        assert resp.status_code == 200

    def test_autre_salarie_interdit(self, client, db_session, users, conge_maladie_avec_justificatif):
        login(client, "paul1", "paul123")
        resp = client.get(f"/rh/conge/{conge_maladie_avec_justificatif.id}/justificatif")
        assert resp.status_code == 403

    def test_responsable_interdit(self, client, db_session, users, conge_maladie_avec_justificatif):
        login(client, "resp1", "resp123")
        resp = client.get(f"/rh/conge/{conge_maladie_avec_justificatif.id}/justificatif")
        assert resp.status_code == 403


class TestValidationRhBloquee:
    def test_valider_sans_justificatif_refuse(self, client, db_session, users, parametrage):
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 2),
            nb_jours_ouvrables=2,
            type_conge="Maladie",
            statut="en_attente_rh",
        )
        db.session.add(c)
        db.session.commit()

        login(client, "rh1", "rh123")
        client.post(f"/rh/conge/{c.id}/valider", follow_redirects=True)
        db.session.refresh(c)
        assert c.statut == "en_attente_rh"
