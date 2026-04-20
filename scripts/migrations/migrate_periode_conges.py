"""
Migration : ajout des colonnes debut_periode_conges / fin_periode_conges
dans la table parametrage_annuel.

Permet de dissocier la période des congés payés (1er juin → 31 mai)
de l'exercice comptable de l'entreprise (1er avril → 31 mars).

S'exécute automatiquement au démarrage de l'app (via app.py) ou manuellement :

    python scripts/migrations/migrate_periode_conges.py
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

    if not column_exists(cursor, "parametrage_annuel", "debut_periode_conges"):
        cursor.execute("ALTER TABLE parametrage_annuel ADD COLUMN debut_periode_conges DATE")
        print("Colonne debut_periode_conges ajoutée à parametrage_annuel.")
    else:
        print("Colonne debut_periode_conges existe déjà dans parametrage_annuel.")

    if not column_exists(cursor, "parametrage_annuel", "fin_periode_conges"):
        cursor.execute("ALTER TABLE parametrage_annuel ADD COLUMN fin_periode_conges DATE")
        print("Colonne fin_periode_conges ajoutée à parametrage_annuel.")
    else:
        print("Colonne fin_periode_conges existe déjà dans parametrage_annuel.")

    conn.commit()
    conn.close()
    print("Migration période congés terminée.")


if __name__ == "__main__":
    migrate()
