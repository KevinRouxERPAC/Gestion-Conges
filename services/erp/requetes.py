"""Requêtes SQL READ-ONLY sur l'ERP SILOG/Cegid PMI (base PMI, SQL Server).

Toutes les fonctions reçoivent une connexion pyodbc déjà ouverte et retournent
des listes de namedtuples. Aucune écriture vers l'ERP.

Schéma pertinent (découvert par introspection 2026-06-29) :
  dbo.TEMPAS   : temps déclarés sur OF par salarié/semaine.
    BECTMATRI1  nchar(12) — matricule (= SALARIES.MAKTCODE, ex. '000011')
    BECSSAREAL  nchar(12) — semaine réelle au format AAAASS (ex. '202624')
    BECNREALIS  decimal   — heures réalisées (quand BECTUNCONS='H')
    BEKTSOC     nchar(6)  — société (= '100' chez ERPAC)

  dbo.SALARIES : fiches salariés.
    MAKTCODE    nchar(12) — matricule
    MACTNOM     nchar(80) — nom complet (ex. 'GAUTHE Sébastien')
    MAKTSOC     nchar(6)  — société
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class HeuresSemaine:
    matricule: str       # '000011'
    semaine_erp: str     # '202624'
    heures: float        # somme des heures déclarées (BECTUNCONS='H')
    date_lundi: date     # calculé par le service appelant


@dataclass
class SalarieErp:
    matricule: str
    nom_complet: str


# Code société ERPAC dans SILOG.
SOC = "100"


def heures_semaine(conn, semaine_erp: str) -> list[HeuresSemaine]:
    """Somme des heures déclarées par salarié pour une semaine ISO (format AAAASS).

    Filtre : unité d'œuvre = 'H' (heures), société = '100', semaine = semaine_erp.
    """
    sql = """
        SELECT RTRIM(BECTMATRI1) AS matricule,
               RTRIM(BECSSAREAL) AS semaine,
               SUM(CAST(BECNREALIS AS float)) AS heures
        FROM dbo.TEMPAS
        WHERE BEKTSOC     = ?
          AND BECTUNCONS  = 'H'
          AND BECTMATRI1  <> ''
          AND BECSSAREAL  = ?
        GROUP BY BECTMATRI1, BECSSAREAL
        HAVING SUM(CAST(BECNREALIS AS float)) > 0
    """
    rows = conn.execute(sql, (SOC, semaine_erp)).fetchall()
    return [
        HeuresSemaine(
            matricule=r[0].strip(),
            semaine_erp=r[1].strip(),
            heures=float(r[2]),
            date_lundi=date.min,  # complété par sync_heures
        )
        for r in rows
    ]


def salaries_erp(conn) -> list[SalarieErp]:
    """Liste de tous les salariés de la société."""
    sql = """
        SELECT RTRIM(MAKTCODE), RTRIM(MACTNOM)
        FROM dbo.SALARIES
        WHERE MAKTSOC = ?
        ORDER BY MACTNOM
    """
    rows = conn.execute(sql, (SOC,)).fetchall()
    return [SalarieErp(matricule=r[0].strip(), nom_complet=r[1].strip()) for r in rows]
