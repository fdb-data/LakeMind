from __future__ import annotations
import os
import time
import json
import httpx
import psycopg2
import threading
from datetime import datetime, timezone


_SERVER_API = os.environ.get("LAKEMIND_SERVER_API", "http://lakemind-server:10823")
_API_KEY = os.environ.get("SERVER_API_KEY", "")
_PG_DSN = os.environ.get("DATABASE_URL", "postgresql://lakemind:lakemind@lakemind-postgres:5432/lakemind")
_VALKEY_HOST = os.environ.get("VALKEY_HOST", "lakemind-valkey")
_VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
_SEAWEEDFS_URL = os.environ.get("SEAWEEDFS_URL", "http://lakemind-seaweedfs:8333")
_RAY_DASHBOARD = os.environ.get("RAY_DASHBOARD_URL", "http://lakemind-ray-head:8265")
_MODEL_SERVING_URL = os.environ.get("MODEL_SERVING_URL", "http://lakemind-model-serving:10824")
_INTERVAL = int(os.environ.get("TELEMETRY_INTERVAL", "60"))
_SERVICES = os.environ.get("TELEMETRY_SERVICES", "server-api,asset-mcp,data-mcp,admin-mcp,model-serving,control-center").split(",")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _post_metrics(metrics: list[dict]) -> None:
    if not metrics:
        return
    try:
        with httpx.Client() as client:
            resp = client.post(
                f"{_SERVER_API}/api/v1/observability/metrics",
                json={"metrics": metrics},
                headers={"Authorization": f"Bearer {_API_KEY}"},
                timeout=10.0,
            )
            if resp.status_code not in (200, 201):
                print(f"[telemetry] metrics post failed: {resp.status_code} {resp.text[:200]}")
    except Exception as exc:
        print(f"[telemetry] metrics post error: {exc}")


def collect_cpu_memory() -> list[dict]:
    metrics = []
    now = _now().isoformat()
    try:
        with open("/proc/stat") as f:
            cpu_line = f.readline()
            parts = cpu_line.split()
            total = sum(int(x) for x in parts[1:])
            idle = int(parts[4])
            usage = (1 - idle / total) * 100 if total > 0 else 0
            metrics.append({
                "metric_name": "cpu.usage", "value": round(usage, 2),
                "labels": {"service": "telemetry-agent", "instance": "host"},
                "scope_type": "PLATFORM", "observed_at": now,
            })
    except Exception:
        pass

    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                key, val = line.split(":")
                meminfo[key.strip()] = int(val.strip().split()[0])
            total = meminfo.get("MemTotal", 1)
            avail = meminfo.get("MemAvailable", 0)
            usage = (1 - avail / total) * 100 if total > 0 else 0
            metrics.append({
                "metric_name": "memory.usage", "value": round(usage, 2),
                "labels": {"service": "telemetry-agent", "instance": "host"},
                "scope_type": "PLATFORM", "observed_at": now,
            })
    except Exception:
        pass

    return metrics


