"""Tests du service de rappels automatiques (Phase 3b)."""
from datetime import date, timedelta
from unittest.mock import patch

from models import db
from models.conge import Conge
from models.notification import Notification
from services.rappels import (
    rappels_demandes_en_attente,
    rappels_fin_exercice,
    envoyer_rappels,
    DELAI_RAPPEL_JOURS,
)


class TestRappelsDemandesEnAttente:
    def test_demande_recente_pas_de_notif(self, db_session, users, parametrage):
        # Demande créée aujourd'hui → pas de rappel.
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date.today() + timedelta(days=10),
            date_fin=date.today() + timedelta(days=12),
            nb_jours_ouvrables=3, type_conge="CP",
            statut="en_attente_responsable",
        ))
        db.session.commit()
        nb = rappels_demandes_en_attente()
        assert nb == 0
        assert Notification.query.count() == 0

    def test_demande_ancienne_notifiee_responsable(self, db_session, users, parametrage):
        # Demande créée il y a plus de DELAI_RAPPEL_JOURS.
        ancienne = date.today() - timedelta(days=DELAI_RAPPEL_JOURS + 2)
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date.today() + timedelta(days=10),
            date_fin=date.today() + timedelta(days=12),
            nb_jours_ouvrables=3, type_conge="CP",
            statut="en_attente_responsable",
        )
        c.cree_le = ancienne
        db.session.add(c)
        db.session.commit()

        nb = rappels_demandes_en_attente()
        assert nb == 1
        notifs = Notification.query.filter_by(user_id=users["responsable"].id).all()
        assert len(notifs) == 1
        assert "en attente" in notifs[0].message.lower()

    def test_demande_attente_rh_notifiee_tous_les_rh(self, db_session, users, parametrage):
        ancienne = date.today() - timedelta(days=DELAI_RAPPEL_JOURS + 1)
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date.today() + timedelta(days=10),
            date_fin=date.today() + timedelta(days=12),
            nb_jours_ouvrables=3, type_conge="CP",
            statut="en_attente_rh",
        )
        c.cree_le = ancienne
        db.session.add(c)
        db.session.commit()

        nb = rappels_demandes_en_attente()
        # users["rh"] est le seul RH.
        assert nb == 1
        notifs = Notification.query.filter_by(user_id=users["rh"].id).all()
        assert len(notifs) == 1

    def test_idempotent_pas_de_double_notif(self, db_session, users, parametrage):
        ancienne = date.today() - timedelta(days=DELAI_RAPPEL_JOURS + 1)
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date.today() + timedelta(days=10),
            date_fin=date.today() + timedelta(days=12),
            nb_jours_ouvrables=3, type_conge="CP",
            statut="en_attente_responsable",
        )
        c.cree_le = ancienne
        db.session.add(c)
        db.session.commit()

        n1 = rappels_demandes_en_attente()
        n2 = rappels_demandes_en_attente()  # 2e appel le même jour → idempotent.
        assert n1 == 1
        assert n2 == 0
        assert Notification.query.filter_by(user_id=users["responsable"].id).count() == 1

    def test_demande_validee_pas_notifiee(self, db_session, users, parametrage):
        ancienne = date.today() - timedelta(days=DELAI_RAPPEL_JOURS + 5)
        c = Conge(
            user_id=users["salarie"].id,
            date_debut=date.today() + timedelta(days=10),
            date_fin=date.today() + timedelta(days=12),
            nb_jours_ouvrables=3, type_conge="CP",
            statut="valide",
        )
        c.cree_le = ancienne
        db.session.add(c)
        db.session.commit()
        assert rappels_demandes_en_attente() == 0


class TestRappelsFinExercice:
    def test_aucun_parametrage_retourne_zero(self, db_session, users):
        # Pas de paramétrage actif sur cette session (fixture non appelée).
        # On crée un paramétrage non actif pour s'assurer qu'il n'est pas pris.
        from models.parametrage import ParametrageAnnuel
        p = ParametrageAnnuel(
            debut_exercice=date(2025, 1, 1), fin_exercice=date(2025, 12, 31),
            jours_conges_defaut=25, actif=False,
        )
        db.session.add(p)
        db.session.commit()
        assert rappels_fin_exercice() == 0

    def test_loin_fin_exercice_pas_de_notif(self, db_session, users, parametrage):
        # parametrage fin = 31/12/2026 ; aujourd'hui est loin → pas de rappel.
        nb = rappels_fin_exercice()
        # Si aujourd'hui est loin de la fin (> 90 jours), pas de notif.
        today = date.today()
        if (parametrage.fin_exercice - today).days > 90:
            assert nb == 0

    def test_solde_faible_pas_notifie(self, db_session, users, parametrage, allocations):
        # On manipule la fin d'exercice pour être dans la fenêtre de rappel.
        parametrage.fin_exercice = date.today() + timedelta(days=30)
        # Soldes CP faibles pour tous les salariés actifs.
        for a in allocations.values():
            a.jours_alloues = 5
            a.jours_anciennete = 0
            a.jours_report = 0
        db.session.commit()
        nb = rappels_fin_exercice()
        assert nb == 0

    def test_solde_eleve_dans_fenetre_notifie(self, db_session, users, parametrage, allocations):
        parametrage.fin_exercice = date.today() + timedelta(days=30)
        # Allocation CP élevée (> 10), 0 consommation.
        for a in allocations.values():
            a.jours_alloues = 20
            a.jours_report = 0
            a.jours_anciennete = 0
        db.session.commit()
        nb = rappels_fin_exercice()
        assert nb >= 1
        notifs = Notification.query.filter_by(user_id=users["salarie"].id).all()
        assert len(notifs) == 1
        assert "congés payés" in notifs[0].message


class TestEnvoyerRappels:
    def test_bilan_retourne_dictionnaire(self, db_session, users, parametrage):
        bilan = envoyer_rappels()
        assert "en_attente" in bilan
        assert "fin_exercice" in bilan
        assert isinstance(bilan["en_attente"], int)
        assert isinstance(bilan["fin_exercice"], int)

    def test_erreur_isolee_n_arrete_pas(self, db_session, users, parametrage):
        """Si une des fonctions de rappel lève, l'autre s'exécute quand même."""
        with patch(
            "services.rappels.rappels_demandes_en_attente",
            side_effect=RuntimeError("boom"),
        ):
            bilan = envoyer_rappels()
        assert bilan["en_attente"] == 0  # erreur isolée → 0
