"""Tests du calcul de soldes CP et RTT."""
from datetime import date
from models.conge import Conge
from services.solde import (
    calculer_solde,
    calculer_jours_cps_consommes,
    calculer_heures_rtt_consommes,
    get_parametrage_actif,
    verifier_solde_suffisant,
    verifier_solde_rtt_suffisant,
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
        assert solde["cp_restant"] == 25
        assert solde["anciennete_restante"] == 2

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
        assert solde["cp_restant"] == 20
        assert solde["anciennete_restante"] == 2

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
        assert solde["cp_restant"] == 23
        assert solde["anciennete_restante"] == 2

    def test_priorite_cp_avant_anciennete(self, db_session, users, parametrage, allocations):
        """La consommation doit d'abord utiliser les CP, puis l'ancienneté."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30),
            nb_jours_ouvrables=26,
            type_conge="CP",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        solde = calculer_solde(users["salarie"].id)
        assert solde["total_consomme"] == 26
        assert solde["cp_restant"] == 0
        assert solde["anciennete_restante"] == 1

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


class TestVerificationSolde:
    def test_solde_cp_suffisant(self, db_session, users, parametrage, allocations):
        assert verifier_solde_suffisant(users["salarie"].id, 10) is True

    def test_solde_cp_insuffisant(self, db_session, users, parametrage, allocations):
        assert verifier_solde_suffisant(users["salarie"].id, 30) is False

    def test_solde_rtt_suffisant(self, db_session, users, parametrage, allocations):
        assert verifier_solde_rtt_suffisant(users["salarie"].id, 10) is True

    def test_solde_rtt_insuffisant(self, db_session, users, parametrage, allocations):
        assert verifier_solde_rtt_suffisant(users["salarie"].id, 20) is False

    def test_solde_cp_avec_exclusion_conge(self, db_session, users, parametrage, allocations):
        """En modification : le congé exclu doit être ré-ajouté au solde disponible."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30),
            nb_jours_ouvrables=22,
            type_conge="CP",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        assert verifier_solde_suffisant(users["salarie"].id, 22) is False
        assert verifier_solde_suffisant(users["salarie"].id, 22, conge_id_exclu=conge.id) is True

    def test_solde_cp_exactement_egal_total_alloue(self, db_session, users, parametrage, allocations):
        """Demande égale au total alloué doit être acceptée."""
        assert verifier_solde_suffisant(users["salarie"].id, 27) is True

    def test_solde_rtt_exactement_egal_total_alloue(self, db_session, users, parametrage, allocations):
        """RTT demandées égales au total alloué doivent être acceptées."""
        assert verifier_solde_rtt_suffisant(users["salarie"].id, 14) is True


class TestGenerationAllocations:
    def test_generer_allocations(self, db_session, users, parametrage):
        """generer_allocations_pour_parametrage doit créer une allocation par salarié actif."""
        from models.parametrage import AllocationConge
        generer_allocations_pour_parametrage(parametrage)

        allocs = AllocationConge.query.filter_by(parametrage_id=parametrage.id).all()
        assert len(allocs) >= 3  # rh + responsable + 2 salariés (tous actifs)
        for a in allocs:
            assert a.jours_alloues == 25
            assert a.rtt_heures_allouees == 14

    def test_generer_allocations_reporte_solde_negatif_precedent(self, db_session, users):
        """Un solde négatif CP/RTT de l'exercice précédent doit réduire la nouvelle allocation."""
        from models.parametrage import ParametrageAnnuel, AllocationConge

        param_old = ParametrageAnnuel(
            debut_exercice=date(2025, 1, 1),
            fin_exercice=date(2025, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=False,
        )
        param_new = ParametrageAnnuel(
            debut_exercice=date(2026, 1, 1),
            fin_exercice=date(2026, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=True,
        )
        db_session.session.add_all([param_old, param_new])
        db_session.session.flush()

        alloc_old = AllocationConge(
            user_id=users["salarie"].id,
            parametrage_id=param_old.id,
            jours_alloues=25,
            jours_anciennete=0,
            jours_report=0,
            rtt_heures_allouees=14,
            rtt_heures_reportees=0,
        )
        db_session.session.add(alloc_old)

        db_session.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2025, 6, 1),
            date_fin=date(2025, 7, 11),
            nb_jours_ouvrables=30,
            type_conge="CP",
            statut="valide",
        ))
        db_session.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2025, 9, 1),
            date_fin=date(2025, 9, 1),
            nb_jours_ouvrables=1,
            type_conge="RTT",
            nb_heures_rtt=20,
            statut="valide",
        ))
        db_session.session.commit()

        generer_allocations_pour_parametrage(param_new)

        alloc_new = AllocationConge.query.filter_by(
            user_id=users["salarie"].id,
            parametrage_id=param_new.id,
        ).first()
        assert alloc_new is not None
        assert alloc_new.jours_report == -5
        assert alloc_new.rtt_heures_reportees == -6

    def test_generer_allocations_reprend_anciennete_exercice_precedent(self, db_session, users):
        """La création d'un nouvel exercice doit reprendre les jours d'ancienneté par salarié."""
        from models.parametrage import ParametrageAnnuel, AllocationConge

        param_old = ParametrageAnnuel(
            debut_exercice=date(2025, 1, 1),
            fin_exercice=date(2025, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=False,
        )
        param_new = ParametrageAnnuel(
            debut_exercice=date(2026, 1, 1),
            fin_exercice=date(2026, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=True,
        )
        db_session.session.add_all([param_old, param_new])
        db_session.session.flush()

        alloc_old = AllocationConge(
            user_id=users["salarie"].id,
            parametrage_id=param_old.id,
            jours_alloues=25,
            jours_anciennete=7,
            jours_report=0,
            rtt_heures_allouees=14,
            rtt_heures_reportees=0,
        )
        db_session.session.add(alloc_old)
        db_session.session.commit()

        generer_allocations_pour_parametrage(param_new)

        alloc_new = AllocationConge.query.filter_by(
            user_id=users["salarie"].id,
            parametrage_id=param_new.id,
        ).first()
        assert alloc_new is not None
        assert alloc_new.jours_alloues == 25
        assert alloc_new.jours_anciennete == 7

    def test_generer_allocations_calcule_anciennete_depuis_embauche(self, db_session, users):
        """Sans allocation précédente, l'ancienneté doit être calculée depuis la date d'embauche."""
        from models.parametrage import ParametrageAnnuel, AllocationConge

        users["salarie"].date_embauche = date(2014, 1, 1)  # 12 ans au 01/01/2026 -> 2 jours
        db_session.session.commit()

        param_new = ParametrageAnnuel(
            debut_exercice=date(2026, 1, 1),
            fin_exercice=date(2026, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=True,
        )
        db_session.session.add(param_new)
        db_session.session.commit()

        generer_allocations_pour_parametrage(param_new)

        alloc_new = AllocationConge.query.filter_by(
            user_id=users["salarie"].id,
            parametrage_id=param_new.id,
        ).first()
        assert alloc_new is not None
        assert alloc_new.jours_anciennete == 2

    def test_generer_allocations_recalcule_si_anciennete_a_zero(self, db_session, users):
        """Une allocation existante à 0 jour d'ancienneté doit être recalculée."""
        from models.parametrage import ParametrageAnnuel, AllocationConge

        users["salarie"].date_embauche = date(2010, 1, 1)  # 16 ans au 01/01/2026 -> 3 jours
        db_session.session.commit()

        param = ParametrageAnnuel(
            debut_exercice=date(2026, 1, 1),
            fin_exercice=date(2026, 12, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=True,
        )
        db_session.session.add(param)
        db_session.session.flush()

        alloc = AllocationConge(
            user_id=users["salarie"].id,
            parametrage_id=param.id,
            jours_alloues=25,
            jours_anciennete=0,
            jours_report=0,
            rtt_heures_allouees=14,
            rtt_heures_reportees=0,
        )
        db_session.session.add(alloc)
        db_session.session.commit()

        generer_allocations_pour_parametrage(param)

        alloc_after = AllocationConge.query.filter_by(
            user_id=users["salarie"].id,
            parametrage_id=param.id,
        ).first()
        assert alloc_after is not None
        assert alloc_after.jours_anciennete == 3


class TestAutoChangementExercice:
    def test_auto_bascule_exercice_quand_termine(self, db_session, users):
        """Si l'exercice actif est terminé, get_parametrage_actif doit créer/activer le suivant."""
        from models.parametrage import ParametrageAnnuel, AllocationConge

        param_old = ParametrageAnnuel(
            debut_exercice=date(2025, 4, 1),
            fin_exercice=date(2026, 3, 31),
            jours_conges_defaut=25,
            rtt_heures_defaut=14,
            actif=True,
        )
        db_session.session.add(param_old)
        db_session.session.commit()

        # "Aujourd'hui" après la fin d'exercice
        param_active = get_parametrage_actif(today=date(2026, 4, 2))
        assert param_active is not None
        assert param_active.actif is True
        assert param_active.id != param_old.id
        assert param_active.debut_exercice == date(2026, 4, 1)
        assert param_active.fin_exercice == date(2027, 3, 31)

        # Un seul exercice actif en base
        assert ParametrageAnnuel.query.filter_by(actif=True).count() == 1

        # Allocations générées pour les utilisateurs actifs
        for u in (users["rh"], users["responsable"], users["salarie"], users["salarie_sans_resp"]):
            alloc = AllocationConge.query.filter_by(user_id=u.id, parametrage_id=param_active.id).first()
            assert alloc is not None
