"""Smoke tests des exports Excel/PDF.

Valide que chaque générateur produit un fichier non vide et bien formé après la
factorisation des helpers openpyxl (services/export_utils.py). Un .xlsx est une
archive ZIP (signature ``PK``) ; un PDF commence par ``%PDF``.
"""
from datetime import date

from models import db
from models.conge import Conge
from models.interessement_periode import InteressementPeriode
from services.export import (
    export_conges_equipe_excel,
    export_conges_excel,
    export_conges_pdf,
)
from services.export_comptable import export_compta_cp_rtt_xlsx
from services.export_interessement import export_interessement_xlsx


def _conge(user):
    return Conge(
        user_id=user.id,
        date_debut=date(2026, 6, 1),
        date_fin=date(2026, 6, 3),
        nb_jours_ouvrables=3,
        type_conge="CP",
        statut="valide",
    )


class TestExportsExcelPdf:
    def test_export_conges_excel(self, db_session, users):
        buf = export_conges_excel([_conge(users["salarie"])], "Dupont", "Jean")
        assert buf.getvalue()[:2] == b"PK"

    def test_export_conges_equipe_excel(self, db_session, users):
        data = [{"user": users["salarie"], "conges": [_conge(users["salarie"])]}]
        buf = export_conges_equipe_excel(data)
        assert buf.getvalue()[:2] == b"PK"

    def test_export_conges_pdf(self, db_session, users):
        buf = export_conges_pdf([_conge(users["salarie"])], {}, "Dupont", "Jean")
        assert buf.getvalue()[:4] == b"%PDF"

    def test_export_compta_xlsx(self, db_session, users, parametrage, allocations):
        buf = export_compta_cp_rtt_xlsx(parametrage, parametrage.fin_exercice)
        assert buf.getvalue()[:2] == b"PK"

    def test_export_interessement_xlsx(self, db_session, users):
        p = InteressementPeriode(
            libelle="2026",
            date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31),
            base_points=100,
            plancher_points=0,
            actif=True,
        )
        db.session.add(p)
        db.session.commit()
        buf = export_interessement_xlsx(p)
        assert buf.getvalue()[:2] == b"PK"
