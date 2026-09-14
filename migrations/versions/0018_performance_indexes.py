"""Add performance indexes for accounts, jobs, and media assets.

Revision ID: 0018_performance_indexes
Revises: 0017_device_reliability
Create Date: 2026-03-30
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_performance_indexes"
down_revision: str | None = "0017_device_reliability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_accounts_display_name",
        "accounts",
        ["display_name"],
    )
    op.create_index(
        "ix_accounts_status",
        "accounts",
        ["status"],
    )
    op.create_index(
        "ix_accounts_category_id",
        "accounts",
        ["category_id"],
    )
    op.create_index(
        "ix_jobs_state_created",
        "jobs",
        ["state", "created_at"],
    )
    op.create_index(
        "ix_media_assets_type_archived",
        "media_assets",
        ["media_type", "is_archived"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_assets_type_archived", table_name="media_assets")
    op.drop_index("ix_jobs_state_created", table_name="jobs")
    op.drop_index("ix_accounts_category_id", table_name="accounts")
    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_accounts_display_name", table_name="accounts")
