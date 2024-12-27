from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '907bd9bd82e1'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_id', sa.String(length=128), nullable=True))
        batch_op.create_unique_constraint('uq_user_google_id', ['google_id'])  # Add a name for the unique constraint

def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_google_id', type_='unique')  # Use the same name here
        batch_op.drop_column('google_id')