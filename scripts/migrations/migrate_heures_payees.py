"""
Lot 4 - Migration : table heures_payees (saisie manuelle des heures).
- Crée la table heures_payees si absente.

S'exécute automatiquement au démarrage de l'app (via app.py) ou manuellement :

    python scripts/migrations/migrate_heures_payees.py
"""

import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "gestion_conges.db")


def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type=\"table\" AND name=?", (table,))
    return cursor.fetchone() is not None


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not table_exists(cursor, "heures_payees"):
        cursor.execute(
            "CREATE TABLE heures_payees ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL, "
            "annee INTEGER NOT NULL, "
            "mois INTEGER NOT NULL, "
            "heures_payees INTEGER NOT NULL DEFAULT 0, "
            "heures_trajet INTEGER NOT NULL DEFAULT 0, "
            "heures_travaillees INTEGER NOT NULL DEFAULT 0, "
            "source TEXT NOT NULL DEFAULT 'manuel', "
            "saisi_par_id INTEGER, "
            "saisi_le DATETIME NOT NULL DEFAULT (datetime('now')), "
            "CONSTRAINT uq_heures_user_annee_mois UNIQUE (user_id, annee, mois)"
            ")"
        )
        cursor.execute("CREATE INDEX idx_heures_payees_user ON heures_payees(user_id)")
        cursor.execute("CREATE INDEX idx_heures_payees_annee_mois ON heures_payees(annee, mois)")
        print("Table heures_payees créée.")
    else:
        print("Table heures_payees existe déjà.")

    conn.commit()
    conn.close()
    print("Migration heures_payees terminée.")


if __name__ == "__main__":
    migrate()
