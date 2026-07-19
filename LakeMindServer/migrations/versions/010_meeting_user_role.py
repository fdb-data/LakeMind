"""Meeting Agent: meeting_user role + ensure meeting-agent-demo tenant

Revision ID: 010
Revises: 009
Create Date: 2026-07-17
"""
from __future__ import annotations
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO roles (role_id, name, permissions, is_builtin)
        VALUES (
            'role_meeting_user',
            'meeting_user',
            '["asset:create","asset:read","knowledge:ingest","knowledge:search","memory:add","memory:read","job:submit","job:read","model:read"]',
            true
        )
        ON CONFLICT (role_id) DO NOTHING
    """)

    op.execute("""
        INSERT INTO tenants (tenant_id, name, status)
        VALUES ('examples-meeting-agent', 'Meeting Agent Example', 'active')
        ON CONFLICT (tenant_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_bindings WHERE role_id = 'role_meeting_user'")
    op.execute("DELETE FROM roles WHERE role_id = 'role_meeting_user'")
