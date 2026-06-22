"""rtt heures en décimal (Numeric 6,2) + merge des heads + rtt_acquis_par_semaine

Revision ID: e3f1a2b4c5d6
Revises: 09cb9c4b92e4, c7e1a2f4b9d0
Create Date: 2026-06-16 00:00:00.000000

Cette migration :
1. Fusionne les deux têtes Alembic divergentes (09cb9c4b92e4 et c7e1a2f4b9d0).
2. Ajoute la colonne ``parametrage_annuel.rtt_acquis_par_semaine`` (présente dans
   le modèle mais sans migration dédiée jusqu'ici) — idempotent.
3. Convertit les heures RTT de ``Integer`` vers ``Numeric(6,2)`` pour conserver
   les fractions d'heure (ex. 16,10 h) sans perte d'arrondi (R3).

Sauvegarder la base avant ``flask db upgrade`` en production (cf. plan d'audit).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3f1a2b4c5d6'
down_revision = ('09cb9c4b92e4', 'c7e1a2f4b9d0')
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Colonne rtt_acquis_par_semaine (ajoutée au modèle sans migration dédiée).
    param_cols = {c["name"] for c in inspector.get_columns("parametrage_annuel")}
    if "rtt_acquis_par_semaine" not in param_cols:
        with op.batch_alter_table("parametrage_annuel", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("rtt_acquis_par_semaine", sa.Float(), nullable=False, server_default="0")
            )

    # 2. Heures RTT consommées (conges.nb_heures_rtt) en décimal.
    with op.batch_alter_table("conges", schema=None) as batch_op:
        batch_op.alter_column(
            "nb_heures_rtt",
            existing_type=sa.Integer(),
            type_=sa.Numeric(6, 2),
            existing_nullable=True,
        )

    # 3. Heures RTT allouées / reportées (allocations_conges) en décimal.
    with op.batch_alter_table("allocations_conges", schema=None) as batch_op:
        batch_op.alter_column(
            "rtt_heures_allouees",
            existing_type=sa.Integer(),
            type_=sa.Numeric(6, 2),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "rtt_heures_reportees",
            existing_type=sa.Integer(),
            type_=sa.Numeric(6, 2),
            existing_nullable=False,
        )


def downgrade():
    # On revient au stockage entier (les fractions d'heure seront tronquées).
    with op.batch_alter_table("allocations_conges", schema=None) as batch_op:
        batch_op.alter_column(
            "rtt_heures_reportees",
            existing_type=sa.Numeric(6, 2),
            type_=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "rtt_heures_allouees",
            existing_type=sa.Numeric(6, 2),
            type_=sa.Integer(),
            existing_nullable=False,
        )
    with op.batch_alter_table("conges", schema=None) as batch_op:
        batch_op.alter_column(
            "nb_heures_rtt",
            existing_type=sa.Numeric(6, 2),
            type_=sa.Integer(),
            existing_nullable=True,
        )
    # rtt_acquis_par_semaine n'est pas retiré : il relève d'une évolution
    # fonctionnelle distincte (RTT hebdomadaire), pas du périmètre R3.
