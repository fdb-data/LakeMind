# Control Center Phase 1 开发计划

> 基于 `v0.2.0.design/LakeMind_Control_Center_世界级改造设计方案.md` §22.2  
> 基准日期：2026-07-16  
> 前置条件：Phase 0（WP0–WP5）已全部完成并通过部署验证  
> 估算：55–79 人日（3 名开发 → 约 4–5 周）

---

## 〇、Phase 1 范围与边界

### 目标

形成完整统一控制中心（Control Center 1.0），覆盖设计方案 §6–§17 的全部信息架构、核心页面、BFF 聚合层和后端服务补全。

### 包含

| 类别 | 内容 |
|------|------|
| 信息架构 | 8 一级导航 + 全局上下文条 + 路由权限 + 设计系统 |
| 首页 | Mission Control（4 屏 + 角色化 + 下钻） |
| 组织 | Tenant Center（列表 + 创建向导 + 详情页 + 生命周期） |
| 资产 | Asset Catalog + 统一详情框架 + 类型专属能力 + Health Score |
| 运行 | Job Portfolio + 详情页 + 比较 + 实时更新 + Ray 管理 |
| 模型 | 五类对象 + Deployment 详情 + Route Builder + Embedding Space + Test Console + Desired/Active 收敛 |
| 配置 | 配置浏览器 + Schema 驱动编辑 + Revision 工作流 + Diff + Rollout + Drift + Feature Flags |
| 平台 | 服务拓扑 + Resource Center + Capacity + Storage 视图 |
| 运维 | Operation + Alert + Incident + Runbook + Change + Notification |
| 安全 | Identity + Role & Policy + Access Explorer + Token & Session + Secret + Findings + Audit |
| 可观测性 | Metrics/Logs/Traces/Events 统一查询 + SLO + 事件时间线 |
| Steward | Context Panel + Daily Brief + Finding + 上下文对话 + 行动闭环 |
| 全局 | Search + Command Palette + Saved Views + Realtime(SSE) |

### 不包含（Phase 2–4）

- LakeMind Control Graph / Blast Radius / Evidence-based RCA
- Auto-Governance（自动执行治理动作）
- LLM 驱动对话（Phase 1 Steward 用规则引擎 + 模板）
- Predictive Capacity / Cost Attribution / Quality Score / Policy Simulation
- 多节点 / HA / Failover / Cluster Maintenance
- Studio 协同

### 设计约束

1. **Steward 用规则引擎 + 模板**，不接 LLM（Phase 2 才引入）
2. **单实例部署**，Rollout API 保留多实例语义但 UI 只展示单实例
3. **可观测性后端轻量实现**，OpenTelemetry 采集契约先行，不引入外部 Observability 栈
4. **Search Projection 用 PG tsvector + GIN**，不引入 Elasticsearch
5. **SSE 而非 WebSocket**，Phase 1 实时推送用 Server-Sent Events

---

## 一、工作包总览

| WP | 名称 | 核心目标 | 任务数 | 估算(人日) |
|----|------|----------|--------|-----------|
| WP0 | 信息架构与 App Shell | 8 导航 + 上下文条 + 路由权限 + 设计系统 + Object Page Framework | T1–T6 | 6–8 |
| WP1 | Mission Control 首页 | 4 屏 + 角色化 + 下钻 + BFF View Model | T1–T4 | 4–6 |
| WP2 | 全局搜索与 Command Palette | Search Projection + ⌘K + 快速动作 | T1–T3 | 3–4 |
| WP3 | 实时事件流与通知中心 | SSE 网关 + Notification Service + 订阅 | T1–T3 | 4–5 |
| WP4 | Alert / Incident / Runbook | Alert 规则 + 去重 + Incident 聚合 + Runbook 注册 | T1–T4 | 5–7 |
| WP5 | Resource & Capacity + Service Topology | 服务拓扑图 + Resource Center + Capacity + Storage 视图 | T1–T4 | 5–7 |
| WP6 | Steward Context Panel | 对象页内嵌 + Daily Brief + 行动闭环 + Finding 视图 | T1–T4 | 5–7 |
| WP7 | Saved Views 与 User Preferences | 持久化视图 + 偏好 + Dashboard Layout + Recent Objects | T1–T2 | 2–3 |
| WP8 | BFF 聚合层增强 | View Model + 跨服务聚合 + 导出 + Rate Limit + Error Normalization | T1–T4 | 5–6 |
| WP9 | 后端服务补全 | Organization / Alert / Search / Notification / Change Service | T1–T5 | 8–12 |
| WP10 | 测试与硬化 | E2E + 性能 + 安全 + 验收证据 | T1–T4 | 8–14 |

**合计：55–79 人日**

---

## 二、依赖图

```
WP0 (App Shell) ─┬→ WP1 (Mission Control)
                  ├→ WP2 (Search + ⌘K)
                  ├→ WP3 (SSE + Notification)
                  ├→ WP7 (Saved Views)
                  └→ WP8 (BFF 聚合)

WP9 (后端服务) ─┬→ WP1 (需要聚合数据)
                ├→ WP4 (Alert/Incident API)
                ├→ WP5 (Resource/Topology API)
                └→ WP6 (Steward 数据)

WP3 ─→ WP4 (Alert 触发通知)
WP4 ─→ WP6 (Finding → Incident 关联)
WP8 ─→ WP10 (BFF 接口测试)
所有 WP ─→ WP10 (测试与硬化)
```

**推荐执行顺序**：WP0 → WP9(并行) → WP8 → WP1 → WP2 → WP3 → WP7 → WP4 → WP5 → WP6 → WP10

---

## 三、WP0：信息架构与 App Shell

**目标**：将现有 10 个平铺页面重组为 8 一级导航 + 二级导航的层级结构，建立 App Shell、路由权限、设计系统和对象页框架。

### WP0-T1：路由重组与导航层级

**改动文件**：
- `frontend/src/router.tsx` — 重写为 8 一级路由 + 二级子路由
- `frontend/src/components/AppLayout.tsx` — 重写 Sider 为分组导航 + Header 为全局上下文条

**导航结构**（对应设计 §6.1–§6.2）：

