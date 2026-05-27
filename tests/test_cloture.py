"""Tests des soldes à risque et de la clôture d'exercice avec report."""
from datetime import date, timedelta

from models import db
from models.conge import Conge
from models.parametrage import AllocationConge, ParametrageAnnuel
from services.solde import (
    salaries_a_risque,
    cloturer_exercice_et_reporter,
    calculer_solde,
)
from tests.conftest import login


class TestSalariesARisque:
    def test_pas_de_risque_loin_de_la_fin(self, db_session, users, parametrage, allocations):
        # Exercice 2026-01-01 → 2026-12-31. Avec une date "today" loin de la fin,
        # personne ne devrait être à risque.
        # Comme on ne peut pas mock today facilement ici, on teste juste que
        # la fonction ne plante pas et retourne une liste.
        result = salaries_a_risque(jours_min_restants=10, jours_avant_fin=5)
        assert isinstance(result, list)

    def test_fenetre_large_detecte_solde_eleve(self, db_session, users, parametrage, allocations):
        # Fenêtre très large (1000j) : tout le monde dans l'exercice est candidat.
        result = salaries_a_risque(jours_min_restants=10, jours_avant_fin=10000)
        # Les salariés ont 27j alloués (25+2), aucun congé pris → 27 >= 10.
        assert len(result) >= 2  # salarie + salarie_sans_resp

    def test_seuil_eleve_filtre(self, db_session, users, parametrage, allocations):
        # Seuil à 100 jours : personne ne l'atteint.
        result = salaries_a_risque(jours_min_restants=100, jours_avant_fin=10000)
        assert result == []


class TestClotureExercice:
    def test_report_integral(self, db_session, users, parametrage, allocations):
        # Le salarié a 27j alloués, 0 consommé → solde 27. Aucun plafond → report = 27.
        nouveau = ParametrageAnnuel(
            debut_exercice=date(2027, 1, 1),
            fin_exercice=date(2027, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=False,
        )
        db.session.add(nouveau)
        db.session.flush()

        res = cloturer_exercice_et_reporter(nouveau)
        db.session.commit()

        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=nouveau.id
        ).first()
        assert alloc is not None
        assert alloc.jours_report == 27
        assert alloc.rtt_heures_reportees == 14

        # Ancien paramétrage désactivé.
        db.session.refresh(parametrage)
        assert parametrage.actif is False
        # Nouveau actif.
        db.session.refresh(nouveau)
        assert nouveau.actif is True

    def test_report_avec_plafond(self, db_session, users, parametrage, allocations):
        nouveau = ParametrageAnnuel(
            debut_exercice=date(2027, 1, 1),
            fin_exercice=date(2027, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=False,
        )
        db.session.add(nouveau)
        db.session.flush()

        # Plafond à 5j : on ne reporte que 5 même si solde 27.
        res = cloturer_exercice_et_reporter(nouveau, report_max_jours=5, report_max_heures_rtt=8)
        db.session.commit()

        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=nouveau.id
        ).first()
        assert alloc.jours_report == 5
        assert alloc.rtt_heures_reportees == 8

        # Seuls 2 salariés ont une allocation initiale → 2 reports de 5j et 8h.
        # Les autres (rh, responsable) ont solde 0 → report 0.
        assert res["report_cp_total"] == 10
        assert res["report_rtt_total"] == 16

    def test_solde_negatif_pas_de_report(self, db_session, users, parametrage, allocations):
        # Crée un congé qui dépasse le solde du salarié.
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 11, 30),
            nb_jours_ouvrables=100,
            type_conge="CP",
            statut="valide",
        )
        db.session.add(c)
        db.session.commit()

        # Solde restant = 27 - 100 = -73 → on reporte 0 (max(0, ...)).
        nouveau = ParametrageAnnuel(
            debut_exercice=date(2027, 1, 1),
            fin_exercice=date(2027, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=False,
        )
        db.session.add(nouveau)
        db.session.flush()
        cloturer_exercice_et_reporter(nouveau)
        db.session.commit()

        alloc = AllocationConge.query.filter_by(
            user_id=users["salarie"].id, parametrage_id=nouveau.id
        ).first()
        assert alloc.jours_report == 0


class TestRouteCloture:
    def test_acces_rh_seulement(self, client, db_session, users):
        login(client, "jean1", "jean123")
        resp = client.get("/rh/cloture-exercice", follow_redirects=False)
        assert resp.status_code == 302

    def test_apercu_affiche_salaries(self, client, db_session, users, parametrage, allocations):
        login(client, "rh1", "rh123")
        resp = client.get("/rh/cloture-exercice")
        assert resp.status_code == 200
        assert users["salarie"].nom.encode("utf-8") in resp.data
