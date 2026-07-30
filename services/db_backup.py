"""Sauvegardes automatiques de la base SQLite (copie cohérente + rotation).

Utilise l'API ``sqlite3.Connection.backup`` pour une copie à chaud sans corrompre
le fichier source pendant les écritures concurrentes.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("gestion_conges.database")

_BACKUP_NAME_RE = re.compile(
    r"^gestion_conges-(?P<raison>[a-z0-9_-]+)-(?P<stamp>\d{8}-\d{6})\.db$"
)


@dataclass(frozen=True)
class SauvegardeInfo:
    chemin: Path
    raison: str
    cree_le: datetime
    taille_octets: int
    users: int | None = None


def sqlite_db_path(database_uri: str | None = None) -> Path | None:
    """Retourne le chemin fichier SQLite, ou None si mémoire / autre SGBD."""
    if database_uri is None:
        from flask import current_app

        database_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not database_uri.startswith("sqlite:///"):
        return None
    path = database_uri.replace("sqlite:///", "", 1)
    if "?" in path:
        path = path.split("?", 1)[0]
    if path == ":memory:":
        return None
    return Path(path)


def configurer_journal_base(app) -> None:
    """Journal dédié base de données → logs/database.log."""
    log_path = app.config.get("DB_LOG_FILE") or os.path.join(app.config["BASE_DIR"], "logs", "database.log")
    log_dir = os.path.dirname(log_path)
    os.makedirs(log_dir, exist_ok=True)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    for name in ("gestion_conges.database", "services.db_backup", "services.db_safety"):
        log = logging.getLogger(name)
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(log_path) for h in log.handlers):
            log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = True

    logger.info("Journal base de données : %s", log_path)


def _compter_users(db_path: Path) -> int | None:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "users" not in tables:
            conn.close()
            return None
        count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        return int(count)
    except sqlite3.Error:
        return None


def _parse_sauvegarde(path: Path) -> SauvegardeInfo | None:
    m = _BACKUP_NAME_RE.match(path.name)
    if not m:
        return None
    try:
        cree_le = datetime.strptime(m.group("stamp"), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return SauvegardeInfo(
        chemin=path,
        raison=m.group("raison"),
        cree_le=cree_le,
        taille_octets=path.stat().st_size,
    )


def _backup_dir(backup_dir: Path | None = None) -> Path:
    if backup_dir is not None:
        return Path(backup_dir)
    from flask import current_app

    return Path(
        current_app.config.get("DB_BACKUP_DIR")
        or os.path.join(current_app.config["BASE_DIR"], "backup")
    )


def lister_sauvegardes(backup_dir: Path | None = None) -> list[SauvegardeInfo]:
    dossier = _backup_dir(backup_dir)
    if not dossier.is_dir():
        return []
    sauvegardes: list[SauvegardeInfo] = []
    for path in dossier.glob("gestion_conges-*.db"):
        info = _parse_sauvegarde(path)
        if info:
            sauvegardes.append(info)
    return sorted(sauvegardes, key=lambda s: s.cree_le, reverse=True)


def purger_anciennes_sauvegardes(backup_dir: Path | None = None, max_count: int | None = None) -> int:
    from flask import current_app

    dossier = _backup_dir(backup_dir)
    limite = max_count if max_count is not None else int(current_app.config.get("DB_BACKUP_MAX_COUNT", 30))
    sauvegardes = lister_sauvegardes(dossier)
    supprimes = 0
    for info in sauvegardes[limite:]:
        try:
            info.chemin.unlink(missing_ok=True)
            meta = info.chemin.with_suffix(".db.meta.json")
            meta.unlink(missing_ok=True)
            supprimes += 1
        except OSError as exc:
            logger.warning("Impossible de supprimer %s : %s", info.chemin, exc)
    if supprimes:
        logger.info("Rotation sauvegardes : %d fichier(s) supprimé(s) (max %d).", supprimes, limite)
    return supprimes


def derniere_sauvegarde(backup_dir: Path | None = None) -> SauvegardeInfo | None:
    sauvegardes = lister_sauvegardes(backup_dir)
    return sauvegardes[0] if sauvegardes else None


def sauvegarder_base(
    raison: str = "manuel",
    *,
    database_uri: str | None = None,
    backup_dir: Path | None = None,
    forcer: bool = False,
) -> SauvegardeInfo | None:
    """Copie la base SQLite dans backup/ et journalise l'opération.

    Retourne None si pas de fichier SQLite (ex. tests en mémoire) ou si une
    sauvegarde récente existe déjà (intervalle configurable) sauf ``forcer=True``.
    """
    from flask import current_app

    db_path = sqlite_db_path(database_uri)
    if db_path is None or not db_path.is_file():
        logger.debug("Sauvegarde ignorée (%s) : pas de fichier SQLite.", raison)
        return None

    dossier = _backup_dir(backup_dir)
    dossier.mkdir(parents=True, exist_ok=True)

    if not forcer:
        interval_h = int(current_app.config.get("DB_BACKUP_MIN_INTERVAL_HOURS", 6))
        derniere = derniere_sauvegarde(dossier)
        if derniere and datetime.now() - derniere.cree_le < timedelta(hours=interval_h):
            logger.info(
                "Sauvegarde ignorée (%s) : dernière il y a moins de %dh (%s).",
                raison,
                interval_h,
                derniere.chemin.name,
            )
            return derniere

    raison_safe = re.sub(r"[^a-z0-9_-]+", "-", raison.lower()).strip("-") or "manuel"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dossier / f"gestion_conges-{raison_safe}-{stamp}.db"

    users = _compter_users(db_path)
    try:
        src = sqlite3.connect(str(db_path), timeout=30)
        dst = sqlite3.connect(str(dest))
        src.backup(dst)
        dst.close()
        src.close()
    except sqlite3.Error as exc:
        logger.error("Échec sauvegarde (%s) : %s", raison, exc)
        dest.unlink(missing_ok=True)
        raise

    info = SauvegardeInfo(
        chemin=dest,
        raison=raison_safe,
        cree_le=datetime.strptime(stamp, "%Y%m%d-%H%M%S"),
        taille_octets=dest.stat().st_size,
        users=users,
    )
    meta = {
        "source": str(db_path),
        "raison": raison_safe,
        "cree_le": stamp,
        "taille_octets": info.taille_octets,
        "users": users,
    }
    dest.with_suffix(".db.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    purger_anciennes_sauvegardes(dossier)
    logger.info(
        "Sauvegarde OK (%s) → %s | %d octets | users=%s",
        raison_safe,
        dest.name,
        info.taille_octets,
        users if users is not None else "?",
    )
    return info


def sauvegarder_si_demarrage() -> SauvegardeInfo | None:
    """Sauvegarde au démarrage serveur si activée dans la config."""
    from flask import current_app

    if not current_app.config.get("DB_BACKUP_ON_STARTUP", True):
        return None
    if current_app.config.get("TESTING"):
        return None
    return sauvegarder_base("demarrage")
