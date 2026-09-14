"""Add facebook pages and groups schema.

Revision ID: 0009_pages_and_groups
Revises: 0008_device_pool_and_snapshots
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_pages_and_groups"
down_revision: str | None = "0008_device_pool_and_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facebook_pages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("page_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("tasks", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("access_token_ref", sa.String(length=36), nullable=True),
        sa.Column("can_publish", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("followers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("likes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("health", sa.String(length=50), nullable=False, server_default="healthy"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "page_id", name="uq_facebook_pages_account_page"),
    )
    op.create_index(
        "ix_facebook_pages_account_id",
        "facebook_pages",
        ["account_id"],
    )
    op.create_index(
        "ix_facebook_pages_page_id",
        "facebook_pages",
        ["page_id"],
    )

    op.create_table(
        "facebook_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("privacy", sa.String(length=50), nullable=False, server_default="PUBLIC"),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="MEMBER"),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("can_post", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("health", sa.String(length=50), nullable=False, server_default="healthy"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "group_id", name="uq_facebook_groups_account_group"),
    )
    op.create_index(
        "ix_facebook_groups_account_id",
        "facebook_groups",
        ["account_id"],
    )
    op.create_index(
        "ix_facebook_groups_group_id",
        "facebook_groups",
        ["group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_facebook_groups_group_id", table_name="facebook_groups")
    op.drop_index("ix_facebook_groups_account_id", table_name="facebook_groups")
    op.drop_table("facebook_groups")

    op.drop_index("ix_facebook_pages_page_id", table_name="facebook_pages")
    op.drop_index("ix_facebook_pages_account_id", table_name="facebook_pages")
    op.drop_table("facebook_pages")
