# Control Center Phase 1 开发计划（v3 修订版）

> 基于 v2 评审意见（10 个 P0 + 7 个 P1）修订  
> 基准日期：2026-07-16  
> 前置条件：Phase 0 已通过验收  
> 估算：200–310 人日（含 10–15% 缓冲）  
> 评审状态：v3 待评审（v2 有条件通过）

---

## 〇、v2 → v3 修订摘要

### 评审结论变化

| 版本 | 结论 | 综合评分 |
|------|------|----------|
| v1 | 退回修改 | 5.3/10 |
| v2 | 有条件通过 | 7.6/10 |
| v3 | 待评审（目标：通过） | — |

### v2 → v3 修订（10 个 P0 + 7 个 P1）

| # | 级别 | v2 问题 | v3 修正 |
|---|------|---------|---------|
| P0-1 | P0 | 仍有页面无 WP | 新增 WP-ASSET-OPS / WP-RUNTIME-OPS / WP-PLATFORM-ADMIN |
| P0-2 | P0 | Observability 只定义 Metrics 存储 | WP-OBS-T7 补充 Logs/Traces 存储方案；缩小承诺为"对象关联日志 + 关键链路 Trace" |
| P0-3 | P0 | Metrics 高基数问题 | WP-OBS-T6 标签分级 + Cardinality Policy + Rollup |
| P0-4 | P0 | Event 双写不一致 | WP-EVT-T4 Outbox 模式 + Event Relay + published_at |
| P0-5 | P0 | Valkey Streams 多 BFF 广播 | WP-EVT-T5 BFF 直接按游标读持久事件 + Valkey 仅作唤醒通知 + 慢客户端 resync_required |
| P0-6 | P0 | SSE CSRF 不可行 | WP-EVT-T6 改用 Session Cookie + Origin + SameSite + CORS，不强制 CSRF Header |
| P0-7 | P0 | 平台级事件 tenant_id NOT NULL | WP-C-T7 统一 Scope 模型（scope_type + scope_id） |
| P0-8 | P0 | Telemetry Agent 不独立 | WP-TELEMETRY 独立容器 + 独立 Service Identity + 只读权限 |
| P0-9 | P0 | Runbook 用 authorized_roles | 改为 required_permissions + required_capabilities + 步骤引用受控 Operation Type |
| P0-10 | P0 | WP-MODEL 含 Cost/Quality 与边界冲突 | 缩小为 Usage/Latency/ErrorRate/RateLimit/Cache/手工测试，不含完整成本归因/自动质量评分/漂移分析 |
| P1-1 | P1 | SLO 硬编码 | 新增 slo_definitions + slo_evaluations 表 |
| P1-2 | P1 | Mission Control 健康用平均 | 改为关键组件失败→红色；否则加权最差状态；每 Plane 可解释 |
| P1-3 | P1 | Search N+1 权限检查 | 粗过滤 + 批量 Authorization + 不泄露未授权总量 |
| P1-4 | P1 | Notification 目标在 Delivery 表 | 拆为 notification_destinations + notification_deliveries + Webhook DNS Rebinding 防护 |
| P1-5 | P1 | Daily Brief 定时机制未定义 | Phase 1A 按需生成，1B 后半加定时 Scheduler |
| P1-6 | P1 | 大导出缺敏感数据治理 | 增加字段权限/分类/体积/有效期/签名 URL |
| P1-7 | P1 | Feature Flag 缺管理对象 | 新增 Feature Flag 管理模型（Scope/Owner/到期/审计/清理） |

### 新增工作包/任务

| 新增 | 内容 | Phase | 优先级 |
|------|------|-------|--------|
| WP-C-T7 | 统一 Scope 模型 | 1A | P0 |
| WP-OBS-T6 | Metrics Cardinality 与 Rollup | 1A | P0 |
| WP-OBS-T7 | Logs 与 Traces 存储方案 | 1A | P0 |
| WP-EVT-T4 | Event Relay + Outbox 一致性 | 1A | P0 |
| WP-EVT-T5 | 多 BFF 广播 + Resync | 1A | P0 |
| WP-EVT-T6 | SSE 认证模型修订 | 1A | P0 |
| WP-TELEMETRY | 独立 Telemetry Agent 服务 | 1A | P0 |
| WP-ASSET-OPS | Asset 运营页面 | 1B | P1 |
| WP-RUNTIME-OPS | Runtime 运营页面 | 1B | P1 |
| WP-PLATFORM-ADMIN | Platform 管理页面 | 1B | P1 |
| WP10A | Phase 1A 独立测试与门禁 | 1A | P0 |
| WP10B | Phase 1B 测试与门禁 | 1B | P0 |

---

## 一、Phase 1 范围与边界

### 目标

形成完整统一控制中心（Control Center 1.0），拆分为两个内部版本：

- **Phase 1A：Control Center Foundation Preview** — 统一产品框架和可靠数据基础
- **Phase 1B 完成后：Control Center 1.0** — 完整运维治理闭环

> Phase 1A 结束时不宣称 Control Center 1.0 完成。

### 信息架构

8 业务一级导航 + Steward 全局右侧助手（与 v2 相同）。

### 不包含（Phase 2–4）

- LakeMind Control Graph / Blast Radius / Evidence-based RCA
- Auto-Governance / LLM 对话
- 完整成本归因 / 自动输出质量评分 / 模型漂移分析 / 复杂安全评测（P0-10）
- Predictive Capacity / Policy Simulation
- 多节点 / HA / Failover
- Studio 协同
- 通用大规模日志分析平台（P0-2）

### 设计约束

