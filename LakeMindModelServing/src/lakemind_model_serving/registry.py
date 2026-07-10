from __future__ import annotations

import json
import logging
import psycopg2

logger = logging.getLogger(__name__)


class ModelRegistry:
    def __init__(self, host: str, port: int, db: str, user: str, password: str):
        self._dsn = f"host={host} port={port} dbname={db} user={user} password={password}"
        self._initialized = False

    def _ensure_table(self):
        if not self._initialized:
            try:
                with psycopg2.connect(self._dsn) as conn, conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS model_registry (
                            model_id VARCHAR(128) PRIMARY KEY,
                            type VARCHAR(16) NOT NULL,
                            provider VARCHAR(64) NOT NULL,
                            litellm_model VARCHAR(256),
                            api_key TEXT,
                            base_url VARCHAR(512),
                            tags VARCHAR(64)[],
                            context_window INT DEFAULT 0,
                            dim INT DEFAULT 0,
                            priority INT DEFAULT 99,
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    conn.commit()
                self._initialized = True
            except Exception as e:
                logger.error("Failed to init model_registry table: %s", e)

    def list_active(self) -> list[dict]:
        self._ensure_table()
        try:
            with psycopg2.connect(self._dsn) as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT model_id, type, provider, litellm_model, api_key, base_url,
                           tags, context_window, dim, priority
                    FROM model_registry WHERE is_active = TRUE
                """)
                rows = cur.fetchall()
            return [
                {
                    "model_id": r[0],
                    "type": r[1],
                    "provider": r[2],
                    "litellm_model": r[3],
                    "api_key": r[4],
                    "base_url": r[5],
                    "tags": r[6] if r[6] else [],
                    "context_window": r[7],
                    "dim": r[8],
                    "priority": r[9],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Failed to list active models: %s", e)
            return []

    def register(self, model_id: str, model_type: str, provider: str,
                 litellm_model: str = "", api_key: str = "", base_url: str = "",
                 tags: list = None, context_window: int = 0, dim: int = 0,
                 priority: int = 99) -> bool:
        self._ensure_table()
        try:
            with psycopg2.connect(self._dsn) as conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO model_registry (model_id, type, provider, litellm_model, api_key, base_url, tags, context_window, dim, priority, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (model_id) DO UPDATE SET
                        type=EXCLUDED.type, provider=EXCLUDED.provider,
                        litellm_model=EXCLUDED.litellm_model, api_key=EXCLUDED.api_key,
                        base_url=EXCLUDED.base_url, tags=EXCLUDED.tags,
                        context_window=EXCLUDED.context_window, dim=EXCLUDED.dim,
                        priority=EXCLUDED.priority, is_active=TRUE
                """, (model_id, model_type, provider, litellm_model, api_key, base_url,
                      tags or [], context_window, dim, priority))
                conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to register model %s: %s", model_id, e)
            return False

    def deregister(self, model_id: str) -> bool:
        self._ensure_table()
        try:
            with psycopg2.connect(self._dsn) as conn, conn.cursor() as cur:
                cur.execute("UPDATE model_registry SET is_active=FALSE WHERE model_id=%s", (model_id,))
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error("Failed to deregister model %s: %s", model_id, e)
            return False

    def get(self, model_id: str) -> dict | None:
        self._ensure_table()
        try:
            with psycopg2.connect(self._dsn) as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT model_id, type, provider, litellm_model, base_url, tags, context_window, dim, priority, is_active
                    FROM model_registry WHERE model_id=%s
                """, (model_id,))
                r = cur.fetchone()
            if not r:
                return None
            return {
                "model_id": r[0],
                "type": r[1],
                "provider": r[2],
                "litellm_model": r[3],
                "base_url": r[4],
                "tags": r[5] if r[5] else [],
                "context_window": r[6],
                "dim": r[7],
                "priority": r[8],
                "is_active": r[9],
            }
        except Exception as e:
            logger.error("Failed to get model %s: %s", model_id, e)
            return None

    def health(self) -> bool:
        try:
            with psycopg2.connect(self._dsn) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