```
Home
  ├─ Mission Control (/)
  ├─ My Tasks (/my-tasks)
  ├─ Notifications (/notifications)
  ├─ Recent Changes (/recent-changes)
  └─ Saved Views (/saved-views)

Organization (/organization)
  ├─ Tenants (/organization/tenants)
  ├─ Users & Groups (/organization/users)
  ├─ Service Accounts (/organization/service-accounts)
  ├─ Environments (/organization/environments)
  ├─ Quotas & Entitlements (/organization/quotas)
  └─ Usage & Budgets (/organization/usage)

Assets (/assets)
  ├─ Catalog (/assets/catalog)
  ├─ Knowledge (/assets/knowledge)
  ├─ Skills (/assets/skills)
  ├─ Memory (/assets/memory)
  ├─ Bindings (/assets/bindings)
  ├─ Lineage (/assets/lineage)
  └─ Quality (/assets/quality)

Runtime (/runtime)
  ├─ Jobs (/runtime/jobs)
  ├─ Attempts (/runtime/attempts)
  ├─ Artifacts (/runtime/artifacts)
  ├─ Schedules (/runtime/schedules)
  ├─ Compute / Ray (/runtime/compute)
  └─ Policies (/runtime/policies)

AI & Models (/models)
  ├─ Models (/models/definitions)
  ├─ Deployments (/models/deployments)
  ├─ Profiles & Routes (/models/routes)
  ├─ Embedding Spaces (/models/embedding)
  ├─ Usage (/models/usage)
  ├─ Quality & Evaluation (/models/quality)
  └─ Provider Secrets (/models/secrets)

Operations (/operations)
  ├─ Operations (/operations/list)
  ├─ Approvals (/operations/approvals)
  ├─ Alerts (/operations/alerts)
  ├─ Incidents (/operations/incidents)
  ├─ Runbooks (/operations/runbooks)
  ├─ Changes (/operations/changes)
  ├─ Maintenance (/operations/maintenance)
  └─ Notifications (/operations/notifications)

Security & Governance (/security)
  ├─ Principals (/security/principals)
  ├─ Roles & Policies (/security/roles)
  ├─ Tokens & Sessions (/security/tokens)
  ├─ Secrets (/security/secrets)
  ├─ Access Explorer (/security/access)
  ├─ Findings (/security/findings)
  ├─ Audit (/security/audit)
  └─ Retention (/security/retention)

Platform (/platform)
  ├─ Services & Topology (/platform/services)
  ├─ Resources & Capacity (/platform/resources)
  ├─ Configuration (/platform/configuration)
  ├─ Versions & Upgrades (/platform/versions)
  ├─ Storage (/platform/storage)
  ├─ Observability (/platform/observability)
  ├─ Feature Flags (/platform/feature-flags)
  └─ System Info (/platform/system)

Steward (/steward)
  ├─ Daily Brief (/steward/brief)
  ├─ Findings (/steward/findings)
  ├─ Recommendations (/steward/recommendations)
  ├─ Conversations (/steward/conversations)
  └─ Action History (/steward/actions)
```

**实现要点**：
- 现有 10 页面映射到新结构：Overview→Mission Control, Assets→Assets/Catalog, Jobs→Runtime/Jobs, ModelServing→AI & Models/Deployments, Services→Platform/Services, Configuration→Platform/Configuration, Security→Security & Governance, Operations→Operations, Audit→Security/Audit, Steward→Steward
- Sider 用 Ant Design Menu 的 `SubMenu` 支持折叠
- 路由懒加载：`React.lazy()` + `Suspense`

**验收**：所有 8 一级导航可点击展开二级，现有页面功能不丢失。

### WP0-T2：全局上下文条

**改动文件**：
- `frontend/src/components/ContextBar.tsx` — 新建
- `frontend/src/components/AppLayout.tsx` — Header 替换为 ContextBar

**内容**（设计 §6.3）：
- Tenant Selector（从 `/auth/me` 返回的 tenant 列表驱动，切换时刷新页面数据）
- Environment Selector（dev / staging / prod，Phase 1 只 dev）
- Time Range Selector（1h / 6h / 24h / 7d / Custom）
- Global Search Input（触发 WP2 的 Search）
- Command Palette Trigger（⌘K / Ctrl+K）
- Notification Bell（未读数 + 下拉面板）
- Current Identity / Role Display
- System Health Indicator（绿/黄/红圆点）

**实现要点**：
- Tenant Selector 调 `GET /tenants` 获取可访问列表
- 切换 Tenant 时更新 BFF Session 中的 `tenant_id`（`POST /auth/switch-tenant`）
- 全局状态用 React Context（`AppContext`）管理 tenant、environment、timeRange

**验收**：上下文条在所有页面顶部固定，Tenant 切换后数据刷新。

### WP0-T3：路由级权限守卫

**改动文件**：
- `frontend/src/components/RouteGuard.tsx` — 新建
- `frontend/src/router.tsx` — 每个路由包裹 RouteGuard
- `frontend/src/auth/permissions.ts` — 新建，角色→路由映射表

**实现要点**：
- 从 `/auth/me` 获取 `role`，查 permissions 表判断是否有权访问
- 无权访问时显示 403 页面而非空白
- 平台管理员可见全部；租户管理员不可见 Organization/Tenants、Platform/Versions；审计员只读 Security + Audit + Operations

**验收**：不同角色登录后导航菜单只显示有权限的项，直接访问无权 URL 显示 403。

### WP0-T4：设计系统与状态语义统一

**改动文件**：
- `frontend/src/design/tokens.ts` — 新建，颜色/间距/字体 token
- `frontend/src/design/StatusBadge.tsx` — 新建，统一状态徽章
- `frontend/src/design/HealthScore.tsx` — 新建，可解释健康评分
- `frontend/src/design/ObjectPageLayout.tsx` — 新建，统一对象页框架

**状态语义**（设计 §18.8）：
```
success / healthy      → green
running / active       → blue
warning / degraded     → orange
failed / unhealthy     → red
pending               → gray
approval_required     → purple
drifted               → yellow
maintenance           → cyan
unknown               → default
```

**Object Page Framework**（设计 §18.1）：
```
ContextHeader (名称/类型/状态/Health/动作)
HealthSummary (评分分项 + 证据)
PrimaryWorkspace (Tabs: Overview/Bindings/Lineage/Quality/Access/Events)
EvidenceDrawer (右侧抽屉，展示证据)
ActionBar (底部固定，安全动作)
Timeline (事件时间线)
```

**验收**：StatusBadge 在所有页面表现一致，ObjectPageLayout 可被任意对象页复用。

### WP0-T5：Data Explorer Framework

**改动文件**：
- `frontend/src/design/DataExplorer.tsx` — 新建，通用列表框架

