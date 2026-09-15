"""Add campaign management schema for multi-destination publishing campaigns and targets.

Revision ID: 0012_campaign_management
Revises: 0011_content_library
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_campaign_management"
down_revision: str | None = "0011_content_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_item_id", sa.String(length=36), nullable=True),
        sa.Column("post_type", sa.String(length=20), nullable=False, server_default="FEED"),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_asset_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("schedule_policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("approval_policy", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("retry_policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_status", "campaigns", ["status"])
    op.create_index("ix_campaigns_title", "campaigns", ["title"])
    op.create_index("ix_campaigns_post_type", "campaigns", ["post_type"])

    op.create_table(
        "campaign_targets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("destination_type", sa.String(length=20), nullable=False),
        sa.Column("destination_id", sa.String(length=100), nullable=False),
        sa.Column("destination_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_post_id", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_targets_campaign_id", "campaign_targets", ["campaign_id"])
    op.create_index("ix_campaign_targets_status", "campaign_targets", ["status"])


def downgrade() -> None:
    op.drop_index("ix_campaign_targets_status", table_name="campaign_targets")
    op.drop_index("ix_campaign_targets_campaign_id", table_name="campaign_targets")
    op.drop_table("campaign_targets")

    op.drop_index("ix_campaigns_post_type", table_name="campaigns")
    op.drop_index("ix_campaigns_title", table_name="campaigns")
    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_table("campaigns")