1. Steward 用规则引擎 + 模板，不接 LLM，不新增自动执行政策
2. 单实例部署，保留多实例语义
3. 可观测性基础先行（WP-OBS）
4. Search Projection 用 PG tsvector + GIN + trigram
5. SSE + Durable Event Backbone（Valkey Streams 唤醒 + event_stream 持久化重放）
6. **禁止挂载 Docker Socket**，资源指标通过独立 Telemetry Agent 容器采集（P0-8）
7. **Capability 驱动权限**，前端根据 capabilities 判断
8. **Tenant 切换经 Server 验证 Membership**
9. **统一 Scope 模型**：所有事件/指标/告警/通知/变更采用 scope_type（PLATFORM/TENANT）+ scope_id（P0-7）
10. **Metrics 低基数标签**，Logs/Traces/Events 可高基数（P0-3）
11. **Event 发布用 Outbox 模式**，业务服务不直接 XADD（P0-4）

---

## 二、Phase 1A：Control Center Foundation Preview

### 工作包总览

| WP | 名称 | 估算(人日) |
|----|------|-----------|
| WP-C | 契约与 UX 冻结 | 10–15 |
| WP0 | App Shell 与设计系统 | 12–18 |
| WP-OBS | 可观测性基础 | 22–36 |
| WP-TELEMETRY | 独立 Telemetry Agent | 5–8 |
| WP-EVT | Durable Event 与 SSE | 14–20 |
| WP1 | Mission Control 基础版 | 8–12 |
| WP2 | Search / Command Palette / Saved Views | 10–15 |
| WP8 | BFF 聚合层 | 10–15 |
| WP9A | Organization Service | 8–12 |
| WP9B | Search Service | 3–5 |
| WP10A | Phase 1A 测试与门禁 | 8–12 |
| **1A 合计** | | **110–168** |

### 依赖图

```
WP-C (契约冻结，含 Scope 模型)
  ↓
WP0 (App Shell) ──→ WP2 (Search/⌘K/Saved Views)
  ↓
WP-TELEMETRY (独立 Agent) ─→ WP-OBS (可观测性)
                              ↓
WP-EVT (Event + SSE)      ─→ WP1 (Mission Control)
  ↓                          ↑
WP9A (Organization) ──→ WP8 (BFF 聚合)
WP9B (Search)
  ↓
WP10A (1A 测试与门禁)
```

---

## 三、WP-C：契约与 UX 冻结

### WP-C-T1～T6（与 v2 相同）

对象模型 / 状态机 / Capability 矩阵 / 事件 Schema / Alert 规则模板 / Observability Provider 契约 / 高保真原型 / API 契约。

### WP-C-T7：统一 Scope 模型（新增，修正 P0-7）

**交付物**：`.agent/adr/ADR-025-unified-scope-model.md`

**设计**：所有事件、指标、告警、通知、变更采用统一 Scope：

```sql
scope_type VARCHAR NOT NULL,  -- PLATFORM | TENANT
scope_id   VARCHAR             -- NULL for PLATFORM, tenant_id for TENANT
```

**影响对象**：
- `event_stream`: `tenant_id NOT NULL` → `scope_type + scope_id`
- `metrics_series`: 同上
- `alerts`: 同上
- `notifications`: 同上
- `changes`: 同上

**平台级事件**（无天然 Tenant）：
- 平台服务异常、PostgreSQL 容量、Ray Head 异常、版本升级、平台配置、全局安全事件

**禁止**：用伪造 Tenant 表示平台范围。

---

## 四、WP0：App Shell 与设计系统

### WP0-T1～T6（与 v2 相同，含 Capability 路由 + Tenant Selector Membership 验证）

---

## 五、WP-OBS：可观测性基础

### WP-OBS-T1：OpenTelemetry 采集契约（与 v2 相同）

### WP-OBS-T2：Metrics 历史存储（修正 P0-3, P0-7）

**标签分级**：

| 信号 | 允许标签 | 基数 |
|------|----------|------|
| Metrics | tenant_id, service, instance, status, model_id, deployment_id, skill_id, environment, scope_type, scope_id | 低 |
| Logs | 上述 + request_id, correlation_id, job_id, attempt_id, asset_id, operation_id, principal_id | 高 |
| Traces | 同 Logs | 高 |
| Events | 同 Logs | 高 |

**Metrics Cardinality Policy**：
- 拒绝高基数 Label（asset_id, job_id, attempt_id, operation_id, principal_id）进入 Metrics
- 高基数需求通过 Logs/Traces 查询
- 违反规则的 Metric 被拒绝或自动聚合

**存储**（修正 P0-7）：
```sql
metrics_series (
  id BIGSERIAL PK,
  scope_type VARCHAR NOT NULL,   -- PLATFORM | TENANT
  scope_id VARCHAR,              -- NULL for PLATFORM
  metric_name VARCHAR NOT NULL,
  labels JSONB NOT NULL,         -- 低基数标签
  value DOUBLE PRECISION,
  observed_at TIMESTAMP NOT NULL,
  retention_until TIMESTAMP
)
-- 按天分区，保留 30 天
-- BRIN 索引 on observed_at
-- GIN 索引 on labels
```

### WP-OBS-T3：Logs / Traces / Events 查询（修正 P0-2）

**Phase 1 存储方案**：

| 信号 | Phase 1 存储 | 说明 |
|------|-------------|------|
| Metrics | PG metrics_series 时序表 | 低基数，30 天保留 |
| Events | event_stream 表 | 持久化事件流 |
| Logs | S3 归档 + PG 日志索引表 | 原始日志存 S3，索引（timestamp/level/service/tenant/request_id/correlation_id）存 PG |
| Traces | PG span_store 表（有限） | Phase 1 只支持关键链路 Trace，不支持全量 Trace |
| Audit | audit_log 表（Phase 0 已有） | — |

