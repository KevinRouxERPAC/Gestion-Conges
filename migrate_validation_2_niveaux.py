"""
Migration : validation a 2 niveaux (responsable puis RH).
- users : ajout responsable_id si absent.
- conges : ajout valide_par_responsable_id, valide_par_responsable_le ; en_attente -> en_attente_rh.
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

    if not column_exists(cursor, "users", "responsable_id"):
        cursor.execute(
            "ALTER TABLE users ADD COLUMN responsable_id INTEGER REFERENCES users(id)"
        )
        print("Colonne 'responsable_id' ajoutée à users.")
    else:
        print("Colonne 'responsable_id' existe déjà dans users.")

    if not column_exists(cursor, "conges", "valide_par_responsable_id"):
        cursor.execute(
            "ALTER TABLE conges ADD COLUMN valide_par_responsable_id INTEGER REFERENCES users(id)"
        )
        print("Colonne 'valide_par_responsable_id' ajoutée à conges.")
    else:
        print("Colonne 'valide_par_responsable_id' existe déjà dans conges.")

    if not column_exists(cursor, "conges", "valide_par_responsable_le"):
        cursor.execute("ALTER TABLE conges ADD COLUMN valide_par_responsable_le DATETIME")
        print("Colonne 'valide_par_responsable_le' ajoutée à conges.")
    else:
        print("Colonne 'valide_par_responsable_le' existe déjà dans conges.")

    cursor.execute("UPDATE conges SET statut = 'en_attente_rh' WHERE statut = 'en_attente'")
    if cursor.rowcount:
        print(f"Statuts migrés : {cursor.rowcount} conge(s) 'en_attente' -> 'en_attente_rh'.")

    conn.commit()
    conn.close()
    print("Migration validation 2 niveaux terminée.")


if __name__ == "__main__":
    migrate()
