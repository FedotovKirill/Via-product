"""add redmine statuses, versions, priorities and bot columns

Revision ID: fix_all_tables
Revises: 0018_pending_notifications_dlq
Create Date: 2026-04-15 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fix_all_tables'
down_revision: Union[str, None] = '0018_pending_notifications_dlq'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # redmine_statuses, redmine_versions, redmine_priorities already created in 0017_reference_data
    # Add columns to bot_users if not exists
    op.add_column('bot_users', sa.Column('versions', sa.JSON(), server_default='["all"]'))
    op.add_column('bot_users', sa.Column('priorities', sa.JSON(), server_default='["all"]'))

    # Add columns to support_groups if not exists
    op.add_column('support_groups', sa.Column('versions', sa.JSON(), server_default='["all"]'))
    op.add_column('support_groups', sa.Column('priorities', sa.JSON(), server_default='["all"]'))


def downgrade() -> None:
    op.drop_column('support_groups', 'priorities')
    op.drop_column('support_groups', 'versions')
    op.drop_column('bot_users', 'priorities')
    op.drop_column('bot_users', 'versions')
