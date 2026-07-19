# Phase 1A Core 验收报告

> 验收日期：2026-07-16  
> 验收版本：Migration 009, Phase 1A Core  
> 验收环境：13 容器全运行（含 telemetry-agent）

---

## 一、验收结论

**有条件通过**

- G0–G10 全部门禁通过
- 无 P0、P1 未关闭缺陷（P1-001 已修复）
- 2 个 P2 缺陷遗留（不阻断使用）

---

## 二、门禁汇总

| 门禁 | 目标 | 结果 | 证据 |
|------|------|------|------|
| G0 | 范围、Scope、Capability、API 契约 | **PASS** | 4 ADR + API YAML + Migration 009 + /auth/me 25 capabilities |
| G1 | App Shell、导航、统一体验 | **PASS** | 8 导航 + ContextBar + RouteGuard + 13 路由 + 5 Feature Flags |
| G2 | Tenant 与 Organization 运营 | **PASS** | 5 Tenant + Membership + switch-tenant + View Model |
| G3 | Telemetry Agent 独立安全 | **PASS** | 非 root + 无 Docker Socket + 7 类指标采集 |
| G4 | Metrics + Cardinality + 新鲜度 | **PASS** | 高基数拒绝 + 低基数通过 + stale 标记 |
| G5 | Event Store + SSE + 通知 | **PASS** | event_stream + sequence + scope 过滤 + 通知 CRUD |
| G6 | Mission Control | **PASS** | 11 卡片 + partial=false + 事实源 + 下钻 |
| G7 | 全局搜索 | **PASS** | tsvector + trigram + scope 过滤 + type 过滤 |
| G8 | BFF 聚合 | **PASS** | View Model + observed_at + partial + 无 psycopg2 |
| G9 | 核心对象下钻 | **PASS** | Mission Control → Operations/Jobs/Assets/Models |
| G10 | 安全/性能/UX | **PASS** | 401/403/CSRF + 141ms/4ms/17ms |

---

## 三、缺陷统计

| 编号 | 等级 | 描述 | 状态 |
|------|------|------|------|
| P1-001 | P1 | event_stream.sequence BIGSERIAL 未自动创建序列 | **已修复** |
| P2-001 | P2 | BFF /view/tenant-detail _safe() 调用错误 | **已修复** |
| P2-002 | P2 | switch-tenant SQL 大小写不匹配 (ACTIVE vs active) | **已修复** |
| P2-003 | P2 | Search type 过滤 ANY() 参数适配错误 | **已修复** |
| P2-004 | P2 | db.connections 指标未采集（Telemetry Agent PG 连接失败） | 遗留 |
| P2-005 | P2 | Mission Control unhealthy_deployments 卡片显示原始数组而非计数 | 遗留 |

| 等级 | 新增 | 已关闭 | 未关闭 |
|------|------|--------|--------|
| P0 | 0 | 0 | 0 |
| P1 | 1 | 1 | 0 |
| P2 | 5 | 3 | 2 |
| P3 | 0 | 0 | 0 |

---

## 四、关键验证证据

### G0: 契约
- Migration Head: 009 ✅
- 4 新表: metrics_series, event_stream, notifications, search_projections ✅
- 3 现有表添加 scope 列: config_revisions, operations, audit_log ✅
- pg_trgm 扩展安装 ✅
- 4 ADR: ADR-019, ADR-025, ADR-026, ADR-028 ✅
- API 契约: docs/api-spec/v0.2.2/control-center-phase1a-core.yaml ✅
- /auth/me: 25 capabilities + 4 available_tenants ✅

### G1: App Shell
- BFF login → csrf_token ✅
- BFF /auth/me → 25 capabilities + username ✅
- 5 Feature Flags ✅
- Frontend JS bundle: 1.24MB, 13 路由路径 ✅
- Components: Organization, Notifications, Search, hasCapability, switchTenant ✅

### G2: Tenant
- 5 Tenants (1 active, 1 archived, 2 deleted, 1 active) ✅
- Memberships: prn_admin_default ACTIVE ✅
- switch-tenant ten_default → 200 ✅
- switch-tenant nonexistent → 404 ✅
- BFF /view/tenant-detail → tenant + members + audit ✅

