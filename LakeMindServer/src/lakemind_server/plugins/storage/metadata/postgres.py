from __future__ import annotations
import json
import uuid
from datetime import datetime
import psycopg2
from psycopg2 import pool

from lakemind_server.utils.crypto import SecretCrypto


class PostgresMetadataStore:
    def __init__(self, host: str, port: int = 5432, db: str = "lakemind",
                 user: str = "lakemind", password: str = "lakemind_pass",
                 pool_size: int = 20, master_key: str = "", **kwargs):
        self._pool = pool.ThreadedConnectionPool(
            1, pool_size,
            host=host, port=port, dbname=db, user=user, password=password,
        )
        self._crypto: SecretCrypto | None = None
        if master_key:
            self._crypto = SecretCrypto(master_key)

    def _conn(self):
        return self._pool.getconn()

    def _putconn(self, conn):
        self._pool.putconn(conn)

    def create_tenant(self, tenant_id: str, name: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenants (tenant_id, name, status) VALUES (%s, %s, 'active') "
                    "ON CONFLICT (tenant_id) DO UPDATE SET name=EXCLUDED.name, status='active' RETURNING tenant_id",
                    (tenant_id, name),
                )
                row = cur.fetchone()
                conn.commit()
            return {"tenant_id": tenant_id, "name": name, "status": "active"}
        finally:
            self._putconn(conn)

    def update_tenant(self, tenant_id: str, name: str | None = None, status: str | None = None) -> dict:
        conn = self._conn()
        try:
            parts, args = [], []
            if name:
                parts.append("name=%s"); args.append(name)
            if status:
                parts.append("status=%s"); args.append(status)
            if parts:
                args.append(tenant_id)
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE tenants SET {', '.join(parts)} WHERE tenant_id=%s", args)
                    conn.commit()
            return {"tenant_id": tenant_id, "updated": True}
        finally:
            self._putconn(conn)

    def delete_tenant(self, tenant_id: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE tenants SET status='deleted' WHERE tenant_id=%s", (tenant_id,))
                cur.execute("UPDATE users SET status='disabled' WHERE tenant_id=%s", (tenant_id,))
                conn.commit()
            return {"tenant_id": tenant_id, "status": "deleted"}
        finally:
            self._putconn(conn)

    def list_tenants(self) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT tenant_id, name, status FROM tenants WHERE status='active'")
                rows = cur.fetchall()
            tenants = [{"tenant_id": r[0], "name": r[1], "status": r[2]} for r in rows]
            return {"tenants": tenants, "count": len(tenants)}
        finally:
            self._putconn(conn)

    def create_user(self, username: str, tenant_id: str, role: str = "user") -> dict:
        uid = f"user_{uuid.uuid4().hex[:8]}"
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (user_id, username, tenant_id, role, status) "
                    "VALUES (%s, %s, %s, %s, 'active') "
                    "ON CONFLICT (username) DO UPDATE SET tenant_id=EXCLUDED.tenant_id, role=EXCLUDED.role, status='active'",
                    (uid, username, tenant_id, role),
                )
                conn.commit()
            return {"user_id": uid, "username": username, "tenant_id": tenant_id, "role": role, "status": "active"}
        finally:
            self._putconn(conn)

    def update_user(self, user_id: str, username: str | None = None,
                    role: str | None = None, status: str | None = None) -> dict:
        conn = self._conn()
        try:
            parts, args = [], []
            if username:
                parts.append("username=%s"); args.append(username)
            if role:
                parts.append("role=%s"); args.append(role)
            if status:
                parts.append("status=%s"); args.append(status)
            if parts:
                args.append(user_id)
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE users SET {', '.join(parts)} WHERE user_id=%s", args)
                    conn.commit()
            return {"user_id": user_id, "updated": True}
        finally:
            self._putconn(conn)

    def delete_user(self, user_id: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET status='deleted' WHERE user_id=%s", (user_id,))
                conn.commit()
            return {"user_id": user_id, "status": "deleted"}
        finally:
            self._putconn(conn)

    def list_users(self, tenant_id: str | None = None) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                if tenant_id:
                    cur.execute("SELECT user_id, username, tenant_id, role, status FROM users WHERE tenant_id=%s AND status!='deleted'", (tenant_id,))
                else:
                    cur.execute("SELECT user_id, username, tenant_id, role, status FROM users WHERE status!='deleted'")
                rows = cur.fetchall()
            users = [{"user_id": r[0], "username": r[1], "tenant_id": r[2], "role": r[3], "status": r[4]} for r in rows]
            return {"users": users, "count": len(users)}
        finally:
            self._putconn(conn)

    def issue_token(self, agent_id: str, tenant_id: str, scopes: list[str]) -> dict:
        tok = f"tk_{uuid.uuid4().hex[:16]}"
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tokens (token, agent_id, tenant_id, scopes, status) "
                    "VALUES (%s, %s, %s, %s, 'active')",
                    (tok, agent_id, tenant_id, scopes),
                )
                conn.commit()
            return {"token": tok, "agent_id": agent_id, "tenant_id": tenant_id, "scopes": scopes, "status": "active"}
        finally:
            self._putconn(conn)

    def revoke_token(self, token: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE tokens SET status='revoked', revoked_at=NOW() WHERE token=%s", (token,))
                conn.commit()
            return {"token": token, "status": "revoked"}
        finally:
            self._putconn(conn)

    def list_tokens(self, tenant_id: str | None = None, agent_id: str | None = None) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                q = "SELECT token, agent_id, tenant_id, scopes, status FROM tokens WHERE status='active'"
                args = []
                if tenant_id:
                    q += " AND tenant_id=%s"; args.append(tenant_id)
                if agent_id:
                    q += " AND agent_id=%s"; args.append(agent_id)
                cur.execute(q, args)
                rows = cur.fetchall()
            tokens = [{"token": r[0], "agent_id": r[1], "tenant_id": r[2], "scopes": r[3] if r[3] else [], "status": r[4]} for r in rows]
            return {"tokens": tokens, "count": len(tokens)}
        finally:
            self._putconn(conn)

    def validate_token(self, token: str) -> dict | None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT agent_id, tenant_id, scopes FROM tokens WHERE token=%s AND status='active'", (token,))
                row = cur.fetchone()
            if not row:
                return None
            return {"agent_id": row[0], "tenant_id": row[1], "scopes": row[2] if row[2] else []}
        finally:
            self._putconn(conn)

    def register_asset_type(self, type: str, yaml_def: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO asset_types (type, definition_yaml) "
                    "VALUES (%s, %s) ON CONFLICT (type) DO UPDATE SET definition_yaml=EXCLUDED.definition_yaml",
                    (type, yaml_def),
                )
                conn.commit()
            return {"type": type, "status": "registered"}
        finally:
            self._putconn(conn)

    def unregister_asset_type(self, type: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM asset_types WHERE type=%s", (type,))
                conn.commit()
            return {"type": type, "status": "unregistered"}
        finally:
            self._putconn(conn)

    def list_asset_types(self) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT type, definition_yaml FROM asset_types")
                rows = cur.fetchall()
            types = [{"type": r[0], "yaml": r[1]} for r in rows]
            return {"asset_types": types, "count": len(types)}
        finally:
            self._putconn(conn)

    def create_secret(self, tenant_id: str, key_name: str, value: str,
                      description: str = "", created_by: str = "") -> dict:
        if self._crypto is None:
            raise RuntimeError("master key not configured")
        enc = self._crypto.encrypt(tenant_id, key_name, value)
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenant_secrets (tenant_id, key_name, encrypted_value, iv, auth_tag, description, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id, key_name) DO UPDATE SET "
                    "encrypted_value=EXCLUDED.encrypted_value, iv=EXCLUDED.iv, "
                    "auth_tag=EXCLUDED.auth_tag, description=EXCLUDED.description, "
                    "updated_at=now()",
                    (tenant_id, key_name, enc["encrypted_value"], enc["iv"],
                     enc["auth_tag"], description or None, created_by or None),
                )
                conn.commit()
            return {"tenant_id": tenant_id, "key_name": key_name, "created": True}
        finally:
            self._putconn(conn)

    def update_secret(self, tenant_id: str, key_name: str, value: str,
                      description: str = "") -> dict:
        if self._crypto is None:
            raise RuntimeError("master key not configured")
        enc = self._crypto.encrypt(tenant_id, key_name, value)
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenant_secrets SET encrypted_value=%s, iv=%s, auth_tag=%s, "
                    "description=%s, updated_at=now() "
                    "WHERE tenant_id=%s AND key_name=%s",
                    (enc["encrypted_value"], enc["iv"], enc["auth_tag"],
                     description or None, tenant_id, key_name),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    return {"tenant_id": tenant_id, "key_name": key_name, "updated": False}
                conn.commit()
            return {"tenant_id": tenant_id, "key_name": key_name, "updated": True}
        finally:
            self._putconn(conn)

    def delete_secret(self, tenant_id: str, key_name: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tenant_secrets WHERE tenant_id=%s AND key_name=%s",
                    (tenant_id, key_name),
                )
                conn.commit()
            return {"tenant_id": tenant_id, "key_name": key_name, "deleted": True}
        finally:
            self._putconn(conn)

    def list_secrets(self, tenant_id: str) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key_name, description, updated_at FROM tenant_secrets WHERE tenant_id=%s",
                    (tenant_id,),
                )
                rows = cur.fetchall()
            secrets = [
                {"key_name": r[0], "description": r[1], "updated_at": r[2].isoformat() if r[2] else None}
                for r in rows
            ]
            return {"secrets": secrets, "count": len(secrets)}
        finally:
            self._putconn(conn)

    def get_secret_values(self, tenant_id: str) -> dict:
        if self._crypto is None:
            raise RuntimeError("master key not configured")
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key_name, encrypted_value, iv, auth_tag FROM tenant_secrets WHERE tenant_id=%s",
                    (tenant_id,),
                )
                rows = cur.fetchall()
            result: dict[str, str] = {}
            for r in rows:
                result[r[0]] = self._crypto.decrypt(tenant_id, r[0], r[1], r[2], r[3])
            return result
        finally:
            self._putconn(conn)

    def log_secret_access(self, tenant_id: str, key_name: str,
                          accessed_by: str, task_id: str = "",
                          ray_job_id: str = "") -> None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO secret_access_log (tenant_id, key_name, task_id, ray_job_id, accessed_by) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (tenant_id, key_name, task_id or None, ray_job_id or None, accessed_by),
                )
                conn.commit()
        finally:
            self._putconn(conn)

    def create_ray_job(self, job_id: str, tenant_id: str, agent_id: str,
                       skill_uri: str, job_name: str, entrypoint: str,
                       params: dict, task_id: str = "") -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ray_jobs (job_id, tenant_id, agent_id, skill_uri, job_name, entrypoint, params, task_id, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'submitted')",
                    (job_id, tenant_id, agent_id, skill_uri, job_name, entrypoint,
                     json.dumps(params), task_id or None),
                )
                conn.commit()
            return {"job_id": job_id, "status": "submitted"}
        finally:
            self._putconn(conn)

    def update_ray_job_status(self, job_id: str, status: str,
                              ray_job_id: str = "", result_uri: str = "") -> dict:
        conn = self._conn()
        try:
            parts = ["status=%s"]
            args: list = [status]
            if ray_job_id:
                parts.append("ray_job_id=%s"); args.append(ray_job_id)
            if result_uri:
                parts.append("result_uri=%s"); args.append(result_uri)
            if status in ("completed", "failed", "cancelled"):
                parts.append("completed_at=now()")
            args.append(job_id)
            with conn.cursor() as cur:
                cur.execute(f"UPDATE ray_jobs SET {', '.join(parts)} WHERE job_id=%s", args)
                conn.commit()
            return {"job_id": job_id, "status": status}
        finally:
            self._putconn(conn)

    def get_ray_job(self, job_id: str) -> dict | None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT job_id, tenant_id, agent_id, skill_uri, job_name, entrypoint, "
                    "params, task_id, status, ray_job_id, result_uri, created_at, completed_at "
                    "FROM ray_jobs WHERE job_id=%s",
                    (job_id,),
                )
                row = cur.fetchone()
            if not row:
                return None
            return {
                "job_id": row[0], "tenant_id": row[1], "agent_id": row[2],
                "skill_uri": row[3], "job_name": row[4], "entrypoint": row[5],
                "params": row[6] if row[6] else {}, "task_id": row[7],
                "status": row[8], "ray_job_id": row[9], "result_uri": row[10],
                "created_at": row[11].isoformat() if row[11] else None,
                "completed_at": row[12].isoformat() if row[12] else None,
            }
        finally:
            self._putconn(conn)

    def list_ray_jobs(self, tenant_id: str, status: str = "") -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                q = ("SELECT job_id, skill_uri, job_name, task_id, status, ray_job_id, created_at "
                     "FROM ray_jobs WHERE tenant_id=%s")
                args: list = [tenant_id]
                if status:
                    q += " AND status=%s"; args.append(status)
                q += " ORDER BY created_at DESC LIMIT 100"
                cur.execute(q, args)
                rows = cur.fetchall()
            jobs = [
                {
                    "job_id": r[0], "skill_uri": r[1], "job_name": r[2],
                    "task_id": r[3], "status": r[4], "ray_job_id": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                }
                for r in rows
            ]
            return {"jobs": jobs, "count": len(jobs)}
        finally:
            self._putconn(conn)

    def health(self) -> bool:
        try:
            conn = self._conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            finally:
                self._putconn(conn)
        except Exception:
            return False
