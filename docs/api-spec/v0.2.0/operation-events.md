# LakeMind v0.2.0 Operation / 事件 / 幂等规范

> 日期：2026-07-13  
> 状态：accepted  
> 依据：[设计方案](../../../reports/v0.2.0-design/LakeMind_v0.2.0_设计方案.md) §12.5-§12.6, §12.9

---

## 1. Operation 状态机

```
PENDING ──→ APPROVAL_REQUIRED ──→ APPROVED ──→ RUNNING ──→ SUCCEEDED
  │              │                    │              │
  │              └──→ CANCELLED       │              └──→ FAILED
  │                                   │
  └──→ RUNNING (无需审批) ────────────┘
  
  任何状态 ──→ CANCELLED（由发起者或审批者取消）
```

### 1.1 状态转换规则

| 当前状态 | 允许转换到 | 触发者 |
|----------|-----------|--------|
| PENDING | RUNNING | 系统（无需审批时自动） |
| PENDING | APPROVAL_REQUIRED | 系统（风险等级判定） |
| APPROVAL_REQUIRED | APPROVED | 审批人 |
| APPROVAL_REQUIRED | CANCELLED | 审批人 / 发起者 |
| APPROVED | RUNNING | 系统 |
| RUNNING | SUCCEEDED | 系统 |
| RUNNING | FAILED | 系统 |
| RUNNING | CANCELLED | 发起者（CANCELLING → CANCELLED） |

### 1.2 死锁分析

- 所有状态转换都是单向的（无回退）
- CANCELLED 和 SUCCEEDED / FAILED 是终态
- 不存在无法到达终态的路径
- **结论：无死锁状态**

---

## 2. Operation 记录字段

| 字段 | 类型 | 说明 |
|------|------|------|
| operation_id | string | `op_{ulid}` |
| type | enum | `asset_delete` / `asset_reindex` / `skill_publish` / `skill_revoke` / `job_submit` / `model_reload` / `config_activate` / `config_rollback` / `secret_rotate` / `data_migration` |
| target_resource | string | 逻辑 URI |
| initiator_id | string | `prn_{ulid}` |
| initiator_channel | enum | `rest` / `mcp` / `control_center` / `steward` / `system` |
| reason | string | 操作原因 |
| risk_level | enum | `LOW` / `MEDIUM` / `HIGH` |
| requires_approval | boolean | |
| approver_id | string? | `prn_{ulid}` |
| status | enum | 状态机 |
| result | json? | 执行结果 |
| failure_reason | string? | |
| audit_event_ids | string[] | 关联审计事件 |
| created_at / updated_at | timestamp | |

---

## 3. 内部事件名清单

| 事件名 | 触发 | 消费者 |
|--------|------|--------|
| `asset.created` | AssetService.create_asset | Outbox Worker |
| `asset.processing` | 资产进入 PROCESSING | Outbox Worker |
| `asset.ready` | 全部 Required Binding 完成 | Audit, Notification |
| `asset.degraded` | 可选 Binding 失败 | Audit, Reconciler |
| `asset.deleted` | 异步删除完成 | Audit |
| `job.submitted` | JobService.submit | Execution Backend |
| `job.running` | Execution Backend 开始执行 | Audit |
| `job.succeeded` | 执行成功 | Audit, Artifact 资产化 |
| `job.failed` | 执行失败 | Audit, Retry 判定 |
| `job.lost` | Reconciler 发现丢失 | Audit |
| `operation.approval_required` | Operation 需审批 | Control Center, Steward |
| `operation.succeeded` | Operation 成功 | Audit, 发起者通知 |
| `config.activated` | Configuration Revision 激活 | Instance Registry, 热更新 |
| `model.deployment_unhealthy` | ModelServing 健康检查失败 | Reconciler, Alert |

### 3.1 事件格式

```json
{
  "event_id": "evt_01H8X7K2M3P4Q5R6S7T8V9W0X",
  "event_type": "asset.ready",
  "resource_id": "ast_01H8X7K2M3P4Q5R6S7T8V9W0X",
  "tenant_id": "ten_01H8X7K2M3P4Q5R6S7T8V9W0X",
  "timestamp": "2026-07-13T10:30:00Z",
  "payload": {
    "bindings": ["bnd_01H8X7K2M3", "bnd_01H8X7K2M4"]
  },
  "correlation_id": "corr_01H8X7K2M3P4Q5R6S7T8V9W0X"
}
```

### 3.2 事件投递保证

- 使用 PostgreSQL Outbox 模式保证至少一次投递
- 事件顺序：同一 resource_id 的事件按 created_at 排序
- 幂等消费：消费者根据 event_id 去重

---

## 4. 幂等键规则

| 规则 | 说明 |
|------|------|
| Header | `X-Idempotency-Key: {string}` |
| 适用操作 | 创建资产 / 摄入 Knowledge / 添加 Memory / 发布 Skill / 提交 Job / 删除资产 / 创建 Operation |
| 键范围 | 每个Principal 独立命名空间（相同 Principal + 相同 Key = 幂等） |
| 缓存 | PG 表 `idempotency_keys`：`(principal_id, key, request_hash, response, created_at)`，TTL 24h |
| 冲突处理 | 相同 Key + 不同 request body → `IDEMPOTENCY_CONFLICT` (409) |
| 相同 Key + 相同 request body | 返回缓存的原始响应 |

### 4.1 幂等键生命周期

```
1. 请求携带 X-Idempotency-Key
2. Service 查询 idempotency_keys 表
   ├── 找到 (principal_id, key) 且 request_hash 匹配 → 返回缓存响应
   ├── 找到 (principal_id, key) 且 request_hash 不匹配 → IDEMPOTENCY_CONFLICT (409)
   └── 未找到 → 执行操作，缓存响应
3. TTL 24h 后自动清理
```

### 4.2 request_hash 计算

```
request_hash = SHA256(
  method + path + sorted(body.items())
)
```

---

## 5. 评审标准

- [x] Operation 状态机无死锁状态（所有路径可达终态）
- [x] 事件名覆盖设计方案 §12.9 全部（14 个事件）
- [x] 幂等规则覆盖设计方案 §12.6 全部操作（7 类操作）
- [x] 事件格式包含 `event_id` / `correlation_id`