**Logs 索引表**：
```sql
log_index (
  id BIGSERIAL PK,
  scope_type VARCHAR, scope_id VARCHAR,
  service VARCHAR, level VARCHAR,
  request_id VARCHAR, correlation_id VARCHAR,
  job_id VARCHAR, asset_id VARCHAR,
  s3_uri VARCHAR NOT NULL,       -- 原始日志在 S3 的位置
  line_offset BIGINT, line_count INT,
  observed_at TIMESTAMP NOT NULL,
  retention_until TIMESTAMP
)
```

**Trace 存储**：
```sql
span_store (
  id BIGSERIAL PK,
  trace_id VARCHAR NOT NULL,
  span_id VARCHAR NOT NULL,
  parent_span_id VARCHAR,
  scope_type VARCHAR, scope_id VARCHAR,
  service VARCHAR, operation VARCHAR,
  start_time TIMESTAMP, end_time TIMESTAMP,
  attributes JSONB,
  status_code VARCHAR
)
-- Phase 1 只存储采样后的关键链路 Trace
```

**承诺缩小**（修正 P0-2）：
> Phase 1 支持对象关联日志和关键链路 Trace，不支持通用大规模日志分析平台。

**API**：
- `GET /api/v1/observability/metrics` — 时序查询（低基数）
- `GET /api/v1/observability/logs` — 日志查询（索引 → S3 原文）
- `GET /api/v1/observability/traces?trace_id=xxx` — Trace Waterfall
- `GET /api/v1/observability/events` — 事件时间线

### WP-OBS-T4：SLO 计算（修正 P1-1）

**SLO 不硬编码**（修正 P1-1）：
```sql
slo_definitions (
  id UUID PK, name VARCHAR,
  scope_type VARCHAR, scope_id VARCHAR,  -- 平台级或租户级
  metric_name VARCHAR, target DOUBLE PRECISION,
  window VARCHAR,         -- 30d / 7d
  calculation_method VARCHAR,  -- ratio / latency_p95 / availability
  owner_id UUID,
  enabled BOOLEAN,
  created_at TIMESTAMP
)
slo_evaluations (
  id UUID PK, slo_id UUID,
  observed_value DOUBLE PRECISION,
  error_budget_remaining DOUBLE PRECISION,
  burn_rate DOUBLE PRECISION,
  evaluated_at TIMESTAMP
)
```

API Availability 99.9% 等作为默认模板，可按 Scope 覆盖。

### WP-OBS-T5：Telemetry Agent 采集（移至 WP-TELEMETRY）

### WP-OBS-T6：Metrics Cardinality 与 Rollup（新增，修正 P0-3）

**Cardinality Policy**：
- 拒绝高基数 Label 进入 Metrics
- 自动聚合：将高基数 Label 降维（如 job_id → skill_id）
- 采样：高频指标按比例采样

**Rollup 策略**：
- 原始数据：30s 粒度，保留 7 天
- Rollup 1：5min 粒度，保留 30 天
- Rollup 2：1h 粒度，保留 90 天
- 定时 Rollup 任务 + 分区清理

### WP-OBS-T7：Logs 与 Traces 存储方案（新增，修正 P0-2）

已在 WP-OBS-T3 中定义。补充：
- Logs S3 归档策略（按 service + date 分区）
- Logs 索引清理（30 天）
- Traces 采样率配置（默认 10%，关键链路 100%）
- 敏感信息脱敏（Token/Secret 不写入 Logs/Traces）

---

## 六、WP-TELEMETRY：独立 Telemetry Agent（新增，修正 P0-8）

**目标**：将 Telemetry Agent 从 LakeMindServer 中拆出为独立服务。

### WP-TELEMETRY-T1：独立容器

**新增**：`LakeMindTelemetryAgent/` 目录

```yaml
# docker-compose.yml 新增
telemetry-agent:
  image: ${LAKEMIND_REGISTRY}/telemetry-agent:${LAKEMIND_VERSION}
  container_name: lakemind-telemetry-agent
  environment:
    PG_HOST: lakemind-postgres
    PG_USER: telemetry_readonly  # 只读账号
    VALKEY_HOST: lakemind-valkey
    SEAWEEDFS_URL: http://lakemind-seaweedfs:8333
    RAY_DASHBOARD_URL: http://lakemind-ray-head:8265
    METRICS_SINK: http://lakemind-server-api:10823/api/v1/observability/metrics
  volumes:
    - /sys/fs/cgroup:/host/cgroup:ro  # 只读 cgroup
  networks: [lakemind]
  restart: unless-stopped
```

**独立 Service Identity**：
- 独立 Token / API Key
- 只读数据库账号（`telemetry_readonly`）
- 只读网络权限
- 不持有业务写权限
- 独立健康检查
- 独立配置

### WP-TELEMETRY-T2：采集器

- PostgreSQL: 只读 SQL（`pg_stat_activity`, `pg_stat_database`）
- Valkey: `INFO` 命令
- SeaweedFS: HTTP `/cluster/status`
- Ray: Ray Dashboard API（只读受控 Provider）
- cgroup v2: 只读文件（`/host/cgroup/.../cpu.stat`, `memory.current`）
  - 验证读取的是目标服务数据，非 Agent 自身 cgroup

**采集频率**：每 30s 采集，写入 metrics_series（通过 Server API）。

---

## 七、WP-EVT：Durable Event 与 SSE

### WP-EVT-T0：Durable Event Backbone（修正 P0-4, P0-7）

