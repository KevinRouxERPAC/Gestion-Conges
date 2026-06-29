"""Introspection LECTURE SEULE du schéma SQL Server de l'ERP.

But : découvrir où se trouvent les heures travaillées et les fiches salariés
(tables/vues, colonnes, échantillons) afin d'écrire ensuite les requêtes de
synchronisation. Ce script n'exécute QUE des SELECT et ne modifie jamais l'ERP.

Identifiants : lus depuis un fichier JSON (--creds) OU les variables
d'environnement ERP_DB_SERVER / ERP_DB_DATABASE / ERP_DB_USER / ERP_DB_PASSWORD /
ERP_DB_DRIVER. Le mot de passe ne transite jamais en argument de ligne de commande.

Usage :
    python scripts/erp_introspect.py --creds chemin/erp_creds.json
    python scripts/erp_introspect.py --creds creds.json --table dbo.MaTable   # détail d'une table
"""
import argparse
import json
import os
import sys

import pyodbc

# Mots-clés pour repérer automatiquement les tables/vues pertinentes.
MOTS_HEURES = ("heure", "temps", "pointage", "presence", "activite", "timesheet", "releve")
MOTS_SALARIES = ("salarie", "personnel", "employe", "agent", "matricule", "collaborateur", "rh")


def charge_creds(args):
    if args.creds:
        with open(args.creds, encoding="utf-8") as f:
            c = json.load(f)
    else:
        c = {
            "server": os.environ.get("ERP_DB_SERVER", ""),
            "database": os.environ.get("ERP_DB_DATABASE", ""),
            "user": os.environ.get("ERP_DB_USER", ""),
            "password": os.environ.get("ERP_DB_PASSWORD", ""),
            "driver": os.environ.get("ERP_DB_DRIVER", "ODBC Driver 18 for SQL Server"),
            "encrypt": os.environ.get("ERP_DB_ENCRYPT", "yes"),
            "trust_server_certificate": os.environ.get("ERP_DB_TRUST_CERT", "yes"),
        }
    manquants = [k for k in ("server", "database", "user", "password") if not c.get(k)]
    if manquants:
        sys.exit(f"Identifiants incomplets (manquants : {', '.join(manquants)}).")
    return c


def connexion(c):
    """Connexion read-only à l'ERP. autocommit=True, aucune transaction d'écriture."""
    conn_str = (
        f"DRIVER={{{c['driver']}}};"
        f"SERVER={c['server']};"
        f"DATABASE={c['database']};"
        f"UID={c['user']};"
        f"PWD={c['password']};"
        f"Encrypt={c.get('encrypt', 'yes')};"
        f"TrustServerCertificate={c.get('trust_server_certificate', 'yes')};"
        f"ApplicationIntent=ReadOnly;"
        f"Connection Timeout=10;"
    )
    return pyodbc.connect(conn_str, autocommit=True, timeout=10, readonly=True)


def liste_objets(cur):
    cur.execute(
        """
        SELECT s.name AS sch, t.name AS nom, 'TABLE' AS typ,
               SUM(p.rows) AS nb
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
        GROUP BY s.name, t.name
        UNION ALL
        SELECT s.name, v.name, 'VUE', NULL
        FROM sys.views v
        JOIN sys.schemas s ON s.schema_id = v.schema_id
        ORDER BY sch, nom
        """
    )
    return cur.fetchall()


def colonnes(cur, schema, nom):
    cur.execute(
        """
        SELECT c.name, ty.name, c.max_length, c.is_nullable
        FROM sys.columns c
        JOIN sys.types ty ON ty.user_type_id = c.user_type_id
        WHERE c.object_id = OBJECT_ID(?)
        ORDER BY c.column_id
        """,
        f"{schema}.{nom}",
    )
    return cur.fetchall()


def echantillon(cur, schema, nom, n=3):
    cur.execute(f"SELECT TOP {n} * FROM [{schema}].[{nom}]")
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()


def pertinent(nom):
    bas = nom.lower()
    h = any(m in bas for m in MOTS_HEURES)
    s = any(m in bas for m in MOTS_SALARIES)
    return h, s


def detail_objet(cur, schema, nom):
    print(f"\n{'='*70}\n{schema}.{nom}\n{'='*70}")
    print("Colonnes :")
    for col, typ, maxlen, nullable in colonnes(cur, schema, nom):
        print(f"   - {col:<35} {typ}({maxlen})  {'NULL' if nullable else 'NOT NULL'}")
    try:
        cols, rows = echantillon(cur, schema, nom)
        print(f"\nÉchantillon ({len(rows)} lignes) :")
        print("   " + " | ".join(cols))
        for r in rows:
            print("   " + " | ".join("" if v is None else str(v)[:30] for v in r))
    except Exception as e:
        print(f"   (échantillon indisponible : {e})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--creds", help="Fichier JSON d'identifiants")
    ap.add_argument("--table", help="Détailler une table/vue précise (schema.nom)")
    args = ap.parse_args()

    c = charge_creds(args)
    conn = connexion(c)
    cur = conn.cursor()
    try:
        ver = cur.execute("SELECT @@VERSION").fetchone()[0]
        print("Connexion OK (lecture seule).")
        print(ver.splitlines()[0])

        if args.table:
            sch, _, nom = args.table.partition(".")
            detail_objet(cur, sch, nom)
            return

        objets = liste_objets(cur)
        print(f"\n{len(objets)} objets (tables + vues).")

        candidats_h, candidats_s, autres = [], [], []
        for o in objets:
            h, s = pertinent(o.nom)
            if h:
                candidats_h.append(o)
            elif s:
                candidats_s.append(o)
            else:
                autres.append(o)

        def affiche(titre, lst):
            print(f"\n### {titre} ({len(lst)})")
            for o in lst:
                nb = "" if o.nb is None else f"  ~{o.nb} lignes"
                print(f"   {o.sch}.{o.nom}  [{o.typ}]{nb}")

        affiche("Candidats HEURES / TEMPS", candidats_h)
        affiche("Candidats SALARIÉS / PERSONNEL", candidats_s)

        # Détail automatique des candidats les plus probables.
        for o in candidats_h + candidats_s:
            detail_objet(cur, o.sch, o.nom)

        # Liste compacte des autres objets (pour repérage manuel).
        print(f"\n### Autres objets ({len(autres)}) — noms seulement")
        for o in autres:
            print(f"   {o.sch}.{o.nom} [{o.typ}]")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
