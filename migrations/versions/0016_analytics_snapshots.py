"""create analytics snapshots table

Revision ID: 0016_analytics_snapshots
Revises: 0015_publish_attempts
Create Date: 2026-03-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_analytics_snapshots"
down_revision: str | None = "0015_publish_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("external_post_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("destination_id", sa.String(length=64), nullable=False),
        sa.Column("destination_name", sa.String(length=255), nullable=False),
        sa.Column("post_type", sa.String(length=32), nullable=False),
        sa.Column("publish_attempt_id", sa.String(length=36), nullable=True),
        sa.Column("likes_count", sa.Integer(), nullable=False, default=0),
        sa.Column("comments_count", sa.Integer(), nullable=False, default=0),
        sa.Column("shares_count", sa.Integer(), nullable=False, default=0),
        sa.Column("views_count", sa.Integer(), nullable=False, default=0),
        sa.Column("impressions_count", sa.Integer(), nullable=False, default=0),
        sa.Column("reach_count", sa.Integer(), nullable=False, default=0),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_analytics_snapshots_external_post_id",
        "analytics_snapshots",
        ["external_post_id"],
    )
    op.create_index(
        "ix_analytics_snapshots_destination_id",
        "analytics_snapshots",
        ["destination_id"],
    )
    op.create_index(
        "ix_analytics_snapshots_synced_at",
        "analytics_snapshots",
        ["synced_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_snapshots_synced_at", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_destination_id", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_external_post_id", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")
