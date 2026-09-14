"""Add persistent device profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_device_profiles"
down_revision: str | None = "0003_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_profiles",
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_device_profiles_identity",
        "device_profiles",
        ["provider", "external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_device_profiles_identity", table_name="device_profiles")
    op.drop_table("device_profiles")
