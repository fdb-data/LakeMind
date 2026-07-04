from __future__ import annotations
import json
import time
import uuid
import pyarrow as pa
import psycopg2


class BasicMemory:
    def __init__(self, host: str = "lakemind-postgres", port: int = 5432,
                 db: str = "lakemind", user: str = "lakemind",
                 password: str = "lakemind_pass",
                 kv_host: str = "lakemind-dragonfly", kv_port: int = 6379,
                 lance_uri: str = "/data/lance",
                 embedding_model: str = "BAAI/bge-small-en-v1.5",
                 embedding_dim: int = 384, **kwargs):
        self._dsn = f"host={host} port={port} dbname={db} user={user} password={password}"
        self._kv_host = kv_host
        self._kv_port = kv_port
        self._lance_uri = lance_uri
        self._embed_model = None
        self._embed_dim = embedding_dim
        self._embed_model_name = embedding_model
        self._redis = None

    def _ensure_redis(self):
        if self._redis is None:
            import redis
            self._redis = redis.Redis(host=self._kv_host, port=self._kv_port, decode_responses=True)

    def _ensure_embed(self):
        if self._embed_model is None:
            from fastembed import TextEmbedding
            self._embed_model = TextEmbedding(model_name=self._embed_model_name,
                                              cache_dir="/tmp/fastembed_cache")

    def _embed(self, text: str) -> list[float]:
        self._ensure_embed()
        return [float(x) for x in next(self._embed_model.embed([text]))]

    def remember(self, agent_id: str, tenant_id: str, content: str,
                 context: str | None = None, ttl: int | None = None,
                 kind: str = "general") -> dict:
        if ttl:
            self._ensure_redis()
            key = f"{tenant_id}:{agent_id}:short:{uuid.uuid4().hex[:8]}"
            val = json.dumps({"content": content, "context": context or "", "kind": kind}, ensure_ascii=False)
            self._redis.set(key, val, ex=ttl)
            return {"status": "ok", "type": "short_term", "key": key}

        vec = self._embed(content)
        import lancedb
        db_name = f"memory_{tenant_id}"
        conn = lancedb.connect(f"{self._lance_uri}/{db_name}")
        tbl_name = f"mem_{agent_id}"
        row = pa.Table.from_pylist([{
            "content": content,
            "context": context or "",
            "kind": kind,
            "vector": vec,
            "created_at": int(time.time()),
        }])
        if tbl_name in conn.table_names():
            conn.open_table(tbl_name).add(row)
        else:
            conn.create_table(tbl_name, data=row)
        return {"status": "ok", "type": "long_term", "rows": 1}

    def recall(self, agent_id: str, tenant_id: str, query: str,
               limit: int = 5, kind: str | None = None) -> list[dict]:
        results = []
        try:
            qvec = self._embed(query)
            import lancedb
            db_name = f"memory_{tenant_id}"
            conn = lancedb.connect(f"{self._lance_uri}/{db_name}")
            tbl_name = f"mem_{agent_id}"
            if tbl_name in conn.table_names():
                q = conn.open_table(tbl_name).search(qvec).limit(limit)
                results = q.to_list()
                if kind:
                    results = [r for r in results if r.get("kind") == kind]
        except Exception:
            pass

        try:
            self._ensure_redis()
            for key in self._redis.scan_iter(match=f"{tenant_id}:{agent_id}:short:*"):
                val = self._redis.get(key)
                if val:
                    d = json.loads(val)
                    if kind and d.get("kind") != kind:
                        continue
                    if query.lower() in d.get("content", "").lower():
                        results.append(d)
        except Exception:
            pass

        return results[:limit]

    def forget(self, agent_id: str, tenant_id: str, query: str | None = None) -> dict:
        deleted = 0
        try:
            self._ensure_redis()
            for key in self._redis.scan_iter(match=f"{tenant_id}:{agent_id}:short:*"):
                if query is None:
                    self._redis.delete(key)
                    deleted += 1
                else:
                    val = self._redis.get(key)
                    if val and query.lower() in json.loads(val).get("content", "").lower():
                        self._redis.delete(key)
                        deleted += 1
        except Exception:
            pass
        return {"status": "ok", "deleted": deleted}

    def health(self) -> bool:
        try:
            with psycopg2.connect(self._dsn) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
