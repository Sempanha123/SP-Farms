"""Add scheduler and calendar items table.

Revision ID: 0013_scheduler_and_calendar
Revises: 0012_campaign_management
Create Date: 2026-03-31 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_scheduler_and_calendar"
down_revision: str | None = "0012_campaign_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=True),
        sa.Column("content_item_id", sa.String(length=36), nullable=True),
        sa.Column("destination_type", sa.String(length=20), nullable=False),
        sa.Column("destination_id", sa.String(length=100), nullable=False),
        sa.Column("destination_name", sa.String(length=255), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("post_type", sa.String(length=20), nullable=False, server_default="FEED"),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_asset_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("timezone_name", sa.String(length=50), nullable=False, server_default="UTC"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_items_scheduled_at", "scheduled_items", ["scheduled_at"])
    op.create_index("ix_scheduled_items_status", "scheduled_items", ["status"])
    op.create_index("ix_scheduled_items_dest", "scheduled_items", ["destination_id"])
    op.create_index("ix_scheduled_items_campaign", "scheduled_items", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_items_campaign", table_name="scheduled_items")
    op.drop_index("ix_scheduled_items_dest", table_name="scheduled_items")
    op.drop_index("ix_scheduled_items_status", table_name="scheduled_items")
    op.drop_index("ix_scheduled_items_scheduled_at", table_name="scheduled_items")
    op.drop_table("scheduled_items")