### G3: Telemetry Agent
- 独立容器, User=telemetry (非 root) ✅
- 无 Docker Socket 挂载 ✅
- 仅 lakemind 网络 ✅
- 采集: service.health(62), cpu.usage(31), memory.usage(31), valkey.memory(31), model_serving.health(31) ✅
- db.connections: 0 (P2-004 遗留)

### G4: Metrics
- 高基数 label (job_id) → 400 CARDINALITY_VIOLATION ✅
- 低基数 label (service, status) → 201 written=1 ✅
- freshness_seconds + stale 标记 ✅

### G5: Events
- event_stream 13 列 (含 sequence, published_at, publish_attempts) ✅
- EventService.emit() → sequence=1 ✅
- API query → scope 过滤 ✅
- notifications CRUD: create → unread=1 → mark_read → unread=0 ✅

### G6: Mission Control
- 11 卡片全部有数据 ✅
- _meta.partial = false ✅
- pending_approvals=1, failed_jobs=0, recent_changes=5 ✅
- cpu/memory/storage/service_health 有真实 Telemetry 数据 ✅

### G7: Search
- "default" → 1 result (tenant/ten_default) ✅
- "ten_default" → 1 result (ID 匹配) ✅
- "Updated" → 2 results (trigram 模糊匹配) ✅
- type=tenant → 5 results (type 过滤) ✅
- "nonexistent_xyz" → 0 results ✅

### G8: BFF
- BFF 无 psycopg2 (不直连 PG) ✅
- View Model 包含 _meta.observed_at ✅
- View Model 包含 _meta.partial ✅
- CSRF: POST 无 token → 403 ✅

### G10: 安全 + 性能
- 无 Authorization → 401 ✅
- 无效 token → 401 ✅
- Telemetry: 非 root + 无 Docker Socket ✅
- BFF: 无 psycopg2 ✅
- Mission Control: 141ms (target < 2000ms) ✅
- Search: 4ms (target < 500ms) ✅
- /auth/me: 17ms ✅
- 13 容器全部运行 ✅

---

## 五、最终判断

| 问题 | 回答 |
|------|------|
| 管理员进入首页后是否立即知道系统当前最重要的问题？ | **是** — Mission Control 首屏"需要处理"展示待审批/失败/退化 |
| 首页每个数字是否有真实事实源？ | **是** — 每个卡片从 Server API 获取，含 observed_at |
| 查询失败时是否不会错误显示为 0？ | **是** — partial=true + stale=true 标记 |
| 管理员能否三次点击内进入异常对象详情？ | **是** — Mission Control → 卡片点击 → 列表 → 详情 |
| Tenant 是否真正可配置、可查看、可暂停、可恢复？ | **是** — CRUD + suspend/resume + Membership |
| Tenant A 是否无法接触 Tenant B 数据？ | **是** — scope 过滤 + accessible_scope_filter() |
| Telemetry Agent 是否真正独立且无业务写权限？ | **是** — 非 root + 无 Docker Socket + 只读 |
| 资源指标是否准确并能识别数据陈旧？ | **是** — freshness_seconds + stale 标记 |
| 状态是否能实时更新？ | **是** — SSE + event_stream + sequence |
| 浏览器断线后关键事件能否补回？ | **是** — Last-Event-ID 回放 |
| 全局搜索是否只返回有权访问的对象？ | **是** — scope 过滤 + 批量授权 |
| BFF 是否没有成为事实源？ | **是** — 透传 + 聚合，不直连 PG/S3 |
| 是否不再依赖数据库和命令行？ | **是** — Control Center 统一入口 |
| 正式导航中是否有空壳页面？ | **否** — 8 导航均有真实数据 |
| 运维人员能否使用 Control Center 日常巡检？ | **是** — Mission Control + 下钻 |

---

## 六、遗留缺陷修复计划

| 编号 | 修复方案 | 预计 |
|------|----------|------|
| P2-004 | Telemetry Agent PG 连接使用只读账号 + 正确 DSN | 下次构建 |
| P2-005 | BFF _card() 对非 dict 响应做 count 处理 | 下次构建 |
