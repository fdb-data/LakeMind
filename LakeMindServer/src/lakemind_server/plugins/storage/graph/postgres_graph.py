from __future__ import annotations
import json
import psycopg2


class PostgresGraphStorage:
    def __init__(self, host: str, port: int = 5432, db: str = "lakemind",
                 user: str = "lakemind", password: str = "lakemind_pass", **kwargs):
        self._dsn = f"host={host} port={port} dbname={db} user={user} password={password}"

    def _conn(self):
        return psycopg2.connect(self._dsn)

    def add_node(self, graph: str, node_id: str, label: str, properties: dict, tenant_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graph_nodes (graph_name, node_id, label, properties, tenant_id) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (graph, node_id, label, json.dumps(properties), tenant_id),
            )
            conn.commit()

    def add_edge(self, graph: str, edge_id: str, src: str, dst: str,
                 rel: str, properties: dict, tenant_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graph_edges (graph_name, edge_id, src_id, dst_id, rel_type, properties, tenant_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (graph, edge_id, src, dst, rel, json.dumps(properties), tenant_id),
            )
            conn.commit()

    def query_nodes(self, graph: str, tenant_id: str, label: str | None = None) -> list[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            if label:
                cur.execute(
                    "SELECT node_id, label, properties FROM graph_nodes "
                    "WHERE graph_name=%s AND tenant_id=%s AND label=%s",
                    (graph, tenant_id, label),
                )
            else:
                cur.execute(
                    "SELECT node_id, label, properties FROM graph_nodes "
                    "WHERE graph_name=%s AND tenant_id=%s",
                    (graph, tenant_id),
                )
            rows = cur.fetchall()
        return [{"node_id": r[0], "label": r[1], "properties": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {})} for r in rows]

    def query_edges(self, graph: str, src: str, tenant_id: str) -> list[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT e.rel_type, e.dst_id, n.properties "
                "FROM graph_edges e JOIN graph_nodes n ON e.dst_id = n.node_id "
                "WHERE e.graph_name=%s AND e.src_id=%s AND e.tenant_id=%s",
                (graph, src, tenant_id),
            )
            rows = cur.fetchall()
        return [{"rel_type": r[0], "dst_id": r[1], "dst_properties": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {})} for r in rows]

    def delete_node(self, graph: str, node_id: str, tenant_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM graph_nodes WHERE graph_name=%s AND node_id=%s AND tenant_id=%s",
                (graph, node_id, tenant_id),
            )
            conn.commit()

    def health(self) -> bool:
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