**持久化事件表**（修正 P0-7 Scope 模型）：
```sql
event_stream (
  event_id UUID PK DEFAULT gen_random_uuid(),
  event_type VARCHAR NOT NULL,
  scope_type VARCHAR NOT NULL,   -- PLATFORM | TENANT
  scope_id VARCHAR,              -- NULL for PLATFORM
  resource_type VARCHAR,
  resource_id VARCHAR,
  sequence BIGSERIAL,
  created_at TIMESTAMP DEFAULT now(),
  payload JSONB NOT NULL,
  retention_until TIMESTAMP,
  -- Outbox 模式（修正 P0-4）
  published_at TIMESTAMP,        -- NULL = 未发布
  publish_attempts INT DEFAULT 0,
  last_publish_error TEXT
)
CREATE INDEX idx_event_seq ON event_stream(sequence);
CREATE INDEX idx_event_unpublished ON event_stream(published_at) WHERE published_at IS NULL;
```

**发布流程**（Outbox 模式，修正 P0-4）：
```
业务事务
  → 写业务状态
  → 写 event_stream（published_at = NULL）
  → 事务提交
  → Event Relay 读取 published_at IS NULL 的事件
  → XADD Valkey Stream（payload 含 event_id + sequence）
  → 更新 published_at = now()
```

**禁止**：业务服务直接 XADD Valkey Stream。

### WP-EVT-T1：Event Relay（新增，修正 P0-4）

**改动文件**：
- `LakeMindServer/src/lakemind_server/events/event_relay.py` — 新建

**Relay 要求**：
- 幂等（重复发布不产生副作用）
- 可重启（崩溃后从 published_at IS NULL 继续）
- 可补发（遗漏事件自动补发）
- 可监控积压（`SELECT count(*) FROM event_stream WHERE published_at IS NULL`）
- 事件顺序保证（按 sequence）
- 不重复产生业务副作用

### WP-EVT-T2：SSE 实时网关（修正 P0-5, P0-6）

**认证模型**（修正 P0-6）：
```
SSE 认证：
  Session Cookie（HttpOnly + SameSite）
  + Origin 校验（CORS 禁止任意 Origin）
  + 服务端 SecurityContext
  + Tenant 权限过滤
```

**不强制 CSRF Header**（原生 EventSource 不能设置自定义 Header）。

如需额外连接票据，使用一次性短期 SSE Ticket（`GET /events/ticket` 返回 30s 有效 ticket，`GET /events/stream?ticket=xxx`）。

**多 BFF 广播**（修正 P0-5）：
```
BFF 不使用 XREADGROUP 消费 Valkey Stream。
BFF 直接按游标读取 event_stream 表：
  → 客户端连接时带上 Last-Event-ID（sequence）
  → BFF 从 event_stream 查询 sequence 之后的事件
  → 推送给客户端
  → 更新本地游标
  → Valkey 仅用于唤醒通知（SUBSCRIBE channel → 有新事件时唤醒 BFF 轮询）
```

**慢客户端处理**（修正 P0-5）：
- 不丢弃旧事件
- 发送 `resync_required` 事件
- 或主动断开
- 客户端重新查询 View Model
- 从新游标继续

**Job 日志独立通道**：`job.log_appended` 不进入通用事件总线。

### WP-EVT-T3：Notification Service（修正 P1-4）

**数据模型**（修正 P1-4）：
```sql
notification_destinations (
  id UUID PK, principal_id UUID,
  channel VARCHAR,    -- email / webhook
  config JSONB,       -- {email: "..."} or {webhook_url: "...", signature_secret_ref: "..."}
  url_allowlist BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP
)
notification_deliveries (
  id UUID PK, notification_id UUID,
  destination_id UUID,    -- 引用 destination，不直接存目标
  status VARCHAR,         -- PENDING/DELIVERED/FAILED/DEAD_LETTER
  attempt_count INT, max_retries INT DEFAULT 3,
  next_retry_at TIMESTAMP, delivered_at TIMESTAMP,
  error TEXT
)
```

**Webhook 防护**（增强 P1-4）：
- SSRF 防护：URL 允许列表
- DNS Rebinding 防护
- 禁止重定向到内网
- HTTPS 要求
- IP 解析检查
- Egress Allowlist
- 超时和响应体限制
- HMAC 签名

### WP-EVT-T4：Event Relay 一致性测试（新增，修正 P0-4）

测试场景：
- 数据库写成功、Valkey 失败 → Relay 补发
- Relay 重启 → 从 unpublished 继续
- 重复发布 → 幂等
- 事件顺序 → sequence 递增
- 过期游标 → 从当前开始
- 游标早于 Retention → resync_required

### WP-EVT-T5：多 BFF 广播与 Resync（新增，修正 P0-5）

测试场景：
- 多个 BFF 实例各自按游标读 event_stream
- 慢客户端 → resync_required
- 客户端重连 → Last-Event-ID → 回放

### WP-EVT-T6：SSE 认证模型修订（新增，修正 P0-6）

测试场景：
- 无 Session Cookie → 拒绝
- 无效 Origin → 拒绝
- 跨租户事件 → 过滤
- SSE Ticket 过期 → 拒绝

---

## 八、WP1：Mission Control 基础版

### WP1-T1：BFF Mission Control View Model（修正 P1-2）

**健康计算**（修正 P1-2）：
- 关键组件失败 → Plane 红色（不取平均）
- 否则按加权最差状态
- 每 Plane 可解释由哪些服务决定
- Error Budget 由 SLO Service 按正式窗口计算

**每个卡片定义事实源**（与 v2 相同，含 observed_at + freshness + source + partial）。

### WP1-T2～T3（与 v2 相同）

---

## 九、WP2：Search / Command Palette / Saved Views

### WP2-T1：Search Projection（修正 P1-3）

