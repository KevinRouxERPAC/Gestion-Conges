"""Tests du calcul RTT hebdomadaire tenant compte des absences (points 7 + 9)."""
from datetime import date

from models import db
from models.conge import Conge
from models.heures_hebdo import HeuresHebdo
from models.parametrage import AllocationConge
from services.rtt_hebdo import (
    calculer_rtt_semaine,
    maj_rtt_allocations_hebdo,
    jours_absence_semaine,
    seuil_hebdo_param,
    heures_par_jour_absence_param,
    SEUIL_HEBDO_DEFAUT,
    HEURES_PAR_JOUR_DEFAUT,
)

SEUIL = 34.65


class TestCalculRttSemaine:
    def test_semaine_complete_surplus(self):
        assert calculer_rtt_semaine(39, 0, seuil_hebdo=SEUIL, heures_par_jour=7, coef=1.0) == 4.35

    def test_absence_ne_penalise_pas(self):
        assert calculer_rtt_semaine(28, 1, seuil_hebdo=SEUIL, heures_par_jour=7, coef=1.0) == 0.35

    def test_absence_surplus_proratise(self):
        assert calculer_rtt_semaine(31, 1, seuil_hebdo=SEUIL, heures_par_jour=7, coef=1.0) == 3.35

    def test_sous_le_seuil_zero(self):
        assert calculer_rtt_semaine(30, 0, seuil_hebdo=SEUIL, heures_par_jour=7, coef=1.0) == 0.0

    def test_semaine_35h_produit_035(self):
        assert calculer_rtt_semaine(35, 0, seuil_hebdo=SEUIL, heures_par_jour=7, coef=1.0) == 0.35

    def test_coef_applique(self):
        # Arrondi à 2 décimales (centièmes d'heure) : round(4.35 * 0.5, 2) = 2.18.
        assert calculer_rtt_semaine(39, 0, seuil_hebdo=SEUIL, heures_par_jour=7, coef=0.5) == 2.18

    def test_deux_jours_absence(self):
        assert calculer_rtt_semaine(24, 2, seuil_hebdo=SEUIL, heures_par_jour=7, coef=1.0) == 3.35


class TestJoursAbsenceSemaine:
    def test_un_jour_de_conge(self, db_session, users, parametrage):
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 1),
            nb_jours_ouvrables=1,
            type_conge="CP",
            statut="valide",
        )
        db.session.add(c)
        db.session.commit()
        assert jours_absence_semaine(users["salarie"].id, date(2026, 6, 1)) == 1.0

    def test_demi_journee_compte_un_demi(self, db_session, users, parametrage):
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2),
            date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=0.5,
            type_conge="RTT",
            nb_heures_rtt=4,
            demi_journee_debut="apres_midi",
            statut="valide",
        )
        db.session.add(c)
        db.session.commit()
        assert jours_absence_semaine(users["salarie"].id, date(2026, 6, 1)) == 0.5


class TestMajAllocationsHebdo:
    def test_recalcul_avec_absence(self, db_session, users, parametrage, allocations):
        parametrage.rtt_seuil_hebdo = SEUIL
        db.session.commit()
        db.session.add(HeuresHebdo(user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=39))
        db.session.add(HeuresHebdo(user_id=users["salarie"].id, date_lundi=date(2026, 6, 8), heures_travaillees=31))
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 8),
            date_fin=date(2026, 6, 8),
            nb_jours_ouvrables=1,
            type_conge="CP",
            statut="valide",
        ))
        db.session.commit()

        maj_rtt_allocations_hebdo(parametrage)
        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=parametrage.id
        ).first()
        assert alloc.rtt_heures_allouees == 7.7

    def test_recalcul_applique_par_defaut(self, db_session, users, parametrage, allocations):
        parametrage.rtt_seuil_hebdo = SEUIL
        db.session.commit()
        db.session.add(HeuresHebdo(user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=39))
        db.session.commit()

        maj_rtt_allocations_hebdo(parametrage)
        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=parametrage.id
        ).first()
        assert alloc.rtt_heures_allouees == 4.35


class TestParametrageSeuilRtt:
    def test_seuil_hebdo_personnalise(self, db_session, users, parametrage, allocations):
        parametrage.rtt_seuil_hebdo = 30
        db.session.commit()

        db.session.add(HeuresHebdo(
            user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=33
        ))
        db.session.commit()

        maj_rtt_allocations_hebdo(parametrage)
        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=parametrage.id
        ).first()
        assert alloc.rtt_heures_allouees == 3

    def test_heures_par_jour_absence_personnalise(self, db_session, users, parametrage, allocations):
        parametrage.rtt_seuil_hebdo = SEUIL
        parametrage.rtt_heures_par_jour_absence = 6
        db.session.commit()

        db.session.add(HeuresHebdo(
            user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=31
        ))
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2),
            date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=1,
            type_conge="CP",
            statut="valide",
        ))
        db.session.commit()

        maj_rtt_allocations_hebdo(parametrage)
        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=parametrage.id
        ).first()
        assert alloc.rtt_heures_allouees == 2.35

    def test_helpers_fallback_defaut(self, db_session, parametrage):
        assert seuil_hebdo_param(None) == SEUIL_HEBDO_DEFAUT
        assert heures_par_jour_absence_param(None) == HEURES_PAR_JOUR_DEFAUT


class TestTypesAbsenceExclus:
    def test_maladie_ne_reduit_pas_le_seuil(self, db_session, users, parametrage, allocations):
        parametrage.rtt_seuil_hebdo = SEUIL
        parametrage.rtt_types_absence_exclus = "Maladie"
        db.session.commit()

        db.session.add(HeuresHebdo(
            user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=38
        ))
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=1, type_conge="Maladie", statut="valide",
        ))
        db.session.commit()

        maj_rtt_allocations_hebdo(parametrage)
        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=parametrage.id
        ).first()
        assert alloc.rtt_heures_allouees == 3.35
