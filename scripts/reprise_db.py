"""Reprise d'une base existante : aligne le schéma SQLite sur le code actuel.

À lancer SUR LA COPIE de travail (gestion_conges.db à la racine du projet),
jamais sur l'original. Idempotent et transactionnel : relançable sans risque,
et tout est annulé (rollback) en cas d'erreur.

Actions :
  1. Ajoute les colonnes manquantes (avec les défauts du modèle).
  2. Supprime des colonnes héritées OBSOLÈTES, NOT NULL sans défaut, qui
     empêcheraient toute nouvelle insertion (ex. clôture d'exercice) car le code
     actuel ne les renseigne plus.

Les 4 tables récentes manquantes (audit_logs, delegations, heures_hebdo,
justificatifs) ne sont PAS gérées ici : elles sont créées automatiquement et à
vide au démarrage de l'application (db.create_all).

Usage :
    python scripts/reprise_db.py                 # gestion_conges.db à la racine
    python scripts/reprise_db.py chemin\\base.db
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Colonnes à AJOUTER si absentes (DDL avec défaut = valeur du modèle).
ADD_COLUMNS = [
    ("conges", "demi_journee_debut",
     "ALTER TABLE conges ADD COLUMN demi_journee_debut VARCHAR(15)"),
    ("conges", "demi_journee_fin",
     "ALTER TABLE conges ADD COLUMN demi_journee_fin VARCHAR(15)"),
    ("conges", "archive",
     "ALTER TABLE conges ADD COLUMN archive BOOLEAN NOT NULL DEFAULT 0"),
    ("conges_exceptionnels_types", "justificatif_requis",
     "ALTER TABLE conges_exceptionnels_types ADD COLUMN justificatif_requis BOOLEAN NOT NULL DEFAULT 0"),
    ("parametrage_annuel", "rtt_seuil_hebdo",
     "ALTER TABLE parametrage_annuel ADD COLUMN rtt_seuil_hebdo INTEGER NOT NULL DEFAULT 35"),
    ("parametrage_annuel", "rtt_heures_par_jour_absence",
     "ALTER TABLE parametrage_annuel ADD COLUMN rtt_heures_par_jour_absence INTEGER NOT NULL DEFAULT 7"),
    ("parametrage_annuel", "rtt_acquis_par_semaine",
     "ALTER TABLE parametrage_annuel ADD COLUMN rtt_acquis_par_semaine FLOAT NOT NULL DEFAULT 0"),
]

# Colonnes héritées obsolètes à SUPPRIMER (NOT NULL sans défaut, hors modèle).
DROP_COLUMNS = [
    ("parametrage_annuel", "rtt_calc_mode"),
    ("parametrage_annuel", "rtt_heures_defaut"),
    ("parametrage_annuel", "rtt_heures_reference"),
]


def columns_of(cur, table):
    cur.execute(f"PRAGMA table_info('{table}')")
    return {row[1] for row in cur.fetchall()}


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "gestion_conges.db")
    if not os.path.isfile(db_path):
        print(f"Base introuvable : {db_path}")
        print("Copiez d'abord votre base dans le projet, par exemple :")
        print('  Copy-Item "C:\\Users\\kevin\\Downloads\\gestion_conges.db" ".\\gestion_conges.db"')
        sys.exit(1)

    print(f"Reprise de schéma sur : {db_path}")
    print(f"SQLite version : {sqlite3.sqlite_version}\n")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")

        for table, col, ddl in ADD_COLUMNS:
            if col in columns_of(cur, table):
                print(f"  = {table}.{col} déjà présent")
                continue
            cur.execute(ddl)
            print(f"  + {table}.{col} ajouté")

        for table, col in DROP_COLUMNS:
            if col not in columns_of(cur, table):
                print(f"  = {table}.{col} déjà absent")
                continue
            cur.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
            print(f"  - {table}.{col} supprimé (obsolète)")

        conn.commit()
        print("\nMigration appliquée avec succès.")
    except Exception as e:
        conn.rollback()
        print(f"\nERREUR : {e}")
        print("Aucune modification appliquée (rollback). La base est intacte.")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
