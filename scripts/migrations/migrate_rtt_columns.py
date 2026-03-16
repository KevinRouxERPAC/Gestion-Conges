"""
Migration : ajout des colonnes liées aux RTT (heures) dans ParametrageAnnuel,
AllocationConge et Conge.

S'exécute automatiquement au démarrage de l'app (via app.py) ou manuellement :

    python scripts/migrations/migrate_rtt_columns.py
"""

import os
import sqlite3

# Racine du projet (parent de scripts/migrations)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "gestion_conges.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ParametrageAnnuel.rtt_heures_defaut
    if not column_exists(cursor, "parametrage_annuel", "rtt_heures_defaut"):
        cursor.execute(
            "ALTER TABLE parametrage_annuel "
            "ADD COLUMN rtt_heures_defaut INTEGER NOT NULL DEFAULT 0"
        )
        print("Colonne 'rtt_heures_defaut' ajoutée à parametrage_annuel.")
    else:
        print("Colonne 'rtt_heures_defaut' existe déjà dans parametrage_annuel.")

    # AllocationConge.rtt_heures_allouees / rtt_heures_reportees
    if not column_exists(cursor, "allocations_conges", "rtt_heures_allouees"):
        cursor.execute(
            "ALTER TABLE allocations_conges "
            "ADD COLUMN rtt_heures_allouees INTEGER NOT NULL DEFAULT 0"
        )
        print("Colonne 'rtt_heures_allouees' ajoutée à allocations_conges.")
    else:
        print("Colonne 'rtt_heures_allouees' existe déjà dans allocations_conges.")

    if not column_exists(cursor, "allocations_conges", "rtt_heures_reportees"):
        cursor.execute(
            "ALTER TABLE allocations_conges "
            "ADD COLUMN rtt_heures_reportees INTEGER NOT NULL DEFAULT 0"
        )
        print("Colonne 'rtt_heures_reportees' ajoutée à allocations_conges.")
    else:
        print("Colonne 'rtt_heures_reportees' existe déjà dans allocations_conges.")

    # Conge.nb_heures_rtt
    if not column_exists(cursor, "conges", "nb_heures_rtt"):
        cursor.execute(
            "ALTER TABLE conges "
            "ADD COLUMN nb_heures_rtt INTEGER"
        )
        print("Colonne 'nb_heures_rtt' ajoutée à conges.")
    else:
        print("Colonne 'nb_heures_rtt' existe déjà dans conges.")

    conn.commit()
    conn.close()
    print("Migration RTT terminée.")


if __name__ == "__main__":
    migrate()