**能力**（设计 §18.2）：
- Search（全文搜索输入框）
- Advanced Filter（多条件组合过滤面板）
- Saved View（保存/加载当前过滤+列配置）
- Custom Columns（列显示/隐藏/排序）
- Sort + Group
- Bulk Actions（多选行 + 批量操作）
- Export（CSV/JSON 导出）
- Row Preview（行内展开预览）
- Detail Navigation（点击行跳转详情）
- Empty State / Loading State / Error State

**实现要点**：
- 泛型组件 `DataExplorer<T>`，接受 columns、fetcher、filters 定义
- 分页/虚拟滚动处理大数据集
- 与 WP7 Saved Views 集成

**验收**：Assets/Jobs/Operations 等列表页全部改用 DataExplorer。

### WP0-T6：Feature Flag 基础设施

**改动文件**：
- `frontend/src/auth/featureFlags.ts` — 新建
- `bff/app.py` — `GET /feature-flags` 端点

**实现要点**：
- BFF 从 Server `GET /api/v1/configuration?scope=platform&key=feature_flags` 获取
- 前端 `useFlag(name)` hook 返回 boolean
- Phase 1 flags: `steward_context_panel`, `realtime_sse`, `command_palette`, `saved_views`

**验收**：关闭 flag 后对应 UI 元素隐藏。

---

## 四、WP1：Mission Control 首页

**目标**：将现有 Overview 页面升级为 Mission Control，实现 4 屏结构 + 角色化 + 下钻。

### WP1-T1：BFF Mission Control View Model

**改动文件**：
- `bff/app.py` — 新增 `GET /view/mission-control` 聚合端点

**聚合查询**（并行调 Server API）：
```
GET /api/v1/operations?status=PENDING_APPROVAL&page_size=10   → pending_approvals
GET /api/v1/steward/findings?status=OPEN&severity=CRITICAL    → critical_findings
GET /api/v1/jobs?status=FAILED&page_size=10                   → recent_failed_jobs
GET /api/v1/assets?health=DEGRADED&page_size=10               → degraded_assets
GET /api/v1/model-deployments?health=UNHEALTHY                → unhealthy_deployments
GET /api/v1/instances                                          → service_health
GET /api/v1/tenants?status=ACTIVE&page_size=100               → tenant_usage_top
GET /api/v1/audit?page_size=5                                  → recent_changes
```

**View Model 结构**：
```json
{
  "needs_action": { "pending_approvals": [...], "critical_findings": [...], ... },
  "platform_health": { "planes": [...], "error_budget": {...}, ... },
  "resource_usage": { "cpu": {...}, "memory": {...}, "storage": {...}, ... },
  "asset_status": { "knowledge": {...}, "skills": {...}, "memory": {...}, ... }
}
```

**验收**：`GET /view/mission-control` 返回完整 View Model，单次请求 < 2s。

### WP1-T2：四屏首页布局

**改动文件**：
- `frontend/src/pages/MissionControl.tsx` — 新建（替换 Overview.tsx）

**四屏结构**（设计 §7.1）：
1. **需要行动**：Critical Incident、Pending Approval、Security Finding、Failed Config Rollout、Model Unhealthy、Job SLA Breach、Asset Drift、Capacity Forecast
2. **平台健康**：4 Plane（Access/Control/Data/Execution）Health Score + Error Budget + 当前告警 + 受影响 Tenant
3. **资源与使用**：CPU/Memory/Storage + Job Queue + Model Throughput + Token Usage + Tenant Top N + 容量趋势
4. **资产和认知运行**：Knowledge READY/DEGRADED + Skill PUBLISHED/REVOKED + Memory 活跃/过期 + Binding Drift + Reindex Backlog

**实现要点**：
- 每屏用 Ant Design Card + Row/Col 布局
- 数据来自 BFF View Model，前端不做二次聚合
- 空状态/加载状态/错误状态处理

**验收**：首页展示 4 屏，每屏数据正确。

### WP1-T3：角色化首页与下钻

**改动文件**：
- `frontend/src/pages/MissionControl.tsx` — 角色判断 + 下钻链接

**角色化**（设计 §7.2）：
- `platform_admin`：全部 4 屏
- `tenant_admin`：隐藏平台健康屏，资源屏只显示本租户
- `sre`：强调平台健康 + 资源屏，弱化资产屏
- `auditor`：只展示需要行动中的审批 + 安全 Finding

**下钻**（设计 §7.3）：
- `12 Failed Jobs` → `/runtime/jobs?status=FAILED`
- `3 Config Drifts` → `/platform/configuration?tab=drift`
- `2 Unhealthy Deployments` → `/models/deployments?health=UNHEALTHY`
- 每个数字都是 Link，不是纯文本

**验收**：不同角色看到不同内容，所有数字可点击跳转到过滤后的列表。

### WP1-T4：My Tasks 页面

**改动文件**：
- `frontend/src/pages/MyTasks.tsx` — 新建
- `bff/app.py` — `GET /view/my-tasks` 聚合

**内容**：
- 待我审批的 Operation
- 我创建的 Operation 状态
- 我 Acknowledge 的 Finding
- 我 Follow 的 Job/Asset/Deployment 变更

**验收**：My Tasks 展示当前用户相关的待办事项。

---

## 五、WP2：全局搜索与 Command Palette

**目标**：实现可重建的全局搜索投影和 ⌘K Command Palette。

