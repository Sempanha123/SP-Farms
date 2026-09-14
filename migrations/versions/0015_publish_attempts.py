"""create publish attempts table

Revision ID: 0015_publish_attempts
Revises: 0014_approval_queue
Create Date: 2026-03-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_publish_attempts"
down_revision: str | None = "0014_approval_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publish_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("destination_type", sa.String(length=32), nullable=False),
        sa.Column("destination_id", sa.String(length=64), nullable=False),
        sa.Column("destination_name", sa.String(length=255), nullable=False),
        sa.Column("post_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("method_used", sa.String(length=16), nullable=False, default="api"),
        sa.Column("scheduled_item_id", sa.String(length=36), nullable=True),
        sa.Column("campaign_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("external_post_id", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_retryable", sa.Boolean(), nullable=False, default=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("duration_ms", sa.Integer(), nullable=False, default=0),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_publish_attempts_destination_id",
        "publish_attempts",
        ["destination_id"],
    )
    op.create_index(
        "ix_publish_attempts_campaign_id",
        "publish_attempts",
        ["campaign_id"],
    )
    op.create_index(
        "ix_publish_attempts_status",
        "publish_attempts",
        ["status"],
    )
    op.create_index(
        "ix_publish_attempts_idempotency_key",
        "publish_attempts",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_publish_attempts_idempotency_key", table_name="publish_attempts")
    op.drop_index("ix_publish_attempts_status", table_name="publish_attempts")
    op.drop_index("ix_publish_attempts_campaign_id", table_name="publish_attempts")
    op.drop_index("ix_publish_attempts_destination_id", table_name="publish_attempts")
    op.drop_table("publish_attempts")
