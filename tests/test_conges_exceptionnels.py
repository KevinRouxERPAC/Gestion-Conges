"""Tests de la feature « congés exceptionnels ».

Couvre :
- les helpers de service (parse_code, calculer_consommation, verifier_plafond) ;
- le builder construire_conge (liste blanche par mode, plafond bloquant, unités) ;
- la route RH de gestion des types (validation du plafond / des longueurs) ;
- le filet de sécurité du plafond à la validation RH (2 demandes concurrentes).
"""
from datetime import date

import pytest

from models.conge import Conge
from models.conge_exceptionnel_type import CongeExceptionnelType
from tests.conftest import login


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_type(db, code="MARIAGE", libelle="Mariage", unite="jours", plafond=None, actif=True):
    t = CongeExceptionnelType(
        code=code, libelle=libelle, unite=unite, plafond_annuel=plafond, actif=actif
    )
    db.session.add(t)
    db.session.commit()
    return t


def _make_conge_exc(
    db,
    user_id,
    code="MARIAGE",
    statut="valide",
    nb_jours=3.0,
    nb_heures=None,
    debut=date(2026, 6, 1),
    fin=date(2026, 6, 3),
):
    c = Conge(
        user_id=user_id,
        date_debut=debut,
        date_fin=fin,
        nb_jours_ouvrables=nb_jours,
        type_conge=f"EXC:{code}",
        statut=statut,
        nb_heures_exceptionnelles=nb_heures,
    )
    db.session.add(c)
    db.session.commit()
    return c


# --------------------------------------------------------------------------- #
# Service : parse_code
# --------------------------------------------------------------------------- #
class TestParseCode:
    def test_extrait_le_code(self, db_session):
        from services.conges_exceptionnels import parse_code

        assert parse_code("EXC:MARIAGE") == "MARIAGE"
        assert parse_code("EXC: MARIAGE ") == "MARIAGE"

    def test_non_exceptionnel_retourne_none(self, db_session):
        from services.conges_exceptionnels import parse_code

        assert parse_code("CP") is None
        assert parse_code("") is None
        assert parse_code(None) is None
        assert parse_code("EXC:   ") is None


# --------------------------------------------------------------------------- #
# Service : calculer_consommation
# --------------------------------------------------------------------------- #
class TestCalculerConsommation:
    def test_compte_uniquement_les_valides(self, db_session, users, parametrage):
        from services.conges_exceptionnels import calculer_consommation

        _make_type(db_session)
        sal = users["salarie_sans_resp"].id
        _make_conge_exc(db_session, sal, statut="valide", nb_jours=3.0)
        _make_conge_exc(
            db_session, sal, statut="en_attente_rh", nb_jours=2.0,
            debut=date(2026, 6, 8), fin=date(2026, 6, 9),
        )

        # Seul le congé validé (3) est compté, pas le congé en attente (2).
        assert calculer_consommation(sal, "MARIAGE", "jours") == 3.0

    def test_exclut_le_conge_donne(self, db_session, users, parametrage):
        from services.conges_exceptionnels import calculer_consommation

        _make_type(db_session)
        sal = users["salarie_sans_resp"].id
        c = _make_conge_exc(db_session, sal, statut="valide", nb_jours=3.0)

        assert calculer_consommation(sal, "MARIAGE", "jours", conge_id_exclu=c.id) == 0.0

    def test_demi_journees_non_tronquees(self, db_session, users, parametrage):
        """Régression : une demi-journée ne doit pas être tronquée à 0."""
        from services.conges_exceptionnels import calculer_consommation

        _make_type(db_session)
        sal = users["salarie_sans_resp"].id
        _make_conge_exc(
            db_session, sal, statut="valide", nb_jours=0.5,
            debut=date(2026, 6, 1), fin=date(2026, 6, 1),
        )

        assert calculer_consommation(sal, "MARIAGE", "jours") == 0.5

    def test_unite_heures(self, db_session, users, parametrage):
        from services.conges_exceptionnels import calculer_consommation

        _make_type(db_session, code="ENFANT_MALADE", libelle="Enfant malade", unite="heures")
        sal = users["salarie_sans_resp"].id
        _make_conge_exc(
            db_session, sal, code="ENFANT_MALADE", statut="valide",
            nb_jours=1.0, nb_heures=4,
        )

        assert calculer_consommation(sal, "ENFANT_MALADE", "heures") == 4


