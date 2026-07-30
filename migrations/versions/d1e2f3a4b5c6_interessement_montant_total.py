"""interessement : montant total a repartir

Revision ID: d1e2f3a4b5c6
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 00:00:00.000000

Ajoute ``interessement_periodes.montant_total_euros`` (Numeric, nullable=True) :
montant global qu'on souhaite répartir entre les salariés au prorata de leurs
points finaux. Si NULL ou <= 0, aucun calcul en euros n'est effectué (on reste
sur le seul calcul de points).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("interessement_periodes")}
    if "montant_total_euros" not in cols:
        with op.batch_alter_table("interessement_periodes", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("montant_total_euros", sa.Numeric(precision=12, scale=2),
                          nullable=True)
            )


def downgrade():
    with op.batch_alter_table("interessement_periodes", schema=None) as batch_op:
        batch_op.drop_column("montant_total_euros")
