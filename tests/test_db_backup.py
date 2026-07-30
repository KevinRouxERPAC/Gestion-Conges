"""Tests sauvegardes base de données."""
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from models import db
from services.db_backup import (
    lister_sauvegardes,
    purger_anciennes_sauvegardes,
    sauvegarder_base,
)
from services.db_safety import patch_drop_all


def _creer_db_minimale(path: Path, nb_users: int = 1) -> str:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    for i in range(nb_users):
        conn.execute("INSERT INTO users (id) VALUES (?)", (i + 1,))
    conn.commit()
    conn.close()
    return "sqlite:///" + str(path).replace("\\", "/")


def test_sauvegarder_base_cree_fichier(app, tmp_path):
    db_path = tmp_path / "test.db"
    backup_dir = tmp_path / "backups"
    uri = _creer_db_minimale(db_path, nb_users=2)
    with app.app_context():
        info = sauvegarder_base(
            "test",
            database_uri=uri,
            backup_dir=backup_dir,
            forcer=True,
        )
        assert info is not None
        assert info.chemin.is_file()
        assert info.users == 2
        c = sqlite3.connect(info.chemin)
        assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
        c.close()


def test_rotation_supprime_anciennes(app, tmp_path):
    db_path = tmp_path / "test.db"
    backup_dir = tmp_path / "backups"
    _creer_db_minimale(db_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        dest = backup_dir / f"gestion_conges-test-{datetime(2026, 1, 1, i):%Y%m%d-%H%M%S}.db"
        c = sqlite3.connect(db_path)
        d = sqlite3.connect(dest)
        c.backup(d)
        d.close()
        c.close()
    with app.app_context():
        app.config["DB_BACKUP_DIR"] = str(backup_dir)
        assert len(lister_sauvegardes(backup_dir)) == 5
        purger_anciennes_sauvegardes(backup_dir, max_count=3)
        assert len(lister_sauvegardes(backup_dir)) == 3


def test_drop_all_bloque_sur_gestion_conges_db(app):
    """drop_all() ne doit jamais effacer gestion_conges.db à la racine du projet."""
    prod_db = Path(app.config["BASE_DIR"]) / "gestion_conges.db"
    uri = "sqlite:///" + str(prod_db).replace("\\", "/")
    ancien_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    try:
        app.config["SQLALCHEMY_DATABASE_URI"] = uri
        with app.app_context():
            patch_drop_all(db)
            with pytest.raises(RuntimeError, match="drop_all"):
                db.drop_all()
    finally:
        app.config["SQLALCHEMY_DATABASE_URI"] = ancien_uri


def test_drop_all_autorise_en_mode_test(app):
    with app.app_context():
        patch_drop_all(db)
        db.drop_all()
        db.create_all()