# --------------------------------------------------------------------------- #
# Service : verifier_plafond
# --------------------------------------------------------------------------- #
class TestVerifierPlafond:
    def test_pas_de_plafond_toujours_ok(self, db_session, users, parametrage):
        from services.conges_exceptionnels import verifier_plafond

        t = _make_type(db_session, plafond=None)
        sal = users["salarie_sans_resp"].id
        assert verifier_plafond(sal, t, 999) is True

    def test_plafond_respecte_et_depasse(self, db_session, users, parametrage):
        from services.conges_exceptionnels import verifier_plafond

        t = _make_type(db_session, plafond=5)
        sal = users["salarie_sans_resp"].id
        _make_conge_exc(db_session, sal, statut="valide", nb_jours=3.0)

        assert verifier_plafond(sal, t, 2) is True   # 3 + 2 = 5 <= 5
        assert verifier_plafond(sal, t, 3) is False  # 3 + 3 = 6 > 5


# --------------------------------------------------------------------------- #
# Builder : construire_conge
# --------------------------------------------------------------------------- #
class TestConstruireConge:
    def _payload(self, code, **extra):
        base = {
            "date_debut": "2026-06-01",
            "date_fin": "2026-06-03",
            "type_conge": f"EXC:{code}",
        }
        base.update(extra)
        return base

    def test_salarie_ne_peut_pas_poser_exceptionnel(self, db_session, users, parametrage):
        from services.creer_conge import construire_conge, MODE_SALARIE

        _make_type(db_session)
        result = construire_conge(
            users["salarie_sans_resp"], self._payload("MARIAGE"),
            mode=MODE_SALARIE, statut_initial="en_attente_rh",
        )
        assert not result.success
        assert any("non disponible" in msg for _, msg in result.errors)

    def test_rh_cree_exceptionnel_jours(self, db_session, users, parametrage):
        from services.creer_conge import construire_conge, MODE_RH

        _make_type(db_session, plafond=10)
        result = construire_conge(
            users["salarie_sans_resp"], self._payload("MARIAGE"),
            mode=MODE_RH, statut_initial="valide",
        )
        assert result.success
        assert result.conge.type_conge == "EXC:MARIAGE"
        assert result.conge.nb_jours_ouvrables == 3
        assert result.conge.nb_heures_exceptionnelles is None

    def test_rh_plafond_bloquant(self, db_session, users, parametrage):
        from services.creer_conge import construire_conge, MODE_RH

        _make_type(db_session, plafond=2)  # 3 jours demandés > 2
        result = construire_conge(
            users["salarie_sans_resp"], self._payload("MARIAGE"),
            mode=MODE_RH, statut_initial="valide",
        )
        assert not result.success
        assert any("Plafond" in msg for _, msg in result.errors)

    def test_rh_type_inactif_refuse(self, db_session, users, parametrage):
        from services.creer_conge import construire_conge, MODE_RH

        _make_type(db_session, actif=False)
        result = construire_conge(
            users["salarie_sans_resp"], self._payload("MARIAGE"),
            mode=MODE_RH, statut_initial="valide",
        )
        assert not result.success

    def test_rh_exceptionnel_heures_requiert_quantite(self, db_session, users, parametrage):
        from services.creer_conge import construire_conge, MODE_RH

        _make_type(db_session, code="ENFANT_MALADE", libelle="Enfant malade", unite="heures")
        # Pas de nb_heures_exceptionnelles → erreur.
        result = construire_conge(
            users["salarie_sans_resp"], self._payload("ENFANT_MALADE"),
            mode=MODE_RH, statut_initial="valide",
        )
        assert not result.success

        result_ok = construire_conge(
            users["salarie_sans_resp"],
            self._payload("ENFANT_MALADE", nb_heures_exceptionnelles="4"),
            mode=MODE_RH, statut_initial="valide",
        )
        assert result_ok.success
        assert result_ok.conge.nb_heures_exceptionnelles == 4


