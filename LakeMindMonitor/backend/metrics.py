"""Prometheus 指标。"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUESTS = Counter("monitor_bff_requests_total", "BFF 请求总数", ["endpoint", "status"])
LATENCY = Histogram("monitor_bff_latency_seconds", "BFF 请求延迟", ["endpoint"])
MCP_READS = Counter("monitor_mcp_reads_total", "MCP 资源读取次数", ["resource"])
