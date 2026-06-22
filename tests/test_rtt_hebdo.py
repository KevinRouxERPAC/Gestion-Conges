"""Tests du calcul RTT hebdomadaire tenant compte des absences (points 7 + 9)."""
from datetime import date

from models import db
from models.conge import Conge
from models.heures_hebdo import HeuresHebdo
from models.parametrage import AllocationConge
from services.rtt_hebdo import (
    calculer_rtt_semaine,
    calculer_rtt_hebdo,
    maj_rtt_allocations_hebdo,
    jours_absence_semaine,
    seuil_hebdo_param,
    heures_par_jour_absence_param,
    SEUIL_HEBDO_DEFAUT,
    HEURES_PAR_JOUR_DEFAUT,
)


class TestCalculRttSemaine:
    def test_semaine_complete_surplus(self):
        # 39 h travaillées, seuil 35, aucune absence -> 4 h RTT.
        assert calculer_rtt_semaine(39, 0, seuil_hebdo=35, heures_par_jour=7, coef=1.0) == 4.0

    def test_absence_ne_penalise_pas(self):
        # 1 jour d'absence -> seuil ajusté 28. 28 h travaillées -> 0 RTT (pas de perte).
        assert calculer_rtt_semaine(28, 1, seuil_hebdo=35, heures_par_jour=7, coef=1.0) == 0.0

    def test_absence_surplus_proratise(self):
        # 1 jour d'absence -> seuil 28. 31 h travaillées -> 3 h RTT.
        assert calculer_rtt_semaine(31, 1, seuil_hebdo=35, heures_par_jour=7, coef=1.0) == 3.0

    def test_sous_le_seuil_zero(self):
        assert calculer_rtt_semaine(30, 0, seuil_hebdo=35, heures_par_jour=7, coef=1.0) == 0.0

    def test_coef_applique(self):
        assert calculer_rtt_semaine(39, 0, seuil_hebdo=35, heures_par_jour=7, coef=0.5) == 2.0

    def test_deux_jours_absence(self):
        # 2 jours d'absence -> seuil 21. 24 h travaillées -> 3 h.
        assert calculer_rtt_semaine(24, 2, seuil_hebdo=35, heures_par_jour=7, coef=1.0) == 3.0


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
        # Semaine 1 (sans absence) : 39 h -> 4 h RTT.
        db.session.add(HeuresHebdo(user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=39))
        # Semaine 2 (1 jour de congé) : 31 h, seuil ajusté 28 -> 3 h RTT.
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

        res = maj_rtt_allocations_hebdo(parametrage)
        assert res  # au moins une allocation traitée

        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=parametrage.id
        ).first()
        # 4 + 3 = 7 h RTT acquises.
        assert alloc.rtt_heures_allouees == 7

    def test_recalcul_applique_par_defaut(self, db_session, users, parametrage, allocations):
        # Le calcul hebdomadaire est désormais le seul mode RTT : il s'applique
        # toujours, sans configuration de mode particulière.
        db.session.add(HeuresHebdo(user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=39))
        db.session.commit()

        res = maj_rtt_allocations_hebdo(parametrage)
        assert res  # recalcul effectué

        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=parametrage.id
        ).first()
        # 39 h, seuil 35, aucune absence -> 4 h RTT.
        assert alloc.rtt_heures_allouees == 4


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
        # 33 h travaillées, seuil 30 -> 3 h RTT.
        assert alloc.rtt_heures_allouees == 3

    def test_heures_par_jour_absence_personnalise(self, db_session, users, parametrage, allocations):
        parametrage.rtt_heures_par_jour_absence = 6
        db.session.commit()

        # 1 jour d'absence : seuil ajusté 35 - 6 = 29. 31 h travaillées -> 2 h RTT.
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
        assert alloc.rtt_heures_allouees == 2

    def test_helpers_fallback_defaut(self, db_session, parametrage):
        assert seuil_hebdo_param(None) == SEUIL_HEBDO_DEFAUT
        assert heures_par_jour_absence_param(None) == HEURES_PAR_JOUR_DEFAUT
        assert seuil_hebdo_param(parametrage) == 35
        assert heures_par_jour_absence_param(parametrage) == 7