# --------------------------------------------------------------------------- #
# Route RH : gestion des types
# --------------------------------------------------------------------------- #
class TestRouteTypesExceptionnels:
    def test_create_plafond_invalide_refuse(self, client, db_session, users):
        login(client, "rh1", "rh123")
        resp = client.post("/rh/types-exceptionnels", data={
            "action": "create",
            "code": "MARIAGE",
            "libelle": "Mariage",
            "unite": "jours",
            "plafond_annuel": "abc",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Aucun type ne doit avoir été créé.
        assert CongeExceptionnelType.query.filter_by(code="MARIAGE").first() is None

    def test_create_valide(self, client, db_session, users):
        login(client, "rh1", "rh123")
        client.post("/rh/types-exceptionnels", data={
            "action": "create",
            "code": "mariage",  # sera mis en majuscules
            "libelle": "Mariage",
            "unite": "jours",
            "plafond_annuel": "5",
        }, follow_redirects=True)
        t = CongeExceptionnelType.query.filter_by(code="MARIAGE").first()
        assert t is not None
        assert t.plafond_annuel == 5

    def test_update_plafond_invalide_ne_modifie_pas(self, client, db_session, users):
        t = _make_type(db_session, plafond=5)
        login(client, "rh1", "rh123")
        client.post("/rh/types-exceptionnels", data={
            "action": "update",
            "type_id": str(t.id),
            "libelle": "Mariage",
            "unite": "jours",
            "plafond_annuel": "oops",
        }, follow_redirects=True)
        db_session.session.refresh(t)
        # Le plafond existant ne doit pas avoir été écrasé par une saisie invalide.
        assert t.plafond_annuel == 5


# --------------------------------------------------------------------------- #
# Intégration : recheck du plafond à la validation RH
# --------------------------------------------------------------------------- #
class TestPlafondAValidationRH:
    def test_seconde_demande_refusee_a_la_validation(self, client, db_session, users, parametrage):
        """Deux demandes passent la création (plafond compté sur les validés),
        mais la seconde est bloquée au moment de la validation RH."""
        _make_type(db_session, plafond=5)
        sal = users["salarie"].id

        # A déjà validé (3 jours), B en attente RH (3 jours) → A + B = 6 > 5.
        _make_conge_exc(
            db_session, sal, statut="valide", nb_jours=3.0,
            debut=date(2026, 6, 1), fin=date(2026, 6, 3),
        )
        b = _make_conge_exc(
            db_session, sal, statut="en_attente_rh", nb_jours=3.0,
            debut=date(2026, 6, 8), fin=date(2026, 6, 10),
        )

        login(client, "rh1", "rh123")
        client.post(f"/rh/conge/{b.id}/valider", follow_redirects=True)

        db_session.session.refresh(b)
        assert b.statut == "en_attente_rh"  # resté bloqué

    def test_validation_ok_sous_plafond(self, client, db_session, users, parametrage):
        _make_type(db_session, plafond=6)
        sal = users["salarie"].id
        _make_conge_exc(
            db_session, sal, statut="valide", nb_jours=3.0,
            debut=date(2026, 6, 1), fin=date(2026, 6, 3),
        )
        b = _make_conge_exc(
            db_session, sal, statut="en_attente_rh", nb_jours=3.0,
            debut=date(2026, 6, 8), fin=date(2026, 6, 10),
        )

        login(client, "rh1", "rh123")
        client.post(f"/rh/conge/{b.id}/valider", follow_redirects=True)

        db_session.session.refresh(b)
        assert b.statut == "valide"