**权限检查优化**（修正 P1-3）：
1. 先按 Tenant、Visibility、Classification 做粗过滤（SQL 层）
2. 批量调用 AuthorizationService（非逐条 N+1）
3. 授权后再计算分页和总数
4. 不向用户泄露未授权结果总量和排名信息

### WP2-T2～T4（与 v2 相同）

---

## 十、WP8：BFF 聚合层

### WP8-T2：导出（修正 P1-6）

**敏感数据治理**（增强 P1-6）：
- 最大文件体积限制
- 可导出字段权限（分类数据、Secret 不可导出）
- 导出权限检查
- 下载有效期（24h）
- 下载次数限制
- Artifact Retention
- 审计
- 签名下载 URL

### WP8-T1/T3/T4（与 v2 相同）

---

## 十一、WP9A / WP9B（与 v2 相同）

---

## 十二、WP10A：Phase 1A 独立测试与门禁（新增，修正评审意见 §五.1）

**目标**：Phase 1A 结束时有完整自动化测试，不等到 Phase 1B 末尾。

### WP10A-T1：功能测试

- Capability 路由守卫
- Tenant 切换 Membership 验证
- Search 权限过滤 + 粗过滤 + 批量授权
- Event 重放（Last-Event-ID）
- SSE 跨租户事件过滤
- SSE 认证（Cookie + Origin）
- Mission Control 事实源 + 新鲜度
- BFF partial failure（必需失败→503，可选失败→partial）
- Saved Views 权限 + Schema 兼容
- Observability 数据新鲜度 + Metrics Cardinality 拒绝
- Feature Flag 管理

### WP10A-T2：事件双写和 Relay 故障测试

- 数据库写成功、Valkey 失败 → Relay 补发
- Relay 重启 → 从 unpublished 继续
- 重复发布 → 幂等
- 事件顺序 → sequence 递增
- 过期游标 → resync_required
- 多 BFF 实例各自读 event_stream
- 慢客户端 Resync

### WP10A-T3：Metrics 高基数测试

- 非法高基数 Label 被拒绝
- 10000 Job 不创建 10000 条独立核心时序
- 30 天分区清理
- Rollup 正确
- 查询性能（30 天范围 P95 < 3s）

### WP10A-T4：性能基线

- BFF View Model P95 < 2s
- Search P95 < 500ms
- SSE 50 并发稳定
- 首页首屏 < 3s

### WP10A-T5：可用性和 UX 验收

- 5 个核心任务的可用性测试
- 键盘操作
- WCAG AA
- 中英文布局预留
- 1366×768 和 1920×1080 显示
- 错误和空状态
- 用户从告警进入根因的点击数 ≤ 3

### WP10A 门禁

- [ ] Capability 路由工作
- [ ] Tenant Selector 经 Membership 验证
- [ ] WP-OBS 历史存储工作（Metrics 24h + Logs S3 + Traces 采样）
- [ ] Metrics Cardinality Policy 执行
- [ ] Durable Event + Relay 一致性
- [ ] SSE 断线重放 + 跨租户过滤
- [ ] SSE 认证（Cookie + Origin，无 CSRF Header）
- [ ] Telemetry Agent 独立运行
- [ ] Mission Control 每卡片有事实源
- [ ] BFF partial failure 正确
- [ ] Search 批量授权
- [ ] 1A 全部测试通过
---

## 十三、Phase 1B：Operations & Intelligence

### 工作包总览

| WP | 名称 | 估算(人日) |
|----|------|-----------|
| WP4 | Alert / Incident / Runbook | 18–25 |
| WP5 | Resource / Topology / Capacity / Storage | 18–28 |
| WP6 | Steward Context Panel | 10–16 |
| WP7 | Saved Views 与 Preferences 完善 | 2–3 |
| WP9C | Notification Service 完善 | 5–8 |
| WP9D | Change Management | 5–7 |
| WP-MODEL | 模型运营增强（缩小范围） | 8–12 |
| WP-SEC | 安全中心增强 | 15–25 |
| WP-ASSET-OPS | Asset 运营页面 | 8–12 |
| WP-RUNTIME-OPS | Runtime 运营页面 | 6–10 |
| WP-PLATFORM-ADMIN | Platform 管理页面 | 5–8 |
| WP10B | Phase 1B 测试与门禁 | 12–18 |
| **1B 合计** | | **112–172** |

### 依赖图

```
Phase 1A 完成（含 WP10A 门禁通过）
  ↓
WP4 (Alert/Incident/Runbook) ──→ WP6 (Steward)
  ↓
WP5 (Resource/Topology/Capacity)
  ↓
WP-MODEL ──并行──→ WP-SEC ──并行──→ WP-ASSET-OPS ──并行──→ WP-RUNTIME-OPS ──并行──→ WP-PLATFORM-ADMIN
  ↓
WP9C (Notification) ──→ WP9D (Change)
  ↓
WP10B (1B 测试与门禁)
```

---

## 十四、WP4：Alert / Incident / Runbook

### WP4-T1：Alert Service（与 v2 相同，模板化规则）

### WP4-T2：Incident 聚合（与 v2 相同，incident_events 表）

### WP4-T3：Runbook 版本化（修正 P0-9）

**权限模型**（修正 P0-9）：
```sql
runbook_versions (
  ...
  required_permissions VARCHAR[],    -- 替代 authorized_roles
  required_capabilities VARCHAR[],
  allowed_principal_types VARCHAR[],  -- user / agent / steward
  risk_level VARCHAR,
  approval_policy VARCHAR,            -- none / single / multi
  ...
)
```

