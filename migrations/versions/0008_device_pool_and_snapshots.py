"""Add device pool locks, restore policies, and lightweight workspace snapshots.

Revision ID: 0008_device_pool_and_snapshots
Revises: 0007_account_device_profiles_and_restore
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_device_pool_and_snapshots"
down_revision: str | None = "0007_account_device_profiles_and_restore"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_workspace_locks",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("device_key", sa.String(length=255), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_index(
        "ix_account_workspace_locks_device_key",
        "account_workspace_locks",
        ["device_key"],
    )
    op.create_index(
        "ix_account_workspace_locks_expires_at",
        "account_workspace_locks",
        ["expires_at"],
    )

    op.create_table(
        "account_workspace_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False, server_default="1.0"),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("device_profile_id", sa.String(length=36), nullable=True),
        sa.Column("preferred_app", sa.String(length=30), nullable=False, server_default="browser"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_workspace_snapshots_account_id",
        "account_workspace_snapshots",
        ["account_id"],
    )

    op.create_table(
        "device_pool_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "policy",
            sa.String(length=50),
            nullable=False,
            server_default="bound_device_first",
        ),
        sa.Column(
            "preferred_provider_order",
            sa.String(length=255),
            nullable=False,
            server_default="ldplayer,mumu,physical",
        ),
        sa.Column("allow_fallback", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("max_concurrent_restores", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("device_pool_policies")
    op.drop_index(
        "ix_account_workspace_snapshots_account_id",
        table_name="account_workspace_snapshots",
    )
    op.drop_table("account_workspace_snapshots")
    op.drop_index(
        "ix_account_workspace_locks_expires_at",
        table_name="account_workspace_locks",
    )
    op.drop_index(
        "ix_account_workspace_locks_device_key",
        table_name="account_workspace_locks",
    )
    op.drop_table("account_workspace_locks")
