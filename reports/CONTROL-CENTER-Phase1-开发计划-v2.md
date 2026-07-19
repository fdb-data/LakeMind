# Control Center Phase 1 开发计划（v2 修订版）

> 基于 `v0.2.0.design/LakeMind_Control_Center_世界级改造设计方案.md` §22.2  
> 及评审意见 v1 → v2 修订（12 个 P0 + 9 个 P1 项）  
> 基准日期：2026-07-16  
> 前置条件：Phase 0 已通过验收（有条件通过，P1 缺陷已修复）  
> 估算：165–251 人日（拆分为 Phase 1A + Phase 1B）  
> 评审状态：v2 待评审

---

## 〇、评审修订摘要

### v1 → v2 修订（12 个 P0 + 9 个 P1）

| # | 级别 | 问题 | v2 修正 |
|---|------|------|---------|
| P0-1 | P0 | "8 一级导航"实际 9 个 | 改为 8 业务导航 + Steward 全局右侧助手；Steward Workspace 放 Operations 下 |
| P0-2 | P0 | 范围与 WP 严重不一致 | 采用方案 B 补齐 WP，新增 WP-MODEL / WP-SEC，拆分 WP9 |
| P0-3 | P0 | 缺少可观测性基础 | 新增 WP-OBS Observability Foundation |
| P0-4 | P0 | SSE 重放不可实现 | 新增 WP3-T0 Durable Event Backbone（Valkey Streams + 持久化事件表） |
| P0-5 | P0 | Tenant Selector 越权风险 | switch-tenant 调 Server 验证 Membership，Session 存 active_membership_id |
| P0-6 | P0 | 路由权限硬编码角色 | 改用 Capability 模型，`/auth/me` 返回 effective_permissions + capabilities |
| P0-7 | P0 | Mission Control 数据源不完整 | 每个卡片定义事实源/计算公式/刷新频率/新鲜度/下钻，View Model 含 observed_at + freshness + source |
| P0-8 | P0 | Alert 规则引擎过于宽泛 | 改为模板化规则（metric+aggregation+window+operator+threshold+for_duration），增加 Rule Validation / Watermark / Auto Resolve / Alert Storm Protection |
| P0-9 | P0 | Incident timeline_json 不合理 | 改为 incident_events 独立表；blast_radius_json 改为 affected_objects，不宣称 Blast Radius |
| P0-10 | P0 | Resource Center Docker Socket 风险 | 改用独立只读 Telemetry Agent，禁止挂载 Docker Socket / Shell 调用 |
| P0-11 | P0 | 容量预测缺历史数据和可信边界 | 依赖 WP-OBS 历史存储；增加最低样本数/slope≤0/置信度/估算标记；不直接触发高风险操作 |
| P0-12 | P0 | Steward Auto-Governance 与边界矛盾 | Phase 1 只做 Finding→推荐→Operation Proposal→人工确认，不新增自动执行政策 |
| P1-1 | P1 | Search Projection 权限不足 | 增加 visibility/owner_id/classification/resource_scope，查询时过 AuthorizationService，增加 trigram + 前缀匹配 |
| P1-2 | P1 | Command Palette 写操作无治理 | 写命令必须打开正式表单/确认→权限检查→Operation，不直接执行 |
| P1-3 | P1 | Runbook 无版本化 | 增加 Draft/Published/Deprecated 状态机 + Change History + Input Schema + 引用不可变 |
| P1-4 | P1 | Notification 无可靠投递 | 增加 Delivery 记录/重试/Dead Letter/Webhook 签名/SSRF 防护/URL 允许策略 |
| P1-5 | P1 | Saved View 无权限规则 | 增加 Owner/Tenant/修改删除权限/加载时重新检查/Schema 兼容 |
| P1-6 | P1 | BFF partial failure 静默吞错 | 定义必需 vs 可选数据/Section 状态/Retry 入口/空数组不伪装错误 |
| P1-7 | P1 | 大规模导出同步经 BFF | 大导出改异步 Operation→后台生成→Artifact→下载，设同步上限 |
| P1-8 | P1 | Rate Limit 统一 100/min | 改为按接口分策略（Login: IP+Username, Search: Principal, Export: Principal+并发, SSE: Principal+连接数, 写: Principal+Tenant） |
| P1-9 | P1 | Change Management 应为事件投影 | changes 从 Operation/Config Rollout/Model Deployment/权限变更投影生成，rollback_rate 由统计接口计算 |

**估算修订**：55–79 人日 → **165–251 人日**，拆分为 Phase 1A（70–100）+ Phase 1B（90–140）。

---

## 一、Phase 1 范围与边界

### 目标

形成完整统一控制中心（Control Center 1.0），覆盖设计方案 §6–§17 的信息架构、核心页面、BFF 聚合层和后端服务补全。

### 拆分为两个内部版本

#### Phase 1A：Control Center Foundation（70–100 人日）

目标：统一产品框架和可靠数据基础。

#### Phase 1B：Operations & Intelligence（90–140 人日）

目标：形成完整运维治理闭环。

二者全部完成后，发布为 **LakeMind Control Center 1.0**。

### 信息架构（修正 P0-1）

**8 个业务一级导航 + Steward 全局右侧助手**：

```
Home
Organization
Assets
Runtime
AI & Models
Operations
Security & Governance
Platform
```

**Steward 定位**：
- 全局右侧助手（在任意对象页可打开 Steward Context Panel）
- Steward Workspace 放在 Operations 下（`/operations/steward`）
- Daily Brief 放在 Home 下（`/home/daily-brief`）
- 不作为独立一级导航

### 不包含（Phase 2–4）

- LakeMind Control Graph / Blast Radius / Evidence-based RCA
- Auto-Governance（自动执行治理动作）
- LLM 驱动对话（Phase 1 Steward 用规则引擎 + 模板）
- Predictive Capacity / Cost Attribution / Quality Score / Policy Simulation
- 多节点 / HA / Failover / Cluster Maintenance
- Studio 协同

### 设计约束

1. **Steward 用规则引擎 + 模板**，不接 LLM，不新增自动执行政策（P0-12）
2. **单实例部署**，Rollout API 保留多实例语义但 UI 只展示单实例
3. **可观测性基础先行**，OpenTelemetry 采集契约 + 历史存储在 WP-OBS 完成
4. **Search Projection 用 PG tsvector + GIN + trigram**，不引入 Elasticsearch
5. **SSE + Durable Event Backbone**，用 Valkey Streams + 持久化事件表支持断线重放
6. **禁止挂载 Docker Socket**，资源指标通过独立只读 Telemetry Agent 采集（P0-10）
7. **Capability 驱动权限**，前端根据 effective_permissions 判断，不硬编码角色（P0-6）
8. **Tenant 切换经 Server 验证 Membership**，BFF 不自行修改 tenant_id（P0-5）

---

## 二、Phase 1A：Control Center Foundation

### 工作包总览

