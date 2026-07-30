"""Garde-fous base de données : schéma cohérent et commits transactionnels.

Objectif : aucun enregistrement ne doit laisser la session SQLAlchemy dans un état
incohérent ni écrire sur un schéma incompatible avec les modèles.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass, field

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

logger = logging.getLogger("gestion_conges.database")


class DbSaveError(Exception):
    """Erreur métier lors d'un enregistrement (message affichable à l'utilisateur)."""

    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message)
        self.message = message
        self.original = original


@dataclass
class SchemaCheckResult:
    ok: bool
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    risky_extra_columns: list[str] = field(default_factory=list)
    alembic_version: str | None = None

    @property
    def resume(self) -> str:
        parts = []
        if self.missing_tables:
            parts.append(f"tables manquantes : {', '.join(self.missing_tables)}")
        if self.missing_columns:
            parts.append(f"colonnes manquantes : {', '.join(self.missing_columns)}")
        if self.risky_extra_columns:
            parts.append(
                f"colonnes héritées à risque : {', '.join(self.risky_extra_columns)}"
            )
        if self.alembic_version:
            parts.append(f"alembic={self.alembic_version}")
        return " ; ".join(parts) if parts else "schéma compatible"


def _sqlite_db_path(database_uri: str) -> str | None:
    from services.db_backup import sqlite_db_path as _path

    p = _path(database_uri)
    return str(p) if p else None


def _est_base_production_par_defaut(database_uri: str | None = None) -> bool:
    """True si la BDD pointe vers gestion_conges.db à la racine du projet."""
    from flask import current_app

    uri = database_uri or current_app.config["SQLALCHEMY_DATABASE_URI"]
    path = _sqlite_db_path(uri)
    if not path:
        return False
    prod = os.path.normpath(
        os.path.join(current_app.config["BASE_DIR"], "gestion_conges.db")
    )
    return os.path.normpath(path) == prod


def patch_drop_all(db) -> None:
    """Interdit drop_all() sur gestion_conges.db (protection anti pytest / scripts)."""
    if getattr(db, "_drop_all_patched", False):
        return

    original = db.drop_all

    def drop_all_protege(*args, **kwargs):
        from flask import has_app_context

        if has_app_context() and _est_base_production_par_defaut():
            msg = (
                "drop_all() bloqué sur gestion_conges.db. "
                "Utilisez une copie de travail ou sqlite:///:memory: pour les tests."
            )
            logger.critical(msg)
            raise RuntimeError(msg)
        return original(*args, **kwargs)

    db.drop_all = drop_all_protege  # type: ignore[method-assign]
    db._drop_all_patched = True  # type: ignore[attr-defined]


def analyser_schema(database_uri: str | None = None) -> SchemaCheckResult:
    """Compare le schéma SQLite aux modèles ORM (lecture seule)."""
    from flask import current_app
    from models import db

    uri = database_uri or current_app.config["SQLALCHEMY_DATABASE_URI"]
    db_path = _sqlite_db_path(uri)
    if db_path is None:
        return SchemaCheckResult(ok=True)

    if not os.path.isfile(db_path):
        return SchemaCheckResult(ok=True, missing_tables=list(db.metadata.tables.keys()))

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {r[0] for r in cur.fetchall()}

    missing_tables: list[str] = []
    missing_columns: list[str] = []
    risky_extra_columns: list[str] = []

    for tname, table in db.metadata.tables.items():
        if tname not in existing_tables:
            missing_tables.append(tname)
            continue
        cur.execute(f"PRAGMA table_info('{tname}')")
        actual = {row[1]: row for row in cur.fetchall()}
        expected_cols = {c.name for c in table.columns}
        for col in sorted(expected_cols - actual.keys()):
            missing_columns.append(f"{tname}.{col}")
        for name in sorted(actual.keys() - expected_cols):
            _cid, _nm, _ctype, notnull, dflt, _pk = actual[name]
            if notnull and dflt is None:
                risky_extra_columns.append(f"{tname}.{name}")

    alembic_version = None
    if "alembic_version" in existing_tables:
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
        if row:
            alembic_version = row[0]

    conn.close()
    ok = not missing_tables and not missing_columns and not risky_extra_columns
    return SchemaCheckResult(
        ok=ok,
        missing_tables=missing_tables,
        missing_columns=missing_columns,
        risky_extra_columns=risky_extra_columns,
        alembic_version=alembic_version,
    )


def _message_integrity(exc: IntegrityError) -> str:
    orig = str(getattr(exc, "orig", exc) or exc).lower()
    if "users.matricule" in orig or "ix_users_matricule" in orig:
        return "Ce matricule ERP est déjà utilisé par un autre salarié."
    if "users.identifiant" in orig or "identifiant" in orig:
        return "Cet identifiant est déjà utilisé."
    if "unique" in orig or "duplicate" in orig:
        return "Enregistrement impossible : une contrainte d'unicité est violée."
    return "Enregistrement impossible : donnée déjà existante ou référence invalide."


def _message_operational(exc: OperationalError) -> str:
    orig = str(getattr(exc, "orig", exc) or exc).lower()
    if "no such column" in orig or "has no column" in orig:
        return (
            "Schéma de base incompatible avec l'application. "
            "Contactez l'administrateur (migration Alembic requise)."
        )
    if "no such table" in orig:
        return (
            "Table manquante en base. "
            "Contactez l'administrateur (migration Alembic requise)."
        )
    return "Erreur base de données lors de l'enregistrement."


def patch_session_commit(db) -> None:
    """Intercepte db.session.commit() pour rollback automatique en cas d'erreur."""
    session = db.session
    if getattr(session, "_commit_patched", False):
        return

    original_commit = session.commit

    def commit_protege():
        try:
            return original_commit()
        except IntegrityError as exc:
            session.rollback()
            raise DbSaveError(_message_integrity(exc), exc) from exc
        except OperationalError as exc:
            session.rollback()
            raise DbSaveError(_message_operational(exc), exc) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise DbSaveError(
                "Erreur lors de l'enregistrement. Aucune modification n'a été conservée.",
                exc,
            ) from exc

    session.commit = commit_protege  # type: ignore[method-assign]
    session._commit_patched = True  # type: ignore[attr-defined]


