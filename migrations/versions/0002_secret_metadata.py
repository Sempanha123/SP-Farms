"""Add secret reference metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_secret_metadata"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "secret_metadata",
        sa.Column("secret_type", sa.String(length=50), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=False),
        sa.Column("vault_ref", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vault_ref"),
    )
    op.create_index("ix_secret_metadata_owner_id", "secret_metadata", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_secret_metadata_owner_id", table_name="secret_metadata")
    op.drop_table("secret_metadata")