| WP | 名称 | 核心目标 | 估算(人日) |
|----|------|----------|-----------|
| WP-C | 契约与 UX 冻结 | 对象模型/Capability 矩阵/事件 Schema/状态机/API 契约/高保真原型 | 8–12 |
| WP0 | App Shell 与设计系统 | 8 导航 + 上下文条 + Capability 路由 + 设计系统 + Object Page + Data Explorer | 12–18 |
| WP-OBS | 可观测性基础 | OTel 采集 + 历史存储 + Metrics/Logs/Traces/Events 查询 + SLO + Retention | 18–30 |
| WP-EVT | Durable Event 与 SSE | 持久化事件流 + Valkey Streams + SSE 网关 + 断线重连 + Notification | 10–15 |
| WP1 | Mission Control 基础版 | 4 屏 + 事实源定义 + View Model + 角色化 + 下钻 | 8–12 |
| WP2 | Search / Command Palette / Saved Views | Search Projection + ⌘K + 治理写操作 + Saved Views 权限 | 10–15 |
| WP8 | BFF 聚合层 | View Model + 跨服务聚合 + partial failure + 导出 + Rate Limit + Error Normalization | 10–15 |
| WP9A | Organization Service | Tenant CRUD + Membership + Group + Quota + Entitlement + Budget + Usage 聚合 | 8–12 |
| WP9B | Search Service | Projection 更新 + 全量重建 + 权限过滤 + trigram | 3–5 |

**Phase 1A 合计：77–119 人日**（取中值 70–100）

### 依赖图

```
WP-C (契约冻结)
  ↓
WP0 (App Shell) ──→ WP2 (Search/⌘K/Saved Views)
  ↓                    ↑
WP-OBS (可观测性) ─→ WP1 (Mission Control)
  ↓
WP-EVT (Event + SSE)
  ↓
WP9A (Organization) ──→ WP8 (BFF 聚合)
WP9B (Search)
```

---

## 三、WP-C：契约与 UX 冻结

**目标**：在编码前冻结全部产品语义、状态机、API 契约和 UX 原型。

### WP-C-T1：Phase 1 对象模型与状态机

**交付物**：
- `.agent/adr/ADR-017-phase1-object-model.md` — 全部对象模型
- `.agent/adr/ADR-018-phase1-state-machines.md` — 状态机定义

**对象模型**：
- Alert（OPEN/ACKNOWLEDGED/RESOLVED/SILENCED + Auto Resolve + Reopen）
- Incident（OPEN/INVESTIGATING/MITIGATING/MONITORING/RESOLVED）
- Runbook（DRAFT/PUBLISHED/DEPRECATED + Version History）
- Notification（PENDING/DELIVERED/FAILED/DEAD_LETTER + Retry）
- Change（从 Operation/Config Rollout/Model Deployment 投影）
- SavedView（Owner/Tenant/Shared + Schema 兼容版本）
- StewardFinding（Phase 0 已有，扩展 suggested_action → Operation Proposal）

**状态机**：每个状态机定义合法转换 + 转换条件 + 审计要求。

### WP-C-T2：Capability 权限矩阵（修正 P0-6）

**交付物**：
- `.agent/adr/ADR-019-capability-model.md`

**设计**：
```
/auth/me 返回:
{
  "principal_id": "...",
  "active_tenant_id": "...",
  "effective_permissions": ["model:read", "audit:read", "operation:approve", ...],
  "capabilities": {
    "can_view_models": true,
    "can_manage_tenants": false,
    "can_read_audit": true,
    "can_approve_operations": true,
    "can_manage_security": false,
    ...
  },
  "accessible_tenants": [{"tenant_id": "...", "membership_status": "ACTIVE", "role": "..."}],
  "feature_flags": {"steward_context_panel": true, ...}
}
```

前端 RouteGuard 根据 `capabilities` 判断，不硬编码角色名。后端仍是最终授权者。

### WP-C-T3：事件 Schema 与 Alert 规则模板（修正 P0-4, P0-8）

**交付物**：
- `.agent/adr/ADR-020-event-schema.md`
- `.agent/adr/ADR-021-alert-rule-template.md`

**事件 Schema**：
```sql
event_stream (
  event_id UUID PK,
  event_type VARCHAR,       -- job.status_changed, alert.triggered, ...
  tenant_id UUID,
  resource_type VARCHAR,
  resource_id UUID,
  sequence BIGINT,           -- 全局递增序列
  created_at TIMESTAMP,
  payload JSONB,
  retention_until TIMESTAMP
)
```

**Alert 规则模板**（非任意表达式）：
```yaml
rule:
  template: job_failure_rate
  metric: job.failure_rate
  aggregation: rate
  window: 5m
  group_by: [tenant_id]
  operator: ">"
  threshold: 0.2
  for_duration: 10m
  evaluation_interval: 30s
  severity: warning
  auto_resolve_after: 30m
  alert_storm_limit: 10  -- 同 group 每分钟最多触发 10 条
```

### WP-C-T4：Observability Provider 契约

**交付物**：
- `.agent/adr/ADR-022-observability-provider.md`

定义 Metrics/Logs/Traces/Events Provider 接口、时间序列 Schema、采样策略、保留策略、权限过滤。

### WP-C-T5：高保真原型与用户旅程

**交付物**：
- `design/prototypes/` — 7 个核心页面高保真原型
- `design/user-journeys/` — 7 个核心用户旅程

**7 个用户旅程**：
1. 创建和运营 Tenant
2. 定位失败 Job
3. 模型路由变更
4. Knowledge DEGRADED 诊断
5. 配置变更与回滚
6. 安全审计
7. Steward 治理（Finding → Runbook → Operation → 验证）

### WP-C-T6：API 契约与验收指标

**交付物**：
- `docs/api-spec/v0.2.2/control-center-phase1.yaml` — OpenAPI 契约
- 每个端点定义：请求/响应 Schema、权限要求、审计、Rate Limit

---

## 四、WP0：App Shell 与设计系统

**目标**：建立 8 导航 + 全局上下文条 + Capability 路由 + 设计系统 + 对象页框架 + Data Explorer。

### WP0-T1：路由重组与 8 导航层级

**导航结构**（修正 P0-1）：

```
Home
  ├─ Mission Control (/)
  ├─ My Tasks (/my-tasks)
  ├─ Daily Brief (/home/daily-brief)
  ├─ Notifications (/home/notifications)
  ├─ Recent Changes (/home/recent-changes)
  └─ Saved Views (/home/saved-views)

Organization (/organization)
  ├─ Tenants
  ├─ Users & Groups
  ├─ Service Accounts
  ├─ Environments
  ├─ Quotas & Entitlements
  └─ Usage & Budgets

Assets (/assets)
  ├─ Catalog
  ├─ Knowledge
  ├─ Skills
  ├─ Memory
  ├─ Bindings
  ├─ Lineage
  └─ Quality

Runtime (/runtime)
  ├─ Jobs
  ├─ Attempts
  ├─ Artifacts
  ├─ Schedules
  ├─ Compute / Ray
  └─ Policies

AI & Models (/models)
  ├─ Models
  ├─ Deployments
  ├─ Profiles & Routes
  ├─ Embedding Spaces
  ├─ Usage
  ├─ Quality & Evaluation
  ├─ Test Console
  └─ Provider Secrets

Operations (/operations)
  ├─ Operations
  ├─ Approvals
  ├─ Alerts
  ├─ Incidents
  ├─ Runbooks
  ├─ Changes
  ├─ Maintenance
  ├─ Notifications
  └─ Steward Workspace

Security & Governance (/security)
  ├─ Principals
  ├─ Roles & Policies
  ├─ Tokens & Sessions
  ├─ Secrets
  ├─ Access Explorer
  ├─ Findings
  ├─ Audit
  └─ Retention & Classification

Platform (/platform)
  ├─ Services & Topology
  ├─ Resources & Capacity
  ├─ Configuration
  ├─ Versions & Upgrades
  ├─ Storage
  ├─ Observability
  ├─ Feature Flags
  └─ System Info
```

