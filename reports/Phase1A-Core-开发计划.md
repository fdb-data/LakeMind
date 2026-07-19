# Phase 1A Core：统一管理与运行态势

> 基于 v3 评审意见 §四–§九精简  
> 基准日期：2026-07-16  
> 前置条件：Phase 0 已通过验收（P1-001 已修复）  
> 估算：80–120 人日（含缓冲）  
> 日历周期：4–6 周  
> 评审状态：已批准执行

---

## 〇、定位

> Phase 1A Core 完成后，LakeMind Control Center 将从"可信但偏弱的后台"升级为"真正可日常使用的统一管理与运行态势中心"。

不建设完整 Observability 平台、事件平台或治理平台。这些能力放入 Backlog，根据实际使用反馈逐步进入后续小版本。

---

## 一、目标

交付后，Control Center 达到：

1. **统一产品框架** — 8 导航 + Context Bar + Capability 路由 + 设计系统
2. **清晰信息架构** — 不再有空壳页面
3. **Tenant 和角色上下文** — Tenant Selector 经 Membership 验证
4. **Mission Control** — 首页即知系统态势，每项可下钻
5. **服务与资源基础监控** — 独立 Telemetry Agent + 核心 Metrics
6. **核心对象全局搜索** — 按名称/ID 找到任意对象
7. **快速下钻** — 3 次点击内从首页异常进入对象详情
8. **关键状态实时刷新** — SSE + Durable Event + 断线重放
9. **统一体验** — 错误/空状态/加载状态/操作反馈
10. **完整权限过滤** — Capability 驱动 + 后端最终授权
11. **基础站内通知** — 未读数 + 审批/失败/漂移提醒

---

## 二、工作包总览

| WP | 名称 | 估算(人日) |
|----|------|-----------|
| WP-C-Core | 契约与 UX 冻结（精简） | 6–9 |
| WP0 | App Shell 与设计系统 | 10–15 |
| WP-TELEMETRY-Core | 独立只读 Agent + 核心采集 | 4–6 |
| WP-OBS-Core | 核心 Metrics + 7 天存储 + 新鲜度 | 8–12 |
| WP-EVT-Core | Outbox + Relay + SSE + 断线重放 | 6–10 |
| WP1 | Mission Control | 8–12 |
| WP-SEARCH-Core | 基础全局搜索 | 4–7 |
| WP8 | BFF 聚合与错误规范 | 7–10 |
| WP9A | Organization 与 Tenant 运营 | 8–12 |
| WP10A | 自动化/性能/安全/UX 验收 | 10–14 |
| **合计** | | **71–107** |

**正式预算：80–120 人日（含 10–15% 缓冲）**

### 人员

| 角色 | 人数 |
|------|------|
| 后端工程师 | 2 |
| 前端工程师 | 1–2 |
| QA / 自动化测试 | 1 |
| UX / 产品设计 | 兼职或阶段性 |
| Tech Lead / 架构师 | 兼职 |

### 依赖图

```
WP-C-Core (契约冻结)
  ↓
WP0 (App Shell) ──→ WP-SEARCH-Core (搜索)
  ↓
WP-TELEMETRY-Core ─→ WP-OBS-Core (Metrics)
                       ↓
WP-EVT-Core (Event+SSE) ─→ WP1 (Mission Control)
  ↓                         ↑
WP9A (Organization) ──→ WP8 (BFF 聚合)
  ↓
WP10A (测试与验收)
```

---

## 三、WP-C-Core：契约与 UX 冻结（精简）

**只冻结第一阶段所需契约，不冻结 Alert/Incident/Runbook 全部状态机。**

### WP-C-Core-T1：Scope 与 Capability 模型

- 统一 Scope 模型（scope_type: PLATFORM|TENANT + scope_id）
- Capability 模型（`/auth/me` 返回 effective_permissions + capabilities）
- ADR-019 + ADR-025

### WP-C-Core-T2：核心事件 Schema

只定义第一阶段事件类型：
```
job.status_changed, job.resource_update
operation.status_changed, operation.approval_needed
model.deployment_health_changed
config.drift_detected
service.health_changed
asset.health_changed
notification.created
```

### WP-C-Core-T3：核心 Metrics Schema

只定义第一阶段指标：
```
cpu.usage, memory.usage, storage.usage
db.connections, db.slow_queries
valkey.memory, valkey.keys
ray.workers, ray.queue_depth
model_serving.health
service.health, service.response_time
job.queue_depth, job.failure_rate
```

