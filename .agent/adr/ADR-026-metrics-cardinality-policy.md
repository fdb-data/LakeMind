# ADR-026: Metrics Cardinality Policy

> 状态：已批准  
> 日期：2026-07-16  
> 上下文：Phase 1A Core WP-C-Core-T3

## 背景

Metrics 系统如果允许高基数标签（如 `asset_id`, `job_id`, `principal_id`），会导致 `metrics_series` 表行数爆炸、查询变慢、存储成本不可控。Prometheus 等系统通过 relabel 规则在采集端丢弃高基数标签，LakeMind 需要类似策略。

## 决策

### 标签分类

| 类别 | 标签 | 基数 | 允许 |
|------|------|------|------|
| **低基数** | `tenant_id`, `service`, `instance`, `status`, `model_id`, `deployment_id`, `skill_id`, `environment`, `scope_type`, `scope_id` | < 1000 | ✅ |
| **高基数** | `asset_id`, `job_id`, `attempt_id`, `operation_id`, `principal_id`, `request_id`, `correlation_id` | 无上限 | ❌ 拒绝 |

### 拒绝策略

Telemetry Agent 在写入 `metrics_series` 时执行 Cardinality 检查：

```python
FORBIDDEN_LABELS = {
    "asset_id", "job_id", "attempt_id", "operation_id",
    "principal_id", "request_id", "correlation_id",
    "user_id", "token_id", "session_id",
}

def validate_labels(labels: dict) -> dict:
    forbidden = set(labels.keys()) & FORBIDDEN_LABELS
    if forbidden:
        # 拒绝写入，记录告警 metric
        raise CardinalityViolation(forbidden)
    return labels
```

### 高基数需求的替代方案

需要按 `job_id` 查看指标时，不通过 Metrics 系统而是直接查询业务表（`jobs`, `job_attempts`）。Metrics 只负责聚合视图。

### 标签数量限制

单个 Metric 数据点的标签数量上限 20。超过时截断并记录告警。

### 指标名称规范

```
<domain>.<metric_name>
```

| 域 | 示例 |
|----|------|
| `cpu` | `cpu.usage` |
| `memory` | `memory.usage` |
| `storage` | `storage.usage` |
| `db` | `db.connections`, `db.slow_queries` |
| `valkey` | `valkey.memory`, `valkey.keys` |
| `ray` | `ray.workers`, `ray.queue_depth` |
| `model_serving` | `model_serving.health` |
| `service` | `service.health`, `service.response_time` |
| `job` | `job.queue_depth`, `job.failure_rate` |

### 查询时 Cardinality 保护

查询 API 也做标签白名单过滤，防止注入高基数标签：

```sql
-- 查询只允许低基数标签
SELECT * FROM metrics_series
WHERE metric_name = %s
  AND observed_at BETWEEN %s AND %s
  AND labels @> %s::jsonb  -- 只含低基数标签
ORDER BY observed_at
```

## 理由

- **可预测的存储** — 7 天保留 + 低基数标签 = 可预测的行数上限
- **查询性能** — GIN 索引 on labels 在低基数下高效
- **运维简单** — 不需要 relabel 规则配置，策略在代码中硬编码

## 影响

- Telemetry Agent 采集端强制 Cardinality 检查
- Server API `POST /api/v1/observability/metrics` 拒绝高基数标签
- 查询 API 只接受白名单标签过滤
- ADR-028 事件 Schema 中 metrics 事件遵循同一策略
