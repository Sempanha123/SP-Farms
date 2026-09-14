"""Add approval requests and policy rules schema for human-in-the-loop review.

Revision ID: 0014_approval_queue
Revises: 0013_scheduler_and_calendar
Create Date: 2026-03-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_approval_queue"
down_revision: str | None = "0013_scheduler_and_calendar"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("campaign_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approval_requests_action_type", "approval_requests", ["action_type"])
    op.create_index("ix_approval_requests_job_id", "approval_requests", ["job_id"])
    op.create_index("ix_approval_requests_campaign_id", "approval_requests", ["campaign_id"])

    op.create_table(
        "approval_policy_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_pattern", sa.String(length=255), nullable=False, server_default="*"),
        sa.Column("require_reason", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_pending_hours", sa.Integer(), nullable=False, server_default="48"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("approval_policy_rules")
    op.drop_table("approval_requests")