### WP2-T1：Search Projection 后端

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/search_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/search.py` — 新建
- `LakeMindServer/migrations/versions/009_search_projection.py` — 新建

**Search Projection 设计**（设计 §19.6）：
- PG 表 `search_projection`：`object_type, object_id, tenant_id, title, subtitle, keywords, metadata_json, tsv (tsvector), updated_at`
- GIN 索引 on `tsv`
- 各 Service 在创建/更新/删除对象时写入/更新投影（通过 Outbox 事件异步更新）
- `GET /api/v1/search?q=xxx&type=asset,job&tenant=xxx` → tsvector 查询 + 权限过滤

**可搜索对象**（设计 §6.4）：
Tenant, Asset, Skill, Job, Model, Deployment, Service, Operation, Incident, Principal, Config Key, Audit Request ID, Correlation ID

**验收**：搜索 "knowledge" 返回所有 Knowledge 资产；搜索 Correlation ID 返回相关 Audit 记录。

### WP2-T2：全局搜索 UI

**改动文件**：
- `frontend/src/components/GlobalSearch.tsx` — 新建

**实现要点**：
- 上下文条中的搜索输入框，输入时调 `GET /search?q=xxx`
- 结果按对象类型分组（设计 §6.4）
- 每条结果：图标 + 标题 + 副标题 + 类型标签 + 快速动作（如 Job → Cancel）
- 回车跳转第一结果，点击跳转详情

**验收**：搜索框输入后展示分组结果，点击跳转正确。

### WP2-T3：Command Palette

**改动文件**：
- `frontend/src/components/CommandPalette.tsx` — 新建

**命令集**（设计 §6.5）：
- 创建租户、查看失败 Job、重新索引资产、打开平台配置
- 切换 Tenant、查找使用某 Deployment 的 Job
- 运行系统巡检、查看待审批操作
- 导航命令（跳转到任意页面）

**实现要点**：
- ⌘K / Ctrl+K 触发，Ant Design Modal + Input
- fuzzy match 命令名称
- 所有命令遵循用户权限（无权限的命令不显示）
- 导航命令自动从路由表生成

**验收**：⌘K 打开 Palette，输入 "tenant" 显示创建租户 + 跳转 Tenants 页面。

---

## 六、WP3：实时事件流与通知中心

**目标**：实现认证 SSE 推送 + Notification Service + 订阅机制。

### WP3-T1：SSE 实时网关

**改动文件**：
- `bff/app.py` — 新增 `GET /events/stream` SSE 端点
- `bff/sse_manager.py` — 新建，SSE 连接管理 + 事件分发

**事件类型**（设计 §19.4）：
```
job.status_changed, job.log_appended, job.resource_update
operation.status_changed, operation.approval_needed
alert.triggered, alert.resolved
incident.created, incident.updated
config.rollout_progress, config.drift_detected
model.deployment_health_changed
service.health_changed
steward.finding_created, steward.finding_updated
notification.created
```

**实现要点**：
- SSE 连接用 Session 认证（Cookie + CSRF）
- BFF 维护 Valkey Pub/Sub 订阅，Server 发布事件到 Valkey Channel
- BFF 将 Valkey 消息转发到 SSE 客户端
- 支持事件过滤（客户端可订阅特定类型）
- 断线重连 + Last-Event-ID 恢复

**验收**：提交 Job 后首页 Job 状态自动更新，无需刷新。

### WP3-T2：Notification Service 后端

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/notification_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/notifications.py` — 新建
- `LakeMindServer/migrations/versions/010_notifications.py` — 新建

**数据模型**：
```sql
notifications (
  id UUID PK, tenant_id UUID, principal_id UUID,
  type VARCHAR, severity VARCHAR,
  title TEXT, body TEXT, metadata_json JSONB,
  read_at TIMESTAMP, created_at TIMESTAMP
)
notification_subscriptions (
  id UUID PK, principal_id UUID,
  event_type VARCHAR, severity_filter VARCHAR[],
  tenant_filter UUID[], resource_filter JSONB,
  channel VARCHAR  -- in_app / email / webhook
)
```

**API**：
- `GET /api/v1/notifications` — 列表（分页 + 未读过滤）
- `POST /api/v1/notifications/{id}/read` — 标记已读
- `POST /api/v1/notifications/read-all` — 全部已读
- `GET /api/v1/notifications/subscriptions` — 订阅列表
- `POST /api/v1/notifications/subscriptions` — 创建订阅
- `DELETE /api/v1/notifications/subscriptions/{id}` — 删除订阅

**验收**：Alert 触发时生成 Notification，SSE 推送到前端。

### WP3-T3：Notification Center UI

**改动文件**：
- `frontend/src/components/NotificationCenter.tsx` — 新建（上下文条 Bell 下拉）
- `frontend/src/pages/Notifications.tsx` — 新建（完整页面）

**实现要点**：
- Bell 图标显示未读数 Badge
- 下拉面板展示最近 10 条，点击跳转详情
- 完整页面用 DataExplorer，支持按类型/严重度/时间过滤
- 订阅管理 Tab：创建/编辑/删除订阅

**验收**：触发事件后 Bell Badge 更新，下拉面板展示新通知。
---

## 七、WP4：Alert / Incident / Runbook

**目标**：实现 Alert 规则引擎 + 去重 + Incident 聚合 + Runbook 注册与调用。

### WP4-T1：Alert Service 后端

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/alert_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/alerts.py` — 新建
- `LakeMindServer/migrations/versions/011_alerts_incidents.py` — 新建

**数据模型**：
```sql
alert_rules (
  id UUID PK, name VARCHAR, description TEXT,
  source VARCHAR, condition_json JSONB,
  severity VARCHAR, tenant_scope UUID[],
  enabled BOOLEAN, created_by UUID
)
alerts (
  id UUID PK, rule_id UUID, tenant_id UUID,
  source VARCHAR, severity VARCHAR, resource_type VARCHAR, resource_id UUID,
  title TEXT, evidence_json JSONB,
  status VARCHAR,  -- OPEN / ACKNOWLEDGED / RESOLVED / SILENCED
  first_seen TIMESTAMP, last_seen TIMESTAMP, count INT,
  runbook_id UUID, owner_id UUID,
  dedup_key VARCHAR  -- 去重键
)
```

**API**（设计 §14.2）：
- `GET/POST/PUT/DELETE /api/v1/alerts/rules`
- `GET /api/v1/alerts` — 列表 + 过滤(severity/status/tenant/source/time)
- `POST /api/v1/alerts/{id}/acknowledge`
- `POST /api/v1/alerts/{id}/resolve`
- `POST /api/v1/alerts/{id}/silence` — 静默 N 分钟

**去重**：相同 `dedup_key` 的 Alert 合并为一条，`count++`，`last_seen` 更新。

**验收**：同一规则触发的相同 Alert 不重复创建，count 递增。

### WP4-T2：Incident 聚合

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/incident_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/incidents.py` — 新建

**数据模型**：
```sql
incidents (
  id UUID PK, title TEXT, severity VARCHAR,
  status VARCHAR,  -- OPEN / INVESTIGATING / MITIGATING / MONITORING / RESOLVED
  commander_id UUID, tenant_id UUID,
  affected_objects JSONB, blast_radius_json JSONB,
  timeline_json JSONB, root_cause TEXT,
  created_at TIMESTAMP, resolved_at TIMESTAMP
)
incident_alerts (
  incident_id UUID, alert_id UUID
)
```

**API**（设计 §14.3）：
- `GET/POST /api/v1/incidents`
- `POST /api/v1/incidents/{id}/alerts/{alert_id}` — 关联 Alert
- `POST /api/v1/incidents/{id}/status` — 状态流转
- `POST /api/v1/incidents/{id}/commander` — 指定 Commander

**验收**：多个 Alert 可聚合为一个 Incident，状态流转正确。

