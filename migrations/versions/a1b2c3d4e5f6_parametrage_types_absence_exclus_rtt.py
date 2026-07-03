"""parametrage : types d'absence exclus du seuil RTT hebdo

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-07-03 00:00:00.000000

Ajoute ``parametrage_annuel.rtt_types_absence_exclus`` (String, défaut '') : liste
de codes de types d'absence séparés par des virgules qui ne réduiront pas le seuil
hebdomadaire RTT (ex. « Maladie » ne doit pas faire perdre de RTT au salarié).

Par défaut vide → tous les congés validés réduisent le seuil (comportement
historique préservé).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    param_cols = {c["name"] for c in inspector.get_columns("parametrage_annuel")}
    if "rtt_types_absence_exclus" not in param_cols:
        with op.batch_alter_table("parametrage_annuel", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("rtt_types_absence_exclus", sa.String(length=255),
                          nullable=False, server_default="")
            )


def downgrade():
    with op.batch_alter_table("parametrage_annuel", schema=None) as batch_op:
        batch_op.drop_column("rtt_types_absence_exclus")