低基数标签：tenant_id, service, instance, status, model_id, deployment_id, skill_id, environment, scope_type, scope_id

### WP-C-Core-T4：Mission Control 卡片定义

每个卡片定义：事实源 / 计算公式 / 刷新频率 / 新鲜度 / 下钻目标 / 不可用时显示

### WP-C-Core-T5：高保真原型

5 个核心页面：Mission Control / Tenant 详情 / Job 详情 / Asset 详情 / Model 详情

### WP-C-Core-T6：API 契约

`docs/api-spec/v0.2.2/control-center-phase1a-core.yaml`

---

## 四、WP0：App Shell 与设计系统

### WP0-T1：路由重组与 8 导航

8 业务一级导航 + Steward 全局右侧助手（基础面板，不完整 Workspace）。

现有 10 页面映射到新结构。懒加载。

### WP0-T2：全局上下文条与 Tenant Selector

- Tenant Selector 经 Server Membership 验证（`POST /api/v1/security/switch-tenant`）
- Environment Selector（Phase 1 只 dev）
- Time Range Selector
- Global Search Input
- Notification Bell（未读数）
- Current Identity / Role
- System Health Indicator

### WP0-T3：Capability 路由守卫

- `/auth/me` 返回 capabilities
- RouteGuard 根据 capabilities 判断
- 导航菜单动态生成

### WP0-T4：设计系统

- StatusBadge（统一状态语义）
- HealthScore（可解释评分）
- ObjectPageLayout（ContextHeader + HealthSummary + PrimaryWorkspace + EvidenceDrawer + ActionBar + Timeline）
- DataExplorer（Search + Filter + Sort + Group + Bulk Actions + Export + Row Preview + Empty/Loading/Error State）
- 状态语义统一（success/running/warning/failed/pending/approval_required/drifted/maintenance/unknown）

### WP0-T5：Feature Flag 基础

- `useFlag(name)` hook
- BFF `GET /feature-flags`
- Phase 1 flags: `steward_context_panel`, `realtime_sse`, `global_search`

---

## 五、WP-TELEMETRY-Core：独立只读 Agent

### WP-TELEMETRY-Core-T1：独立容器

新增 `LakeMindTelemetryAgent/` 目录 + docker-compose 服务。

- 独立容器 + 独立 Service Identity
- 只读数据库账号（`telemetry_readonly`）
- 只读网络权限
- 不持有业务写权限
- **禁止挂载 Docker Socket**

### WP-TELEMETRY-Core-T2：核心采集

只采集：
- CPU / Memory（cgroup v2 只读文件）
- Storage（SeaweedFS HTTP `/cluster/status`）
- PostgreSQL 连接（只读 SQL `pg_stat_activity`）
- Valkey 内存（`INFO` 命令）
- Ray Worker 和 Queue（Ray Dashboard API 只读）
- ModelServing 健康（HTTP `/health`）
- 服务实例心跳

采集频率：每 60s。写入 metrics_series（通过 Server API）。

---

## 六、WP-OBS-Core：核心 Metrics

### WP-OBS-Core-T1：Metrics 存储

```sql
metrics_series (
  id BIGSERIAL PK,
  scope_type VARCHAR NOT NULL,
  scope_id VARCHAR,
  metric_name VARCHAR NOT NULL,
  labels JSONB NOT NULL,         -- 低基数标签
  value DOUBLE PRECISION,
  observed_at TIMESTAMP NOT NULL,
  retention_until TIMESTAMP
)
-- 按天分区，保留 7 天
-- BRIN 索引 on observed_at
-- GIN 索引 on labels
```

### WP-OBS-Core-T2：Cardinality Policy

- 拒绝高基数 Label（asset_id, job_id, attempt_id, operation_id, principal_id）进入 Metrics
- 违反规则的 Metric 被拒绝或自动聚合

### WP-OBS-Core-T3：查询 API

- `GET /api/v1/observability/metrics?name=xxx&labels=xxx&from=xxx&to=xxx`
- 权限按 SecurityContext 过滤 scope

### WP-OBS-Core-T4：数据新鲜度

- 每个查询结果包含 `observed_at` + `freshness_seconds`
- 数据陈旧时标记 `stale: true`

### WP-OBS-Core-T5：自动清理

- 每天清理过期分区（retention_until < now()）
- **不做多级 Rollup**（7 天原始数据足够第一阶段）

### 不包含

- 通用 Logs 查询平台
- Trace Span Store
- 可配置 SLO / Error Budget / Burn Rate
- 多级 Rollup

