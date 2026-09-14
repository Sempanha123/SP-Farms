"""Add content library schema for media assets, templates, hashtags, and content items.

Revision ID: 0011_content_library
Revises: 0010_audit_events
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_content_library"
down_revision: str | None = "0010_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=512), nullable=True),
        sa.Column("folder", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="0"),
        # Metadata columns
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("aspect_ratio", sa.String(length=20), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_hash", "media_assets", ["sha256_hash"])
    op.create_index("ix_media_assets_folder", "media_assets", ["folder"])
    op.create_index("ix_media_assets_media_type", "media_assets", ["media_type"])
    op.create_index("ix_media_assets_favorite", "media_assets", ["is_favorite"])
    op.create_index("ix_media_assets_archived", "media_assets", ["is_archived"])

    op.create_table(
        "caption_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_caption_templates_name", "caption_templates", ["name"])

    op.create_table(
        "hashtag_sets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("hashtags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="general"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hashtag_sets_category", "hashtag_sets", ["category"])

    op.create_table(
        "content_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_asset_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("hashtag_set_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("caption_template_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("folder", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_items_status", "content_items", ["status"])
    op.create_index("ix_content_items_folder", "content_items", ["folder"])


def downgrade() -> None:
    op.drop_index("ix_content_items_folder", table_name="content_items")
    op.drop_index("ix_content_items_status", table_name="content_items")
    op.drop_table("content_items")

    op.drop_index("ix_hashtag_sets_category", table_name="hashtag_sets")
    op.drop_table("hashtag_sets")

    op.drop_index("ix_caption_templates_name", table_name="caption_templates")
    op.drop_table("caption_templates")

    op.drop_index("ix_media_assets_archived", table_name="media_assets")
    op.drop_index("ix_media_assets_favorite", table_name="media_assets")
    op.drop_index("ix_media_assets_media_type", table_name="media_assets")
    op.drop_index("ix_media_assets_folder", table_name="media_assets")
    op.drop_index("ix_media_assets_hash", table_name="media_assets")
    op.drop_table("media_assets")
