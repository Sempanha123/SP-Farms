"""Add account device profiles and restore bindings.

Revision ID: 0007_account_device_profiles_and_restore
Revises: 0006_accounts
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_account_device_profiles_and_restore"
down_revision: str | None = "0006_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "device_profiles",
        sa.Column("friendly_name", sa.String(length=100), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("emulator_instance", sa.String(length=100), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("adb_serial", sa.String(length=100), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("android_version", sa.String(length=50), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("model", sa.String(length=100), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("resolution", sa.String(length=50), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("dpi", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_profiles",
        sa.Column("language", sa.String(length=50), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("locale", sa.String(length=50), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("timezone", sa.String(length=100), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "device_profiles",
        sa.Column("keyboard_config", sa.String(length=100), nullable=False, server_default=""),
    )
    op.add_column(
        "device_profiles",
        sa.Column("app_versions", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "device_profiles",
        sa.Column("preferred_app", sa.String(length=30), nullable=False, server_default="browser"),
    )
    op.add_column(
        "device_profiles",
        sa.Column("network_profile_ref", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "device_profiles",
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "account_device_bindings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("device_profile_id", sa.String(length=36), nullable=False),
        sa.Column("preferred_app", sa.String(length=30), nullable=False, server_default="browser"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_profile_id"], ["device_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
    )


def downgrade() -> None:
    op.drop_table("account_device_bindings")
    with op.batch_alter_table("device_profiles") as batch_op:
        batch_op.drop_column("last_heartbeat")
        batch_op.drop_column("network_profile_ref")
        batch_op.drop_column("preferred_app")
        batch_op.drop_column("app_versions")
        batch_op.drop_column("keyboard_config")
        batch_op.drop_column("timezone")
        batch_op.drop_column("locale")
        batch_op.drop_column("language")
        batch_op.drop_column("dpi")
        batch_op.drop_column("resolution")
        batch_op.drop_column("model")
        batch_op.drop_column("android_version")
        batch_op.drop_column("adb_serial")
        batch_op.drop_column("emulator_instance")
        batch_op.drop_column("friendly_name")