> Mission Control 使用固定、可解释的健康规则（API 可用 / 服务健康 / Job 失败率 / Model 健康 / Config 漂移 / Asset DEGRADED / Outbox 积压 / 资源超阈值），放在平台配置中。

---

## 七、WP-EVT-Core：Outbox + Relay + SSE

### WP-EVT-Core-T1：Durable Event Backbone

```sql
event_stream (
  event_id UUID PK DEFAULT gen_random_uuid(),
  event_type VARCHAR NOT NULL,
  scope_type VARCHAR NOT NULL,
  scope_id VARCHAR,
  resource_type VARCHAR,
  resource_id VARCHAR,
  sequence BIGSERIAL,
  created_at TIMESTAMP DEFAULT now(),
  payload JSONB NOT NULL,
  retention_until TIMESTAMP,
  published_at TIMESTAMP,        -- NULL = 未发布
  publish_attempts INT DEFAULT 0,
  last_publish_error TEXT
)
```

### WP-EVT-Core-T2：Event Relay

Outbox 模式：
```
业务事务 → 写业务状态 + 写 event_stream(published_at=NULL) → 事务提交
Event Relay → 读取 published_at IS NULL → XADD Valkey Stream → 更新 published_at
```

- 幂等 / 可重启 / 可补发 / 可监控积压 / 按 sequence 保序

### WP-EVT-Core-T3：SSE 网关

认证：Session Cookie + Origin 校验 + SameSite + CORS（不强制 CSRF Header）

单 BFF 模式：
```
BFF 按 sequence 从 event_stream 读取
客户端带 Last-Event-ID 重连 → 回放缺失事件
Valkey 仅用于唤醒通知（SUBSCRIBE → 有新事件时唤醒 BFF 轮询）
```

事件按 scope 过滤（Tenant 权限）。
心跳 15s。
Job 日志独立通道（不进入通用事件总线）。

### WP-EVT-Core-T4：站内通知

只做站内通知：
- 写 notifications 表 + SSE 推送
- 未读数 + 标记已读
- 事件类型：Operation 审批 / Job 失败 / Config 漂移 / Model 健康异常

**不包含**：Email / Webhook / HMAC / Dead Letter / 复杂订阅

### 必须保留

- 事务一致性 / 重启补发 / 断线重放 / Tenant 过滤

### 可推迟

- 多 BFF 广播 / 多实例游标协调 / 复杂慢客户端策略

---

## 八、WP1：Mission Control

### WP1-T1：BFF View Model

每个卡片定义事实源 + observed_at + freshness + source + partial：

| 卡片 | 事实源 | 刷新 |
|------|--------|------|
| Pending Approvals | `GET /operations?status=APPROVAL_REQUIRED` | 10s |
| Failed Jobs (24h) | `GET /jobs?status=FAILED&from=now-24h` | 30s |
| Degraded Assets | `GET /assets?health=DEGRADED` | 60s |
| Unhealthy Deployments | `GET /models/deployments?health=UNHEALTHY` | 30s |
| Config Drifts | `GET /configuration/drifts` | 60s |
| Outbox Backlog | `GET /system/reconcile/drifts` | 30s |
| Service Health (4 Plane) | `GET /observability/metrics?name=service.health` | 30s |
| CPU Usage | `GET /observability/metrics?name=cpu.usage` | 30s |
| Memory Usage | `GET /observability/metrics?name=memory.usage` | 30s |
| Storage Usage | `GET /observability/metrics?name=storage.usage` | 60s |
| Job Queue | `GET /observability/metrics?name=job.queue_depth` | 10s |
| Recent Changes | `GET /audit?page_size=5` | 30s |

**健康计算**：关键组件失败 → Plane 红色；否则加权最差状态。不取简单平均。

**partial failure**：必需数据失败 → 503；可选失败 → `partial: true`；空数组不伪装错误。

### WP1-T2：四屏布局

1. 需要处理（审批/失败/退化/漂移/不健康）
2. 平台健康（4 Plane + 关键服务 + 当前告警）
3. 资源与使用（CPU/Memory/Storage/Job Queue）
4. 资产和认知运行（Knowledge/Skill/Memory 状态）

### WP1-T3：角色化与下钻

- 根据 capabilities 决定显示内容
- 每个数字是 Link → 跳转过滤后列表

---

## 九、WP-SEARCH-Core：基础全局搜索

### WP-SEARCH-Core-T1：Search Projection

