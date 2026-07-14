"""Control Plane core schema: 12 tables

Revision ID: 002
Revises: 001
Create Date: 2026-07-13
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "principals",
        sa.Column("principal_id", sa.Text, primary_key=True),
        sa.Column("principal_type", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_principals_tenant", "principals", ["tenant_id", "status"])
    op.create_index("idx_principals_type", "principals", ["principal_type"])

    op.create_table(
        "roles",
        sa.Column("role_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("permissions", JSONB, nullable=False),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "role_bindings",
        sa.Column("binding_id", sa.Text, primary_key=True),
        sa.Column("principal_id", sa.Text, sa.ForeignKey("principals.principal_id"), nullable=False),
        sa.Column("role_id", sa.Text, sa.ForeignKey("roles.role_id"), nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("principal_id", "role_id", "tenant_id"),
    )
    op.create_index("idx_role_bindings_principal", "role_bindings", ["principal_id"])

    op.create_table(
        "v2_tokens",
        sa.Column("token_id", sa.Text, primary_key=True),
        sa.Column("principal_id", sa.Text, sa.ForeignKey("principals.principal_id"), nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("scopes", JSONB, nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_v2_tokens_hash", "v2_tokens", ["token_hash"])

    op.create_table(
        "audit_log",
        sa.Column("audit_id", sa.Text, primary_key=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("principal_id", sa.Text),
        sa.Column("tenant_id", sa.Text),
        sa.Column("resource_id", sa.Text),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("result", sa.Text, nullable=False),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("request_id", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_audit_tenant_time", "audit_log", ["tenant_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_event", "audit_log", ["event_type", sa.text("created_at DESC")])

    op.create_table(
        "operations",
        sa.Column("operation_id", sa.Text, primary_key=True),
        sa.Column("op_type", sa.Text, nullable=False),
        sa.Column("target_resource", sa.Text, nullable=False),
        sa.Column("initiator_id", sa.Text, nullable=False),
        sa.Column("initiator_channel", sa.Text, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("risk_level", sa.Text, nullable=False, server_default="LOW"),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("approver_id", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("result", JSONB),
        sa.Column("failure_reason", sa.Text),
        sa.Column("audit_event_ids", JSONB, server_default="[]"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_operations_status", "operations", ["status"])
    op.create_index("idx_operations_initiator", "operations", ["initiator_id"])

    op.create_table(
        "config_revisions",
        sa.Column("revision_id", sa.Text, primary_key=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("values", JSONB, nullable=False),
        sa.Column("schema_version", sa.Text, nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("parent_revision_id", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("activated_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("idx_config_rev_scope", "config_revisions", ["scope", "is_active"])

    op.create_table(
        "config_values",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("revision_id", sa.Text, sa.ForeignKey("config_revisions.revision_id"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("effective_mode", sa.Text, nullable=False, server_default="HOT_RELOAD"),
    )

    op.create_table(
        "v2_secrets",
        sa.Column("secret_id", sa.Text, primary_key=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("rotated_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("scope", "name", "version"),
    )
    op.create_index("idx_v2_secrets_scope_name", "v2_secrets", ["scope", "name"])

    op.create_table(
        "instance_registry",
        sa.Column("instance_id", sa.Text, primary_key=True),
        sa.Column("service_type", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("capabilities", JSONB, server_default="[]"),
        sa.Column("active_revision_id", sa.Text),
        sa.Column("last_heartbeat", sa.TIMESTAMP(timezone=True)),
        sa.Column("health_status", sa.Text, nullable=False, server_default="unknown"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_instances_service", "instance_registry", ["service_type"])

    op.create_table(
        "outbox",
        sa.Column("event_id", sa.Text, primary_key=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("aggregate_id", sa.Text, nullable=False),
        sa.Column("aggregate_type", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("correlation_id", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="5"),
        sa.Column("next_retry_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("idx_outbox_pending", "outbox", ["status", "next_retry_at"])

    op.execute("""
        INSERT INTO roles (role_id, name, permissions, is_builtin) VALUES
        ('role_platform_admin', 'platform_admin',
         '["asset:create","asset:read","asset:update","asset:delete","knowledge:ingest","knowledge:search","knowledge:reindex","skill:register","skill:publish","skill:execute","skill:revoke","memory:add","memory:read","memory:update","memory:delete","memory:clear","job:submit","job:read","job:cancel","job:retry","model:read","model:configure","model:use","secret:use","secret:rotate","operation:request","operation:approve","config:read","config:write","config:activate","audit:read"]',
         true),
        ('role_tenant_admin', 'tenant_admin',
         '["asset:create","asset:read","asset:update","asset:delete","knowledge:ingest","knowledge:search","knowledge:reindex","skill:register","skill:publish","skill:execute","skill:revoke","memory:add","memory:read","memory:update","memory:delete","memory:clear","job:submit","job:read","job:cancel","job:retry","model:read","model:use","secret:use","secret:rotate","operation:request","config:read","audit:read"]',
         true),
        ('role_agent', 'agent',
         '["asset:read","knowledge:ingest","knowledge:search","skill:read","skill:execute","memory:add","memory:read","memory:update","memory:delete","memory:clear","job:submit","job:read","job:cancel","job:retry","model:use"]',
         true),
        ('role_steward', 'steward',
         '["asset:read","knowledge:search","skill:read","memory:read","job:read","model:read","config:read","audit:read","operation:request"]',
         true),
        ('role_readonly', 'readonly',
         '["asset:read","knowledge:search","skill:read","memory:read","job:read","model:read","config:read","audit:read"]',
         true)
    """)

    op.execute("""
        INSERT INTO tenants (tenant_id, name, status)
        VALUES ('ten_default', 'default', 'active')
        ON CONFLICT (tenant_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("instance_registry")
    op.drop_table("v2_secrets")
    op.drop_table("config_values")
    op.drop_table("config_revisions")
    op.drop_table("operations")
    op.drop_table("audit_log")
    op.drop_table("v2_tokens")
    op.drop_table("role_bindings")
    op.drop_table("roles")
    op.drop_table("principals")
