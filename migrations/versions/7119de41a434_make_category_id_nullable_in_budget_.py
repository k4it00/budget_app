"""Make category_id nullable in budget_goals

Revision ID: 7119de41a434
Revises: fc184a15ce60
Create Date: 2024-12-29 18:01:43.792088

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7119de41a434'
down_revision = 'fc184a15ce60'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('budget_goals', schema=None) as batch_op:
        batch_op.alter_column('category_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('budget_goals', schema=None) as batch_op:
        batch_op.alter_column('category_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # ### end Alembic commands ###