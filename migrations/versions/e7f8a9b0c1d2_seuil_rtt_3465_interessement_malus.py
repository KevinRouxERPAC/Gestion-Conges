"""Seuil RTT 34,65 h + malus maladie intéressement.

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3a4b5c6
"""
from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    param_cols = {c["name"] for c in inspector.get_columns("parametrage_annuel")}
    if "rtt_seuil_hebdo" in param_cols:
        with op.batch_alter_table("parametrage_annuel", schema=None) as batch_op:
            batch_op.alter_column(
                "rtt_seuil_hebdo",
                existing_type=sa.Integer(),
                type_=sa.Numeric(precision=5, scale=2),
                existing_nullable=False,
                server_default="34.65",
            )
        op.execute(
            "UPDATE parametrage_annuel SET rtt_seuil_hebdo = 34.65 "
            "WHERE rtt_seuil_hebdo = 35 OR rtt_seuil_hebdo IS NULL"
        )

    inter_cols = {c["name"] for c in inspector.get_columns("interessement_periodes")}
    if "malus_maladie_par_jour" not in inter_cols:
        with op.batch_alter_table("interessement_periodes", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("malus_maladie_par_jour", sa.Float(), nullable=False, server_default="5")
            )


def downgrade():
    with op.batch_alter_table("interessement_periodes", schema=None) as batch_op:
        batch_op.drop_column("malus_maladie_par_jour")

    with op.batch_alter_table("parametrage_annuel", schema=None) as batch_op:
        batch_op.alter_column(
            "rtt_seuil_hebdo",
            existing_type=sa.Numeric(precision=5, scale=2),
            type_=sa.Integer(),
            existing_nullable=False,
            server_default="35",
        )