**步骤约束**（修正 P0-9）：
- 每个可执行步骤必须引用受控 Operation Type：
  ```
  REINDEX_ASSET, RETRY_JOB, RELOAD_MODEL, RUN_RECONCILER,
  REPAIR_BINDING, SYNC_RAY_STATUS, CLEANUP_TEMP_RESOURCE
  ```
- **禁止**：通过 JSON 步骤执行任意 Shell 或任意 HTTP
- 每步有独立权限检查 + 超时 + 回滚 + 验证

### WP4-T4：UI（与 v2 相同）

---

## 十五、WP5：Resource / Topology / Capacity / Storage

### WP5-T1～T4（与 v2 相同）

**补充**：所有资源指标来自 WP-TELEMETRY → metrics_series，不直接调用采集器。

---

## 十六、WP6：Steward Context Panel

### WP6-T1：Context Panel（与 v2 相同）

### WP6-T2：Daily Brief（修正 P1-5）

**Phase 1A**：按需生成（`POST /api/v1/steward/brief/generate`）
**Phase 1B 后半**：定时生成（内部 Scheduler）

**定时生成要求**：
- 平台时区配置
- Tenant 时区支持
- 失败重试
- 重复执行幂等
- Brief 版本 + 生成时间 + 数据截止时间

### WP6-T3：行动闭环（与 v2 相同，不新增 Auto-Governance）

### WP6-T4：Finding 视图（与 v2 相同）

---

## 十七、WP-MODEL：模型运营增强（修正 P0-10）

**范围缩小**（修正 P0-10）：

### Phase 1 包含

| 能力 | 说明 |
|------|------|
| 请求量 | per Tenant / Skill / Job / Deployment |
| Token 量 | per Tenant / Model |
| Provider 报告费用 | 直接透传 Provider 费用（不做归因） |
| 延迟 | P50 / P95 / P99 |
| 错误率 | per Deployment / Model |
| 限流 | Rate Limit 命中 |
| 缓存命中 | Cache Hit Rate |
| 手工测试记录 | Test Console 保存证据 |

### Phase 1 不包含（移至 Phase 2）

| 能力 | 原因 |
|------|------|
| 完整成本归因 | Phase 2 Cost Attribution |
| 自动输出质量评分 | Phase 2 Quality Score |
| 模型漂移分析 | Phase 2 Model Drift |
| 复杂安全评测 | Phase 2 Safety Evaluation |

### WP-MODEL-T1～T5（与 v2 相同，但缩小 T2/T3 范围）

---

## 十八、WP-SEC：安全中心增强（与 v2 相同）

---

## 十九、WP-ASSET-OPS：Asset 运营页面（新增，修正 P0-1）

**目标**：补齐 Assets 下全部二级页面。

### WP-ASSET-OPS-T1：Knowledge 运营页面

- 文档和 Chunk 统计 / Parser 版本 / Embedding Space / 索引覆盖
- 检索测试 / Search Quality / Top Queries / 无结果查询
- Reindex 预览 / 源文件与派生内容 / DEGRADED 根因

### WP-ASSET-OPS-T2：Skill 运营页面

- Manifest / 版本与 Checksum / 输入输出 Schema
- Secret / Model Profile / 权限 / 资源和网络
- 依赖扫描 / 发布者 / 使用 Job / 成功率和平均耗时
- Deprecated / Revoke

### WP-ASSET-OPS-T3：Memory 运营页面

- Memory Type / Subject / Scope / Source / Importance
- Retention / Expiration / Revision / Search / Access
- Consolidation / Archive / Clear 影响分析

### WP-ASSET-OPS-T4：全局 Bindings 页面

- 跨 Asset 的 Binding 视图 / 状态 / Drift / Repair

### WP-ASSET-OPS-T5：全局 Lineage 页面

- DAG 可视化 / 上游下游 / 跨 Asset 追踪

### WP-ASSET-OPS-T6：Asset Quality 页面

- 四维度评分（完整性/可检索性/可执行性/时效性）/ Drift / 趋势

---

## 二十、WP-RUNTIME-OPS：Runtime 运营页面（新增，修正 P0-1）

### WP-RUNTIME-OPS-T1：Attempts 全局页面

- 跨 Job 的 Attempt 比较 / 状态 / 失败原因 / 资源 / 模型

### WP-RUNTIME-OPS-T2：Artifacts 页面

- Artifact 列表 / 类型 / 大小 / Checksum / 下载 / 保留

### WP-RUNTIME-OPS-T3：Schedules 页面

- 定时 Job / Cron / 状态 / 下次执行 / 暂停 / 恢复

### WP-RUNTIME-OPS-T4：Runtime Policies 页面

- 超时 / 重试 / 资源限制 / 并发限制 / 优先级

### WP-RUNTIME-OPS-T5：Compute / Ray 运营页面

- LakeMind 语义的 Compute 页面（非直接暴露 Ray Dashboard）
- Cluster / Worker / Capacity / Running Job / Queue / Resource Slot
- Worker Health / Version / Drift / Lost Job / Logs / 维护 Operation

---

## 二十一、WP-PLATFORM-ADMIN：Platform 管理页面（新增，修正 P0-1, P1-7）

### WP-PLATFORM-ADMIN-T1：Versions & Upgrades

- 当前版本 / 可用版本 / 升级历史 / 兼容性检查 / 升级 Operation

### WP-PLATFORM-ADMIN-T2：Feature Flags 管理（修正 P1-7）

**管理模型**：
```sql
feature_flags (
  id UUID PK, name VARCHAR NOT NULL,
  scope_type VARCHAR, scope_id VARCHAR,  -- 平台级或租户级
  owner_id UUID,
  default_value BOOLEAN,
  current_value BOOLEAN,
  expires_at TIMESTAMP,        -- 到期自动关闭
  created_at TIMESTAMP, updated_at TIMESTAMP
)
```

