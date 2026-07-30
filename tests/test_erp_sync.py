"""Tests de la synchronisation ERP → heures_hebdo (Lot 4).

La connexion SQL Server n'est pas disponible en test : on mocke
`erp_connexion` et `heures_semaine` pour valider la logique d'import
(mapping matricule, upsert, préservation manuelle, mode aperçu).
"""
from datetime import date
from unittest.mock import patch

import pytest

from models import db
from models.heures_hebdo import HeuresHebdo
from models.user import User
from services.erp.requetes import HeuresSemaine, SalarieErp, normaliser_matricule_erp
from services.erp.sync_heures import (
    synchroniser_exercice,
    synchroniser_semaine,
    _lundi_depuis_semaine_erp,
    _semaine_precedente,
    _semaines_erp_exercice,
)


def _ligne(matricule: str, semaine_erp: str, heures: float) -> HeuresSemaine:
    return HeuresSemaine(
        matricule=matricule,
        semaine_erp=semaine_erp,
        heures=heures,
        date_lundi=_lundi_depuis_semaine_erp(semaine_erp),
    )


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_import_creheures_pour_matricule_connenu(mock_heures, mock_conn, db_session, users, parametrage):
    """Un matricule rattaché à un salarié → HeuresHebdo créée avec source='erp'."""
    users["salarie"].matricule = "000011"
    db.session.commit()

    mock_heures.return_value = [_ligne("000011", "202623", 39.0)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 1
    assert rapport.nb_skipped_sans_user == 0
    row = HeuresHebdo.query.filter_by(
        user_id=users["salarie"].id,
        date_lundi=date(2026, 6, 1),  # lundi de la semaine ISO 23 de 2026
    ).first()
    assert row is not None
    assert row.source == "erp"
    assert row.heures_travaillees == 39.0


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
@patch("services.erp.sync_heures.salaries_erp")
def test_import_matricule_inconnu_avertit(mock_salaries, mock_heures, mock_conn, db_session, users, parametrage):
    """Un matricule absent de l'app est signalé, pas bloquant."""
    mock_salaries.return_value = []
    mock_heures.return_value = [_ligne("999999", "202623", 35.0)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 0
    assert rapport.nb_skipped_sans_user == 1
    assert any("999999" in w for w in rapport.avertissements)


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
@patch("services.erp.sync_heures.salaries_erp")
def test_auto_rattache_matricule_par_nom_unique(
    mock_salaries, mock_heures, mock_conn, db_session, users, parametrage
):
    """Si un seul salarié actif sans matricule matche le nom ERP, on le rattache."""
    users["salarie"].matricule = None
    db.session.commit()
    mock_heures.return_value = [_ligne("000011", "202623", 39.0)]
    nom_erp = f"{users['salarie'].nom} {users['salarie'].prenom}"
    mock_salaries.return_value = [SalarieErp(matricule="000011", nom_complet=nom_erp)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 1
    assert users["salarie"].matricule == "000011"
    assert any("auto-rattaché" in w for w in rapport.avertissements)


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
@patch("services.erp.sync_heures.salaries_erp")
def test_auto_rattache_pas_si_nom_ambigu(
    mock_salaries, mock_heures, mock_conn, db_session, users, parametrage
):
    """Le rattachement auto est ignoré en cas d'ambiguïté de nom."""
    users["salarie"].matricule = None
    clone = User(
        nom=users["salarie"].nom,
        prenom=users["salarie"].prenom,
        identifiant="clone_test",
        mot_de_passe_hash=users["salarie"].mot_de_passe_hash,
        role="salarie",
        actif=True,
    )
    db.session.add(clone)
    db.session.commit()
    mock_heures.return_value = [_ligne("000011", "202623", 39.0)]
    nom_erp = f"{users['salarie'].nom} {users['salarie'].prenom}"
    mock_salaries.return_value = [SalarieErp(matricule="000011", nom_complet=nom_erp)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 0
    assert users["salarie"].matricule is None
    assert any("absent de l'app" in w for w in rapport.avertissements)


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_valeur_manuelle_non_ecrasee(mock_heures, mock_conn, db_session, users, parametrage):
    """Une saisie manuelle existante n'est pas écrasée par l'ERP."""
    users["salarie"].matricule = "000011"
    lundi = _lundi_depuis_semaine_erp("202623")
    db.session.add(HeuresHebdo(
        user_id=users["salarie"].id,
        date_lundi=lundi,
        heures_travaillees=40.0,
        source="manuel",
    ))
    db.session.commit()

    mock_heures.return_value = [_ligne("000011", "202623", 35.0)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 0
    row = HeuresHebdo.query.filter_by(user_id=users["salarie"].id, date_lundi=lundi).first()
    assert row.heures_travaillees == 40.0  # inchangée
    assert row.source == "manuel"
    assert any("manuelle conservée" in w for w in rapport.avertissements)


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_valeur_erp_reimportee_ecrase(mock_heures, mock_conn, db_session, users, parametrage):
    """Une valeur source='erp' existante est mise à jour par un nouvel import."""
    users["salarie"].matricule = "000011"
    lundi = _lundi_depuis_semaine_erp("202623")
    db.session.add(HeuresHebdo(
        user_id=users["salarie"].id,
        date_lundi=lundi,
        heures_travaillees=30.0,
        source="erp",
    ))
    db.session.commit()

    mock_heures.return_value = [_ligne("000011", "202623", 38.5)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 1
    row = HeuresHebdo.query.filter_by(user_id=users["salarie"].id, date_lundi=lundi).first()
    assert row.heures_travaillees == 38.5


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_dry_run_n_ecrit_rien(mock_heures, mock_conn, db_session, users, parametrage):
    """Le mode aperçu remplit preview mais ne crée aucune ligne en base."""
    users["salarie"].matricule = "000011"
    db.session.commit()

    mock_heures.return_value = [_ligne("000011", "202623", 39.0)]

    rapport = synchroniser_semaine(
        semaine_erp="202623", recalculer_rtt=False, dry_run=True
    )

    assert rapport.dry_run is True
    assert rapport.nb_importes == 1
    assert len(rapport.preview) == 1
    assert rapport.preview[0]["heures_erp"] == 39.0
    assert rapport.preview[0]["action"] == "import"
    # Aucune ligne en base.
    assert HeuresHebdo.query.filter_by(user_id=users["salarie"].id).count() == 0


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_dry_run_affiche_ancienne_valeur(mock_heures, mock_conn, db_session, users, parametrage):
    """En aperçu, l'ancienne valeur ERP est exposée pour comparaison."""
    users["salarie"].matricule = "000011"
    lundi = _lundi_depuis_semaine_erp("202623")
    db.session.add(HeuresHebdo(
        user_id=users["salarie"].id,
        date_lundi=lundi,
        heures_travaillees=30.0,
        source="erp",
    ))
    db.session.commit()

    mock_heures.return_value = [_ligne("000011", "202623", 38.0)]

    rapport = synchroniser_semaine(
        semaine_erp="202623", recalculer_rtt=False, dry_run=True
    )

    assert rapport.preview[0]["ancienne_valeur"] == 30.0
    assert rapport.preview[0]["heures_erp"] == 38.0
    # La base n'a pas bougé.
    row = HeuresHebdo.query.filter_by(user_id=users["salarie"].id, date_lundi=lundi).first()
    assert row.heures_travaillees == 30.0


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_aucune_heure_renvoie_avertissement(mock_heures, mock_conn, db_session, parametrage):
    mock_heures.return_value = []
    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)
    assert rapport.nb_importes == 0
    assert any("Aucune heure" in w for w in rapport.avertissements)


def test_semaine_precedente_format_aaaass():
    s = _semaine_precedente(reference=date(2026, 6, 12))  # vendredi
    # Semaine précédente = semaine 23 du 1er juin 2026.
    assert s == "202623"


def test_lundi_depuis_semaine_erp():
    assert _lundi_depuis_semaine_erp("202623") == date(2026, 6, 1)


class TestNormaliserMatricule:
    def test_zeros_initiaux(self):
        assert normaliser_matricule_erp("24") == "000024"
        assert normaliser_matricule_erp("000024") == "000024"
        assert normaliser_matricule_erp("  11  ") == "000011"


@patch("services.erp.sync_heures.salaries_erp")
@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_import_matricule_format_erp_avec_zeros(
    mock_heures, mock_conn, mock_salaries, db_session, users, parametrage
):
    """ERP '000024' matche un salarié saisi avec '24'."""
    users["salarie"].matricule = "24"
    db.session.commit()
    mock_salaries.return_value = []
    mock_heures.return_value = [_ligne("000024", "202623", 35.0)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 1
    assert rapport.nb_skipped_sans_user == 0


@patch("services.erp.sync_heures.salaries_erp")
@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_semaine")
def test_import_matricule_format_erp_sans_zeros(
    mock_heures, mock_conn, mock_salaries, db_session, users, parametrage
):
    """ERP '24' matche un salarié saisi avec '000024'."""
    users["salarie"].matricule = "000024"
    db.session.commit()
    mock_salaries.return_value = []
    mock_heures.return_value = [_ligne("24", "202623", 35.0)]

    rapport = synchroniser_semaine(semaine_erp="202623", recalculer_rtt=False)

    assert rapport.nb_importes == 1
    assert rapport.nb_skipped_sans_user == 0


@patch("services.erp.sync_heures.erp_connexion")
@patch("services.erp.sync_heures.heures_periode")
@patch("services.erp.sync_heures.salaries_erp")
def test_import_exercice_plusieurs_semaines(
    mock_salaries, mock_heures_periode, mock_conn, db_session, users, parametrage
):
    """L'import exercice récupère toutes les semaines depuis le début de l'exercice."""
    users["salarie"].matricule = "000011"
    db.session.commit()
    mock_salaries.return_value = []
    mock_heures_periode.return_value = [
        _ligne("000011", "202601", 38.0),
        _ligne("000011", "202602", 40.0),
    ]

    rapport = synchroniser_exercice(recalculer_rtt=False)

    assert rapport.nb_importes == 2
    assert len(rapport.semaines) > 0
    assert HeuresHebdo.query.filter_by(user_id=users["salarie"].id).count() == 2


def test_semaines_erp_exercice_couvre_debut_a_aujourdhui(parametrage):
    semaines = _semaines_erp_exercice(parametrage, jusqu_a=date(2026, 1, 12))
    assert semaines[0] == "202601"
    assert "202603" in semaines
    assert "202604" not in semaines
