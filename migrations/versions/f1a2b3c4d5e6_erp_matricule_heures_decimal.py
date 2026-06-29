"""Synchro ERP : colonne users.matricule + heures_hebdo en décimal.

Revision ID: f1a2b3c4d5e6
Revises: e3f1a2b4c5d6
Create Date: 2026-06-29 00:00:00.000000

Deux ajouts liés à la synchro ERP (lecture SILOG/PMI → heures_hebdo) :
1. ``users.matricule`` : code salarié ERP (clé de rapprochement, NULL = non relié).
2. ``heures_hebdo.heures_travaillees`` : Integer → Numeric(5,2) pour accepter les
   demi-heures renvoyées par TEMPAS (ex. 32,5 h ; 30,25 h).
"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e6'
down_revision = 'e3f1a2b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. users.matricule
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "matricule" not in user_cols:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("matricule", sa.String(20), nullable=True)
            )
        op.create_index("ix_users_matricule", "users", ["matricule"], unique=True)

    # 2. heures_hebdo.heures_travaillees Integer → Numeric(5,2)
    # batch_alter_table reconstruit la table en SQLite (pas d'ALTER COLUMN natif).
    with op.batch_alter_table("heures_hebdo", schema=None) as batch_op:
        batch_op.alter_column(
            "heures_travaillees",
            existing_type=sa.Integer(),
            type_=sa.Numeric(5, 2),
            existing_nullable=False,
        )


def downgrade():
    # Retire l'index avant de supprimer la colonne.
    try:
        op.drop_index("ix_users_matricule", table_name="users")
    except Exception:
        pass
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("matricule")

    with op.batch_alter_table("heures_hebdo", schema=None) as batch_op:
        batch_op.alter_column(
            "heures_travaillees",
            existing_type=sa.Numeric(5, 2),
            type_=sa.Integer(),
            existing_nullable=False,
        )