**Steward 全局右侧助手**：在任意页面可通过按钮打开 Steward Context Panel 抽屉。

### WP0-T2：全局上下文条与 Tenant Selector（修正 P0-5）

**Tenant Selector 安全模型**：
```
POST /auth/switch-tenant
  → BFF 调用 Server: POST /api/v1/security/switch-tenant
  → Server 验证用户拥有该 Membership（membership_status = ACTIVE）
  → Server 返回新的授权上下文（新 token + security_version）
  → BFF 更新 Session: active_membership_id, active_tenant_id, token
  → 每次请求 Server 仍重新验证 Membership 有效
  → Tenant Suspend 或 Membership 撤销后立即失效
```

**禁止**：BFF 自行修改 Valkey 中的 tenant_id。

### WP0-T3：Capability 路由守卫（修正 P0-6）

**实现**：
- `/auth/me` 返回 `capabilities` 对象
- `RouteGuard` 根据 `capabilities[requiredCapability]` 判断
- 无权访问显示 403 页面
- 导航菜单根据 capabilities 动态生成，不硬编码角色

### WP0-T4：设计系统与状态语义统一

（与 v1 相同，保留 ObjectPageLayout / DataExplorer / StatusBadge / HealthScore / ContextBar）

### WP0-T5：Data Explorer Framework

（与 v1 相同，增加 Saved Views 权限检查：加载时重新验证用户是否有权访问 Saved View 引用的字段）

### WP0-T6：Feature Flag 基础设施

（与 v1 相同）

---

## 五、WP-OBS：可观测性基础（修正 P0-3）

**目标**：建立遥测采集、历史存储、查询接口和 SLO 计算基础，为 Mission Control、Alert、Resource Center 提供事实数据源。

**门禁**：WP-OBS 完成前，Mission Control、Resource Center、Topology、Capacity 只能展示当前状态，不宣称完成历史趋势和预测。

### WP-OBS-T1：OpenTelemetry 采集契约

**改动文件**：
- `LakeMindServer/src/lakemind_server/observability/otel_config.py` — 新建
- `LakeMindControlCenter/bff/otel_config.py` — 新建

**统一标签**（设计 §16.2）：
```
tenant_id, principal_id, request_id, correlation_id, service, instance,
asset_id, job_id, attempt_id, skill_id/version, model_id, deployment_id,
operation_id, environment, version
```

**采集器**：
- LakeMindServer: FastAPI 中间件自动采集 HTTP 请求 Metrics + Spans
- BFF: 同上
- Ray: Ray metrics → OTel exporter
- ModelServing: litellm 日志 → OTel

### WP-OBS-T2：Metrics 历史存储

**改动文件**：
- `LakeMindServer/migrations/versions/015_observability.py` — 新建
- `LakeMindServer/src/lakemind_server/observability/metrics_store.py` — 新建

**存储方案**：PG 时序表（单节点阶段不引入 Prometheus）

```sql
metrics_series (
  id BIGSERIAL PK,
  tenant_id UUID,
  metric_name VARCHAR,     -- e.g. job.failure_rate, model.latency_p95
  labels JSONB,            -- {deployment_id: "...", service: "..."}
  value DOUBLE PRECISION,
  observed_at TIMESTAMP,
  retention_until TIMESTAMP
)
-- 分区按天，保留 30 天
-- BRIN 索引 on observed_at
-- GIN 索引 on labels
```

**采集**：各服务每 30s 写入 Metrics（CPU/Memory/Latency/ErrorRate/Throughput/QueueDepth 等）

### WP-OBS-T3：Logs / Traces / Events 查询

**改动文件**：
- `LakeMindServer/src/lakemind_server/observability/query_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/observability.py` — 新建

**API**：
- `GET /api/v1/observability/metrics?name=xxx&labels=xxx&from=xxx&to=xxx` — 时序查询
- `GET /api/v1/observability/logs?tenant=xxx&service=xxx&from=xxx&to=xxx&level=xxx` — 日志查询
- `GET /api/v1/observability/traces?trace_id=xxx` — Trace 查询
- `GET /api/v1/observability/events?resource_type=xxx&resource_id=xxx` — 事件时间线

**权限**：所有查询按 SecurityContext 过滤 tenant_id。

### WP-OBS-T4：SLO 计算

**改动文件**：
- `LakeMindServer/src/lakemind_server/observability/slo_service.py` — 新建

**SLO 定义**（设计 §16.3）：
- API Availability: 99.9%
- Job Success Rate: 95%
- Model Serving Latency P95: < 2s
- Knowledge Search Latency P95: < 500ms
- Config Convergence: < 5min

**计算**：每 5min 从 metrics_series 计算 SLI → Error Budget → Burn Rate。

### WP-OBS-T5：Telemetry Agent（修正 P0-10）

**改动文件**：
- `LakeMindServer/src/lakemind_server/observability/telemetry_agent.py` — 新建

**安全采集**：
- **禁止**挂载 Docker Socket
- **禁止**通过 Shell 执行命令
- PostgreSQL: 只读 SQL 查询（`pg_stat_activity`, `pg_stat_database`）
- Valkey: `INFO` 命令（只读）
- SeaweedFS: HTTP `/cluster/status`（只读）
- Ray: Ray Dashboard API（只读，受控 Provider）
- 系统指标：cgroup v2 只读文件（`/sys/fs/cgroup/.../cpu.stat`, `memory.current`）

**采集频率**：每 30s 采集一次，写入 metrics_series。

---

## 六、WP-EVT：Durable Event 与 SSE（修正 P0-4）

**目标**：建立可重放的持久化事件流 + SSE 网关 + Notification Center。

### WP-EVT-T0：Durable Event Backbone

**改动文件**：
- `LakeMindServer/migrations/versions/016_event_stream.py` — 新建
- `LakeMindServer/src/lakemind_server/events/event_store.py` — 新建
- `LakeMindServer/src/lakemind_server/events/event_publisher.py` — 新建

**持久化事件表**：
```sql
event_stream (
  event_id UUID PK DEFAULT gen_random_uuid(),
  event_type VARCHAR NOT NULL,
  tenant_id UUID NOT NULL,
  resource_type VARCHAR,
  resource_id UUID,
  sequence BIGSERIAL,          -- 全局递增，用于 Last-Event-ID
  created_at TIMESTAMP DEFAULT now(),
  payload JSONB NOT NULL,
  retention_until TIMESTAMP,
  -- 分区按天
)
CREATE INDEX idx_event_seq ON event_stream(sequence);
CREATE INDEX idx_event_tenant_type ON event_stream(tenant_id, event_type, sequence);
```

**Valkey Streams**：用于实时推送（XADD/XREADGROUP），event_stream 表用于持久化和重放。

**发布流程**：
```
Service 产生事件
  → 写入 event_stream 表（获取 sequence）
  → XADD 到 Valkey Stream（payload 含 event_id + sequence）
  → BFF SSE 网关 XREADGROUP 消费
```

