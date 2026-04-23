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
    # redmine_statuses already created in 0017_reference_data

    # Create redmine_versions if not exists
    op.create_table(
        "redmine_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("redmine_version_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("redmine_version_id"),
    )
    op.create_index(op.f("ix_redmine_versions_is_active"), "redmine_versions", ["is_active"], unique=False)
    op.create_index(op.f("ix_redmine_versions_redmine_version_id"), "redmine_versions", ["redmine_version_id"], unique=True)

    # Create redmine_priorities if not exists
    op.create_table(
        "redmine_priorities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("redmine_priority_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("redmine_priority_id"),
    )
    op.create_index(op.f("ix_redmine_priorities_is_active"), "redmine_priorities", ["is_active"], unique=False)
    op.create_index(op.f("ix_redmine_priorities_redmine_priority_id"), "redmine_priorities", ["redmine_priority_id"], unique=True)

    # Add columns to bot_users if not exists
    op.add_column("bot_users", sa.Column("versions", sa.JSON(), server_default='["all"]'))
    op.add_column("bot_users", sa.Column("priorities", sa.JSON(), server_default='["all"]'))

    # Add columns to support_groups if not exists
    op.add_column("support_groups", sa.Column("versions", sa.JSON(), server_default='["all"]'))
    op.add_column("support_groups", sa.Column("priorities", sa.JSON(), server_default='["all"]'))


def downgrade() -> None:
    op.drop_column("support_groups", "priorities")
    op.drop_column("support_groups", "versions")
    op.drop_column("bot_users", "priorities")
    op.drop_column("bot_users", "versions")
    op.drop_index(op.f("ix_redmine_priorities_redmine_priority_id"), table_name="redmine_priorities")
    op.drop_index(op.f("ix_redmine_priorities_is_active"), table_name="redmine_priorities")
    op.drop_table("redmine_priorities")
    op.drop_index(op.f("ix_redmine_versions_redmine_version_id"), table_name="redmine_versions")
    op.drop_index(op.f("ix_redmine_versions_is_active"), table_name="redmine_versions")
    op.drop_table("redmine_versions")
