"""
Lot 4 - Migration : paramètres de calcul RTT depuis heures dans parametrage_annuel.
- Ajoute parametrage_annuel.rtt_calc_mode, rtt_heures_reference, rtt_coef_surplus si absents.

S'exécute automatiquement au démarrage de l'app (via app.py) ou manuellement :

    python scripts/migrations/migrate_rtt_calc_heures.py
"""

import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "gestion_conges.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not column_exists(cursor, "parametrage_annuel", "rtt_calc_mode"):
        cursor.execute("ALTER TABLE parametrage_annuel ADD COLUMN rtt_calc_mode TEXT NOT NULL DEFAULT 'fixe'")
        print("Colonne rtt_calc_mode ajoutée à parametrage_annuel.")
    else:
        print("Colonne rtt_calc_mode existe déjà dans parametrage_annuel.")

    if not column_exists(cursor, "parametrage_annuel", "rtt_heures_reference"):
        cursor.execute("ALTER TABLE parametrage_annuel ADD COLUMN rtt_heures_reference INTEGER NOT NULL DEFAULT 0")
        print("Colonne rtt_heures_reference ajoutée à parametrage_annuel.")
    else:
        print("Colonne rtt_heures_reference existe déjà dans parametrage_annuel.")

    if not column_exists(cursor, "parametrage_annuel", "rtt_coef_surplus"):
        cursor.execute("ALTER TABLE parametrage_annuel ADD COLUMN rtt_coef_surplus REAL NOT NULL DEFAULT 0.0")
        print("Colonne rtt_coef_surplus ajoutée à parametrage_annuel.")
    else:
        print("Colonne rtt_coef_surplus existe déjà dans parametrage_annuel.")

    conn.commit()
    conn.close()
    print("Migration paramètres RTT (heures) terminée.")


if __name__ == "__main__":
    migrate()