**断线重连**：
```
客户端断线 → 带 Last-Event-ID (sequence) 重连
  → BFF 从 event_stream 表查询 sequence 之后的事件
  → 回放给客户端
  → 然后继续 XREADGROUP 实时消费
```

**Job 日志独立通道**：`job.log_appended` 不进入通用事件总线，使用独立日志 Tail 端点。

### WP-EVT-T1：SSE 实时网关

**改动文件**：
- `bff/app.py` — `GET /events/stream` SSE 端点
- `bff/sse_manager.py` — 新建

**事件类型**：
```
job.status_changed, job.resource_update
operation.status_changed, operation.approval_needed
alert.triggered, alert.resolved, alert.acknowledged
incident.created, incident.updated, incident.status_changed
config.rollout_progress, config.drift_detected
model.deployment_health_changed
service.health_changed
steward.finding_created, steward.finding_updated
notification.created
```

**实现要点**：
- SSE 连接用 Session 认证（Cookie + CSRF）
- Valkey Streams XREADGROUP 消费
- 支持 Last-Event-ID 断线重连（从 event_stream 表回放）
- 每连接心跳（15s）
- 背压处理（慢客户端丢弃旧事件，保留最新）
- 事件按 tenant_id 过滤（权限）
- 连接数限制（per principal）

### WP-EVT-T2：Notification Service（修正 P1-4）

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/notification_service.py` — 新建
- `LakeMindServer/migrations/versions/017_notifications.py` — 新建

**数据模型**：
```sql
notifications (
  id UUID PK, tenant_id UUID, principal_id UUID,
  type VARCHAR, severity VARCHAR,
  title TEXT, body TEXT, metadata JSONB,
  read_at TIMESTAMP, created_at TIMESTAMP
)
notification_subscriptions (
  id UUID PK, principal_id UUID,
  event_type VARCHAR, severity_filter VARCHAR[],
  tenant_filter UUID[], resource_filter JSONB,
  channel VARCHAR  -- in_app / email / webhook
)
notification_deliveries (
  id UUID PK, notification_id UUID,
  channel VARCHAR, status VARCHAR,  -- PENDING/DELIVERED/FAILED/DEAD_LETTER
  attempt_count INT, max_retries INT DEFAULT 3,
  next_retry_at TIMESTAMP, delivered_at TIMESTAMP,
  error TEXT,
  webhook_url TEXT, webhook_signature VARCHAR
)
```

**可靠投递**：
- in_app: 写 DB + SSE 推送
- email: SMTP + 重试（3 次，指数退避）+ Dead Letter
- webhook: POST + HMAC 签名 + SSRF 防护（URL 允许列表）+ 重试 + Dead Letter

**SSRF 防护**：webhook URL 必须在允许列表内（管理员配置），禁止内网地址。

### WP-EVT-T3：Notification Center UI

- Bell 图标 + 未读数 Badge
- 下拉面板 + 完整页面（DataExplorer）
- 订阅管理 Tab

---

## 七、WP1：Mission Control 基础版（修正 P0-7）

**目标**：4 屏首页，每个卡片定义事实源、计算公式、刷新频率和新鲜度。

### WP1-T1：BFF Mission Control View Model

**每个卡片定义**：

| 卡片 | 事实源 | 计算公式 | 刷新频率 | 新鲜度 | 下钻 |
|------|--------|----------|----------|--------|------|
| Pending Approvals | `GET /operations?status=APPROVAL_REQUIRED` | count | 10s | 10s | `/operations/approvals` |
| Critical Findings | `GET /steward/findings?severity=CRITICAL&status=OPEN` | count | 30s | 30s | `/steward/findings` |
| Failed Jobs (24h) | `GET /jobs?status=FAILED&from=now-24h` | count | 30s | 30s | `/runtime/jobs?status=FAILED` |
| Degraded Assets | `GET /assets?health=DEGRADED` | count | 60s | 60s | `/assets?health=DEGRADED` |
| Unhealthy Deployments | `GET /models/deployments?health=UNHEALTHY` | count | 30s | 30s | `/models/deployments?health=UNHEALTHY` |
| Platform Health (4 Plane) | `GET /observability/metrics?name=service.health` | avg per plane | 30s | 30s | `/platform/services` |
| Error Budget | `GET /observability/slo` | 1 - (errors / budget) | 5min | 5min | `/platform/observability` |
| CPU Usage | `GET /observability/metrics?name=cpu.usage` | current value | 30s | 30s | `/platform/resources` |
| Memory Usage | `GET /observability/metrics?name=memory.usage` | current value | 30s | 30s | `/platform/resources` |
| Storage Usage | `GET /observability/metrics?name=storage.usage` | current value | 60s | 60s | `/platform/storage` |
| Job Queue Depth | `GET /observability/metrics?name=job.queue_depth` | current value | 10s | 10s | `/runtime/jobs` |
| Tenant Usage Top N | `GET /tenants?sort=usage&limit=10` | sum per tenant | 5min | 5min | `/organization/tenants` |
| Knowledge Status | `GET /assets?type=knowledge` | group by status | 60s | 60s | `/assets/knowledge` |
| Skill Status | `GET /assets?type=skill` | group by status | 60s | 60s | `/assets/skills` |

**View Model 结构**（每个字段含元数据）：
```json
{
  "needs_action": {
    "pending_approvals": {
      "value": 3,
      "observed_at": "2026-07-16T07:00:00Z",
      "freshness_seconds": 10,
      "source": "operations_api",
      "partial": false,
      "items": [...]
    }
  }
}
```

**partial failure 处理（修正 P1-6）**：
- 必需数据失败 → 整体 503
- 可选数据失败 → `partial: true` + 该 section 标记 error
- 数据陈旧 → `stale: true` + 最后更新时间
- 空数组不伪装错误（区分 "查询成功返回 0 条" vs "查询失败"）

### WP1-T2：四屏首页布局

（与 v1 相同，但每个数字必须可下钻，数据来自 View Model）

### WP1-T3：角色化与下钻

- 根据 `capabilities` 决定显示哪些屏
- 每个数字是 Link，跳转到过滤后列表

---

## 八、WP2：Search / Command Palette / Saved Views

### WP2-T1：Search Projection 后端（修正 P1-1）

**增强权限模型**：
```sql
search_projection (
  object_type VARCHAR, object_id UUID,
  tenant_id UUID, title TEXT, subtitle TEXT,
  keywords TEXT, metadata JSONB,
  visibility VARCHAR,     -- public / private / shared
  owner_id UUID,
  classification VARCHAR, -- e.g. internal / confidential
  resource_scope VARCHAR,
  status VARCHAR,
  tsv TSVECTOR,
  updated_at TIMESTAMP
)
```

**查询时过 AuthorizationService**：不认为"进入投影就可见"，每次查询结果再过权限过滤。

**搜索策略**：tsvector（全文）+ trigram（模糊/前缀）+ 精确 ID 匹配。

### WP2-T2：全局搜索 UI

（与 v1 相同）

### WP2-T3：Command Palette（修正 P1-2）

**写操作治理**：
```
选择写命令（如 "Cancel Job"）
  → 打开正式确认表单（显示影响、风险、原因输入）
  → 权限检查
  → 创建 Operation
  → 显示结果
