"""Phase 1A Core: metrics_series, event_stream, notifications, search_projections, unified scope

Revision ID: 009
Revises: 008
Create Date: 2026-07-16
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

JSONB = sa.dialects.postgresql.JSONB
UUID = sa.dialects.postgresql.UUID


def upgrade() -> None:
    op.create_table(
        "metrics_series",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("scope_type", sa.Text, nullable=False, server_default="TENANT"),
        sa.Column("scope_id", sa.Text, nullable=True),
        sa.Column("metric_name", sa.Text, nullable=False),
        sa.Column("labels", JSONB, nullable=False, server_default="{}"),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("retention_until", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("idx_metrics_name_observed", "metrics_series", ["metric_name", sa.text("observed_at DESC")])
    op.create_index("idx_metrics_scope", "metrics_series", ["scope_type", "scope_id", "observed_at"])
    op.execute("CREATE INDEX idx_metrics_labels ON metrics_series USING GIN (labels)")
    op.execute("CREATE INDEX idx_metrics_observed_brin ON metrics_series USING BRIN (observed_at)")

    op.create_table(
        "event_stream",
        sa.Column("event_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("scope_type", sa.Text, nullable=False, server_default="TENANT"),
        sa.Column("scope_id", sa.Text, nullable=True),
        sa.Column("resource_type", sa.Text, nullable=True),
        sa.Column("resource_id", sa.Text, nullable=True),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("retention_until", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("publish_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_publish_error", sa.Text, nullable=True),
    )
    op.execute("CREATE SEQUENCE IF NOT EXISTS event_stream_sequence_seq")
    op.execute("ALTER TABLE event_stream ALTER COLUMN sequence SET DEFAULT nextval('event_stream_sequence_seq')")
    op.create_index("idx_event_stream_seq", "event_stream", ["sequence"])
    op.create_index("idx_event_stream_unpublished", "event_stream", ["published_at", "sequence"])
    op.create_index("idx_event_stream_type", "event_stream", ["event_type", sa.text("created_at DESC")])
    op.create_index("idx_event_stream_scope", "event_stream", ["scope_type", "scope_id", "sequence"])
    op.create_index("idx_event_stream_resource", "event_stream", ["resource_type", "resource_id", "sequence"])

    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.Text, primary_key=True),
        sa.Column("principal_id", sa.Text, nullable=True),
        sa.Column("scope_type", sa.Text, nullable=False, server_default="TENANT"),
        sa.Column("scope_id", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False, server_default="info"),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("resource_type", sa.Text, nullable=True),
        sa.Column("resource_id", sa.Text, nullable=True),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_notifications_principal_unread", "notifications", ["principal_id", "read", sa.text("created_at DESC")])
    op.create_index("idx_notifications_scope", "notifications", ["scope_type", "scope_id", sa.text("created_at DESC")])

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "search_projections",
        sa.Column("object_type", sa.Text, nullable=False),
        sa.Column("object_id", sa.Text, nullable=False),
        sa.Column("scope_type", sa.Text, nullable=False, server_default="TENANT"),
        sa.Column("scope_id", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("subtitle", sa.Text, nullable=True),
        sa.Column("keywords", sa.Text, nullable=True),
        sa.Column("visibility", sa.Text, nullable=False, server_default="tenant"),
        sa.Column("owner_id", sa.Text, nullable=True),
        sa.Column("tsv", sa.dialects.postgresql.TSVECTOR, nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("object_type", "object_id"),
    )
    op.execute("CREATE INDEX idx_search_tsv ON search_projections USING GIN (tsv)")
    op.execute("CREATE INDEX idx_search_title_trgm ON search_projections USING GIN (title gin_trgm_ops)")
    op.create_index("idx_search_scope", "search_projections", ["scope_type", "scope_id", "object_type"])

    op.add_column("config_revisions", sa.Column("scope_type", sa.Text, nullable=False, server_default="TENANT"))
    op.add_column("config_revisions", sa.Column("scope_id_new", sa.Text, nullable=True))
    op.execute("UPDATE config_revisions SET scope_id_new = regexp_replace(scope, '^tenant:', '') WHERE scope LIKE 'tenant:%'")
    op.execute("UPDATE config_revisions SET scope_type = 'PLATFORM', scope_id_new = NULL WHERE scope NOT LIKE 'tenant:%'")
    op.create_index("idx_config_rev_scope", "config_revisions", ["scope_type", "scope_id_new"])

    op.add_column("operations", sa.Column("scope_type", sa.Text, nullable=False, server_default="TENANT"))
    op.add_column("operations", sa.Column("scope_id_new", sa.Text, nullable=True))

    op.add_column("audit_log", sa.Column("scope_type", sa.Text, nullable=False, server_default="TENANT"))
    op.add_column("audit_log", sa.Column("scope_id_new", sa.Text, nullable=True))
    op.execute("UPDATE audit_log SET scope_id_new = tenant_id")


def downgrade() -> None:
    op.drop_column("audit_log", "scope_id_new")
    op.drop_column("audit_log", "scope_type")
    op.drop_column("operations", "scope_id_new")
    op.drop_column("operations", "scope_type")
    op.drop_index("idx_config_rev_scope", table_name="config_revisions")
    op.drop_column("config_revisions", "scope_id_new")
    op.drop_column("config_revisions", "scope_type")
    op.drop_table("search_projections")
    op.drop_table("notifications")
    op.drop_table("event_stream")
    op.drop_table("metrics_series")
