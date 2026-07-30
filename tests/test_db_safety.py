"""Tests des garde-fous base de données (commit protégé, analyse schéma)."""
import pytest

from models import db
from models.user import User
from services.db_safety import DbSaveError, analyser_schema, patch_session_commit


def test_commit_protege_rollback_sur_doublon_identifiant(app, db_session, users, _hash):
    with app.app_context():
        patch_session_commit(db)
        avant = User.query.count()
        db.session.add(User(
            nom="Test",
            prenom="Doublon",
            identifiant=users["salarie"].identifiant,
            mot_de_passe_hash=_hash("x"),
            role="salarie",
            actif=True,
        ))
        with pytest.raises(DbSaveError) as exc:
            db.session.commit()
        assert "identifiant" in exc.value.message.lower()
        assert User.query.count() == avant


def test_analyser_schema_base_compatible(app, parametrage):
    with app.app_context():
        result = analyser_schema()
        assert result.ok is True
        assert result.missing_tables == []
        assert result.missing_columns == []