```

**禁止**：在搜索结果旁直接提供无确认的一键执行。

### WP2-T4：Saved Views（修正 P1-5）

**权限规则**：
- Owner 可修改/删除
- Shared View 在 Tenant 内共享
- 加载时重新检查用户是否有权访问 Saved View 引用的字段
- Schema 版本兼容（页面升级后旧 View 标记 incompatible）

---

## 九、WP8：BFF 聚合层增强

### WP8-T1：View Model 聚合端点

（与 v1 相同，增加 partial failure 处理规范）

### WP8-T2：导出（修正 P1-7）

- 小规模（< 10000 行）：同步 CSV/JSON 流式输出
- 大规模（≥ 10000 行）：异步 Export Operation → 后台生成 → Artifact → 下载链接
- 同步导出上限：10000 行

### WP8-T3：Rate Limit（修正 P1-8）

| 接口类型 | 限流维度 | 默认限制 |
|----------|----------|----------|
| Login | IP + Username | 10/min |
| Search | Principal | 60/min |
| Export | Principal + 并发数 | 1 并发, 10/hour |
| SSE | Principal + 连接数 | 5 连接 |
| 写操作 | Principal + Tenant | 100/min |
| 健康检查 | Service Identity | 不限 |
| Webhook | 目标地址 + 租户 | 100/min |

### WP8-T4：Error Normalization

（与 v1 相同）

---

## 十、WP9A：Organization Service

**目标**：补齐 Organization 全部后端和前端。

### WP9A-T1：Tenant 增强后端

- Tenant 创建向导后端（10 步 + Provisioning Saga）
- Group 管理 API
- Entitlement 管理 API
- Quota 管理 API
- Budget 管理 API
- Usage 聚合 API（从 metrics_series 聚合）

### WP9A-T2：Organization 前端

- Tenants 列表 + 创建向导 + 详情页（Overview/Members/Entitlements/Quotas/Resources/Assets/Jobs/Config/Security/Audit）
- Users & Groups 页面
- Service Accounts 页面
- Environments 页面
- Quotas & Entitlements 页面
- Usage & Budgets 页面

---

## 十一、WP9B：Search Service

（与 WP2-T1 配合，补全投影更新机制）

- 各 Service Outbox 事件 → Search Projection 更新
- 全量重建端点
- Tombstone 删除
- Projection Lag 监控
- 幂等消费
---

## 十二、Phase 1B：Operations & Intelligence

### 工作包总览

| WP | 名称 | 核心目标 | 估算(人日) |
|----|------|----------|-----------|
| WP4 | Alert / Incident / Runbook | 模板化规则 + 事件表 + 版本化 Runbook | 18–25 |
| WP5 | Resource / Topology / Capacity / Storage | Telemetry Agent + 拓扑 + 容量预测 + Storage | 18–28 |
| WP6 | Steward Context Panel | 对象页内嵌 + Daily Brief + Finding→Proposal 闭环 | 10–16 |
| WP7 | Saved Views 与 Preferences 完善 | 持久化 + 共享 + Dashboard Layout | 2–3 |
| WP9C | Notification Service 完善 | 投递 + 重试 + Dead Letter + Webhook | 5–8 |
| WP9D | Change Management | 事件投影 + 统计 | 5–7 |
| WP-MODEL | 模型运营增强 | Embedding Space + Usage + Quality + Test Console + Provider Secrets | 10–15 |
| WP-SEC | 安全中心增强 | Principals + Roles + Access Explorer + Tokens + Secrets + Findings + Retention | 15–25 |
| WP10 | 测试与硬化 | E2E + 性能 + 安全 + 验收证据 | 18–25 |

**Phase 1B 合计：101–152 人日**（取中值 90–140）

### 依赖图

```
Phase 1A 完成
  ↓
WP4 (Alert/Incident/Runbook) ──→ WP6 (Steward)
  ↓
WP5 (Resource/Topology/Capacity)
  ↓
WP-MODEL (模型运营) ──并行──→ WP-SEC (安全中心)
  ↓
WP9C (Notification 完善) ──→ WP9D (Change)
  ↓
