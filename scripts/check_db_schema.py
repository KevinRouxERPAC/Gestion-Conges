"""Diagnostic READ-ONLY : compare le schéma d'une base SQLite aux modèles du code.

N'écrit jamais dans la base (ouverture en mode lecture seule). Sert à savoir, avant
de brancher une base existante, s'il manque des tables ou des colonnes par rapport
à la version actuelle du code.

Usage (depuis la racine du projet) :
    python scripts/check_db_schema.py "C:\\Users\\kevin\\Downloads\\gestion_conges.db"

Sans argument : vérifie gestion_conges.db à la racine du projet.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importe tous les modèles → remplit db.metadata (aucun contexte d'app requis,
# aucune écriture, pas besoin de SECRET_KEY).
from models import db


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default = os.path.join(root, "gestion_conges.db")
    db_path = sys.argv[1] if len(sys.argv) > 1 else default

    if not os.path.isfile(db_path):
        print(f"Base introuvable : {db_path}")
        sys.exit(1)

    # Ouverture en lecture seule (mode=ro) : impossible d'altérer la base.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {r[0] for r in cur.fetchall()}

    expected = db.metadata.tables  # {nom_table: Table}

    print("=" * 70)
    print(f"Base analysée : {db_path}")
    print(f"Tables présentes : {len(existing_tables)}  |  attendues (code) : {len(expected)}")
    print("=" * 70)

    missing_tables = []
    tables_ok = True

    for tname, table in sorted(expected.items()):
        if tname not in existing_tables:
            missing_tables.append(tname)
            continue
        cur.execute(f"PRAGMA table_info('{tname}')")
        info = cur.fetchall()  # (cid, name, type, notnull, dflt_value, pk)
        actual = {row[1]: row for row in info}
        expected_cols = {c.name for c in table.columns}
        missing_cols = expected_cols - actual.keys()
        extra_cols = set(actual.keys()) - expected_cols
        if missing_cols or extra_cols:
            tables_ok = False
            print(f"\n[{tname}]")
            for c in table.columns:
                if c.name in missing_cols:
                    sd = c.server_default.arg if c.server_default is not None else None
                    print(
                        f"  COLONNE MANQUANTE : {c.name} "
                        f"(type={c.type}, nullable={c.nullable}, server_default={sd})"
                    )
            for name in sorted(extra_cols):
                _cid, _nm, ctype, notnull, dflt, _pk = actual[name]
                # Une colonne héritée NOT NULL sans défaut casse les futures
                # insertions ORM (qui ne la renseignent pas) → à signaler.
                risque = " <-- RISQUE INSERT (NOT NULL sans défaut)" if (notnull and dflt is None) else ""
                print(
                    f"  colonne héritée : {name} "
                    f"(type={ctype}, NOT NULL={bool(notnull)}, default={dflt}){risque}"
                )

    if missing_tables:
        print(
            "\nTABLES MANQUANTES (seront créées vides par db.create_all au démarrage) : "
            f"{sorted(missing_tables)}"
        )

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
    has_alembic = cur.fetchone() is not None
    print(f"\nSuivi de migrations Alembic : {'présent' if has_alembic else 'absent'}")
    if has_alembic:
        cur.execute("SELECT version_num FROM alembic_version")
        print("  version_num :", [r[0] for r in cur.fetchall()])

    print("\n" + "-" * 70)
    if tables_ok and not missing_tables:
        print("RÉSULTAT : schéma compatible. La base peut être utilisée telle quelle.")
    elif tables_ok and missing_tables:
        print("RÉSULTAT : seules des tables NEUVES manquent → db.create_all suffira.")
    else:
        print("RÉSULTAT : des colonnes manquent → migration nécessaire (voir ci-dessus).")
    print("-" * 70)

    conn.close()


if __name__ == "__main__":
    main()
