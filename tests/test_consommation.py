"""Tests de la source de vérité unique du calcul de consommation (NFR9).

Vérifie que la primitive `somme_consommation` se comporte correctement et que
les différents consommateurs (solde, export comptable, intéressement) produisent
des chiffres cohérents pour un même salarié/exercice.
"""
from datetime import date

import openpyxl

from models.conge import Conge
from services.consommation import (
    somme_consommation,
    STATUT_VALIDE,
    STATUTS_EN_ATTENTE,
    TYPES_CP,
    TYPE_RTT,
)
from services.solde import calculer_jours_cps_consommes, calculer_heures_rtt_consommes
from services.export_comptable import export_compta_cp_rtt_xlsx
from services.interessement import calculer_interessement


def _ajouter_conge(db_session, user_id, **kwargs):
    defaults = dict(
        date_debut=date(2026, 6, 1),
        date_fin=date(2026, 6, 5),
        nb_jours_ouvrables=5,
        type_conge="CP",
        statut="valide",
    )
    defaults.update(kwargs)
    c = Conge(user_id=user_id, **defaults)
    db_session.session.add(c)
    db_session.session.commit()
    return c


class TestPrimitive:
    def test_scalaire_valide(self, db_session, users, parametrage):
        _ajouter_conge(db_session, users["salarie"].id)
        total = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=parametrage.debut_exercice,
            date_fin_max=parametrage.fin_exercice,
            statuts=STATUT_VALIDE,
            types=TYPES_CP,
            user_id=users["salarie"].id,
        )
        assert total == 5

    def test_statut_filtre(self, db_session, users, parametrage):
        _ajouter_conge(db_session, users["salarie"].id, statut="en_attente_rh")
        valide = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=parametrage.debut_exercice,
            date_fin_max=parametrage.fin_exercice,
            statuts=STATUT_VALIDE,
            types=TYPES_CP,
            user_id=users["salarie"].id,
        )
        en_attente = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=parametrage.debut_exercice,
            date_fin_max=parametrage.fin_exercice,
            statuts=STATUTS_EN_ATTENTE,
            types=TYPES_CP,
            user_id=users["salarie"].id,
        )
        assert valide == 0
        assert en_attente == 5

    def test_conge_id_exclu(self, db_session, users, parametrage):
        c = _ajouter_conge(db_session, users["salarie"].id)
        total = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=parametrage.debut_exercice,
            date_fin_max=parametrage.fin_exercice,
            statuts=STATUT_VALIDE,
            types=TYPES_CP,
            user_id=users["salarie"].id,
            conge_id_exclu=c.id,
        )
        assert total == 0

    def test_group_by_user(self, db_session, users, parametrage):
        _ajouter_conge(db_session, users["salarie"].id)
        _ajouter_conge(db_session, users["salarie_sans_resp"].id, nb_jours_ouvrables=3)
        res = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=parametrage.debut_exercice,
            date_fin_max=parametrage.fin_exercice,
            statuts=STATUT_VALIDE,
            types=TYPES_CP,
            user_ids=[users["salarie"].id, users["salarie_sans_resp"].id],
            group_by="user",
        )
        assert res[users["salarie"].id] == 5
        assert res[users["salarie_sans_resp"].id] == 3

    def test_group_by_user_type(self, db_session, users, parametrage):
        _ajouter_conge(db_session, users["salarie"].id, type_conge="CP")
        _ajouter_conge(
            db_session, users["salarie"].id, type_conge="Maladie",
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 2), nb_jours_ouvrables=2,
        )
        res = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=parametrage.debut_exercice,
            date_fin_max=parametrage.fin_exercice,
            statuts=STATUT_VALIDE,
            user_ids=[users["salarie"].id],
            group_by="user_type",
        )
        assert res[(users["salarie"].id, "CP")] == 5
        assert res[(users["salarie"].id, "Maladie")] == 2

    def test_demi_journee_non_tronquee(self, db_session, users, parametrage):
        _ajouter_conge(
            db_session, users["salarie"].id, nb_jours_ouvrables=4.5,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
        )
        total = somme_consommation(
            colonne=Conge.nb_jours_ouvrables,
            date_debut_min=parametrage.debut_exercice,
            date_fin_max=parametrage.fin_exercice,
            statuts=STATUT_VALIDE,
            types=TYPES_CP,
            user_id=users["salarie"].id,
        )
        assert total == 4.5


class TestCoherenceInterEcrans:
    """0 écart entre l'écran salarié, l'export comptable et l'intéressement (NFR9)."""

    def _consomme_export_compta_cp(self, parametrage, user):
        buffer = export_compta_cp_rtt_xlsx(parametrage, parametrage.fin_exercice)
        wb = openpyxl.load_workbook(buffer)
        ws = wb["Synthèse CP"]
        nom_complet = f"{user.prenom} {user.nom}"
        for row in ws.iter_rows(values_only=True):
            if row and row[0] == nom_complet:
                return row[2]  # colonne "Consommé (jours)"
        return None

    def test_cp_coherent_solde_export_interessement(self, db_session, users, parametrage, allocations):
        user = users["salarie"]
        _ajouter_conge(db_session, user.id, nb_jours_ouvrables=5, type_conge="CP")
        _ajouter_conge(
            db_session, user.id, nb_jours_ouvrables=2, type_conge="Anciennete",
            date_debut=date(2026, 3, 2), date_fin=date(2026, 3, 3),
        )

        solde_consomme = calculer_jours_cps_consommes(user.id)
        export_consomme = self._consomme_export_compta_cp(parametrage, user)

        from models.interessement_periode import InteressementPeriode
        periode = InteressementPeriode(
            libelle="2026", date_debut=parametrage.debut_exercice,
            date_fin=parametrage.fin_exercice, base_points=100, plancher_points=0, actif=True,
        )
        db_session.session.add(periode)
        db_session.session.commit()
        res = [r for r in calculer_interessement(periode) if r.user_id == user.id][0]
        interessement_cp = sum(d.jours for d in res.details if d.type_absence in ("CP", "Anciennete"))

        assert solde_consomme == 7
        assert export_consomme == 7
        assert interessement_cp == 7

    def test_rtt_coherent_solde_export(self, db_session, users, parametrage, allocations):
        user = users["salarie"]
        _ajouter_conge(
            db_session, user.id, type_conge="RTT", nb_heures_rtt=7, nb_jours_ouvrables=0,
            date_debut=date(2026, 5, 4), date_fin=date(2026, 5, 4),
        )

        solde_rtt = calculer_heures_rtt_consommes(user.id)

        buffer = export_compta_cp_rtt_xlsx(parametrage, parametrage.fin_exercice)
        wb = openpyxl.load_workbook(buffer)
        ws = wb["Synthèse RTT"]
        nom_complet = f"{user.prenom} {user.nom}"
        export_rtt = None
        for row in ws.iter_rows(values_only=True):
            if row and row[0] == nom_complet:
                export_rtt = row[2]
                break

        assert solde_rtt == 7
        assert export_rtt == 7
