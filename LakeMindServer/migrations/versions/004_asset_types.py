"""Asset type metadata: knowledge_meta + skill_meta + memory_meta

Revision ID: 004
Revises: 003
Create Date: 2026-07-13
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "knowledge_meta",
        sa.Column("asset_id", sa.Text, sa.ForeignKey("assets.asset_id"), primary_key=True),
        sa.Column("kb_name", sa.Text, nullable=False),
        sa.Column("parser_version", sa.Text),
        sa.Column("embedding_space_id", sa.Text),
        sa.Column("chunk_config", JSONB, server_default="{}"),
        sa.Column("index_status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("concept_count", sa.Integer, server_default="0"),
        sa.Column("total_chunks", sa.Integer, server_default="0"),
    )

    op.create_table(
        "skill_meta",
        sa.Column("asset_id", sa.Text, sa.ForeignKey("assets.asset_id"), primary_key=True),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("code_checksum", sa.Text, nullable=False),
        sa.Column("entry_point", sa.Text, nullable=False),
        sa.Column("input_schema", JSONB, nullable=False),
        sa.Column("output_schema", JSONB, nullable=False),
        sa.Column("dependencies", JSONB, server_default="[]"),
        sa.Column("permissions", JSONB, server_default="[]"),
        sa.Column("model_profiles", JSONB, server_default="[]"),
        sa.Column("secret_declarations", JSONB, server_default="[]"),
        sa.Column("resource_needs", JSONB, server_default="{}"),
        sa.Column("network_needs", JSONB, server_default="{}"),
        sa.Column("trust_level", sa.Text, nullable=False, server_default="untrusted"),
        sa.Column("publish_status", sa.Text, nullable=False, server_default="DRAFT"),
        sa.Column("published_by", sa.Text),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "memory_meta",
        sa.Column("asset_id", sa.Text, sa.ForeignKey("assets.asset_id"), primary_key=True),
        sa.Column("memory_type", sa.Text, nullable=False),
        sa.Column("subject", sa.Text),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("importance", sa.Float, server_default="0.5"),
        sa.Column("retention", sa.Text, server_default="permanent"),
        sa.Column("expiration", sa.TIMESTAMP(timezone=True)),
        sa.Column("access_scope", sa.Text, server_default="private"),
        sa.Column("embedding_status", sa.Text, server_default="PENDING"),
        sa.Column("consolidation_status", sa.Text, server_default="none"),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("memory_meta")
    op.drop_table("skill_meta")
    op.drop_table("knowledge_meta")
