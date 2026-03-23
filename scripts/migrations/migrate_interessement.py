"""Migration: create interessement tables (interessement_periodes + interessement_regles)."""

import os
import sys
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "gestion_conges.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"[SKIP] Base introuvable : {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interessement_periodes'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE interessement_periodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                libelle VARCHAR(120) NOT NULL,
                date_debut DATE NOT NULL,
                date_fin DATE NOT NULL,
                base_points INTEGER NOT NULL DEFAULT 100,
                plancher_points INTEGER NOT NULL DEFAULT 0,
                actif BOOLEAN NOT NULL DEFAULT 0,
                cree_le DATETIME,
                modifie_le DATETIME
            )
        """)
        print("[OK] Table interessement_periodes créée.")
    else:
        print("[SKIP] Table interessement_periodes existe déjà.")

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interessement_regles'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE interessement_regles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periode_id INTEGER NOT NULL REFERENCES interessement_periodes(id),
                type_absence VARCHAR(50) NOT NULL,
                points_par_jour REAL NOT NULL DEFAULT 0.0,
                cree_le DATETIME,
                modifie_le DATETIME,
                UNIQUE(periode_id, type_absence)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_interessement_regles_periode ON interessement_regles(periode_id)")
        print("[OK] Table interessement_regles créée.")
    else:
        print("[SKIP] Table interessement_regles existe déjà.")

    conn.commit()
    conn.close()
    print("[DONE] Migration intéressement terminée.")


if __name__ == "__main__":
    migrate()