### WP4-T3：Runbook 注册与调用

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/runbook_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/runbooks.py` — 新建
- `LakeMindServer/migrations/versions/012_runbooks.py` — 新建

**数据模型**：
```sql
runbooks (
  id UUID PK, name VARCHAR, description TEXT,
  trigger_condition_json JSONB,
  diagnosis_steps JSONB,  -- 有序步骤数组
  auto_steps JSONB,       -- 可自动执行的步骤
  manual_steps JSONB,
  risk_level VARCHAR, rollback_plan TEXT,
  validation_steps JSONB, owner_id UUID,
  authorized_roles VARCHAR[]
)
```

**API**（设计 §14.4）：
- `GET/POST/PUT/DELETE /api/v1/runbooks`
- `POST /api/v1/runbooks/{id}/execute` — 创建 Operation 执行 Runbook

**安全约束**：Steward 只能调用 `authorized_roles` 包含 steward 的 Runbook。

**验收**：注册的 Runbook 可被 Steward Finding 引用，执行时创建 Operation。

### WP4-T4：Alert/Incident UI

**改动文件**：
- `frontend/src/pages/Alerts.tsx` — 新建
- `frontend/src/pages/Incidents.tsx` — 新建
- `frontend/src/pages/Runbooks.tsx` — 新建

**Alert 列表**：DataExplorer + severity 颜色 + 状态过滤 + Acknowledge/Resolve/Silence 操作
**Incident 详情**：ObjectPageLayout + Timeline + 关联 Alert 列表 + Blast Radius
**Runbook 详情**：步骤展示 + 执行按钮（创建 Operation）

**验收**：Alert 可 Acknowledge/Resolve，Incident 可关联 Alert，Runbook 可执行。

---

## 八、WP5：Resource & Capacity + Service Topology

**目标**：实现服务拓扑图、Resource Center、Capacity Planning 和 Storage 视图。

### WP5-T1：Service Topology 后端与 UI

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/topology_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/services.py` — 扩展
- `frontend/src/pages/ServiceTopology.tsx` — 新建

**后端**（设计 §13.1–§13.2）：
- `GET /api/v1/services` — 服务列表（Control Center / Server / ModelServing / PostgreSQL / S3 / Lance / Valkey / Ray）
- `GET /api/v1/services/{id}/instances` — 实例列表
- `GET /api/v1/services/{id}/metrics` — 服务指标（health/error_rate/latency/throughput）
- `GET /api/v1/services/topology` — 拓扑图数据（节点 + 边 + 状态）

**拓扑数据结构**：
```json
{
  "nodes": [{"id": "server", "name": "LakeMindServer", "status": "healthy", "type": "control_plane"}, ...],
  "edges": [{"from": "control_center", "to": "server", "error_rate": 0.01, "latency_ms": 50, "traffic": 1000}, ...]
}
```

**前端**：
- 用 Ant Design + 自定义 SVG/Canvas 绘制拓扑图（或用 react-flow）
- 节点颜色按状态（healthy/degraded/unhealthy/unknown/maintenance）
- 点击节点跳转 Service 详情
- Service 详情用 ObjectPageLayout + Tabs(Overview/Instances/Metrics/Logs/Config/Dependencies/Operations/Incidents/Audit)

**验收**：拓扑图展示全部服务节点和调用关系，节点可点击跳转。

### WP5-T2：Resource Center 后端与 UI

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/resource_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/resources.py` — 新建
- `frontend/src/pages/ResourceCenter.tsx` — 新建

**后端**（设计 §13.3）：
- `GET /api/v1/resources` — 统一资源视图（compute/memory/gpu/storage/network/job_slot/model_concurrency/request_token/db_connection/queue）
- `GET /api/v1/resources/usage?tenant=xxx&by=tenant,agent,skill,job,model,service` — 使用量 + 归因
- `GET /api/v1/resources/capacity` — 容量与饱和点

**数据来源**：
- Docker stats API / cgroup 数据 → CPU/Memory
- SeaweedFS `/cluster/status` → Storage
- Valkey `INFO` → Cache
- PG `pg_stat_activity` → DB Connection
- Ray `ray status` → Compute/Job Slot

**前端**：
- 资源卡片网格（每类资源一张卡片：当前值/峰值/限额/使用率）
- 按租户/服务归因的堆叠柱状图
- 下钻到具体租户/Job/Model

**验收**：Resource Center 展示全部资源类型，可按租户归因。

### WP5-T3：Capacity Planning

**改动文件**：
- `frontend/src/components/CapacityForecast.tsx` — 新建
- `bff/app.py` — `GET /view/capacity-forecast` 聚合

**内容**（设计 §13.4）：
- 当前容量 / 峰值 / 趋势线 / 饱和点 / 预计耗尽时间
- 受影响 Tenant 列表
- 扩容或限流 Operation 创建入口

**实现要点**：
- 趋势用最近 7 天数据线性回归外推
- 预计耗尽 = (limit - current) / slope

**验收**：展示容量趋势线和预计耗尽时间。

### WP5-T4：Storage 视图

**改动文件**：
- `frontend/src/pages/StorageViews.tsx` — 新建
- `bff/app.py` — `GET /view/storage` 聚合

**内容**（设计 §13.5）：
- **PostgreSQL**：容量/连接/慢请求/Lock/Migration/Backup
- **S3 / SeaweedFS**：使用量/Tenant 分布/Orphan/Retention
- **Lance**：Index 数量/空间/Drift/Rebuild/Query Latency
- **Valkey**：Memory/Key/TTL/Eviction/Session

**验收**：4 个 Storage 子页面数据正确。

---

## 九、WP6：Steward Context Panel

**目标**：将 Steward 从独立聊天页升级为三形态（中央 Workspace + 对象页内嵌 + 后台巡检），实现 Daily Brief 和行动闭环。

### WP6-T1：Steward Context Panel 组件

**改动文件**：
- `frontend/src/components/StewardPanel.tsx` — 新建，可嵌入任意对象页的右侧抽屉
- `frontend/src/pages/StewardWorkspace.tsx` — 新建，中央 Workspace 页

**Context Panel 能力**（设计 §17.1 + §17.4）：
- 接收对象上下文（type + id），展示 Steward 对该对象的分析
- 预设问题模板（按对象类型）：
  - Job: "为什么这个 Job 失败？" / "比较这两个 Attempt"
  - Asset: "最近 24 小时哪些资产退化？" / "为什么 DEGRADED？"
  - Deployment: "禁用这个模型会影响什么？"
  - Config: "为什么配置 Revision N 没有生效？"
  - Knowledge: "哪些 Knowledge 因 Embedding 失败没有 READY？"
- 回答只使用用户有权访问的数据（权限过滤）
- 每条回答附证据链接

**实现要点**：
- Phase 1 用规则引擎 + 模板生成回答，不接 LLM
- 规则引擎根据对象状态查询相关数据，生成结构化回答
- 例：Job FAILED → 查询 job_events + logs → 匹配失败模式 → 返回根因 + 建议 Runbook

**验收**：在 Job 详情页打开 Steward Panel，展示失败原因分析 + 建议。

### WP6-T2：Daily Brief

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/steward_brief_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/steward.py` — 扩展 `GET /api/v1/steward/brief`
- `frontend/src/pages/DailyBrief.tsx` — 新建