- Flag 列表 / Scope / Owner / 默认值 / 当前值 / 到期 / 变更审计 / 清理策略

### WP-PLATFORM-ADMIN-T3：System Info

- 系统版本 / 运行时信息 / 容器状态 / 网络拓扑 / 依赖版本

### WP-PLATFORM-ADMIN-T4：Observability 前端完整页面

- Metrics 浏览器 / Logs 查询 / Trace Waterfall / SLO Dashboard / Error Budget

### WP-PLATFORM-ADMIN-T5：Maintenance Window

- 维护窗口创建 / 影响 Tenant / 冲突提示 / 关联 Incident

---

## 二十二、WP9C / WP9D（与 v2 相同）

---

## 二十三、WP10B：Phase 1B 测试与门禁（新增，修正评审意见 §五.1）

### WP10B-T1：E2E 测试（26 场景，与 v2 相同 + 新增）

新增场景：
- Alert 去重/重开/自动恢复/风暴
- Incident 并发更新
- Runbook 版本和权限（required_permissions，非 authorized_roles）
- Runbook 步骤只执行受控 Operation Type
- Webhook SSRF / DNS Rebinding / 内网重定向
- Notification 重试 + Dead Letter
- Resource Provider 不可用 → stale 标记
- 容量预测置信度 + 不触发高风险操作
- Steward 不自动执行（只生成 Proposal）
- Feature Flag 到期自动关闭
- Maintenance Window 冲突检测
- Metrics 高基数 Label 被拒绝
- Event Relay 补发 + 幂等
- SSE resync_required

### WP10B-T2：性能测试（与 v2 相同，与部署规模绑定）

### WP10B-T3：安全测试（与 v2 相同 + 新增）

新增：
- Docker Socket 未挂载验证
- Telemetry Agent 独立只读权限验证
- Runbook 步骤不执行任意 Shell/HTTP
- Feature Flag 变更有审计
- Export 签名 URL 验证

### WP10B-T4：验收证据包

### WP10B 门禁

- [ ] Alert 模板化（无任意表达式）
- [ ] Alert 去重/重开/Auto Resolve/Storm Protection
- [ ] Incident 用 incident_events 表
- [ ] Runbook 用 required_permissions（非 authorized_roles）
- [ ] Runbook 步骤只引用受控 Operation Type
- [ ] Resource Center 不挂载 Docker Socket
- [ ] Telemetry Agent 独立运行
- [ ] 容量预测有置信度 + 不触发高风险操作
- [ ] Steward 不新增 Auto-Governance
- [ ] Steward 用 "Likely Cause" 而非 "Root Cause"
- [ ] Notification 有 Delivery + 重试 + Dead Letter
- [ ] Webhook 有 SSRF + DNS Rebinding 防护
- [ ] Change 从事件投影生成
- [ ] WP-MODEL 不含完整成本归因/自动质量评分/漂移分析
- [ ] 全部二级页面有真实数据（无空壳）
- [ ] Feature Flag 有管理对象 + 到期 + 审计
- [ ] 26+ E2E 场景全部通过
- [ ] 性能指标全部达标
- [ ] 安全测试全部通过

---

## 二十四、估算汇总（统一，修正评审意见 §六）

### Phase 1A

| WP | 低估 | 高估 |
|----|------|------|
| WP-C | 10 | 15 |
| WP0 | 12 | 18 |
| WP-OBS | 22 | 36 |
| WP-TELEMETRY | 5 | 8 |
| WP-EVT | 14 | 20 |
| WP1 | 8 | 12 |
| WP2 | 10 | 15 |
| WP8 | 10 | 15 |
| WP9A | 8 | 12 |
| WP9B | 3 | 5 |
| WP10A | 8 | 12 |
| **1A 合计** | **110** | **168** |

### Phase 1B

| WP | 低估 | 高估 |
|----|------|------|
| WP4 | 18 | 25 |
| WP5 | 18 | 28 |
| WP6 | 10 | 16 |
| WP7 | 2 | 3 |
| WP9C | 5 | 8 |
| WP9D | 5 | 7 |
| WP-MODEL | 8 | 12 |
| WP-SEC | 15 | 25 |
| WP-ASSET-OPS | 8 | 12 |
| WP-RUNTIME-OPS | 6 | 10 |
| WP-PLATFORM-ADMIN | 5 | 8 |
| WP10B | 12 | 18 |
| **1B 合计** | **112** | **172** |

### 总计

| | 低估 | 高估 |
|---|------|------|
| Phase 1A | 110 | 168 |
| Phase 1B | 112 | 172 |
| **小计** | **222** | **340** |
| 10–15% 缓冲 | 22–34 | 34–51 |
| **项目预算** | **244** | **391** |

> **正式估算：222–340 人日（含缓冲 244–391 人日）**

### 人员与日历

| 团队规模 | 日历周期 |
|----------|----------|
| 6 名全职核心 | 9–13 周 |
| 4 名核心 | 13–18 周 |

### 人员构成

| 角色 | 人数 |
|------|------|
| 后端工程师 | 2–3 |
| 前端工程师 | 2 |
| QA / 自动化测试 | 1 |
| UX / 产品设计 | 1 |
| Tech Lead / 架构师 | 0.5–1 |
| 安全和运维评审 | 兼职 |

---

## 二十五、完整依赖图

