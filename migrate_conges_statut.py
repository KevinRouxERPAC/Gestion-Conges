"""
Migration : ajout du workflow de validation aux congés (statut, valide_par_id, valide_le, motif_refus).
S'exécute automatiquement au démarrage de l'app, ou manuellement : python migrate_conges_statut.py
"""
import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "gestion_conges.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not column_exists(cursor, "conges", "statut"):
        cursor.execute(
            "ALTER TABLE conges ADD COLUMN statut VARCHAR(20) NOT NULL DEFAULT 'valide'"
        )
        print("Colonne 'statut' ajoutée.")
    else:
        print("Colonne 'statut' existe déjà.")

    if not column_exists(cursor, "conges", "valide_par_id"):
        cursor.execute(
            "ALTER TABLE conges ADD COLUMN valide_par_id INTEGER REFERENCES users(id)"
        )
        print("Colonne 'valide_par_id' ajoutée.")
    else:
        print("Colonne 'valide_par_id' existe déjà.")

    if not column_exists(cursor, "conges", "valide_le"):
        cursor.execute("ALTER TABLE conges ADD COLUMN valide_le DATETIME")
        print("Colonne 'valide_le' ajoutée.")
    else:
        print("Colonne 'valide_le' existe déjà.")

    if not column_exists(cursor, "conges", "motif_refus"):
        cursor.execute("ALTER TABLE conges ADD COLUMN motif_refus TEXT")
        print("Colonne 'motif_refus' ajoutée.")
    else:
        print("Colonne 'motif_refus' existe déjà.")

    conn.commit()
    conn.close()
    print("Migration terminée.")


if __name__ == "__main__":
    migrate()
