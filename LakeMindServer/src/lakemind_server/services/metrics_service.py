from __future__ import annotations
import json
from datetime import datetime, timezone
from ..db import execute, execute_one


_FORBIDDEN_LABELS = frozenset({
    "asset_id", "job_id", "attempt_id", "operation_id",
    "principal_id", "request_id", "correlation_id",
    "user_id", "token_id", "session_id",
})

_MAX_LABELS = 20


class CardinalityViolation(Exception):
    def __init__(self, forbidden: set[str]):
        self.forbidden = forbidden
        super().__init__(f"Forbidden high-cardinality labels: {forbidden}")


class MetricsService:

    @staticmethod
    def validate_labels(labels: dict) -> dict:
        forbidden = set(labels.keys()) & _FORBIDDEN_LABELS
        if forbidden:
            raise CardinalityViolation(forbidden)
        if len(labels) > _MAX_LABELS:
            labels = dict(list(labels.items())[:_MAX_LABELS])
        return labels

    @staticmethod
    def write(metric_name: str, value: float, labels: dict | None = None,
              scope_type: str = "PLATFORM", scope_id: str | None = None,
              observed_at: datetime | None = None) -> int:
        labels = MetricsService.validate_labels(labels or {})
        now = observed_at or datetime.now(timezone.utc)
        from datetime import timedelta
        retention_until = now + timedelta(days=7)
        row = execute_one(
            "INSERT INTO metrics_series (scope_type, scope_id, metric_name, labels, value, observed_at, retention_until) "
            "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s) RETURNING id",
            (scope_type, scope_id, metric_name, json.dumps(labels), value, now, retention_until),
        )
        return row["id"] if row else 0

    @staticmethod
    def write_batch(metrics: list[dict]) -> int:
        count = 0
        for m in metrics:
            MetricsService.write(
                metric_name=m["metric_name"],
                value=m["value"],
                labels=m.get("labels"),
                scope_type=m.get("scope_type", "PLATFORM"),
                scope_id=m.get("scope_id"),
                observed_at=datetime.fromisoformat(m["observed_at"]) if isinstance(m.get("observed_at"), str) else m.get("observed_at"),
            )
            count += 1
        return count

    @staticmethod
    def query(metric_name: str, labels: dict | None = None,
              from_time: datetime | None = None, to_time: datetime | None = None,
              page_size: int = 500) -> dict:
        conditions = ["metric_name = %s"]
        params: list = [metric_name]
        if labels:
            conditions.append("labels @> %s::jsonb")
            params.append(json.dumps(labels))
        if from_time:
            conditions.append("observed_at >= %s")
            params.append(from_time)
        if to_time:
            conditions.append("observed_at <= %s")
            params.append(to_time)
        where = " AND ".join(conditions)
        items = execute(
            f"SELECT id, scope_type, scope_id, metric_name, labels, value, observed_at "
            f"FROM metrics_series WHERE {where} ORDER BY observed_at DESC LIMIT %s",
            tuple(params + [page_size]),
        )
        latest = items[0]["observed_at"] if items else None
        stale = False
        freshness_seconds = None
        if latest:
            freshness_seconds = (datetime.now(timezone.utc) - latest).total_seconds()
            stale = freshness_seconds > 300
        return {
            "items": items,
            "total": len(items),
            "observed_at": latest.isoformat() if latest else None,
            "freshness_seconds": freshness_seconds,
            "stale": stale,
        }

    @staticmethod
    def cleanup_expired() -> int:
        now = datetime.now(timezone.utc)
        result = execute_one(
            "WITH deleted AS (DELETE FROM metrics_series "
            "WHERE retention_until < %s RETURNING 1) SELECT count(*) AS cnt FROM deleted",
            (now,),
        )
        return result["cnt"] if result else 0