**Brief 内容**（设计 §17.2）：
- 平台健康摘要
- Critical Issue 列表
- Tenant 风险
- Job 异常统计
- Asset Drift 汇总
- Model 异常
- Security Finding
- Capacity 预警
- Pending Approval
- 建议行动列表

**每条结论附证据链接**（设计 §17.2）。

**生成方式**：
- 规则引擎扫描各 Service 数据，生成结构化 Brief
- 缓存 5 分钟（Valkey），避免频繁查询
- 支持按需生成和定时生成（每天 8:00）

**验收**：Daily Brief 展示平台全局摘要，每条结论可点击跳转证据。

### WP6-T3：行动闭环

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/steward_action_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/steward.py` — 扩展

**闭环流程**（设计 §17.5）：
```
Steward Finding
  → 建议 Runbook
  → 创建 Operation（POST /api/v1/operations）
  → 权限检查
  → 审批（POST /api/v1/operations/{id}/approve）
  → 执行
  → Reconciler 验证
  → Steward 总结
```

**API**：
- `POST /api/v1/steward/findings/{id}/propose-action` — 从 Finding 生成 Operation Proposal
- `POST /api/v1/steward/findings/{id}/execute` — 执行（低风险自动，高风险需审批）
- `GET /api/v1/steward/action-history` — 行动历史

**自动治理等级**（设计 §17.6）：
- `observe`：只报告
- `low_risk_auto`：Retry/Reindex/Sync/Reload 自动执行
- `approval_required`：删除/撤销/停服/安全变更/禁用模型 必须审批

**验收**：Finding 可生成 Operation，低风险自动执行，高风险需审批。

### WP6-T4：Finding 视图增强

**改动文件**：
- `frontend/src/pages/StewardFindings.tsx` — 新建（替换现有 Steward.tsx 中的 Finding 部分）

**Finding 展示**（设计 §17.3）：
- DataExplorer 列表：问题/Severity/Confidence/Affected Objects/Status
- 详情：ObjectPageLayout
  - Evidence Drawer：证据列表（数据快照 + 链接）
  - Root Cause Hypothesis
  - Recommended Runbook（链接）
  - Risk 评估
  - Operation Proposal（一键创建）
  - Action History

**验收**：Finding 详情展示完整结构，可一键创建 Operation。

---

## 十、WP7：Saved Views 与 User Preferences

**目标**：实现持久化视图、用户偏好和 Dashboard Layout。

### WP7-T1：Control Center Metadata 后端

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/preferences_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/preferences.py` — 新建
- `LakeMindServer/migrations/versions/013_preferences.py` — 新建

**数据模型**（设计 §19.7）：
```sql
user_preferences (
  id UUID PK, principal_id UUID,
  pref_key VARCHAR, pref_value JSONB,
  updated_at TIMESTAMP
)
saved_views (
  id UUID PK, principal_id UUID, name VARCHAR,
  page VARCHAR,  -- 对应路由
  filters_json JSONB, columns_json JSONB, sort_json JSONB,
  is_shared BOOLEAN, tenant_id UUID,
  created_at TIMESTAMP
)
recent_objects (
  id UUID PK, principal_id UUID,
  object_type VARCHAR, object_id UUID, title VARCHAR,
  visited_at TIMESTAMP
)
```

**API**：
- `GET/PUT /api/v1/preferences/{key}` — 获取/设置偏好
- `GET/POST/DELETE /api/v1/saved-views` — Saved View CRUD
- `GET /api/v1/recent-objects` — 最近访问对象

**验收**：Saved View 可保存/加载，偏好持久化。

### WP7-T2：前端 Saved Views 集成

**改动文件**：
- `frontend/src/design/DataExplorer.tsx` — 集成 Saved View 选择器
- `frontend/src/components/SavedViewsPage.tsx` — 新建
- `frontend/src/hooks/useSavedView.ts` — 新建

**实现要点**：
- DataExplorer 工具栏增加 Saved View 下拉 + 保存按钮
- 保存当前 Filter + Columns + Sort 为 Named View
- 加载 Saved View 恢复完整状态
- Shared View 在租户内共享

**验收**：在 Jobs 列表保存 View "Failed Jobs Today"，刷新后可加载。
---

## 十一、WP8：BFF 聚合层增强

**目标**：BFF 从纯透传升级为聚合层，承担 View Model 组装、跨服务聚合、导出、Rate Limit 和 Error Normalization。

### WP8-T1：View Model 聚合端点

**改动文件**：
- `bff/app.py` — 新增多个 `GET /view/*` 端点
- `bff/view_models/` — 新建目录，存放 View Model 组装逻辑

**View Model 端点**：
- `GET /view/mission-control` — WP1（已定义）
- `GET /view/tenant-detail/{id}` — 聚合 Tenant + Members + Quotas + Usage + Assets + Jobs + Config + Security
- `GET /view/asset-detail/{id}` — 聚合 Asset + Bindings + Lineage + Quality + Access + Events
- `GET /view/job-detail/{id}` — 聚合 Job + Attempts + Timeline + Logs + Resources + Model Bindings
- `GET /view/deployment-detail/{id}` — 聚合 Deployment + Health + Instances + Routes + Usage + Logs
- `GET /view/service-detail/{id}` — 聚合 Service + Instances + Metrics + Dependencies + Incidents
- `GET /view/capacity-forecast` — WP5（已定义）
- `GET /view/storage` — WP5（已定义）
- `GET /view/steward-brief` — WP6（已定义）

**实现要点**（设计 §19.2）：
- 并行调 Server API（`asyncio.gather`）
- 权限感知：只聚合用户有权访问的数据
- 错误容忍：单个子查询失败不阻塞整体，用 `return_exceptions=True`
- 响应包含 `_meta`：`{ "request_id": "...", "correlation_id": "...", "partial_failure": [...] }`