```sql
search_projection (
  object_type VARCHAR, object_id VARCHAR,
  scope_type VARCHAR, scope_id VARCHAR,
  title TEXT, subtitle TEXT, keywords TEXT,
  visibility VARCHAR, owner_id VARCHAR,
  tsv TSVECTOR, updated_at TIMESTAMP
)
-- GIN 索引 on tsv
-- trigram 索引 on title
```

可搜索对象：Tenant / Asset / Job / Model / Service / Operation / Config

### WP-SEARCH-Core-T2：搜索 API

`GET /api/v1/search?q=xxx&type=asset,job`

- tsvector（全文）+ trigram（前缀/模糊）+ 精确 ID 匹配
- 粗过滤（scope + visibility）→ 批量授权 → 分页
- 不泄露未授权总量

### WP-SEARCH-Core-T3：搜索 UI

- 顶部搜索输入框
- 结果按对象类型分组
- 点击跳转详情

**不包含**：Command Palette / Saved Views / Dashboard Layout

---

## 十、WP8：BFF 聚合与错误规范

### WP8-T1：View Model 聚合

- `GET /view/mission-control`
- `GET /view/tenant-detail/{id}`
- `GET /view/job-detail/{id}`
- `GET /view/asset-detail/{id}`
- `GET /view/deployment-detail/{id}`
- `GET /view/service-detail/{id}`

并行查询 + partial failure + `_meta`（request_id + correlation_id + partial_failure）

### WP8-T2：小规模导出

- 同步 CSV/JSON 流式输出
- 上限 10000 行
- 字段权限检查
- **不包含**大规模异步导出

### WP8-T3：Rate Limit

| 接口 | 限流 |
|------|------|
| Login | IP + Username, 10/min |
| Search | Principal, 60/min |
| SSE | Principal + 连接数, 5 |
| 写操作 | Principal + Tenant, 100/min |

### WP8-T4：Error Normalization

统一错误格式 + 401→Login + 403→权限 + 429→限流 + 500→request_id

---

## 十一、WP9A：Organization 与 Tenant 运营

### WP9A-T1：Tenant 后端增强

- 创建向导后端（10 步 + Provisioning Saga）
- Group / Entitlement / Quota / Budget / Usage API
- Usage 从 metrics_series 聚合

### WP9A-T2：Tenant 前端

- Tenants 列表 + 创建向导 + 详情页
  - Overview / Members / Entitlements / Quotas / Resources / Assets / Jobs / Config / Security / Audit
- Users & Groups 页面
- Service Accounts 页面
- Quotas & Entitlements 页面
- Usage & Budgets 页面

---

## 十二、WP10A：测试与验收

### WP10A-T1：功能测试

- Capability 路由守卫
- Tenant 切换 Membership 验证
- Search 权限过滤 + 批量授权
- Event 重放（Last-Event-ID）
- SSE 跨租户事件过滤
- SSE 认证（Cookie + Origin）
- Mission Control 事实源 + 新鲜度
- BFF partial failure
- Observability 数据新鲜度 + Cardinality 拒绝
- Feature Flag

### WP10A-T2：事件一致性测试

- DB 写成功、Valkey 失败 → Relay 补发
- Relay 重启 → 从 unpublished 继续
- 重复发布 → 幂等
- 事件顺序 → sequence 递增
- 断线重连 → Last-Event-ID → 回放

### WP10A-T3：安全测试

- 跨租户隔离
- CSRF / Origin
- XSS / IDOR
- Docker Socket 未挂载
- Telemetry Agent 只读权限
- Rate Limit
- Secret 不泄露

### WP10A-T4：性能基线

- BFF View Model P95 < 2s
- Search P95 < 500ms
- SSE 50 并发稳定
- 首页首屏 < 3s
- Metrics 查询 P95 (7 天) < 2s

### WP10A-T5：UX 验收

- 5 个核心任务可用性测试
- 键盘操作
- WCAG AA
- 1366×768 + 1920×1080
- 错误/空状态/加载状态
- 从首页异常进入对象详情 ≤ 3 次点击

---

## 十三、验收标准

Phase 1A Core 完成时，必须现场证明：

### 1. 管理
- [ ] Tenant 可创建、配置、暂停、恢复
- [ ] 成员、Quota、Entitlement 和有效配置可查看
- [ ] 所有管理操作有 Operation 和 Audit