WP10 (测试与硬化)
```

---

## 十三、WP4：Alert / Incident / Runbook（修正 P0-8, P0-9, P1-3）

### WP4-T1：Alert Service 后端（模板化规则）

**规则模型**（修正 P0-8）：
```sql
alert_rules (
  id UUID PK, name VARCHAR, description TEXT,
  template VARCHAR NOT NULL,    -- 模板名，如 job_failure_rate
  metric VARCHAR NOT NULL,
  aggregation VARCHAR NOT NULL,  -- rate / avg / sum / max / min
  window VARCHAR NOT NULL,       -- 5m / 1h / 24h
  operator VARCHAR NOT NULL,     -- > / < / >= / <= / ==
  threshold DOUBLE PRECISION,
  group_by JSONB,                -- ["tenant_id"]
  for_duration VARCHAR,          -- 持续多久才触发
  evaluation_interval VARCHAR DEFAULT '30s',
  severity VARCHAR NOT NULL,
  auto_resolve_after VARCHAR,    -- 如 30m
  alert_storm_limit INT DEFAULT 10,
  tenant_scope UUID[],
  enabled BOOLEAN,
  owner_id UUID,
  created_at TIMESTAMP
)
```

**规则评估**：
- 定时扫描（按 evaluation_interval）
- Watermark 机制（避免重复评估同一窗口）
- Auto Resolve：条件不再满足后 auto_resolve_after 时间自动关闭
- Reopen：已自动关闭的 Alert 在条件再次满足时重新打开
- Alert Storm Protection：同 group_by 每分钟最多触发 alert_storm_limit 条
- Dedup Fingerprint：相同 fingerprint 的 Alert 合并，count++
- Silence Expiry：静默有过期时间

**规则模板列表**（Phase 1 只实现以下模板）：
1. `job_failure_rate` — Job 失败率超阈值
2. `model_unhealthy` — Deployment health = UNHEALTHY
3. `asset_drift` — Asset health = DEGRADED
4. `capacity_forecast` — 预计耗尽 < N 小时
5. `config_drift` — Desired ≠ Active 超过 N 分钟
6. `security_finding` — Steward Finding severity = CRITICAL
7. `tenant_quota_exceeded` — Tenant 用量超配额
8. `slo_burn_rate` — SLO Error Budget 消耗过快

**禁止**：任意表达式、任意 SQL、无法校验的规则。

### WP4-T2：Incident 聚合（事件表模型）

**数据模型**（修正 P0-9）：
```sql
incidents (
  id UUID PK, title TEXT, severity VARCHAR,
  status VARCHAR,  -- OPEN/INVESTIGATING/MITIGATING/MONITORING/RESOLVED
  commander_id UUID, tenant_id UUID,
  affected_objects JSONB,    -- 不使用 blast_radius_json
  root_cause TEXT,
  created_at TIMESTAMP, resolved_at TIMESTAMP
)
incident_events (
  id UUID PK, incident_id UUID,
  event_type VARCHAR,  -- created/status_changed/alert_linked/note/action_taken/root_cause_set
  event_data JSONB,
  created_by UUID, created_at TIMESTAMP
)
incident_alerts (
  incident_id UUID, alert_id UUID
)
```

**不包含**：blast_radius_json（Phase 2 能力）、自动 Blast Radius 计算。

### WP4-T3：Runbook 版本化（修正 P1-3）

**数据模型**：
```sql
runbooks (
  id UUID PK, name VARCHAR, description TEXT,
  current_version INT DEFAULT 0,
  status VARCHAR DEFAULT 'DRAFT',  -- DRAFT/PUBLISHED/DEPRECATED
  owner_id UUID,
  authorized_roles VARCHAR[],
  created_at TIMESTAMP
)
runbook_versions (
  id UUID PK, runbook_id UUID,
  version INT NOT NULL,
  trigger_condition JSONB,
  diagnosis_steps JSONB,
  auto_steps JSONB,
  manual_steps JSONB,
  risk_level VARCHAR,
  rollback_plan TEXT,
  validation_steps JSONB,
  input_schema JSONB,
  step_permissions JSONB,    -- 每步所需权限
  timeouts JSONB,
  created_by UUID, created_at TIMESTAMP,
  published_at TIMESTAMP,
  -- 不可变：Published 后不可修改，只能新版本
  UNIQUE(runbook_id, version)
)
```

**约束**：
- Published Runbook 不可修改，只能创建新版本
- 已被 Finding/Incident 引用的 Published Runbook 不能静默修改
- Deprecated Runbook 不能被新 Finding 引用，但旧引用仍可查看

### WP4-T4：Alert/Incident/Runbook UI

- Alert 列表（DataExplorer + severity 颜色 + Acknowledge/Resolve/Silence）
- Incident 详情（ObjectPageLayout + incident_events Timeline + 关联 Alert 列表 + affected_objects）
- Runbook 详情（版本历史 + 步骤展示 + 执行按钮 → 创建 Operation）

---

## 十四、WP5：Resource / Topology / Capacity / Storage（修正 P0-10, P0-11）

### WP5-T1：Service Topology

**后端**：
- `GET /api/v1/services` — 服务列表
- `GET /api/v1/services/topology` — 拓扑图（节点 + 边 + 状态）
- 节点状态来自 `GET /observability/metrics?name=service.health`
- 边的 error_rate / latency / traffic 来自 metrics_series 历史聚合

**前端**：交互拓扑图（react-flow 或自定义），节点可点击跳转。

### WP5-T2：Resource Center（Telemetry Agent 采集）

**数据来源**（修正 P0-10）：
- **禁止**挂载 Docker Socket
- **禁止** Shell 调用
- CPU/Memory: cgroup v2 只读文件
- PostgreSQL: 只读 SQL（`pg_stat_activity`）
- Valkey: `INFO` 命令
- SeaweedFS: HTTP `/cluster/status`
- Ray: Ray Dashboard API（受控 Provider）

**所有指标写入 metrics_series**，Resource Center 从 metrics_series 查询，不直接调用采集器。

### WP5-T3：Capacity Planning（修正 P0-11）

**可信预测**：
- 依赖 WP-OBS 历史存储（至少 7 天数据）
- 数据少于最低样本数（48 个点 = 24h @ 30min 间隔）→ 不预测，显示 "数据不足"
- slope ≤ 0 → 显示 "无耗尽趋势"
- 异常点处理：IQR 过滤
- 显示置信度（R² 值）
- 标记 "估算"（非精确预测）
- **不直接触发高风险操作**：扩容/限流只能作为 Operation Proposal

### WP5-T4：Storage 视图

- PostgreSQL: 容量/连接/慢请求/Lock/Migration/Backup
- S3/SeaweedFS: 使用量/Tenant 分布/Orphan/Retention
- Lance: Index 数量/空间/Drift/Rebuild/Query Latency
- Valkey: Memory/Key/TTL/Eviction/Session

---

## 十五、WP6：Steward Context Panel（修正 P0-12）

**目标**：Steward 三形态（全局助手 + 对象页内嵌 + 后台巡检），不新增自动执行政策。

### WP6-T1：Steward Context Panel 组件

- 可嵌入任意对象页的右侧抽屉
- 预设问题模板（按对象类型）
- Phase 1 用规则引擎 + 模板生成回答
- 回答只使用用户有权访问的数据
- 每条回答附证据链接

### WP6-T2：Daily Brief

- 规则引擎扫描各 Service 数据，生成结构化 Brief
- 每条结论附证据链接
- 缓存 5 分钟（Valkey）

### WP6-T3：行动闭环（修正 P0-12）

**Phase 1 闭环**（不新增 Auto-Governance）：
```
Steward Finding
  → 推荐 Runbook
  → 创建 Operation Proposal（不自动执行）
  → 人工确认或已有 Operation 策略执行
  → 验证
  → Steward 总结
