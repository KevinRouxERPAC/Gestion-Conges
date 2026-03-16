"""Tests du service de calcul de jours ouvrables et détection de chevauchement."""
from datetime import date
from models.conge import Conge
from models.jour_ferie import JourFerie
from services.calcul_jours import compter_jours_ouvrables, detecter_chevauchement


class TestCompterJoursOuvrables:
    def test_semaine_complete(self, db_session):
        """Lundi → vendredi = 5 jours ouvrables."""
        assert compter_jours_ouvrables(date(2026, 3, 16), date(2026, 3, 20)) == 5

    def test_inclut_weekend(self, db_session):
        """Lundi → lundi suivant (8 jours calendaires, samedi+dimanche exclus) = 6 jours."""
        assert compter_jours_ouvrables(date(2026, 3, 16), date(2026, 3, 23)) == 6

    def test_un_seul_jour_ouvre(self, db_session):
        """Un seul jour ouvré."""
        assert compter_jours_ouvrables(date(2026, 3, 16), date(2026, 3, 16)) == 1

    def test_un_jour_weekend(self, db_session):
        """Un samedi seul = 0 jour ouvrable."""
        assert compter_jours_ouvrables(date(2026, 3, 21), date(2026, 3, 21)) == 0

    def test_date_fin_avant_debut(self, db_session):
        """Fin < début = 0."""
        assert compter_jours_ouvrables(date(2026, 3, 20), date(2026, 3, 16)) == 0

    def test_jour_ferie_exclu(self, db_session):
        """Un jour férié au milieu de la semaine réduit le compte."""
        jf = JourFerie(date_ferie=date(2026, 3, 18), libelle="Test férié", annee=2026, auto_genere=False)
        db_session.session.add(jf)
        db_session.session.commit()
        assert compter_jours_ouvrables(date(2026, 3, 16), date(2026, 3, 20)) == 4


class TestDetecterChevauchement:
    def test_pas_de_chevauchement(self, db_session, users, parametrage, allocations):
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

        result = detecter_chevauchement(users["salarie"].id, date(2026, 7, 1), date(2026, 7, 5))
        assert result is None

    def test_chevauchement_detecte(self, db_session, users, parametrage, allocations):
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 10),
            nb_jours_ouvrables=8,
            type_conge="CP",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        result = detecter_chevauchement(users["salarie"].id, date(2026, 6, 5), date(2026, 6, 15))
        assert result is not None
        assert result.id == conge.id

    def test_chevauchement_exclusion_conge(self, db_session, users, parametrage, allocations):
        """En modification : le congé exclu ne doit pas être détecté."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 10),
            nb_jours_ouvrables=8,
            type_conge="CP",
            statut="valide",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        result = detecter_chevauchement(users["salarie"].id, date(2026, 6, 1), date(2026, 6, 10), conge_id_exclu=conge.id)
        assert result is None

    def test_conge_refuse_pas_chevauche(self, db_session, users, parametrage, allocations):
        """Un congé refusé ne doit pas causer de chevauchement."""
        conge = Conge(
            user_id=users["salarie"].id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 10),
            nb_jours_ouvrables=8,
            type_conge="CP",
            statut="refuse",
        )
        db_session.session.add(conge)
        db_session.session.commit()

        result = detecter_chevauchement(users["salarie"].id, date(2026, 6, 5), date(2026, 6, 15))
        assert result is None
