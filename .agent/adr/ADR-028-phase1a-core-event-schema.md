# ADR-028: Phase 1A Core 事件 Schema

> 状态：已批准  
> 日期：2026-07-16  
> 上下文：Phase 1A Core WP-C-Core-T2

## 背景

Phase 0 有 `job_events` 和 `outbox` 表，但没有统一的事件总线。Phase 1A 需要实时刷新（SSE），要求所有状态变更产生可订阅的事件。事件需要持久化（断线重放）、按 scope 过滤（租户隔离）、按 sequence 保序。

## 决策

### 事件存储

统一 `event_stream` 表（Outbox 模式）：

```sql
event_stream (
  event_id UUID PK DEFAULT gen_random_uuid(),
  event_type VARCHAR(64) NOT NULL,
  scope_type VARCHAR(16) NOT NULL,        -- PLATFORM | TENANT
  scope_id VARCHAR,                       -- NULL when PLATFORM
  resource_type VARCHAR(32),
  resource_id VARCHAR(64),
  sequence BIGSERIAL,                     -- 全局递增，保序
  created_at TIMESTAMP DEFAULT now(),
  payload JSONB NOT NULL,                 -- 事件特定数据
  retention_until TIMESTAMP,              -- 7 天
  published_at TIMESTAMP,                 -- NULL = 未发布
  publish_attempts INT DEFAULT 0,
  last_publish_error TEXT
)
```

### 事件类型（Phase 1A Core 范围）

| 事件类型 | 触发 | scope | resource_type | payload |
|----------|------|-------|---------------|---------|
| `job.status_changed` | Job 状态机迁移 | TENANT | job | `{job_id, old_status, new_status, attempt_id}` |
| `job.resource_update` | Job 资源变更 | TENANT | job | `{job_id, field, old_value, new_value}` |
| `operation.status_changed` | Operation 状态变更 | TENANT | operation | `{operation_id, old_status, new_status}` |
| `operation.approval_needed` | Operation 进入 APPROVAL_REQUIRED | TENANT | operation | `{operation_id, action, requested_by}` |
| `model.deployment_health_changed` | Model 健康状态变更 | PLATFORM | model_deployment | `{deployment_id, old_health, new_health}` |
| `config.drift_detected` | 配置漂移检测 | TENANT | config | `{revision_id, scope, drift_fields}` |
| `service.health_changed` | 服务健康变更 | PLATFORM | service | `{service, instance, old_status, new_status}` |
| `asset.health_changed` | Asset 健康变更 | TENANT | asset | `{asset_id, old_health, new_health}` |
| `notification.created` | 站内通知创建 | TENANT | notification | `{notification_id, category, severity}` |

### 事件发布流程

```
1. 业务事务
   ├── 写业务状态（UPDATE jobs SET status = ...）
   ├── 写 event_stream（INSERT INTO event_stream ... published_at = NULL）
   └── COMMIT

2. Event Relay（独立线程/进程）
   ├── SELECT * FROM event_stream WHERE published_at IS NULL ORDER BY sequence
   ├── XADD Valkey Stream（通知 BFF 有新事件）
   ├── UPDATE event_stream SET published_at = now() WHERE event_id = ...
   └── 失败时 publish_attempts++ + last_publish_error = ...
```

### SSE 消费流程

```
1. 客户端连接 /events/stream（Session Cookie + Origin 校验）
2. BFF 读取 Last-Event-ID header
3. BFF 从 event_stream 读取 sequence > last_event_id 的事件
4. 按 scope 过滤（SecurityContext.accessible_scope_filter）
5. SSE 推送：id={sequence}\nevent={event_type}\ndata={json_payload}\n\n
6. 心跳 15s
7. 断线重连：客户端带 Last-Event-ID → 回放缺失事件
```

### Valkey Stream 角色

Valkey Stream **不存储事件数据**，仅用于通知 BFF 有新事件：

```
XADD lakemind:events_notify * event_id {uuid}
```

BFF `SUBSCRIBE` 或 `XREAD` 唤醒后，直接从 PG `event_stream` 读取。这样：
- 事件数据持久化在 PG（可靠）
- Valkey 仅做通知（低内存）
- Valkey 宕计/重启不丢事件（PG 是事实源）

### 事件 payload 规范

```json
{
  "event_id": "uuid",
  "event_type": "job.status_changed",
  "sequence": 12345,
  "scope_type": "TENANT",
  "scope_id": "ten_default",
  "resource_type": "job",
  "resource_id": "job_xxx",
  "created_at": "2026-07-16T10:00:00Z",
  "payload": {
    "job_id": "job_xxx",
    "old_status": "RUNNING",
    "new_status": "SUCCEEDED",
    "attempt_id": "att_xxx"
  }
}
```

### 保留策略

- `retention_until = created_at + 7 days`
- 每天清理 `retention_until < now()` 的事件
- 已发布且已过保留期的事件删除
- 未发布且已过保留期的事件保留并告警（说明 Relay 有问题）

### 站内通知

事件触发通知的规则：

| 事件 | 通知 | 接收者 |
|------|------|--------|
| `operation.approval_needed` | 审批提醒 | 有 `operation:approve` capability 的 principals |
| `job.status_changed` (→ FAILED) | Job 失败 | Job 提交者 |
| `config.drift_detected` | 配置漂移 | Tenant admin |
| `model.deployment_health_changed` (→ UNHEALTHY) | Model 不健康 | Platform admin |
| `service.health_changed` (→ DOWN) | 服务不可用 | Platform admin |

通知存储在 `notifications` 表，通过 SSE `notification.created` 事件推送。

## 理由

- **PG 为事实源** — 事件不丢、可重放、可审计
- **Valkey 仅通知** — 不承担持久化责任，重启安全
- **Outbox 模式** — 业务事务和事件发布解耦，不引入分布式事务
- **sequence 保序** — 客户端可正确处理事件顺序和去重

## 影响

- Migration 009 创建 `event_stream` + `notifications` 表
- `services/event_service.py` 新增 EventService（写入事件）
- `outbox/worker.py` 扩展为 Event Relay
- BFF 新增 `/events/stream` SSE 端点
- 各业务 service 在状态变更时调用 EventService.emit()