```

**Phase 0 已有的低风险自动 Operation 保留**，但 Phase 1 不扩大其动作范围。

**不使用 "Root Cause" 作为确定结论**，使用：
- Known Failure Pattern
- Likely Cause
- Evidence
- Suggested Diagnosis

### WP6-T4：Finding 视图增强

- DataExplorer 列表 + ObjectPageLayout 详情
- Evidence Drawer + Likely Cause + Recommended Runbook + Operation Proposal + Action History

---

## 十六、WP-MODEL：模型运营增强（修正 P0-2 缺口）

**目标**：补齐 AI & Models 下全部页面。

### WP-MODEL-T1：Embedding Space 管理

- Space ID / Model Revision / Dimension / Normalization / Distance Metric / Index Version
- Knowledge 使用量 / 兼容 Deployment / Incompatible Warning
- 禁止不兼容模型静默写入

### WP-MODEL-T2：Model Usage

- 成功率/延迟/Token/Cost per Tenant/Skill/Job
- 从 metrics_series 聚合

### WP-MODEL-T3：Quality & Evaluation

- 输出质量 / Drift / Safety Finding / Rate Limit / Cache

### WP-MODEL-T4：Model Test Console

- 选择 Profile/Deployment → 查看响应/延迟/Token/Cost
- 对比多个 Deployment
- 生产 Secret 不向浏览器暴露
- 保存测试证据

### WP-MODEL-T5：Provider Secrets 管理

- Secret Metadata / Scope / Version / Owner / Used By / Last Used / Rotation / Expiration
- **绝不显示完整明文**

---

## 十七、WP-SEC：安全中心增强（修正 P0-2 缺口）

**目标**：补齐 Security & Governance 下全部页面。

### WP-SEC-T1：Principals 管理

- User/Group/Agent/Service Account/Steward/Worker Identity
- 创建/禁用/Role Binding/Token/Session/活动/所属 Tenant/最近访问/风险

### WP-SEC-T2：Roles & Policies

- Built-in Role / Custom Role / Permission / Resource Scope / Tenant Scope / Condition
- Policy Inheritance / Effective Permission

### WP-SEC-T3：Access Explorer

- "某 Principal 能访问什么？" / "某 Asset 谁能访问？"
- Policy Simulation: Principal + Action + Resource + Context → Allow/Deny + Explanation

### WP-SEC-T4：Tokens & Sessions

- Token Hash Metadata / Scope / Expiration / Last Used / IP/Client / Revoke
- Session 列表 / 强制失效

### WP-SEC-T5：Secret Center

- Secret Metadata / Scope / Version / Owner / Used By / Last Used / Rotation / Expiration / Risk / Audit
- **绝不显示完整明文**

### WP-SEC-T6：Security Findings

- 内置检查：默认 Token / 过期 Secret / 高权限长期 Token / 无 Owner 资产 / 跨租户拒绝异常增长 / 不安全模型 Provider / 暴露内部端口 / 失败登录 / Steward 越权尝试 / 配置安全 Drift

### WP-SEC-T7：Audit Explorer

- 多条件搜索 / Correlation / 时间线 / 导出 / 保存查询 / 异常模式 / 从资源详情跳转

### WP-SEC-T8：Retention & Classification

- 数据保留策略 / 分类规则

---

## 十八、WP9C：Notification Service 完善

- 投递记录 + 重试 + Dead Letter
- Webhook 签名 + SSRF 防护 + URL 允许策略
- Email SMTP + 重试
- 订阅管理 UI

---

## 十九、WP9D：Change Management（修正 P1-9）

**事件投影模型**：
- `changes` 表不从人工维护，从以下事件投影生成：
  - Operation 状态变更
  - Config Rollout
  - Model Deployment 变更
  - 权限变更
  - 版本升级
- `rollback_rate` 不放在单条 Change 上，由统计接口计算

**API**：
- `GET /api/v1/changes` — Change Timeline（过滤 + 日历视图）
- `GET /api/v1/changes/stats` — 变更失败率 + 回滚率（统计计算）
---

## 二十、WP10：测试与硬化

### WP10-T1：E2E 测试

**7 个核心场景**（保留 v1）+ **新增场景**（修正评审意见 §九）：

| # | 场景 | 验证内容 |
|---|------|----------|
| 1 | 创建 Tenant | 创建→审批→Provisioning→Membership→Config Scope→ACTIVE→审计 |
| 2 | 模型上线 | 创建 Deployment→Test→Enable→Desired→Apply→Active→CONVERGED→Route→Job 使用 |
| 3 | 配置变更与回滚 | Draft→Validate→Diff→Activate→收敛→Drift→Steward 发现→Rollback→恢复 |
| 4 | 失败 Job 诊断 | 列表→详情→Timeline→Attempt→Logs→Diagnosis→Retry→成功→Audit |
| 5 | Asset Repair | 删除 Binding→Health 下降→Reconciler 发现→Steward Finding→Repair→恢复 |
| 6 | 安全审计 | Audit Explorer→Correlation→从资源跳转→导出 |
| 7 | Steward 治理 | Daily Brief→Finding→推荐 Runbook→Operation Proposal→人工确认→验证 |

**新增场景**：

| # | 场景 | 验证内容 |
|---|------|----------|
| 8 | SSE 未认证连接 | 无 Session → 拒绝 |
| 9 | SSE 跨租户事件泄露 | Tenant A 不收到 Tenant B 事件 |
| 10 | SSE 断线重放 | 断线 → Last-Event-ID → 重连 → 回放缺失事件 |
| 11 | SSE 事件重复和乱序 | sequence 递增，无重复 |
| 12 | Search Projection 延迟与重建 | 创建对象→延迟可见→全量重建→一致 |
| 13 | Search 跨租户 | Tenant A 搜索不返回 Tenant B 资源 |
| 14 | Alert 去重/重开/自动恢复/风暴 | 触发→去重→条件消失→Auto Resolve→条件再现→Reopen→Storm Limit |
| 15 | Incident 并发更新 | 多用户同时更新→状态一致 |
| 16 | Runbook 版本和权限 | Published 不可修改→新版本→Deprecated 不能引用 |
| 17 | Webhook SSRF | 内网 URL → 拒绝 |
| 18 | Notification 重试 | 失败→重试 3 次→Dead Letter |
| 19 | Resource Provider 不可用 | Telemetry Agent 断开→Resource Center 标记 stale |
| 20 | BFF partial failure | 必需数据失败→503；可选失败→partial:true |
| 21 | 大导出限制 | >10000 行→异步 Operation |
| 22 | Saved View 跨租户 | Shared View 只在 Tenant 内可见 |
| 23 | RouteGuard 与后端权限不一致 | 前端有 Capability 但后端拒绝→403 |
| 24 | XSS | 输入 `<script>` → 不执行 |
| 25 | 权限变更后页面即时失效 | Role 移除→security_version→Token 失效→页面跳转 Login |
| 26 | Observability 数据陈旧 | 数据过期→stale 标记 |

### WP10-T2：性能测试（与部署规模绑定）

**验收环境**：
- 单节点：8 CPU / 16GB RAM / 100GB SSD
- 并发管理员：5
- 事件速率：100 events/min
- 资源数量：100 tenants / 1000 assets / 10000 jobs
- 历史数据：30 天 metrics / 10000 audit records
- Search Projection：10000 条

**性能目标**：

| 指标 | 目标 |
|------|------|
| BFF View Model P95 | < 2s |
| Search 查询 P95 | < 500ms |
| SSE 连接 | 50 并发 |
| SSE 事件延迟 | < 1s |
| 列表页虚拟滚动 | 10000 条流畅 |
| 首页首屏加载 | < 3s |
| Metrics 查询 P95 (30 天范围) | < 3s |
| Alert 规则评估延迟 | < evaluation_interval + 10s |

### WP10-T3：安全测试

- 跨租户隔离全端点矩阵
- CSRF / Origin 负向
- XSS / IDOR
- SSRF（Webhook）
- Docker Socket 未挂载验证
- Rate Limit 各接口
- Secret 不泄露
- Capability 与后端权限一致性

### WP10-T4：验收证据包

- E2E 报告（26 场景）
- 性能报告
- 安全报告
- API 契约比对
- Migration 审计
- 门禁检查清单

---

## 二十一、估算汇总

### Phase 1A：Control Center Foundation

| WP | 低估 | 高估 | 说明 |
|----|------|------|------|
| WP-C | 8 | 12 | 契约/UX/原型/API |
| WP0 | 12 | 18 | App Shell + 设计系统 + 框架 |
| WP-OBS | 18 | 30 | OTel + 历史存储 + 查询 + SLO + Telemetry Agent |
| WP-EVT | 10 | 15 | Durable Event + SSE + Notification |
| WP1 | 8 | 12 | Mission Control 基础版 |
| WP2 | 10 | 15 | Search + ⌘K + Saved Views |
| WP8 | 10 | 15 | BFF 聚合 + 导出 + 限流 |
| WP9A | 8 | 12 | Organization Service |
| WP9B | 3 | 5 | Search Service |
| **1A 合计** | **77** | **119** | |

### Phase 1B：Operations & Intelligence

| WP | 低估 | 高估 | 说明 |
|----|------|------|------|
| WP4 | 18 | 25 | Alert + Incident + Runbook |
| WP5 | 18 | 28 | Resource + Topology + Capacity + Storage |
| WP6 | 10 | 16 | Steward Panel + Brief + 闭环 |
| WP7 | 2 | 3 | Saved Views 完善 |
| WP9C | 5 | 8 | Notification 完善 |
| WP9D | 5 | 7 | Change Management |
| WP-MODEL | 10 | 15 | 模型运营增强 |
| WP-SEC | 15 | 25 | 安全中心增强 |
| WP10 | 18 | 25 | E2E + 性能 + 安全 + 证据 |
| **1B 合计** | **101** | **152** | |

### 总计

| | 低估 | 高估 |
|---|------|------|
| Phase 1A | 77 | 119 |
| Phase 1B | 101 | 152 |
| **总计** | **178** | **271** |

> 取评审建议范围：**165–251 人日**

### 人员建议

| 角色 | 人数 |
|------|------|
| 后端工程师 | 2–3 |
| 前端工程师 | 2 |
| QA / 自动化测试 | 1 |
| UX / 产品设计 | 1 |
| Tech Lead / 架构师 | 0.5–1 |
| 安全和运维评审 | 兼职 |

**日历周期：8–12 周**

---

## 二十二、完整依赖图

```
Phase 1A:
  WP-C (契约冻结)
    ↓
  WP0 (App Shell) ──→ WP2 (Search/⌘K/Saved Views)
    ↓                    ↑
  WP-OBS (可观测性) ─→ WP1 (Mission Control)
    ↓
  WP-EVT (Event + SSE)
    ↓
  WP9A (Organization) ──→ WP8 (BFF 聚合)
  WP9B (Search)

