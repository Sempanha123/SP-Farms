"""Add rich account metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_accounts"
down_revision: str | None = "0005_qa_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _entity_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade() -> None:
    op.create_table(
        "account_categories",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=30), nullable=False),
        *_entity_columns(),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "account_tags",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=30), nullable=False),
        *_entity_columns(),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "accounts",
        sa.Column("avatar_ref", sa.String(length=500), nullable=True),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("platform_uid", sa.String(length=255), nullable=False),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=30), nullable=True),
        sa.Column("primary_email", sa.String(length=320), nullable=False),
        sa.Column("recovery_email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("locale", sa.String(length=50), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("account_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("preferred_app", sa.String(length=30), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("group_count", sa.Integer(), nullable=False),
        sa.Column("permission_state", sa.String(length=30), nullable=False),
        sa.Column("security_state", sa.String(length=30), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["category_id"], ["account_categories.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("platform_uid"),
    )
    op.create_table(
        "account_tag_assignments",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["account_tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id", "tag_id"),
    )
    op.create_table(
        "account_device_assignments",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id"),
    )
    op.create_index(
        "ux_account_device_assignments_device",
        "account_device_assignments",
        ["provider", "external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_account_device_assignments_device",
        table_name="account_device_assignments",
    )
    op.drop_table("account_device_assignments")
    op.drop_table("account_tag_assignments")
    op.drop_table("accounts")
    op.drop_table("account_tags")
    op.drop_table("account_categories")