def collect_postgres() -> list[dict]:
    metrics = []
    now = _now().isoformat()
    try:
        conn = psycopg2.connect(_PG_DSN, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
        active = cur.fetchone()[0]
        metrics.append({
            "metric_name": "db.connections", "value": active,
            "labels": {"service": "postgres", "instance": "primary"},
            "scope_type": "PLATFORM", "observed_at": now,
        })
        cur.close()
        conn.close()
    except Exception as exc:
        print(f"[telemetry] pg collect error: {exc}")
    return metrics


def collect_valkey() -> list[dict]:
    metrics = []
    now = _now().isoformat()
    try:
        import redis
        r = redis.Redis(host=_VALKEY_HOST, port=_VALKEY_PORT, decode_responses=True, socket_timeout=5)
        info = r.info("memory")
        used = info.get("used_memory", 0)
        maxmem = info.get("maxmemory", 0)
        usage = (used / maxmem * 100) if maxmem > 0 else 0
        metrics.append({
            "metric_name": "valkey.memory", "value": round(usage, 2),
            "labels": {"service": "valkey", "instance": "primary"},
            "scope_type": "PLATFORM", "observed_at": now,
        })
        metrics.append({
            "metric_name": "valkey.keys", "value": r.dbsize(),
            "labels": {"service": "valkey", "instance": "primary"},
            "scope_type": "PLATFORM", "observed_at": now,
        })
        r.close()
    except Exception as exc:
        print(f"[telemetry] valkey collect error: {exc}")
    return metrics


def collect_seaweedfs() -> list[dict]:
    metrics = []
    now = _now().isoformat()
    try:
        with httpx.Client() as client:
            resp = client.get(f"{_SEAWEEDFS_URL}/cluster/status", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                free = data.get("Free", 0)
                total = data.get("Total", 0)
                usage = ((total - free) / total * 100) if total > 0 else 0
                metrics.append({
                    "metric_name": "storage.usage", "value": round(usage, 2),
                    "labels": {"service": "seaweedfs", "instance": "cluster"},
                    "scope_type": "PLATFORM", "observed_at": now,
                })
    except Exception as exc:
        print(f"[telemetry] seaweedfs collect error: {exc}")
    return metrics


def collect_ray() -> list[dict]:
    metrics = []
    now = _now().isoformat()
    try:
        with httpx.Client() as client:
            resp = client.get(f"{_RAY_DASHBOARD}/api/actors", timeout=5.0)
            if resp.status_code == 200:
                actors = resp.json().get("actors", {})
                workers = sum(1 for a in actors.values() if a.get("state") == "ALIVE")
                metrics.append({
                    "metric_name": "ray.workers", "value": workers,
                    "labels": {"service": "ray", "instance": "head"},
                    "scope_type": "PLATFORM", "observed_at": now,
                })
    except Exception as exc:
        print(f"[telemetry] ray collect error: {exc}")
    return metrics


def collect_model_serving() -> list[dict]:
    metrics = []
    now = _now().isoformat()
    try:
        with httpx.Client() as client:
            resp = client.get(f"{_MODEL_SERVING_URL}/health", timeout=5.0)
            healthy = 1 if resp.status_code == 200 else 0
            metrics.append({
                "metric_name": "model_serving.health", "value": healthy,
                "labels": {"service": "model-serving", "instance": "primary"},
                "scope_type": "PLATFORM", "observed_at": now,
            })
    except Exception:
        metrics.append({
            "metric_name": "model_serving.health", "value": 0,
            "labels": {"service": "model-serving", "instance": "primary"},
            "scope_type": "PLATFORM", "observed_at": now,
        })
    return metrics


def collect_service_health() -> list[dict]:
    metrics = []
    now = _now().isoformat()
    service_urls = {
        "server-api": f"{_SERVER_API}/api/v1/system/health",
        "model-serving": f"{_MODEL_SERVING_URL}/health",
    }
    for svc in _SERVICES:
        url = service_urls.get(svc)
        if not url:
            continue
        try:
            with httpx.Client() as client:
                resp = client.get(url, timeout=5.0)
                healthy = 1 if resp.status_code == 200 else 0
        except Exception:
            healthy = 0
        metrics.append({
            "metric_name": "service.health", "value": healthy,
            "labels": {"service": svc, "instance": "primary", "status": "healthy" if healthy else "down"},
            "scope_type": "PLATFORM", "observed_at": now,
        })
    return metrics


def collect_all() -> list[dict]:
    metrics = []
    metrics.extend(collect_cpu_memory())
    metrics.extend(collect_postgres())
    metrics.extend(collect_valkey())
    metrics.extend(collect_seaweedfs())
    metrics.extend(collect_ray())
    metrics.extend(collect_model_serving())
    metrics.extend(collect_service_health())
    return metrics


def run_loop() -> None:
    print(f"[telemetry] starting, interval={_INTERVAL}s")
    while True:
        try:
            metrics = collect_all()
            _post_metrics(metrics)
            print(f"[telemetry] collected {len(metrics)} metrics")
        except Exception as exc:
            print(f"[telemetry] loop error: {exc}")
        time.sleep(_INTERVAL)


if __name__ == "__main__":
    run_loop()
