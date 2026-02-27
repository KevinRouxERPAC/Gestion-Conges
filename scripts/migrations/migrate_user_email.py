"""
Migration : ajout du champ email à la table users pour les notifications.
S'exécute automatiquement au démarrage de l'app.
"""
import sqlite3
import os

# Racine du projet (parent de scripts/migrations)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "gestion_conges.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not column_exists(cursor, "users", "email"):
        cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(120)")
        print("Colonne 'email' ajoutée à users.")
    else:
        print("Colonne 'email' existe déjà.")

    conn.commit()
    conn.close()
    print("Migration email terminée.")


if __name__ == "__main__":
    migrate()
