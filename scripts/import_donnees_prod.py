"""Importe les données de la base de production (ancien schéma) dans la base
applicative au schéma courant.

Contexte : la base téléchargée du site en production (`--source`) est à jour en
*données* mais en retard d'un cran sur le *schéma* (avant les migrations
demi-journées / archive / refonte RTT du paramétrage). Ce script recopie les
données table par table dans une base cible déjà migrée (schéma courant), en
comblant les colonnes ajoutées par des valeurs par défaut et en ignorant les
colonnes supprimées.

Usage :
    python scripts/import_donnees_prod.py --source <ancienne.db> --target <cible.db>

La cible doit déjà exister avec le schéma courant (alembic upgrade head). Le
script vide les tables concernées de la cible avant import (idempotent).
"""
import argparse
import sqlite3
import sys

# Ordre d'insertion : respecte les dépendances de clés étrangères.
# Les tables vides côté source ne sont pas listées (rien à importer).
TABLES_ORDONNEES = [
    "users",
    "parametrage_annuel",
    "allocations_conges",
    "conges",
    "jours_feries",
    "notifications",
]


def colonnes(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info('{table}')")]


def transforme_ligne(table, row, cols_cible):
    """Retourne un dict {colonne_cible: valeur} pour une ligne source.

    `row` est un sqlite3.Row (accès par nom). On part des colonnes communes,
    puis on applique les valeurs par défaut des colonnes ajoutées au schéma.
    """
    src = dict(row)
    out = {}

    if table == "parametrage_annuel":
        # Colonnes communes conservées telles quelles.
        for c in ("id", "debut_exercice", "fin_exercice", "jours_conges_defaut",
                  "rtt_coef_surplus", "actif"):
            out[c] = src.get(c)
        # Refonte RTT : nouvelles colonnes → valeurs par défaut du modèle.
        out["rtt_seuil_hebdo"] = 35
        out["rtt_heures_par_jour_absence"] = 7
        out["rtt_acquis_par_semaine"] = 0.0
        # Colonnes supprimées (rtt_heures_defaut, rtt_calc_mode,
        # rtt_heures_reference, debut/fin_periode_conges) : ignorées.
        return out

    # Cas général : on copie toutes les colonnes communes.
    for c in cols_cible:
        if c in src:
            out[c] = src[c]

    if table == "conges":
        # Colonnes ajoutées par les migrations demi-journées / archive.
        out["demi_journee_debut"] = None
        out["demi_journee_fin"] = None
        out["archive"] = 0

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Ancienne base (données prod)")
    ap.add_argument("--target", required=True, help="Base cible (schéma courant)")
    args = ap.parse_args()

    src = sqlite3.connect(args.source)
    src.row_factory = sqlite3.Row
    tgt = sqlite3.connect(args.target)

    tgt.execute("PRAGMA foreign_keys = OFF")  # ordre garanti, mais on relâche par sécurité

    total = {}
    try:
        # Purge des tables cibles concernées (ordre inverse des FK).
        for table in reversed(TABLES_ORDONNEES):
            tgt.execute(f"DELETE FROM {table}")

        for table in TABLES_ORDONNEES:
            cols_cible = colonnes(tgt, table)
            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            n = 0
            for row in rows:
                data = transforme_ligne(table, row, cols_cible)
                cols = [c for c in cols_cible if c in data]
                placeholders = ", ".join("?" for _ in cols)
                vals = [data[c] for c in cols]
                tgt.execute(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                    vals,
                )
                n += 1
            total[table] = n

        # Recale les compteurs AUTOINCREMENT sur le max(id) importé.
        seq_existe = tgt.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if seq_existe:
            for table in TABLES_ORDONNEES:
                mx = tgt.execute(f"SELECT MAX(id) FROM {table}").fetchone()[0]
                if mx is not None:
                    # sqlite_sequence n'a pas de contrainte UNIQUE : delete + insert.
                    tgt.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
                    tgt.execute(
                        "INSERT INTO sqlite_sequence(name, seq) VALUES(?, ?)",
                        (table, mx),
                    )

        # Contrôle d'intégrité référentielle avant commit.
        tgt.execute("PRAGMA foreign_keys = ON")
        violations = tgt.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            tgt.rollback()
            print("ERREUR : violations de clés étrangères, import annulé :", file=sys.stderr)
            for v in violations:
                print("  ", v, file=sys.stderr)
            sys.exit(1)

        tgt.commit()
    finally:
        src.close()
        tgt.close()

    print("Import terminé :")
    for table in TABLES_ORDONNEES:
        print(f"  {table}: {total.get(table, 0)} lignes")


if __name__ == "__main__":
    main()
