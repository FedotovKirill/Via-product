"""bot_ops_audit: поля для CRUD-аудита панели

Revision ID: 0014_bot_ops_audit_crud
Revises: 0013_bot_user_timezone
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_bot_ops_audit_crud"
down_revision: str | None = "0013_bot_user_timezone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bot_ops_audit", sa.Column("entity_type", sa.String(length=64), nullable=True))
    op.add_column("bot_ops_audit", sa.Column("entity_id", sa.BigInteger(), nullable=True))
    op.add_column("bot_ops_audit", sa.Column("crud_action", sa.String(length=32), nullable=True))
    op.add_column(
        "bot_ops_audit",
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_bot_ops_audit_entity_type_entity_id",
        "bot_ops_audit",
        ["entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bot_ops_audit_entity_type_entity_id", table_name="bot_ops_audit")
    op.drop_column("bot_ops_audit", "details_json")
    op.drop_column("bot_ops_audit", "crud_action")
    op.drop_column("bot_ops_audit", "entity_id")
    op.drop_column("bot_ops_audit", "entity_type")
