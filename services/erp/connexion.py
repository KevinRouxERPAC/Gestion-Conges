"""Connexion READ-ONLY au SQL Server ERP (SILOG/Cegid PMI).

Garanties read-only (3 niveaux) :
  1. Côté serveur : le login SQL n'a que SELECT sur la base.
  2. Paramètre de connexion ApplicationIntent=ReadOnly + autocommit=True.
  3. Ce module n'exécute jamais de INSERT/UPDATE/DELETE vers l'ERP.

Configuration (variables d'environnement, ex. dans web.config) :
  ERP_DB_ENABLED   = true          # désactivé par défaut — aucune tentative de connexion
  ERP_DB_SERVER    = SRV18150RD1
  ERP_DB_DATABASE  = PMI
  ERP_DB_USER      = lecteur_app
  ERP_DB_PASSWORD  = ...           # jamais dans le dépôt
  ERP_DB_DRIVER    = ODBC Driver 17 for SQL Server
  ERP_DB_ENCRYPT         = yes
  ERP_DB_TRUST_CERT      = yes     # certificat auto-signé interne
  ERP_DB_TIMEOUT         = 10      # secondes
"""
from __future__ import annotations

import os
from contextlib import contextmanager

try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None  # type: ignore[assignment]


class ErpNonConfigureError(RuntimeError):
    """Levée si ERP_DB_ENABLED n'est pas 'true' ou si pyodbc est absent."""


def erp_active() -> bool:
    return os.environ.get("ERP_DB_ENABLED", "").lower() == "true"


def _pilotes_odbc_sql_server() -> list[str]:
    """Liste les pilotes ODBC SQL Server installés sur la machine."""
    if pyodbc is None:
        return []
    try:
        return [d for d in pyodbc.drivers() if "SQL Server" in d]
    except Exception:
        return []


def _conn_str() -> str:
    driver = os.environ.get("ERP_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.environ.get("ERP_DB_SERVER", "")
    database = os.environ.get("ERP_DB_DATABASE", "")
    user = os.environ.get("ERP_DB_USER", "")
    password = os.environ.get("ERP_DB_PASSWORD", "")
    encrypt = os.environ.get("ERP_DB_ENCRYPT", "yes")
    trust = os.environ.get("ERP_DB_TRUST_CERT", "yes")
    timeout = os.environ.get("ERP_DB_TIMEOUT", "10")
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};DATABASE={database};"
        f"UID={user};PWD={password};"
        f"Encrypt={encrypt};TrustServerCertificate={trust};"
        f"ApplicationIntent=ReadOnly;"
        f"Connection Timeout={timeout};"
    )


@contextmanager
def erp_connexion():
    """Context manager : ouvre une connexion read-only et la ferme à la sortie.

    Usage :
        with erp_connexion() as conn:
            rows = conn.execute("SELECT ...").fetchall()

    Lève ErpNonConfigureError si ERP_DB_ENABLED != 'true' ou pyodbc absent.
    """
    if not erp_active():
        raise ErpNonConfigureError(
            "Connexion ERP désactivée. Définissez ERP_DB_ENABLED=true et les variables ERP_DB_*."
        )
    if pyodbc is None:
        raise ErpNonConfigureError("Le module pyodbc n'est pas installé (pip install pyodbc).")

    try:
        conn = pyodbc.connect(_conn_str(), autocommit=True, timeout=10, readonly=True)
    except pyodbc.Error as e:
        code = e.args[0] if e.args else ""
        if code == "IM002":
            driver = os.environ.get("ERP_DB_DRIVER", "ODBC Driver 17 for SQL Server")
            installes = _pilotes_odbc_sql_server()
            liste = ", ".join(installes) if installes else "(aucun pilote SQL Server détecté)"
            raise ErpNonConfigureError(
                f"Pilote ODBC introuvable : {driver!r}. "
                f"Pilotes SQL Server installés : {liste}. "
                "Installez « ODBC Driver 17/18 for SQL Server » ou ajustez ERP_DB_DRIVER dans web.config."
            ) from e
        raise
    try:
        yield conn
    finally:
        conn.close()
