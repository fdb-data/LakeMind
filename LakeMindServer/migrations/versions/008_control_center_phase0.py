"""Control Center Phase 0: membership, security_version, operation REJECTED, config rollout, job events, steward findings

Revision ID: 008
Revises: 007
Create Date: 2026-07-16
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    op.add_column("tenants", sa.Column("quotas", JSONB, server_default="{}"))
    op.add_column("tenants", sa.Column("allowed_models", JSONB, server_default="[]"))

    op.add_column("model_deployments", sa.Column("desired_state", sa.Text, nullable=True))
    op.add_column("model_deployments", sa.Column("test_state", sa.Text, nullable=False, server_default="UNKNOWN"))
    op.add_column("model_deployments", sa.Column("readiness_state", sa.Text, nullable=False, server_default="UNKNOWN"))
    op.execute("UPDATE model_deployments SET desired_state = CASE WHEN status = 'enabled' THEN 'ACTIVE' ELSE 'DISABLED' END")

    op.add_column("principals", sa.Column("security_version", sa.BigInteger, nullable=False, server_default="0"))
    op.add_column("v2_tokens", sa.Column("security_version", sa.BigInteger, nullable=False, server_default="0"))
    op.add_column("v2_tokens", sa.Column("jti", sa.Text, nullable=True))

    op.create_table(
        "principal_tenant_memberships",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("principal_id", sa.Text, sa.ForeignKey("principals.principal_id"), nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("role_binding_id", sa.Text, sa.ForeignKey("role_bindings.binding_id"), nullable=True),
        sa.Column("membership_status", sa.Text, nullable=False, server_default="ACTIVE"),
        sa.Column("invited_by", sa.Text, sa.ForeignKey("principals.principal_id"), nullable=True),
        sa.Column("invited_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("joined_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("principal_id", "tenant_id", name="uq_membership_principal_tenant"),
    )
    op.create_index("idx_membership_principal", "principal_tenant_memberships", ["principal_id", "membership_status"])
    op.create_index("idx_membership_tenant", "principal_tenant_memberships", ["tenant_id", "membership_status"])

    op.execute("""
        INSERT INTO principal_tenant_memberships (id, principal_id, tenant_id, membership_status, joined_at)
        SELECT 'mb_' || p.principal_id, p.principal_id, p.tenant_id, 'ACTIVE', p.created_at
        FROM principals p
        ON CONFLICT (principal_id, tenant_id) DO NOTHING
    """)

    op.add_column("config_revisions", sa.Column("rollout_status", sa.Text, nullable=True))
    op.add_column("config_revisions", sa.Column("rollout_version", sa.BigInteger, nullable=False, server_default="0"))

    op.create_table(
        "job_events",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("job_id", sa.Text, nullable=False),
        sa.Column("attempt_id", sa.Text, nullable=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("event_seq", sa.BigInteger, nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("payload", JSONB, server_default="{}"),
        sa.Column("correlation_id", sa.Text, nullable=True),
        sa.Column("cause_event_id", sa.Text, nullable=True),
    )
    op.create_index("idx_job_events_job_seq", "job_events", ["job_id", "event_seq"])
    op.create_index("idx_job_events_type", "job_events", ["event_type", sa.text("occurred_at DESC")])

    op.create_table(
        "steward_findings",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("evidence", JSONB, server_default="[]"),
        sa.Column("affected_objects", JSONB, server_default="[]"),
        sa.Column("suggested_action", sa.Text, nullable=True),
        sa.Column("confidence", sa.Text, nullable=True),
        sa.Column("fingerprint", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="OPEN"),
        sa.Column("acknowledged_by", sa.Text, nullable=True),
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("first_seen_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_findings_fingerprint_status", "steward_findings", ["fingerprint", "status"])
    op.create_index("idx_findings_status", "steward_findings", ["status", sa.text("last_seen_at DESC")])

    op.create_table(
        "tenant_provisioning_sagas",
        sa.Column("saga_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=True),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("step_name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("compensated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_saga_tenant", "tenant_provisioning_sagas", ["saga_id", "step_index"])


def downgrade() -> None:
    op.drop_table("tenant_provisioning_sagas")
    op.drop_table("steward_findings")
    op.drop_table("job_events")
    op.drop_column("config_revisions", "rollout_version")
    op.drop_column("config_revisions", "rollout_status")
    op.drop_table("principal_tenant_memberships")
    op.drop_column("v2_tokens", "jti")
    op.drop_column("v2_tokens", "security_version")
    op.drop_column("principals", "security_version")
    op.drop_column("model_deployments", "readiness_state")
    op.drop_column("model_deployments", "test_state")
    op.drop_column("model_deployments", "desired_state")
    op.drop_column("tenants", "allowed_models")
    op.drop_column("tenants", "quotas")
