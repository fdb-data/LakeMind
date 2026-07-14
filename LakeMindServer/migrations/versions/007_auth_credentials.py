"""Auth credentials: add username/password_hash to principals + seed admin

Revision ID: 007
Revises: 006
Create Date: 2026-07-14
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("principals", sa.Column("username", sa.Text, nullable=True))
    op.add_column("principals", sa.Column("password_hash", sa.Text, nullable=True))
    op.create_index("idx_principals_username", "principals", ["username"], unique=True)

    op.execute("""
        INSERT INTO principals (principal_id, principal_type, name, tenant_id, username, password_hash, status)
        VALUES (
            'prn_admin_default',
            'user',
            'admin',
            'ten_default',
            'admin',
            '02ead2719473c54c36c6acb440b16ec86fc9d9be0787fd1eefa37a5acbf81b8e',
            'active'
        )
        ON CONFLICT (principal_id) DO NOTHING
    """)

    op.execute("""
        INSERT INTO role_bindings (binding_id, principal_id, role_id, tenant_id)
        SELECT 'rb_admin_default', 'prn_admin_default', role_id, 'ten_default'
        FROM roles WHERE name = 'platform_admin'
        ON CONFLICT (principal_id, role_id, tenant_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_bindings WHERE principal_id = 'prn_admin_default'")
    op.execute("DELETE FROM principals WHERE principal_id = 'prn_admin_default'")
    op.drop_index("idx_principals_username", table_name="principals")
    op.drop_column("principals", "password_hash")
    op.drop_column("principals", "username")