Phase 1B (依赖 1A 全部完成):
  WP4 (Alert/Incident/Runbook) ──→ WP6 (Steward)
    ↓
  WP5 (Resource/Topology/Capacity)
    ↓
  WP-MODEL (模型运营) ──并行──→ WP-SEC (安全中心)
    ↓
  WP9C (Notification 完善) ──→ WP9D (Change)
    ↓
  WP10 (测试与硬化)
```

**关键约束**：
- WP-OBS 必须在 WP1 / WP4 / WP5 之前完成（事实数据源）
- WP-EVT 必须在 WP4 之前完成（Alert 触发事件）
- WP-C 必须最先完成（契约冻结）
- 前端骨架可并行，但真实业务页面不能早于事实数据源和 API 契约

---

## 二十三、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| WP-OBS 历史存储性能 | 中 | 高 | PG 分区 + BRIN 索引 + 30 天保留 + 采样 |
| Durable Event 吞吐 | 中 | 高 | Valkey Streams + 批量写 + 背压处理 |
| BFF 聚合查询性能 | 中 | 高 | 并行查询 + 缓存 + View Model 精简 + partial failure |
| Alert 规则引擎误报 | 中 | 中 | 模板化 + for_duration + Auto Resolve + Storm Protection |
| 容量预测准确性 | 高 | 低 | 置信度标记 + 不触发高风险操作 + 标记 "估算" |
| 前端路由重组回归 | 中 | 中 | E2E 先行 + 逐步迁移 |
| 工作量超估 | 中 | 高 | 拆分 1A/1B，1A 完成后评估是否调整 1B 范围 |
| Telemetry Agent 采集不全 | 中 | 中 | 先支持核心指标，逐步扩展 |
| SSE 连接稳定性 | 中 | 中 | 心跳 + 断线重连 + Last-Event-ID + 游标 |

---

## 二十四、交付物清单

### 文档
- `reports/CONTROL-CENTER-Phase1-开发计划-v2.md` — 本文档
- `design/prototypes/` — 高保真原型
- `design/user-journeys/` — 用户旅程

### ADR
- ADR-017 Phase 1 对象模型
- ADR-018 Phase 1 状态机
- ADR-019 Capability 权限模型
- ADR-020 事件 Schema
- ADR-021 Alert 规则模板
- ADR-022 Observability Provider 契约
- ADR-023 Durable Event Backbone
- ADR-024 Telemetry Agent 安全采集

### Migration
- 015_observability.py — metrics_series + SLO
- 016_event_stream.py — event_stream
- 017_notifications.py — notifications + deliveries
- 018_alerts_incidents.py — alert_rules + alerts + incidents + incident_events
- 019_runbooks.py — runbooks + runbook_versions
- 020_preferences.py — user_preferences + saved_views + recent_objects
- 021_changes.py — changes（投影表）

### API 契约
- `docs/api-spec/v0.2.2/control-center-phase1.yaml`

### 前端
- 8 业务一级导航 + Steward 全局右侧助手
- App Shell + ContextBar + Capability RouteGuard + DesignSystem + DataExplorer + ObjectPageLayout
- GlobalSearch + CommandPalette + NotificationCenter + StewardPanel
- SavedViews + FeatureFlags
- 全部二级页面（Phase 1A 核心 + Phase 1B 补齐）

### BFF
- View Model 聚合端点（15+）
- SSE 实时网关（Durable Event + 断线重连）
- 导出（同步 + 异步）+ Rate Limit + Error Normalization

### 后端
- Observability Service（Metrics/Logs/Traces/Events + SLO）
- Event Store + Publisher
- Notification Service（可靠投递）
- Organization Service（完整）
- Search Service（Projection + 权限）
- Alert Service（模板化规则）
- Incident Service（事件表模型）
- Runbook Service（版本化）
- Change Service（事件投影）
- Resource / Topology / Capacity Service
- Steward Brief + Action Service
- Preferences Service
- Model 运营增强（Embedding Space + Usage + Quality + Test Console + Provider Secrets）
- Security 中心增强（Principals + Roles + Access Explorer + Tokens + Secrets + Findings + Retention）

---

## 二十五、门禁检查清单

### Phase 1A 门禁

- [ ] WP-C 契约冻结完成（对象模型 + 状态机 + Capability 矩阵 + 事件 Schema + API 契约 + 原型）
- [ ] 8 业务导航 + Steward 全局助手可用
- [ ] Capability 路由守卫工作（非硬编码角色）
- [ ] Tenant Selector 经 Server Membership 验证
- [ ] WP-OBS 历史存储工作（Metrics 至少 24h 数据）
- [ ] Durable Event Backbone 支持 Last-Event-ID 断线重放
- [ ] SSE 50 并发稳定
- [ ] Mission Control 每个卡片有事实源 + observed_at + freshness
- [ ] BFF partial failure 正确处理
- [ ] Search 查询时过 AuthorizationService
- [ ] Command Palette 写操作经确认表单
- [ ] Saved View 加载时重新检查权限
- [ ] Rate Limit 按接口分策略
- [ ] 大导出异步化

### Phase 1B 门禁

- [ ] Alert 规则模板化（无任意表达式）
- [ ] Alert 去重/重开/Auto Resolve/Storm Protection 工作
- [ ] Incident 用 incident_events 表（非 timeline_json）
- [ ] Runbook 版本化（Published 不可修改）
- [ ] Resource Center 不挂载 Docker Socket
- [ ] 容量预测有置信度 + 不触发高风险操作
- [ ] Steward 不新增 Auto-Governance
- [ ] Steward 使用 "Likely Cause" 而非 "Root Cause"
- [ ] Notification 有 Delivery 记录 + 重试 + Dead Letter
- [ ] Webhook 有 SSRF 防护
- [ ] Change 从事件投影生成
- [ ] 模型运营全部页面有真实数据
- [ ] 安全中心全部页面有真实数据
- [ ] 26 个 E2E 场景全部通过
- [ ] 性能指标全部达标
- [ ] 安全测试全部通过

---

## 二十六、可立即启动的内容

在修订版评审通过前，以下内容可并行启动（不依赖完整计划批准）：

1. **WP-C 契约冻结**（对象模型 + 状态机 + Capability 矩阵 + 事件 Schema）
2. **高保真原型**（7 个核心页面）
3. **App Shell 和设计系统基础**（ObjectPageLayout / DataExplorer / StatusBadge / HealthScore）
4. **Observability 与 Event Backbone 技术验证**（PoC：PG 时序存储 + Valkey Streams + SSE 断线重放）
