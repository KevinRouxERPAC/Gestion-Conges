"""Tests du service de reporting d'absentéisme (Phase 3a)."""
from datetime import date

from models import db
from models.conge import Conge
from services.reporting import generer_rapport


class TestRapportVide:
    def test_periode_sans_conges(self, db_session, users, parametrage):
        r = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert r.nb_salaries_actifs >= 2
        assert r.par_type == []
        assert r.par_service == []
        assert r.taux_absenteisme_global == 0.0


class TestRapportAvecConges:
    def test_un_conge_cp_compte(self, db_session, users, parametrage):
        # CP du 2 au 5 juin 2026 (mardi → vendredi) = 4 jours ouvrables.
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 5),
            nb_jours_ouvrables=4, type_conge="CP", statut="valide",
        ))
        db.session.commit()

        r = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert len(r.par_type) == 1
        assert r.par_type[0].cle == "CP"
        assert r.par_type[0].nb_conges == 1
        assert r.par_type[0].nb_jours == 4.0

    def test_conge_a_cheval_reparti(self, db_session, users, parametrage):
        # Congé du 28 mai au 3 juin 2026 (jeu → mer).
        # Sur juin : 1er au 3 = lun, mar, mer = 3 jours ouvrables.
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 5, 28), date_fin=date(2026, 6, 3),
            nb_jours_ouvrables=5, type_conge="CP", statut="valide",
        ))
        db.session.commit()

        r_juin = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert r_juin.par_type[0].nb_jours == 3.0

        r_mai = generer_rapport(date(2026, 5, 1), date(2026, 5, 31))
        assert r_mai.par_type[0].nb_jours == 2.0  # 28 (jeu) + 29 (ven)

    def test_par_service_groupe_par_responsable(self, db_session, users, parametrage):
        # users["salarie"] a responsable_id = users["responsable"].id.
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=1, type_conge="RTT", nb_heures_rtt=7, statut="valide",
        ))
        db.session.commit()

        r = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert len(r.par_service) == 1
        assert "Resp" in r.par_service[0].cle  # nom du responsable

    def test_par_mois_agrege(self, db_session, users, parametrage):
        # Deux congés en juin.
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=1, type_conge="CP", statut="valide",
        ))
        db.session.add(Conge(
            user_id=users["salarie_sans_resp"].id,
            date_debut=date(2026, 6, 10), date_fin=date(2026, 6, 10),
            nb_jours_ouvrables=1, type_conge="CP", statut="valide",
        ))
        db.session.commit()

        r = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert len(r.par_mois) == 1
        assert r.par_mois[0]["mois"] == "2026-06"
        assert r.par_mois[0]["nb_conges"] == 2

    def test_taux_absenteisme_superieur_a_zero(self, db_session, users, parametrage):
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 5),
            nb_jours_ouvrables=4, type_conge="CP", statut="valide",
        ))
        db.session.commit()

        r = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert r.taux_absenteisme_global > 0.0

    def test_top_consommateurs_cp(self, db_session, users, parametrage):
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 5),
            nb_jours_ouvrables=4, type_conge="CP", statut="valide",
        ))
        db.session.add(Conge(
            user_id=users["salarie_sans_resp"].id,
            date_debut=date(2026, 6, 10), date_fin=date(2026, 6, 12),
            nb_jours_ouvrables=3, type_conge="CP", statut="valide",
        ))
        db.session.commit()

        r = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert len(r.top_consommateurs_cp) == 2
        # Le top est trié par nb_jours décroissant.
        assert r.top_consommateurs_cp[0]["nb_jours"] == 4.0
        assert r.top_consommateurs_cp[1]["nb_jours"] == 3.0

    def test_conges_non_valides_exclus(self, db_session, users, parametrage):
        # Congé en attente : ne compte pas dans le rapport d'absentéisme.
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=1, type_conge="CP", statut="en_attente_rh",
        ))
        db.session.commit()

        r = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert r.par_type == []

    def test_include_inactifs(self, db_session, users, parametrage):
        # Désactive un salarié qui a un congé.
        users["salarie"].actif = False
        db.session.add(Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 2),
            nb_jours_ouvrables=1, type_conge="CP", statut="valide",
        ))
        db.session.commit()

        # Par défaut (actifs only) : vide.
        r_actifs = generer_rapport(date(2026, 6, 1), date(2026, 6, 30))
        assert r_actifs.par_type == []

        # Avec inactifs : trouvé.
        r_tous = generer_rapport(
            date(2026, 6, 1), date(2026, 6, 30), include_inactifs=True
        )
        assert len(r_tous.par_type) == 1
