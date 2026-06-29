"""Sonde ciblée (lecture seule) de tables/vues candidates de l'ERP SILOG.

Affiche, pour chaque objet : nombre de lignes, colonnes, et 3 lignes d'exemple.
Réutilise la connexion read-only de erp_introspect.
"""
import sys
from erp_introspect import charge_creds, connexion
import argparse

CANDIDATS = [
    "dbo.ACTITRAC", "dbo.TEMPAS", "dbo.HORAIRES", "dbo.RPACH",
    "dbo.POINTAGE", "dbo.TRAVAUX", "dbo.CONSOM",
    "dbo.SALARIES",
    "OData.EmployeeList", "OData.CalendarEmployeeList", "OData.UserList",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--creds", required=True)
    ap.add_argument("--objets", nargs="*", default=CANDIDATS)
    ap.add_argument("--samples", type=int, default=3)
    args = ap.parse_args()

    conn = connexion(charge_creds(args))
    cur = conn.cursor()
    try:
        for obj in args.objets:
            sch, _, nom = obj.partition(".")
            print("\n" + "=" * 75)
            try:
                n = cur.execute(f"SELECT COUNT(*) FROM [{sch}].[{nom}]").fetchone()[0]
            except Exception as e:
                print(f"{obj} : INACCESSIBLE ({e})")
                continue
            print(f"{obj}  —  {n} lignes")
            cols = [c.column_name for c in cur.columns(table=nom, schema=sch)]
            print("Colonnes:", ", ".join(cols))
            if n:
                cur.execute(f"SELECT TOP {args.samples} * FROM [{sch}].[{nom}]")
                desc = [d[0] for d in cur.description]
                rows = cur.fetchall()
                for r in rows:
                    print("  · " + " | ".join(f"{c}={'' if v is None else str(v).strip()[:22]}" for c, v in zip(desc, r)))
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