**验收**：每个 View Model 端点单次请求 < 2s，子查询失败时标注 partial_failure。

### WP8-T2：导出端点

**改动文件**：
- `bff/app.py` — `POST /export` 端点
- `bff/export.py` — 新建

**实现要点**：
- 接受 `{ resource, filters, format, columns }`
- format: `csv` / `json` / `xlsx`
- 大数据集流式输出（StreamingResponse）
- 导出操作记审计

**验收**：Assets 列表可导出 CSV，包含当前过滤结果。

### WP8-T3：Rate Limit

**改动文件**：
- `bff/app.py` — Rate Limit 中间件
- `bff/rate_limiter.py` — 新建

**实现要点**：
- 基于 Valkey 的滑动窗口限流
- 按 principal_id + endpoint 限流
- 默认 100 req/min/user，可按端点配置
- 超限返回 429 + `Retry-After` header

**验收**：快速请求 100 次后返回 429。

### WP8-T4：Error Normalization

**改动文件**：
- `bff/app.py` — 全局异常处理器增强

**实现要点**：
- Server 返回的错误统一包装为 `{ "error": { "code": "...", "message": "...", "details": {...} } }`
- 401 → 前端跳转 Login
- 403 → 前端显示权限不足
- 429 → 前端显示限流提示
- 500 → 前端显示通用错误 + request_id（用于排查）
- 网络超时 → 503 + retry 建议

**验收**：所有错误响应格式统一，前端可统一处理。

---

## 十二、WP9：后端服务补全

**目标**：补齐设计方案 §20 要求的后端服务，为前端提供完整 API 支撑。

### WP9-T1：Organization Service 增强

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/organization_service.py` — 新建/扩展
- `LakeMindServer/src/lakemind_server/api/tenants.py` — 扩展

**补全内容**（设计 §20.1）：
- Tenant CRUD（Phase 0 已完成基础 CRUD）
- Tenant 创建向导后端（10 步数据校验 + Provisioning Saga）
- Group 管理（`GET/POST/PUT/DELETE /api/v1/tenants/{id}/groups`）
- Entitlement 管理（`GET/PUT /api/v1/tenants/{id}/entitlements`）
- Quota 管理（`GET/PUT /api/v1/tenants/{id}/quotas`）
- Budget 管理（`GET/PUT /api/v1/tenants/{id}/budget`）
- Template 管理（配置模板 + 保留策略模板）
- Usage 聚合（`GET /api/v1/tenants/{id}/usage` — 聚合 assets/jobs/storage/model 用量）

**Tenant 详情页数据**（设计 §8.2）：
- Overview：健康/用量/风险/变更/待处理
- Members：Users/Groups/Agents/Service Accounts/Role Bindings/最近登录/Token/Session
- Entitlements：可用 Asset 类型/Skill/模型/Provider/网络能力
- Quotas：Asset Storage/Knowledge/Memory/Job 并发/CPU/Memory/GPU/API Rate/Model Token/Budget
- Resources：当前使用/峰值/趋势/预测/超限历史

**验收**：Tenant 创建向导 10 步全部可提交，详情页各 Tab 数据正确。

### WP9-T2：Alert & Incident Service

**改动文件**：
- 已在 WP4-T1/T2 定义后端，此处补全规则引擎

**规则引擎**：
- 定时扫描（每 60s）各数据源
- 规则类型：
  - `job_failure_rate` — Job 失败率超阈值
  - `model_unhealthy` — Deployment health = UNHEALTHY
  - `asset_drift` — Asset health = DEGRADED
  - `capacity_forecast` — 预计耗尽 < 24h
  - `config_drift` — Desired ≠ Active 超过 N 分钟
  - `security_finding` — Steward Finding severity = CRITICAL
  - `tenant_quota_exceeded` — Tenant 用量超配额
- 触发时创建 Alert → 发 Notification → 发 SSE 事件

**验收**：模拟 Job 失败率超阈值，Alert 自动触发。

### WP9-T3：Search Service

已在 WP2-T1 定义，此处补全投影更新机制。

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/search_service.py` — 扩展
- 各 Service 的 Outbox 消费者

**投影更新**：
- 各 Service 创建/更新/删除对象时发布 Outbox 事件
- Search Service 消费 Outbox 事件，更新 `search_projection` 表
- 全量重建：`POST /api/v1/search/rebuild`（管理员）

**验收**：创建 Asset 后搜索可立即找到，删除后搜索不再返回。

### WP9-T4：Notification Service

