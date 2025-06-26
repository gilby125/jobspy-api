"""Add repost_count, is_evergreen, evergreen_score to job_metrics

Revision ID: 1b2c3d4e5f6a
Revises: 0a6e5a8ae32e
Create Date: 2025-07-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1b2c3d4e5f6a'
down_revision: Union[str, None] = '0a6e5a8ae32e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('job_metrics', sa.Column('repost_count', sa.Integer(), nullable=False, server_default=sa.text('0')))
    op.add_column('job_metrics', sa.Column('is_evergreen', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('job_metrics', sa.Column('evergreen_score', sa.Integer(), nullable=False, server_default=sa.text('0')))

    # Add indexes if not already added via the model for new columns
    # For SQLAlchemy 1.4+ with Alembic 1.7+, explicit index creation might not be needed if `index=True` is on the Column
    # but good to be explicit if older versions or specific naming is desired.
    # Assuming `index=True` in the model handles index creation correctly.
    # If not, uncomment and adjust these:
    # op.create_index(op.f('ix_job_metrics_repost_count'), 'job_metrics', ['repost_count'], unique=False)
    # op.create_index(op.f('ix_job_metrics_is_evergreen'), 'job_metrics', ['is_evergreen'], unique=False)
    # op.create_index(op.f('ix_job_metrics_evergreen_score'), 'job_metrics', ['evergreen_score'], unique=False)

def downgrade() -> None:
    # op.drop_index(op.f('ix_job_metrics_evergreen_score'), table_name='job_metrics') # If created explicitly
    # op.drop_index(op.f('ix_job_metrics_is_evergreen'), table_name='job_metrics') # If created explicitly
    # op.drop_index(op.f('ix_job_metrics_repost_count'), table_name='job_metrics') # If created explicitly

    op.drop_column('job_metrics', 'evergreen_score')
    op.drop_column('job_metrics', 'is_evergreen')
    op.drop_column('job_metrics', 'repost_count')