class TestBaseAcquisitionHebdo:
    """Acquisition automatique de RTT par semaine (ex. 0,35 h), proratisée."""

    def _param(self, db_session, **kw):
        from models.parametrage import ParametrageAnnuel

        defaults = dict(
            debut_exercice=date(2026, 6, 1),  # un lundi
            fin_exercice=date(2026, 6, 28),
            jours_conges_defaut=25,
            actif=False,
        )
        defaults.update(kw)
        p = ParametrageAnnuel(**defaults)
        db.session.add(p)
        db.session.commit()
        return p

    def test_base_acquise_chaque_semaine_sans_absence(self, db_session, users):
        # 2026-06-01 lundi → semaines 01, 08, 15, 22 (29 > 28) = 4 semaines.
        p = self._param(db_session, rtt_acquis_par_semaine=1.0)
        res = calculer_rtt_hebdo(users["salarie"].id, p)
        assert res.nb_semaines == 4
        assert res.rtt_calculee == 4
        assert all(d["base"] == 1.0 for d in res.detail)

    def test_base_proratisee_par_absence(self, db_session, users):
        p = self._param(db_session, fin_exercice=date(2026, 6, 7), rtt_acquis_par_semaine=1.0)
        db.session.add(Conge(
            user_id=users["salarie"].id, date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=1, type_conge="CP", statut="valide",
        ))
        db.session.commit()
        res = calculer_rtt_hebdo(users["salarie"].id, p)
        assert res.nb_semaines == 1
        # présence (5-1)/5 = 0.8 → base 0,8 h.
        assert res.detail[0]["base"] == 0.8

    def test_base_plus_heures_sup(self, db_session, users):
        p = self._param(db_session, fin_exercice=date(2026, 6, 7), rtt_acquis_par_semaine=1.0)
        db.session.add(HeuresHebdo(
            user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=39
        ))
        db.session.commit()
        res = calculer_rtt_hebdo(users["salarie"].id, p)
        # base 1,0 + surplus (39 - 35) = 5 h.
        assert res.detail[0]["base"] == 1.0
        assert res.detail[0]["surplus"] == 4.0
        assert res.rtt_calculee == 5

    def test_sans_base_comportement_historique(self, db_session, users):
        # base 0 → seules les semaines saisies comptent (pas toutes les semaines).
        p = self._param(db_session, rtt_acquis_par_semaine=0.0)
        db.session.add(HeuresHebdo(
            user_id=users["salarie"].id, date_lundi=date(2026, 6, 1), heures_travaillees=39
        ))
        db.session.commit()
        res = calculer_rtt_hebdo(users["salarie"].id, p)
        assert res.nb_semaines == 1
        assert res.rtt_calculee == 4

    def test_fractions_heure_preservees_pas_tronquees(self, db_session, users):
        # R3 : 0,35 h/sem sur 3 semaines = 1,05 h (et non 1 h tronqué).
        from datetime import timedelta
        debut = date(2026, 6, 1)  # lundi
        p = self._param(
            db_session, debut_exercice=debut, fin_exercice=date(2026, 6, 21),
            rtt_acquis_par_semaine=0.35,
        )
        res = calculer_rtt_hebdo(users["salarie"].id, p)
        assert res.nb_semaines == 3
        assert res.rtt_calculee == 1.05

    def test_cas_plan_046_semaines(self, db_session, users):
        # Cas du plan : 0,35 h/sem × 46 sem ≈ 16,1 h, surtout pas 16 h.
        from datetime import timedelta
        debut = date(2026, 6, 1)  # lundi
        fin = debut + timedelta(weeks=45, days=6)  # 46 lundis inclus
        p = self._param(
            db_session, debut_exercice=debut, fin_exercice=fin,
            rtt_acquis_par_semaine=0.35,
        )
        res = calculer_rtt_hebdo(users["salarie"].id, p)
        assert res.nb_semaines == 46
        assert res.rtt_calculee == 16.1
        assert res.rtt_calculee != 16
