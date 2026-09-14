"""Add QA profiles, targets, assignments, and audits."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_qa_profiles"
down_revision: str | None = "0004_device_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILE_TEXT_COLUMNS = (
    "manufacturer",
    "model",
    "market_name",
    "product",
    "hardware",
    "board",
    "bootloader",
    "build_fingerprint",
    "test_android_id",
    "test_serial_number",
    "test_imei",
    "test_meid",
    "test_gsf_id",
    "test_advertising_id",
    "test_mac",
    "test_bluetooth_mac",
    "test_wifi_ssid",
    "test_wifi_bssid",
    "test_network_generation",
    "test_imsi",
    "test_sim_id",
    "test_mobile_number",
    "test_esim_eid",
    "test_sim_operator",
    "test_sim_operator_name",
    "test_sim_country_iso",
)


def _entity_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade() -> None:
    profile_columns = [
        sa.Column("profile_name", sa.String(length=100), nullable=False),
        *[
            sa.Column(
                name,
                sa.Text() if name == "build_fingerprint" else sa.String(255),
                nullable=False,
            )
            for name in _PROFILE_TEXT_COLUMNS
        ],
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        *_entity_columns(),
    ]
    op.create_table("qa_profiles", *profile_columns)
    op.create_table(
        "qa_target_packages",
        sa.Column("package_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("ownership_note", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_profile_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["test_profile_id"], ["qa_profiles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("package_id"),
    )
    op.create_table(
        "qa_device_assignments",
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["profile_id"], ["qa_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ux_qa_device_assignments_identity",
        "qa_device_assignments",
        ["provider", "external_id"],
        unique=True,
    )
    op.create_table(
        "qa_profile_audits",
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("package_id", sa.String(length=255), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=True),
        sa.Column("result", sa.String(length=100), nullable=False),
        *_entity_columns(),
    )


def downgrade() -> None:
    op.drop_table("qa_profile_audits")
    op.drop_index(
        "ux_qa_device_assignments_identity",
        table_name="qa_device_assignments",
    )
    op.drop_table("qa_device_assignments")
    op.drop_table("qa_target_packages")
    op.drop_table("qa_profiles")
