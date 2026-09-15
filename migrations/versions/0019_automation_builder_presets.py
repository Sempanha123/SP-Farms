"""Add automation presets and steps tables for the Automation Builder.

Revision ID: 0019_automation_builder_presets
Revises: 0018_performance_indexes
Create Date: 2026-03-30
"""

from collections.abc import Sequence
import json
import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0019_automation_builder_presets"
down_revision: str | None = "0018_performance_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_presets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_rules_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_built_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "automation_preset_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "preset_id",
            sa.String(length=36),
            sa.ForeignKey("automation_presets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("step_order", sa.Integer(), nullable=False, default=0),
        sa.Column("configuration_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("continue_on_error", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retry_policy", sa.String(length=32), nullable=False, server_default="no_retry"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="120"),
    )

    op.create_index(
        "ix_automation_preset_steps_preset_order",
        "automation_preset_steps",
        ["preset_id", "step_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_preset_steps_preset_order", table_name="automation_preset_steps")
    op.drop_table("automation_preset_steps")
    op.drop_table("automation_presets")
