"""create device operational events table for device reliability analytics

Revision ID: 0017_device_reliability
Revises: 0016_analytics_snapshots
Create Date: 2026-03-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_device_reliability"
down_revision: str | None = "0016_analytics_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_operational_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("device_key", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False, default=0.0),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_device_operational_events_device_key",
        "device_operational_events",
        ["device_key"],
    )
    op.create_index(
        "ix_device_operational_events_provider",
        "device_operational_events",
        ["provider"],
    )
    op.create_index(
        "ix_device_operational_events_event_type",
        "device_operational_events",
        ["event_type"],
    )
    op.create_index(
        "ix_device_operational_events_created_at",
        "device_operational_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_operational_events_created_at",
        table_name="device_operational_events",
    )
    op.drop_index(
        "ix_device_operational_events_event_type",
        table_name="device_operational_events",
    )
    op.drop_index(
        "ix_device_operational_events_provider",
        table_name="device_operational_events",
    )
    op.drop_index(
        "ix_device_operational_events_device_key",
        table_name="device_operational_events",
    )
    op.drop_table("device_operational_events")
