"""Asset Core: assets + asset_bindings + asset_lineage + reconciler_state

Revision ID: 003
Revises: 002
Create Date: 2026-07-13
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("asset_type", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False, server_default="1.0.0"),
        sa.Column("schema_version", sa.Text, nullable=False, server_default="1"),
        sa.Column("status", sa.Text, nullable=False, server_default="DRAFT"),
        sa.Column("owner_id", sa.Text, nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("visibility", sa.Text, nullable=False, server_default="private"),
        sa.Column("classification", sa.Text),
        sa.Column("source_type", sa.Text),
        sa.Column("source_uri", sa.Text),
        sa.Column("checksum", sa.Text),
        sa.Column("retention_policy", JSONB, server_default="{}"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("idx_assets_tenant_type", "assets", ["tenant_id", "asset_type", "status"])
    op.create_index("idx_assets_owner", "assets", ["owner_id", "status"])
    op.create_index("idx_assets_name_version", "assets", ["tenant_id", "asset_type", "name", "version"])

    op.create_table(
        "asset_bindings",
        sa.Column("binding_id", sa.Text, primary_key=True),
        sa.Column("asset_id", sa.Text, sa.ForeignKey("assets.asset_id"), nullable=False),
        sa.Column("binding_type", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("physical_uri", sa.Text, nullable=False),
        sa.Column("binding_version", sa.Text, nullable=False, server_default="1"),
        sa.Column("checksum", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("last_error", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bindings_asset", "asset_bindings", ["asset_id", "status"])

    op.create_table(
        "asset_lineage",
        sa.Column("lineage_id", sa.Text, primary_key=True),
        sa.Column("asset_id", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("source_version", sa.Text),
        sa.Column("relation", sa.Text, nullable=False),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_lineage_asset", "asset_lineage", ["asset_id"])
    op.create_index("idx_lineage_source", "asset_lineage", ["source_type", "source_id"])

    op.create_table(
        "reconciler_state",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("scan_category", sa.Text, nullable=False),
        sa.Column("resource_id", sa.Text, nullable=False),
        sa.Column("drift_type", sa.Text, nullable=False),
        sa.Column("drift_details", JSONB, server_default="{}"),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("resolution_action", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("reconciler_state")
    op.drop_table("asset_lineage")
    op.drop_table("asset_bindings")
    op.drop_table("assets")