### 2. Mission Control
- [ ] 首页展示哪些服务不健康
- [ ] 哪些 Job 失败
- [ ] 哪些 Asset 退化
- [ ] 哪些 Model 不可用
- [ ] 哪些配置漂移
- [ ] 哪些 Operation 待审批
- [ ] 当前 CPU、内存和存储
- [ ] 数据最后更新时间

### 3. 下钻
- [ ] 点击任何异常可进入具体 Job / Asset / Model / Service / Operation / Tenant

### 4. 实时性
- [ ] Job、Operation、Model 和 Service 状态自动更新
- [ ] 断线后能够补回关键事件
- [ ] 不同 Tenant 不会收到彼此事件

### 5. 搜索
- [ ] 能够按名称或 ID 找到 Tenant / Asset / Job / Model / Service / Operation

### 6. 可信性
- [ ] 所有数据有事实源
- [ ] 数据陈旧时明确标记
- [ ] 部分查询失败时不伪装成 0
- [ ] Telemetry Agent 无业务写权限
- [ ] Metrics 不接受高基数标签
- [ ] BFF 不成为身份或数据事实源

### 7. 体验
- [ ] 核心页面风格统一
- [ ] 没有空壳导航
- [ ] 没有只能看不能操作的关键页面
- [ ] 3 次点击内从首页异常进入对象详情
- [ ] 1366×768 和 1920×1080 可正常使用
- [ ] 错误、空状态和加载状态清楚

---

## 十四、暂缓内容（Backlog）

以下放入 Backlog，不进入当前阶段门禁，根据实际使用反馈逐步进入后续小版本：

| 暂缓能力 | 后续位置 |
|----------|----------|
| 通用 Logs 查询平台 | Phase 1B |
| Trace Span Store | Phase 1B |
| 可配置 SLO / Error Budget | Phase 1B |
| 多级 Metrics Rollup | Phase 1B |
| Command Palette | 小版本 |
| Saved Views / Dashboard Layout | 小版本 |
| Email / Webhook 通知 | Phase 1B |
| Alert 规则平台 | Phase 1B |
| Incident 管理 | Phase 1B |
| Runbook 版本和执行 | Phase 1B |
| 容量预测 | Phase 1B |
| 完整模型运营 | Phase 1B |
| Access Explorer / Policy Simulation | Phase 1B |
| 全局 Asset 运营页面 | Phase 1B |
| Schedules / Runtime Policies | Phase 1B |
| Upgrade / Maintenance Window | Phase 1B |
| Daily Brief 定时调度 | Phase 1B |
| 复杂 Steward 治理 | Phase 2 |

---

## 十五、交付物清单

### ADR
- ADR-019 Capability 权限模型
- ADR-025 统一 Scope 模型
- ADR-026 Metrics Cardinality Policy
- ADR-028 Phase 1A Core 事件 Schema

### Migration
- 015_metrics_core.py — metrics_series
- 016_event_stream.py — event_stream（含 Outbox 字段）
- 017_notifications_basic.py — notifications（站内）
- 018_search_projection.py — search_projections

### 新增镜像
- `telemetry-agent`（独立容器，只读）

### API 契约
- `docs/api-spec/v0.2.2/control-center-phase1a-core.yaml`

### 前端
- 8 业务导航 + Steward 基础面板
- App Shell + ContextBar + Capability RouteGuard + DesignSystem + DataExplorer + ObjectPageLayout
- GlobalSearch + NotificationBell
- Mission Control + Tenant 详情 + 全部现有页面升级

### BFF
- View Model 聚合（6 端点）
- SSE 实时网关
- 小规模导出 + Rate Limit + Error Normalization

### 后端
- Metrics 查询 API
- Event Store + Relay
- Search Projection + 更新
- Notification（站内）
- Organization Service（完整）

---

## 十六、与 v3 的差异

| 维度 | v3 Phase 1A | Phase 1A Core |
|------|-------------|---------------|
| 估算 | 110–168 人日 | 80–120 人日 |
| Observability | Metrics + Logs(S3) + Traces + SLO | 只核心 Metrics + 7 天 |
| Rollup | 多级（30s/5min/1h） | 无（7 天原始） |
| SLO | 可配置 slo_definitions | 固定健康规则 |
| Event | 完整多 BFF + Resync | 单 BFF + 断线重放 |
| Notification | Email + Webhook + Dead Letter | 只站内 |
| Search | + Command Palette + Saved Views | 只基础搜索 |
| Export | 同步 + 异步 | 只同步小规模 |
| Logs/Traces | S3 归档 + Span Store | 不包含 |
| 日历周期 | 9–13 周 | 4–6 周 |