已在 WP3-T2 定义后端 API，此处补全通知渠道。

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/notification_service.py` — 扩展

**渠道**（设计 §14.6）：
- `in_app` — 写 DB + SSE 推送
- `email` — SMTP 发送（Phase 1 基础实现，可配置开关）
- `webhook` — POST 到用户配置的 URL

**验收**：配置 email 订阅后，Alert 触发时收到邮件。

### WP9-T5：Change Management

**改动文件**：
- `LakeMindServer/src/lakemind_server/services/change_service.py` — 新建
- `LakeMindServer/src/lakemind_server/api/changes.py` — 新建
- `LakeMindServer/migrations/versions/014_changes.py` — 新建

**数据模型**：
```sql
changes (
  id UUID PK, change_type VARCHAR,  -- config / model / permission / version / maintenance
  target_type VARCHAR, target_id UUID,
  tenant_id UUID, initiated_by UUID,
  summary TEXT, details_json JSONB,
  related_incident_id UUID,
  maintenance_window_id UUID,
  rollback_available BOOLEAN, rollback_rate FLOAT,
  created_at TIMESTAMP
)
```

**API**（设计 §14.5）：
- `GET /api/v1/changes` — Change Timeline（过滤 + 日历视图）
- `GET /api/v1/changes/stats` — 变更失败率 + 回滚率

**自动记录**：所有 Operation / Config Rollout / Model Deployment 变更自动写入 changes 表。

**验收**：执行 Config Rollout 后 Change Timeline 出现记录，可查看详情。

---

## 十三、WP10：测试与硬化

**目标**：E2E 测试 + 性能测试 + 安全测试 + 验收证据包。

### WP10-T1：E2E 测试

**改动文件**：
- `LakeMindControlCenter/frontend/e2e/` — 新建目录
- `LakeMindControlCenter/frontend/e2e/playwright.config.ts`
- `LakeMindControlCenter/frontend/e2e/tests/*.spec.ts`

**测试场景**（对应设计 §23 验收场景）：
1. 创建和运营 Tenant（创建→配额→模型→配置→观察 Provisioning→确认 Active→审计）
2. 定位失败 Job（首页→Failed Jobs→详情→Timeline→Logs→Diagnosis→Runbook）
3. 模型路由变更（Deployment→Route Builder→影响分析→审批→激活→验证）
4. Knowledge DEGRADED（首页→Asset Drift→详情→Binding→Reindex→验证）
5. 配置变更（Configuration→编辑→Validate→Impact→审批→Activate→Drift 检查）
6. 安全审计（Audit Explorer→Correlation→从资源跳转→导出）
7. Steward 治理（Daily Brief→Finding→建议 Runbook→创建 Operation→审批→执行→验证）

**工具**：Playwright

**验收**：7 个 E2E 场景全部通过。

### WP10-T2：性能测试

**改动文件**：
- `scripts/perf_test.py` — 新建

**测试项**：
- BFF View Model 端点 P95 < 2s
- Search 查询 P95 < 500ms
- SSE 连接支持 50 并发
- 列表页 1000 条数据虚拟滚动流畅
- 首页首屏加载 < 3s

**工具**：locust / k6

**验收**：全部性能指标达标。

### WP10-T3：安全测试

**改动文件**：
- `scripts/security_test.py` — 新建

**测试项**：
- 跨租户隔离：Tenant A 用户无法访问 Tenant B 数据（全端点矩阵测试）
- CSRF：无 token / 错误 token → 403
- Session：过期 / 撤销后 → 401
- XSS：输入 `<script>` 在列表/详情/搜索中不执行
- IDOR：直接访问无权对象 URL → 403
- Rate Limit：超限 → 429
- Secret 不泄露：API 响应不含明文 Secret

**验收**：全部安全测试通过。

### WP10-T4：验收证据包

**改动文件**：
- `scripts/collect_evidence.py` — 新建
- `reports/phase1-acceptance/` — 新建目录

**证据内容**：
- E2E 测试报告（Playwright HTML report）
- 性能测试报告
- 安全测试报告
- API 契约比对报告（OpenAPI vs 实现）
- Migration 审计（009–014 全部已应用）
- 部署验证截图
- 门禁检查清单

**门禁检查清单**：
- [ ] 8 一级导航全部可访问
- [ ] Mission Control 4 屏数据正确
- [ ] 全局搜索返回正确结果
- [ ] ⌘K Command Palette 可用
- [ ] SSE 实时推送工作
- [ ] Notification Center 展示未读
- [ ] Alert 规则引擎触发正确
- [ ] Incident 聚合正确
- [ ] Runbook 可执行
- [ ] Service Topology 展示全部服务
- [ ] Resource Center 展示全部资源
- [ ] Steward Context Panel 在对象页可用
- [ ] Daily Brief 生成正确
- [ ] Finding → Operation 闭环完整
- [ ] Saved Views 保存/加载正确
- [ ] BFF View Model P95 < 2s
- [ ] 跨租户隔离全端点通过
- [ ] 7 个 E2E 场景全部通过

**验收**：证据包完整，门禁清单全部勾选。

---

## 十四、估算汇总

| WP | 低估(人日) | 高估(人日) | 说明 |
|----|-----------|-----------|------|
| WP0 | 6 | 8 | 路由重组 + 设计系统 + 框架组件 |
| WP1 | 4 | 6 | BFF 聚合 + 4 屏 + 角色化 |
| WP2 | 3 | 4 | Search Projection + UI |
| WP3 | 4 | 5 | SSE + Notification |
| WP4 | 5 | 7 | Alert + Incident + Runbook |
| WP5 | 5 | 7 | Topology + Resource + Capacity + Storage |
| WP6 | 5 | 7 | Steward Panel + Brief + 闭环 |
| WP7 | 2 | 3 | Saved Views + Preferences |
| WP8 | 5 | 6 | BFF 聚合 + 导出 + 限流 |
| WP9 | 8 | 12 | 5 个后端服务补全 |
| WP10 | 8 | 14 | E2E + 性能 + 安全 + 证据 |
| **合计** | **55** | **79** | **3 名开发 → 4–5 周** |

---

## 十五、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| BFF 聚合查询性能不达标 | 中 | 高 | 并行查询 + 缓存 + View Model 精简 |
| SSE 连接稳定性 | 中 | 中 | 断线重连 + Last-Event-ID + 心跳 |
| Search Projection 一致性 | 低 | 中 | Outbox 事件驱动更新 + 定时全量校验 |
| Steward 规则引擎覆盖不足 | 中 | 低 | Phase 1 只覆盖核心场景，Phase 2 引入 LLM |
| 前端路由重组引入回归 | 中 | 中 | E2E 测试先行 + 逐步迁移 |
| 后端服务补全工作量超估 | 中 | 高 | WP9 可拆分迭代，先补全 P0 端点 |

---

## 十六、交付物清单

### 文档
- `reports/CONTROL-CENTER-Phase1-开发计划.md` — 本文档
- `reports/phase1-acceptance/` — 验收证据包

### ADR
- `.agent/adr/ADR-013-phase1-bff-aggregation.md` — BFF 聚合层设计
- `.agent/adr/ADR-014-phase1-sse-realtime.md` — SSE 实时网关设计
- `.agent/adr/ADR-015-phase1-search-projection.md` — Search Projection 设计
- `.agent/adr/ADR-016-phase1-steward-rule-engine.md` — Steward 规则引擎设计

### Migration
- `009_search_projection.py` — Search Projection 表
- `010_notifications.py` — Notification 表
- `011_alerts_incidents.py` — Alert + Incident 表
- `012_runbooks.py` — Runbook 表
- `013_preferences.py` — User Preferences + Saved Views 表
- `014_changes.py` — Change Management 表

### API 契约
- `docs/api-spec/v0.2.2/control-center-phase1.yaml` — Phase 1 OpenAPI 契约

### 前端
- 8 一级导航 + 全部二级页面
- App Shell + ContextBar + RouteGuard + DesignSystem + DataExplorer + ObjectPageLayout
- GlobalSearch + CommandPalette + NotificationCenter + StewardPanel
- SavedViews + FeatureFlags

### BFF
- View Model 聚合端点（10+）
- SSE 实时网关
- 导出 + Rate Limit + Error Normalization

### 后端
- Organization Service 增强
- Alert & Incident Service + 规则引擎
- Search Service + Projection
- Notification Service + 渠道
- Change Management Service
- Resource & Topology Service
- Steward Brief + Action Service
- Preferences Service
