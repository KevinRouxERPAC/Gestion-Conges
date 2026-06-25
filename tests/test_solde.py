"""Tests du calcul de soldes CP et RTT."""
from datetime import date
from models.conge import Conge
from services.solde import (
    calculer_solde,
    calculer_jours_cps_consommes,
    calculer_heures_rtt_consommes,
    generer_allocations_pour_parametrage,
)


class TestCalculSoldeCP:
    def test_solde_sans_allocation(self, db_session, users):
        """Sans allocation, le solde doit être à 0."""
        solde = calculer_solde(users["salarie"].id)
        assert solde["total_alloue"] == 0
        assert solde["solde_restant"] == 0
        assert solde["rtt_total_alloue"] == 0

    def test_solde_avec_allocation(self, db_session, users, parametrage, allocations):
        """Avec allocation : total_alloue = jours_alloues + jours_anciennete + jours_report."""
        solde = calculer_solde(users["salarie"].id)
        assert solde["total_alloue"] == 27  # 25 + 2 + 0
        assert solde["jours_conges"] == 25
        assert solde["jours_anciennete"] == 2
        assert solde["jours_report"] == 0
        assert solde["solde_restant"] == 27
        assert solde["total_consomme"] == 0

    def test_solde_apres_conge_valide(self, db_session, users, parametrage, allocations):
        """Un congé CP validé dans l'exercice doit être comptabilisé."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        assert calculer_jours_cps_consommes(users["salarie"].id) == 5
        solde = calculer_solde(users["salarie"].id)
        assert solde["total_consomme"] == 5
        assert solde["solde_restant"] == 22  # 27 - 5

    def test_anciennete_debite_solde_cp(self, db_session, users, parametrage, allocations):
        """Un congé de type Ancienneté doit aussi débiter le solde CP."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 3, 2),
            date_fin=date(2026, 3, 3),
            nb_jours_ouvrables=2,
            type_conge="Anciennete",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        assert calculer_jours_cps_consommes(users["salarie"].id) == 2
        solde = calculer_solde(users["salarie"].id)
        assert solde["solde_restant"] == 25  # 27 - 2

    def test_sans_solde_pas_debit(self, db_session, users, parametrage, allocations):
        """Un congé Sans solde ne débite ni CP ni RTT."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 3),
            nb_jours_ouvrables=3,
            type_conge="Sans solde",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        solde = calculer_solde(users["salarie"].id)
        assert solde["total_consomme"] == 0
        assert solde["solde_restant"] == 27

    def test_maladie_pas_debit(self, db_session, users, parametrage, allocations):
        """Un congé Maladie ne débite ni CP ni RTT."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 10),
            nb_jours_ouvrables=8,
            type_conge="Maladie",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        solde = calculer_solde(users["salarie"].id)
        assert solde["total_consomme"] == 0
        assert solde["rtt_total_consomme"] == 0

    def test_conge_refuse_pas_comptabilise(self, db_session, users, parametrage, allocations):
        """Un congé CP refusé ne doit pas impacter le solde."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 8, 1),
            date_fin=date(2026, 8, 5),
            nb_jours_ouvrables=5,
            type_conge="CP",
            statut="refuse",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        assert calculer_jours_cps_consommes(users["salarie"].id) == 0
        assert calculer_solde(users["salarie"].id)["solde_restant"] == 27


class TestCalculSoldeRTT:
    def test_solde_rtt_avec_allocation(self, db_session, users, parametrage, allocations):
        """Allocation RTT : 14h allouées, 0h reportées → total 14h."""
        solde = calculer_solde(users["salarie"].id)
        assert solde["rtt_total_alloue"] == 14
        assert solde["rtt_total_consomme"] == 0
        assert solde["rtt_solde_restant"] == 14

    def test_rtt_consomme(self, db_session, users, parametrage, allocations):
        """Un RTT validé de 4h doit être comptabilisé en heures."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 5, 4),
            date_fin=date(2026, 5, 4),
            nb_jours_ouvrables=1,
            type_conge="RTT",
            nb_heures_rtt=4,
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        assert calculer_heures_rtt_consommes(users["salarie"].id) == 4
        solde = calculer_solde(users["salarie"].id)
        assert solde["rtt_total_consomme"] == 4
        assert solde["rtt_solde_restant"] == 10

    def test_rtt_consomme_tout_solde(self, db_session, users, parametrage, allocations):
        """Consommation RTT égale au total alloué → solde 0."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 5, 4),
            date_fin=date(2026, 5, 4),
            nb_jours_ouvrables=1,
            type_conge="RTT",
            nb_heures_rtt=14,
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        solde = calculer_solde(users["salarie"].id)
        assert solde["rtt_total_consomme"] == 14
        assert solde["rtt_solde_restant"] == 0

    def test_rtt_consomme_decimal_non_tronque(self, db_session, users, parametrage, allocations):
        """R3 : une consommation RTT décimale (3,5 h) n'est pas tronquée."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 5, 4),
            date_fin=date(2026, 5, 4),
            nb_jours_ouvrables=0.5,
            type_conge="RTT",
            nb_heures_rtt=3.5,
            demi_journee_debut="matin",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        assert calculer_heures_rtt_consommes(users["salarie"].id) == 3.5
        solde = calculer_solde(users["salarie"].id)
        assert solde["rtt_total_consomme"] == 3.5
        assert solde["rtt_solde_restant"] == 10.5  # 14 - 3,5

    def test_rtt_ne_debite_pas_cp(self, db_session, users, parametrage, allocations):
        """Un RTT ne doit pas impacter le solde CP."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 9, 1),
            date_fin=date(2026, 9, 1),
            nb_jours_ouvrables=1,
            type_conge="RTT",
            nb_heures_rtt=7,
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        solde = calculer_solde(users["salarie"].id)
        assert solde["total_consomme"] == 0
        assert solde["solde_restant"] == 27


class TestSoldesLot:
    """Parité entre calculer_soldes_lot (groupé, anti N+1) et calculer_solde (individuel)."""

    def _seed_conges(self, db_session, uid):
        conges = [
            # CP validé contenu dans l'exercice
            Conge(user_id=uid, date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
                  nb_jours_ouvrables=5, type_conge="CP", statut="valide"),
            # CP en attente RH
            Conge(user_id=uid, date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 2),
                  nb_jours_ouvrables=2, type_conge="CP", statut="en_attente_rh"),
            # RTT validé (heures)
            Conge(user_id=uid, date_debut=date(2026, 5, 4), date_fin=date(2026, 5, 4),
                  nb_jours_ouvrables=1, type_conge="RTT", nb_heures_rtt=4, statut="valide"),
            # Congé à cheval sur le début d'exercice → exerce le prorata des deux côtés
            Conge(user_id=uid, date_debut=date(2025, 12, 29), date_fin=date(2026, 1, 2),
                  nb_jours_ouvrables=5, type_conge="CP", statut="valide"),
        ]
        db_session.session.add_all(conges)
        db_session.session.commit()

    def test_parite_lot_vs_individuel(self, db_session, users, parametrage, allocations):
        from services.solde import calculer_soldes_lot
        s1 = users["salarie"].id
        s2 = users["salarie_sans_resp"].id
        self._seed_conges(db_session, s1)  # s2 reste sans congé

        lot = calculer_soldes_lot([s1, s2], parametrage)
        assert lot[s1] == calculer_solde(s1)
        assert lot[s2] == calculer_solde(s2)
        # Le scénario a bien consommé du CP et du RTT (sinon le test ne prouverait rien).
        assert lot[s1]["total_consomme"] > 0
        assert lot[s1]["rtt_total_consomme"] == 4
        assert lot[s1]["cp_en_attente"] == 2

    def test_lot_user_sans_allocation_egale_zero(self, db_session, users, parametrage):
        from services.solde import calculer_soldes_lot, _solde_zero
        uid = users["responsable"].id  # pas d'allocation (fixture allocations non chargée)
        lot = calculer_soldes_lot([uid], parametrage)
        assert lot[uid] == _solde_zero()
        assert lot[uid] == calculer_solde(uid)

    def test_lot_vide_et_sans_parametrage(self, db_session, users):
        from services.solde import calculer_soldes_lot
        assert calculer_soldes_lot([]) == {}
        uid = users["salarie"].id
        res = calculer_soldes_lot([uid], None)  # aucun paramétrage actif
        assert res[uid]["solde_restant"] == 0


class TestGenerationAllocations:
    def test_generer_allocations(self, db_session, users, parametrage):
        """generer_allocations_pour_parametrage doit créer une allocation par salarié actif."""
        from models.parametrage import AllocationConge
        generer_allocations_pour_parametrage(parametrage)

        allocs = AllocationConge.query.filter_by(parametrage_id=parametrage.id).all()
        assert len(allocs) >= 3  # rh + responsable + 2 salariés (tous actifs)
        for a in allocs:
            assert a.jours_alloues == 25
            # Le RTT n'est plus alloué par forfait : il est calculé en hebdomadaire
            # (0 tant qu'aucune heure hebdomadaire n'est saisie).
            assert a.rtt_heures_allouees == 0