def preparer_base_au_demarrage(app) -> None:
    """Valide le schéma, protège les écritures et sauvegarde si besoin."""
    from models import db
    from services.db_backup import configurer_journal_base, sauvegarder_si_demarrage

    with app.app_context():
        configurer_journal_base(app)
        patch_session_commit(db)
        patch_drop_all(db)
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        db_path = _sqlite_db_path(uri)
        skip_create = os.environ.get("SKIP_DB_CREATE_ALL") == "1"

        if db_path and not os.path.isfile(db_path):
            if not skip_create:
                db.create_all()
                logger.info("Base SQLite créée (create_all).")
            return

        check = analyser_schema(uri)

        if check.alembic_version and (check.missing_tables or check.missing_columns):
            logger.critical(
                "Schéma BDD incomplet (%s). Exécutez : flask db upgrade",
                check.resume,
            )
        elif not check.ok:
            logger.warning("Schéma BDD : %s", check.resume)
        elif check.ok and check.alembic_version:
            logger.info("Schéma BDD compatible (alembic %s).", check.alembic_version)

        try:
            sauvegarder_si_demarrage()
        except Exception:
            logger.exception("Sauvegarde au démarrage échouée (l'application continue).")

        if skip_create:
            if check.missing_tables or check.missing_columns:
                logger.critical(
                    "SKIP_DB_CREATE_ALL=1 : les enregistrements échoueront tant que "
                    "le schéma n'est pas migré (flask db upgrade)."
                )
            return

        if check.alembic_version:
            if check.missing_tables:
                logger.warning(
                    "alembic_version présent : create_all ignoré. "
                    "Lancez flask db upgrade pour ajouter les tables manquantes."
                )
            return

        if check.missing_tables and not check.missing_columns:
            db.create_all()
            logger.info("Tables manquantes créées (create_all).")
        elif check.missing_tables or check.missing_columns:
            logger.error(
                "Schéma incomplet (%s). Exécutez flask db upgrade avant d'enregistrer.",
                check.resume,
            )
