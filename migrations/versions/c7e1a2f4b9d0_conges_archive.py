"""conges archive flag

Revision ID: c7e1a2f4b9d0
Revises: a48d60a69965
Create Date: 2026-06-02 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e1a2f4b9d0'
down_revision = 'a48d60a69965'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('conges', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('archive', sa.Boolean(), nullable=False, server_default='0')
        )


def downgrade():
    with op.batch_alter_table('conges', schema=None) as batch_op:
        batch_op.drop_column('archive')
