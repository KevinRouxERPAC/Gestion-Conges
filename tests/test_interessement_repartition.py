"""Tests de la répartition du montant total d'intéressement en euros."""
from datetime import date

from models import db
from models.conge import Conge
from models.interessement_periode import InteressementPeriode
from services.interessement import calculer_interessement


def _periode(db_session, montant=None, malus=5.0):
    p = InteressementPeriode(
        libelle="2026",
        date_debut=date(2026, 1, 1),
        date_fin=date(2026, 12, 31),
        base_points=100,
        plancher_points=0,
        montant_total_euros=montant,
        malus_maladie_par_jour=malus,
        actif=True,
    )
    db_session.session.add(p)
    db_session.session.commit()
    return p


class TestRepartitionMontant:
    def test_sans_montant_part_euros_none(self, db_session, users):
        p = _periode(db_session, montant=None)
        res = calculer_interessement(p)
        assert all(r.part_euros is None for r in res)

    def test_montant_reparti_au_prorata(self, db_session, users):
        p = _periode(db_session, montant=1000.0)
        res = calculer_interessement(p)
        parts = [r.part_euros for r in res if r.actif]
        assert len(parts) == 2
        for part in parts:
            assert part == 500.0

    def test_somme_parts_egale_montant_exact(self, db_session, users):
        p = _periode(db_session, montant=100.0)
        res = calculer_interessement(p)
        parts = [r.part_euros for r in res if r.actif]
        assert abs(sum(parts) - 100.0) < 0.01

    def test_montant_negatif_ou_zero_desactive(self, db_session, users):
        p_zero = _periode(db_session, montant=0.0)
        res = calculer_interessement(p_zero)
        assert all(r.part_euros is None for r in res)

    def test_seule_maladie_impacte(self, db_session, users):
        p = _periode(db_session, montant=200.0, malus=10.0)
        salarie = users["salarie"]
        db.session.add(Conge(
            user_id=salarie.id,
            date_debut=date(2026, 3, 1),
            date_fin=date(2026, 3, 3),
            nb_jours_ouvrables=3,
            type_conge="Maladie",
            statut="valide",
        ))
        db.session.add(Conge(
            user_id=salarie.id,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 10),
            nb_jours_ouvrables=7,
            type_conge="CP",
            statut="valide",
        ))
        db.session.commit()

        res = {r.user_id: r for r in calculer_interessement(p)}
        r_salarie = res[salarie.id]
        r_autre = res[users["salarie_sans_resp"].id]
        assert r_salarie.jours_maladie == 3
        assert r_salarie.points_final == 70.0
        assert r_autre.points_final == 100.0
        assert abs(r_salarie.part_euros - round(200 * 70 / 170, 2)) < 0.01
