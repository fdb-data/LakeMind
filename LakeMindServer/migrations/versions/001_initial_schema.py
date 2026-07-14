"""v0.1.0 baseline schema

Revision ID: 001
Revises:
Create Date: 2026-07-13
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TABLE IF NOT EXISTS graph_nodes (graph_name TEXT NOT NULL, node_id TEXT NOT NULL, label TEXT NOT NULL, properties JSONB DEFAULT '{}', tenant_id TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (graph_name, node_id))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_nodes_tenant ON graph_nodes (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_nodes_label ON graph_nodes (graph_name, label)")

    op.execute("CREATE TABLE IF NOT EXISTS graph_edges (graph_name TEXT NOT NULL, edge_id TEXT NOT NULL, src_id TEXT NOT NULL, dst_id TEXT NOT NULL, rel_type TEXT NOT NULL, properties JSONB DEFAULT '{}', tenant_id TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (graph_name, edge_id))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON graph_edges (graph_name, src_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_edges_dst ON graph_edges (graph_name, dst_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_edges_rel ON graph_edges (graph_name, rel_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_edges_tenant ON graph_edges (tenant_id)")

    op.execute("CREATE TABLE IF NOT EXISTS tenants (tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT now())")

    op.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id), role TEXT DEFAULT 'user', status TEXT DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT now())")

    op.execute("CREATE TABLE IF NOT EXISTS tokens (token TEXT PRIMARY KEY, agent_id TEXT NOT NULL, tenant_id TEXT NOT NULL, scopes TEXT[] DEFAULT '{}', status TEXT DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT now(), revoked_at TIMESTAMPTZ)")

    op.execute("CREATE TABLE IF NOT EXISTS asset_types (type TEXT PRIMARY KEY, definition_yaml TEXT NOT NULL, tenant_id TEXT, created_at TIMESTAMPTZ DEFAULT now())")

    op.execute("CREATE TABLE IF NOT EXISTS tenant_secrets (id UUID DEFAULT gen_random_uuid() PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE, key_name VARCHAR(100) NOT NULL, encrypted_value BYTEA NOT NULL, iv BYTEA NOT NULL, auth_tag BYTEA NOT NULL, description TEXT, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(), created_by TEXT, UNIQUE(tenant_id, key_name))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_secrets_tenant ON tenant_secrets (tenant_id)")

    op.execute("CREATE TABLE IF NOT EXISTS secret_access_log (id UUID DEFAULT gen_random_uuid() PRIMARY KEY, tenant_id TEXT NOT NULL, key_name VARCHAR(100) NOT NULL, task_id TEXT, ray_job_id TEXT, accessed_by TEXT NOT NULL, accessed_at TIMESTAMPTZ DEFAULT now())")
    op.execute("CREATE INDEX IF NOT EXISTS idx_secret_log_tenant ON secret_access_log (tenant_id, accessed_at)")

    op.execute("CREATE TABLE IF NOT EXISTS ray_jobs (job_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, agent_id TEXT NOT NULL, skill_uri TEXT NOT NULL, job_name TEXT NOT NULL, entrypoint TEXT, params JSONB DEFAULT '{}', task_id TEXT, status TEXT DEFAULT 'submitted', ray_job_id TEXT, result_uri TEXT, created_at TIMESTAMPTZ DEFAULT now(), completed_at TIMESTAMPTZ)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ray_jobs_tenant ON ray_jobs (tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ray_jobs_task ON ray_jobs (tenant_id, task_id)")

    op.execute("CREATE TABLE IF NOT EXISTS memory_records (memory_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, tenant_id TEXT NOT NULL, content TEXT NOT NULL, metadata JSONB DEFAULT '{}', embedding FLOAT[], importance FLOAT DEFAULT 0.5, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now())")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memory_agent_tenant ON memory_records (agent_id, tenant_id)")


def downgrade() -> None:
    op.drop_table("memory_records")
    op.drop_table("ray_jobs")
    op.drop_table("secret_access_log")
    op.drop_table("tenant_secrets")
    op.drop_table("asset_types")
    op.drop_table("tokens")
    op.drop_table("users")
    op.drop_table("tenants")
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
