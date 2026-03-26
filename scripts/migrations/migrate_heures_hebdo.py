"""Migration: create weekly manual entry tables for RH hours."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "gestion_conges.db")


def table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"[SKIP] Base introuvable : {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if not table_exists(cur, "heures_hebdo_saisies"):
        cur.execute(
            """
            CREATE TABLE heures_hebdo_saisies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                annee_iso INTEGER NOT NULL,
                semaine_iso INTEGER NOT NULL,
                heures_prevues REAL NOT NULL DEFAULT 35.0,
                heures_travaillees REAL NOT NULL DEFAULT 0.0,
                heures_sup REAL NOT NULL DEFAULT 0.0,
                heures_trajet REAL NOT NULL DEFAULT 0.0,
                heures_absence REAL NOT NULL DEFAULT 0.0,
                statut TEXT NOT NULL DEFAULT 'brouillon',
                saisi_par_id INTEGER,
                saisi_le DATETIME NOT NULL DEFAULT (datetime('now')),
                valide_par_id INTEGER,
                valide_le DATETIME,
                CONSTRAINT uq_heures_hebdo_user_annee_semaine UNIQUE (user_id, annee_iso, semaine_iso)
            )
            """
        )
        cur.execute("CREATE INDEX idx_heures_hebdo_user ON heures_hebdo_saisies(user_id)")
        cur.execute("CREATE INDEX idx_heures_hebdo_semaine ON heures_hebdo_saisies(annee_iso, semaine_iso)")
        print("[OK] Table heures_hebdo_saisies créée.")
    else:
        print("[SKIP] Table heures_hebdo_saisies existe déjà.")

    if not table_exists(cur, "heures_hebdo_verrous"):
        cur.execute(
            """
            CREATE TABLE heures_hebdo_verrous (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                annee_iso INTEGER NOT NULL,
                semaine_iso INTEGER NOT NULL,
                verrouille BOOLEAN NOT NULL DEFAULT 0,
                valide_par_id INTEGER,
                valide_le DATETIME,
                CONSTRAINT uq_heures_hebdo_verrou_annee_semaine UNIQUE (annee_iso, semaine_iso)
            )
            """
        )
        cur.execute("CREATE INDEX idx_heures_verrous_semaine ON heures_hebdo_verrous(annee_iso, semaine_iso)")
        print("[OK] Table heures_hebdo_verrous créée.")
    else:
        print("[SKIP] Table heures_hebdo_verrous existe déjà.")

    conn.commit()
    conn.close()
    print("[DONE] Migration heures hebdo terminée.")


if __name__ == "__main__":
    migrate()
