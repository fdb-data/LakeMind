"""WP4: Job Runtime — job_runs, job_attempts, job_artifacts

Revision ID: 005
Revises: 004
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE job_runs (
        job_id          TEXT PRIMARY KEY,
        tenant_id       TEXT NOT NULL,
        skill_asset_id  TEXT NOT NULL REFERENCES assets(asset_id),
        skill_version   TEXT NOT NULL,
        skill_checksum  TEXT NOT NULL,
        initiator_id    TEXT NOT NULL,
        inputs          JSONB NOT NULL,
        params          JSONB DEFAULT '{}',
        model_binding   JSONB,
        secret_refs     JSONB DEFAULT '[]',
        resource_final  JSONB NOT NULL,
        status          TEXT NOT NULL DEFAULT 'SUBMITTED',
        config_revision_id TEXT,
        idempotency_key TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at     TIMESTAMPTZ
    );
    """)
    op.execute("CREATE INDEX idx_jobs_tenant_status ON job_runs(tenant_id, status);")
    op.execute("CREATE UNIQUE INDEX idx_jobs_idempotency ON job_runs(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;")

    op.execute("""
    CREATE TABLE job_attempts (
        attempt_id      TEXT PRIMARY KEY,
        job_id          TEXT NOT NULL REFERENCES job_runs(job_id),
        attempt_number  INTEGER NOT NULL,
        ray_job_id      TEXT,
        status          TEXT NOT NULL DEFAULT 'QUEUED',
        started_at      TIMESTAMPTZ,
        finished_at     TIMESTAMPTZ,
        duration_ms     INTEGER,
        error_message   TEXT,
        resource_used   JSONB,
        UNIQUE(job_id, attempt_number)
    );
    """)
    op.execute("CREATE INDEX idx_attempts_job ON job_attempts(job_id);")
    op.execute("CREATE INDEX idx_attempts_status ON job_attempts(status);")

    op.execute("""
    CREATE TABLE job_artifacts (
        artifact_id     TEXT PRIMARY KEY,
        job_id          TEXT NOT NULL REFERENCES job_runs(job_id),
        attempt_id      TEXT NOT NULL REFERENCES job_attempts(attempt_id),
        artifact_type   TEXT NOT NULL,
        uri             TEXT NOT NULL,
        checksum        TEXT,
        size_bytes      BIGINT,
        can_assetize    BOOLEAN NOT NULL DEFAULT FALSE,
        asset_id        TEXT REFERENCES assets(asset_id),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)
    op.execute("CREATE INDEX idx_artifacts_job ON job_artifacts(job_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS job_artifacts;")
    op.execute("DROP TABLE IF EXISTS job_attempts;")
    op.execute("DROP TABLE IF EXISTS job_runs;")