```
Phase 1A:
  WP-C (契约冻结，含 Scope 模型 + Cardinality Policy)
    ↓
  WP0 (App Shell) ──→ WP2 (Search/⌘K/Saved Views)
    ↓
  WP-TELEMETRY (独立 Agent) ─→ WP-OBS (可观测性 + Logs/Traces + SLO)
                                ↓
  WP-EVT (Event + Relay + SSE) ─→ WP1 (Mission Control)
    ↓                              ↑
  WP9A (Organization) ──→ WP8 (BFF 聚合)
  WP9B (Search)
    ↓
  WP10A (1A 测试与门禁)

Phase 1B (依赖 1A 门禁通过):
  WP4 (Alert/Incident/Runbook) ──→ WP6 (Steward)
    ↓
  WP5 (Resource/Topology/Capacity)
    ↓
  WP-MODEL ──并行──→ WP-SEC ──并行──→ WP-ASSET-OPS ──并行──→ WP-RUNTIME-OPS ──并行──→ WP-PLATFORM-ADMIN
    ↓
  WP9C (Notification) ──→ WP9D (Change)
    ↓
  WP10B (1B 测试与门禁)
```

---

## 二十六、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| WP-OBS PG 时序性能 | 中 | 高 | 分区 + BRIN + Rollup + 30 天保留 + Cardinality Policy |
| Event Relay 一致性 | 中 | 高 | Outbox 模式 + 幂等 + 监控积压 |
| SSE 连接稳定性 | 中 | 中 | 游标重放 + resync_required + 心跳 |
| Telemetry Agent 采集正确性 | 中 | 中 | 验证 cgroup 目标 + 独立只读账号 |
| Alert 规则误报 | 中 | 中 | 模板化 + for_duration + Auto Resolve + Storm Protection |
| 容量预测准确性 | 高 | 低 | 置信度 + 不触发高风险操作 |
| 前端路由重组回归 | 中 | 中 | E2E 先行 + 逐步迁移 |
| 工作量超估 | 中 | 高 | 拆分 1A/1B，1A 门禁后评估 1B |
| Logs S3 查询延迟 | 中 | 中 | PG 索引 + S3 范围读 + 缓存 |
| Runbook 步骤安全 | 低 | 高 | 受控 Operation Type + 禁止任意 Shell/HTTP |

---

## 二十七、交付物清单

### ADR
- ADR-017 Phase 1 对象模型
- ADR-018 Phase 1 状态机
- ADR-019 Capability 权限模型
- ADR-020 事件 Schema
- ADR-021 Alert 规则模板
- ADR-022 Observability Provider 契约
- ADR-023 Durable Event Backbone
- ADR-024 Telemetry Agent 独立服务
- ADR-025 统一 Scope 模型
- ADR-026 Metrics Cardinality Policy
- ADR-027 Runbook 权限与步骤约束

### Migration
- 015_observability.py — metrics_series + slo_definitions + slo_evaluations + log_index + span_store
- 016_event_stream.py — event_stream（含 Outbox 字段）
- 017_notifications.py — notifications + destinations + deliveries + subscriptions
- 018_alerts_incidents.py — alert_rules + alerts + incidents + incident_events
- 019_runbooks.py — runbooks + runbook_versions（required_permissions）
- 020_preferences.py — user_preferences + saved_views + recent_objects
- 021_changes.py — changes（投影表）
- 022_feature_flags.py — feature_flags

### 新增镜像
- `telemetry-agent`（独立容器，只读权限）

### API 契约
- `docs/api-spec/v0.2.2/control-center-phase1.yaml`

---

## 二十八、可立即启动的内容

在 v3 评审通过前，以下内容可并行启动：

1. **WP-C 契约冻结**（对象模型 + 状态机 + Capability 矩阵 + 事件 Schema + Scope 模型 + Cardinality Policy）
2. **高保真原型**（7 个核心页面）
3. **App Shell 和设计系统基础**（ObjectPageLayout / DataExplorer / StatusBadge / HealthScore）
4. **Observability PoC**（PG 时序存储 + Rollup + Cardinality 拒绝）
5. **Event Backbone PoC**（Outbox + Relay + Valkey Streams 唤醒 + SSE 游标重放）
6. **Telemetry Agent PoC**（独立容器 + cgroup 只读 + 只读 DB 账号）

---

## 二十九、与 v2 的差异对照

| 维度 | v2 | v3 |
|------|-----|-----|
| 一级导航 | 8 + Steward | 8 + Steward（不变） |
| Phase 1A WP 数 | 9 | 11（+WP-TELEMETRY, +WP10A） |
| Phase 1B WP 数 | 9 | 12（+WP-ASSET-OPS, +WP-RUNTIME-OPS, +WP-PLATFORM-ADMIN, WP10→WP10B） |
| Observability | 只 Metrics | Metrics + Logs(S3) + Traces(有限) + SLO(可配置) |
| Event 发布 | 直接双写 | Outbox + Relay |
| SSE 认证 | CSRF Header | Cookie + Origin + SSE Ticket |
| Scope 模型 | tenant_id NOT NULL | scope_type + scope_id |
| Telemetry Agent | 在 Server 内 | 独立容器 |
| Runbook 权限 | authorized_roles | required_permissions + 受控 Operation Type |
| WP-MODEL 范围 | 含 Cost/Quality/Drift | 缩小为 Usage/Latency/ErrorRate/手工测试 |
| 估算 | 178–271 | 222–340（含缓冲 244–391） |
| 测试 | WP10 在 1B 末尾 | WP10A(1A) + WP10B(1B) |
| Feature Flag | 前端 useFlag() | 管理对象 + 到期 + 审计 |
| Search 权限 | 逐条检查 | 粗过滤 + 批量授权 |
| Notification | 目标在 Delivery | destinations + deliveries 分离 |
| Export | 行数限制 | + 字段权限/分类/体积/签名 URL |
