"""WP5: ModelServing — 5 model tables

Revision ID: 006
Revises: 005
Create Date: 2025-01-20
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE model_definitions (
        model_id         TEXT PRIMARY KEY,
        name             TEXT NOT NULL,
        model_type       TEXT NOT NULL,
        capabilities     JSONB NOT NULL,
        provider_family  TEXT NOT NULL,
        context_length   INTEGER,
        embedding_dim    INTEGER,
        modalities       JSONB DEFAULT '["text"]',
        metadata         JSONB DEFAULT '{}',
        source           TEXT DEFAULT 'manual',
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE TABLE model_deployments (
        deployment_id    TEXT PRIMARY KEY,
        model_id         TEXT NOT NULL REFERENCES model_definitions(model_id),
        provider         TEXT NOT NULL,
        endpoint         TEXT NOT NULL,
        secret_ref       TEXT NOT NULL,
        status           TEXT NOT NULL DEFAULT 'enabled',
        priority         INTEGER NOT NULL DEFAULT 100,
        timeout_ms       INTEGER DEFAULT 30000,
        max_concurrency  INTEGER DEFAULT 10,
        health_status    TEXT NOT NULL DEFAULT 'unknown',
        config_revision_id TEXT,
        source           TEXT DEFAULT 'manual',
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)
    op.execute("CREATE INDEX idx_deployments_model ON model_deployments(model_id);")
    op.execute("CREATE INDEX idx_deployments_status ON model_deployments(status);")

    op.execute("""
    CREATE TABLE model_profiles (
        profile_id       TEXT PRIMARY KEY,
        name             TEXT NOT NULL UNIQUE,
        description      TEXT,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE TABLE model_routes (
        route_id         TEXT PRIMARY KEY,
        profile_name     TEXT NOT NULL,
        deployment_id    TEXT NOT NULL REFERENCES model_deployments(deployment_id),
        priority         INTEGER NOT NULL DEFAULT 100,
        is_fallback      BOOLEAN NOT NULL DEFAULT FALSE,
        tenant_id        TEXT,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)
    op.execute("CREATE INDEX idx_routes_profile ON model_routes(profile_name);")

    op.execute("""
    CREATE TABLE embedding_spaces (
        space_id         TEXT PRIMARY KEY,
        model_id         TEXT NOT NULL REFERENCES model_definitions(model_id),
        model_revision   TEXT NOT NULL,
        dimension        INTEGER NOT NULL,
        normalize        BOOLEAN NOT NULL DEFAULT TRUE,
        distance_metric  TEXT NOT NULL DEFAULT 'cosine',
        index_version    INTEGER NOT NULL DEFAULT 1,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS embedding_spaces;")
    op.execute("DROP TABLE IF EXISTS model_routes;")
    op.execute("DROP TABLE IF EXISTS model_profiles;")
    op.execute("DROP TABLE IF EXISTS model_deployments;")
    op.execute("DROP TABLE IF EXISTS model_definitions;")
