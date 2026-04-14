"""add is_active to redmine_statuses

Revision ID: a5b7003332e3
Revises: 0018_pending_notifications_dlq
Create Date: 2026-04-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5b7003332e3'
down_revision: Union[str, None] = '0018_pending_notifications_dlq'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('redmine_statuses', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.create_index(op.f('ix_redmine_statuses_is_active'), 'redmine_statuses', ['is_active'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_redmine_statuses_is_active'), table_name='redmine_statuses')
    op.drop_column('redmine_statuses', 'is_active')
