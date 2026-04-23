"""add_bot_dm_cache

Revision ID: 20260423_0019
Revises: 0018_pending_notifications_dlq
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0019_bot_dm_cache'
down_revision: Union[str, None] = '0018_pending_notifications_dlq'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bot_dm_cache',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_mxid', sa.String(), nullable=False),
        sa.Column('room_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_mxid')
    )
    op.create_index(op.f('ix_bot_dm_cache_user_mxid'), 'bot_dm_cache', ['user_mxid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_bot_dm_cache_user_mxid'), table_name='bot_dm_cache')
    op.drop_table('bot_dm_cache')
