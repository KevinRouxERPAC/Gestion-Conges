"""justificatifs absence

Revision ID: 09cb9c4b92e4
Revises: 6c4c4dc24980
Create Date: 2026-06-02 09:02:57.045696

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09cb9c4b92e4'
down_revision = '6c4c4dc24980'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "justificatifs" not in tables:
        op.create_table(
            "justificatifs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("conge_id", sa.Integer(), nullable=False),
            sa.Column("nom_fichier", sa.String(length=255), nullable=False),
            sa.Column("nom_stockage", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=False),
            sa.Column("taille_octets", sa.Integer(), nullable=False),
            sa.Column("upload_par_id", sa.Integer(), nullable=False),
            sa.Column("upload_le", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["conge_id"], ["conges.id"]),
            sa.ForeignKeyConstraint(["upload_par_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("conge_id"),
            sa.UniqueConstraint("nom_stockage"),
        )

    exc_cols = {c["name"] for c in inspector.get_columns("conges_exceptionnels_types")}
    if "justificatif_requis" not in exc_cols:
        with op.batch_alter_table("conges_exceptionnels_types", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("justificatif_requis", sa.Boolean(), nullable=False, server_default=sa.text("0"))
            )


def downgrade():
    with op.batch_alter_table("conges_exceptionnels_types", schema=None) as batch_op:
        batch_op.drop_column("justificatif_requis")
    op.drop_table("justificatifs")
