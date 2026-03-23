"""
Lot 2 - Migration : congés exceptionnels paramétrables.
- Crée la table conges_exceptionnels_types si absente.
- Ajoute conges.nb_heures_exceptionnelles pour les types en heures.

S'exécute automatiquement au démarrage de l'app (via app.py) ou manuellement :

    python scripts/migrations/migrate_conges_exceptionnels.py
"""

import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "gestion_conges.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type=\"table\" AND name=?", (table,))
    return cursor.fetchone() is not None


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table des types exceptionnels
    if not table_exists(cursor, "conges_exceptionnels_types"):
        cursor.execute(
            "CREATE TABLE conges_exceptionnels_types ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "code TEXT NOT NULL UNIQUE, "
            "libelle TEXT NOT NULL, "
            "unite TEXT NOT NULL DEFAULT 'jours', "
            "plafond_annuel INTEGER, "
            "actif BOOLEAN NOT NULL DEFAULT 1"
            ")"
        )
        print("Table conges_exceptionnels_types créée.")
    else:
        print("Table conges_exceptionnels_types existe déjà.")

    # Colonne heures exceptionnelles sur conges
    if not column_exists(cursor, "conges", "nb_heures_exceptionnelles"):
        cursor.execute("ALTER TABLE conges ADD COLUMN nb_heures_exceptionnelles INTEGER")
        print("Colonne nb_heures_exceptionnelles ajoutée à conges.")
    else:
        print("Colonne nb_heures_exceptionnelles existe déjà dans conges.")

    conn.commit()
    conn.close()
    print("Migration congés exceptionnels terminée.")


if __name__ == "__main__":
    migrate()

