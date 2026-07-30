"""Requêtes SQL READ-ONLY sur l'ERP SILOG/Cegid PMI (base PMI, SQL Server).

Toutes les fonctions reçoivent une connexion pyodbc déjà ouverte et retournent
des listes de namedtuples. Aucune écriture vers l'ERP.

Schéma pertinent (découvert par introspection 2026-06-29, confirmé 2026-07-09) :
  dbo.TEMPAS   : temps déclarés sur OF par salarié/semaine.
    BECTMATRI1  nchar(12) — matricule (= SALARIES.MAKTCODE, ex. '000011')
    BECSSAREAL  nchar(12) — semaine réelle au format AAAASS (ex. '202624')
    BECNREALIS  decimal   — temps réel déclaré (≠ BECNPREVU = temps prévu)
    BECTUNCONS  nchar     — unité heures pour saisie différée ('H')
    BECTUNSTK   nchar     — unité heures pour saisie temps réel / pointeuse ('H')
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
    heures: float        # somme des heures déclarées (unité 'H' en consommé ou stock)
    date_lundi: date     # calculé par le service appelant


@dataclass
class SalarieErp:
    matricule: str
    nom_complet: str


# Code société ERPAC dans SILOG.
SOC = "100"

# Longueur canonique des MAKTCODE numériques (ex. '000011', '000024').
MATRICULE_LONGUEUR = 6


def normaliser_matricule_erp(matricule: str | None) -> str:
    """Canonise un matricule ERP (MAKTCODE).

    Les matricules numériques sont complétés à 6 chiffres (24 → 000024) pour
    aligner TEMPAS, SALARIES et la saisie RH.
    """
    mat = (matricule or "").strip()
    if not mat:
        return ""
    if mat.isdigit():
        return mat.zfill(MATRICULE_LONGUEUR)
    return mat


def _sql_heures_agregees(where_semaine_sql: str) -> str:
    """SQL commun d'agrégation des heures TEMPAS (filtre semaine injecté)."""
    return f"""
        SELECT CASE
                 WHEN LTRIM(RTRIM(BECTMATRI1)) NOT LIKE '%[^0-9]%'
                      AND LTRIM(RTRIM(BECTMATRI1)) <> ''
                 THEN RIGHT(REPLICATE('0', 6) + LTRIM(RTRIM(BECTMATRI1)), 6)
                 ELSE LTRIM(RTRIM(BECTMATRI1))
               END AS matricule,
               RTRIM(BECSSAREAL) AS semaine,
               SUM(CAST(BECNREALIS AS float)) AS heures
        FROM dbo.TEMPAS
        WHERE BEKTSOC     = ?
          AND (BECTUNCONS = 'H' OR BECTUNSTK = 'H')
          AND LTRIM(RTRIM(BECTMATRI1)) <> ''
          AND {where_semaine_sql}
        GROUP BY CASE
                   WHEN LTRIM(RTRIM(BECTMATRI1)) NOT LIKE '%[^0-9]%'
                        AND LTRIM(RTRIM(BECTMATRI1)) <> ''
                   THEN RIGHT(REPLICATE('0', 6) + LTRIM(RTRIM(BECTMATRI1)), 6)
                   ELSE LTRIM(RTRIM(BECTMATRI1))
                 END,
                 RTRIM(BECSSAREAL)
        HAVING SUM(CAST(BECNREALIS AS float)) > 0
    """


def _lignes_depuis_rows(rows) -> list[HeuresSemaine]:
    return [
        HeuresSemaine(
            matricule=normaliser_matricule_erp(r[0]),
            semaine_erp=r[1].strip(),
            heures=float(r[2]),
            date_lundi=date.min,
        )
        for r in rows
    ]


def heures_semaine(conn, semaine_erp: str) -> list[HeuresSemaine]:
    """Somme des heures déclarées par salarié pour une semaine ISO (format AAAASS).

    Filtre : heures (BECTUNCONS='H' ou BECTUNSTK='H' — pointeuse temps réel),
    société = '100', semaine réelle = semaine_erp, quantité = BECNREALIS (temps réel).
    """
    sql = _sql_heures_agregees("RTRIM(BECSSAREAL) = ?")
    rows = conn.execute(sql, (SOC, semaine_erp)).fetchall()
    return _lignes_depuis_rows(rows)


def heures_periode(conn, semaines_erp: list[str]) -> list[HeuresSemaine]:
    """Somme des heures déclarées par salarié/semaine sur plusieurs semaines ISO (AAAASS).

    Une seule requête ERP pour couvrir toute la période (ex. depuis le début de l'exercice).
    """
    semaines = [s.strip() for s in semaines_erp if s and s.strip()]
    if not semaines:
        return []
    placeholders = ",".join("?" * len(semaines))
    sql = _sql_heures_agregees(f"RTRIM(BECSSAREAL) IN ({placeholders})")
    rows = conn.execute(sql, (SOC, *semaines)).fetchall()
    return _lignes_depuis_rows(rows)


def salaries_erp(conn) -> list[SalarieErp]:
    """Liste de tous les salariés de la société."""
    sql = """
        SELECT RTRIM(MAKTCODE), RTRIM(MACTNOM)
        FROM dbo.SALARIES
        WHERE MAKTSOC = ?
        ORDER BY MACTNOM
    """
    rows = conn.execute(sql, (SOC,)).fetchall()
    return [
        SalarieErp(
            matricule=normaliser_matricule_erp(r[0]),
            nom_complet=r[1].strip(),
        )
        for r in rows
    ]
