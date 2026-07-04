"""PostgreSQL 图存储（nodes + edges 表，AGE 待补充）。"""
from __future__ import annotations

import json
from typing import Any

import psycopg2

from ..config import PostgresCfg

__all__ = ["GraphClient"]


class GraphClient:
    def __init__(self, cfg: PostgresCfg) -> None:
        self._cfg = cfg

    def _conn(self):
        return psycopg2.connect(
            host=self._cfg.host, port=self._cfg.port,
            dbname=self._cfg.db, user=self._cfg.user, password=self._cfg.password,
        )

    def add_node(self, graph: str, node_id: str, label: str, properties: dict, tenant_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graph_nodes (graph_name, node_id, label, properties, tenant_id) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (graph, node_id, label, json.dumps(properties), tenant_id),
            )

    def add_edge(self, graph: str, edge_id: str, src: str, dst: str, rel: str, properties: dict, tenant_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graph_edges (graph_name, edge_id, src_id, dst_id, rel_type, properties, tenant_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (graph, edge_id, src, dst, rel, json.dumps(properties), tenant_id),
            )

    def query_nodes(self, graph: str, tenant_id: str, label: str | None = None) -> list[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            if label:
                cur.execute(
                    "SELECT node_id, label, properties FROM graph_nodes WHERE graph_name=%s AND tenant_id=%s AND label=%s",
                    (graph, tenant_id, label),
                )
            else:
                cur.execute(
                    "SELECT node_id, label, properties FROM graph_nodes WHERE graph_name=%s AND tenant_id=%s",
                    (graph, tenant_id),
                )
            return [{"node_id": r[0], "label": r[1], "properties": r[2]} for r in cur.fetchall()]

    def query_edges(self, graph: str, src: str, tenant_id: str) -> list[dict]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT e.rel_type, e.dst_id, n.properties FROM graph_edges e "
                "JOIN graph_nodes n ON e.graph_name=n.graph_name AND e.dst_id=n.node_id "
                "WHERE e.graph_name=%s AND e.src_id=%s AND e.tenant_id=%s",
                (graph, src, tenant_id),
            )
            return [{"rel_type": r[0], "dst_id": r[1], "dst_properties": r[2]} for r in cur.fetchall()]

    def health(self) -> str:
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            return "ok"
        except Exception:
            return "error"
