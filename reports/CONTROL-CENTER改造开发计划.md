# Control Center Phase 0 改造开发计划（v3）

> 基于 `v0.2.0.design/LakeMind_Control_Center_世界级改造设计方案.md` §22.1  
> 及评审意见 v1 → v2 → v3 修订  
> 基准日期：2026-07-16  
> 评审状态：v3 待评审（v2 有条件通过，已纳入 14 项新增任务 + 6 项修正）

---

## 〇、评审修订摘要

### v1 → v2 修订（4 个阻断项）

| # | 阻断项 | v1 错误 | v2 修正 |
|---|--------|---------|---------|
| 1 | Tenant 隔离 | BFF 传 tenant_id | Server 从 SecurityContext 解析，BFF 不注入可信 Tenant Header |
| 2 | BFF Token fallback | 用户 token 过期 → BFF_TOKEN | 返回 401，前端重新登录，BFF_TOKEN 仅用于服务自身 |
| 3 | Model Deployment 同步 | 直接调 ModelServing register | Desired/Active Revision + Outbox + Reconciler |
| 4 | Steward 巡检 | 错误查询 + DB 直连 | 调用 ReconciliationService/ConfigurationService/JobService |

### v2 → v3 修订（14 项新增任务 + 6 项修正）

**14 项新增任务**：

| 任务 | WP | 内容 |
|------|-----|------|
| WP0-T7 | WP0 | Principal–Tenant Membership 模型（多租户成员关系） |
| WP0-T8 | WP0 | Token 权限即时生效（Security Version + Opaque Token 机制） |
| WP1-T6 | WP1 | Session 撤销/失效/Valkey 安全（滑动过期 + 并发失效 + revocation list） |
| WP2-T4 | WP2 | Tenant Provisioning Saga + 幂等 + 补偿事务 |
| WP3-T4 | WP3 | Model Test/Readiness/Active 三维度状态拆分与上报 |
| WP3-T5 | WP3 | Config Rollout + 不可变 Revision + 并发控制（乐观锁） |
| WP4-T3 | WP4 | Job 日志归档 + Retention 策略（S3 lifecycle） |
| WP4-T4 | WP4 | Job Event/Timeline 完整性（事件溯源 + 因果排序） |
| WP4-T5 | WP4 | Asset Health/Quality 后端 API（四维度评分 + drift 检测） |
| WP5-T5 | WP5 | Steward Finding 持久化/去重/状态机（Finding → Acknowledge → Resolve） |
| WP5-T6 | WP5 | Request/Correlation ID 全链路传播（BFF→Server→MCP→Steward） |
| WP6-T4 | WP6 | 前端 E2E + 浏览器安全测试（Playwright + OWASP ZAP 基线） |
| WP6-T5 | WP6 | API 契约与前后端 Schema 自动比对（OpenAPI → TS codegen + drift check） |
| WP6-T6 | WP6 | 验收证据包 + 发布门禁报告（自动化证据收集 + 可追溯发布） |

**6 项修正**：

| # | 修正项 | 问题 | v3 修正 |
|---|--------|------|---------|
| 1 | Tenant Provisioning 执行顺序 | v2 先创建 Tenant 记录再创建依赖资源 | 改为 Saga 编排：先校验→创建 Principal+Membership→创建 Config Scope→创建 Secret Namespace→创建 Tenant 记录（最后），每步可补偿 |
| 2 | Model 三维度状态 | v2 只有 Desired/Active 二维度 | 拆分为 Test（模型可用性测试）、Readiness（部署就绪检查）、Active（运行时实际状态）三维度独立上报 |
| 3 | Config Revision/Rollout 分离 | v2 将 Rollout 混在 Config 编辑闭环中 | 独立 WP3-T5：Revision 不可变（append-only），Rollout 有独立状态机 + 并发控制（乐观锁 version） |
| 4 | Steward Outbox 检查 | v2 在禁止项中列出了"用 job_runs 代替 outbox"等错误备选项，可能误导 | 删除错误备选项列表，只保留正确检查方式描述 |
| 5 | CSRF 刷新恢复 | v2 未处理页面刷新后 CSRF token 丢失 | CSRF token 存入 Session（Valkey），刷新时从 Session 恢复，不依赖前端内存 |
| 6 | Operation 按钮状态 | v2 未明确前端按钮状态机 | 明确：PENDING→Cancel；APPROVAL_REQUIRED→Approve+Reject+Cancel；EXECUTING→禁用；COMPLETED→详情；FAILED→Retry+详情；REJECTED→详情 |

**估算修订**：43–65 人日 → **66–92 人日**（3 名开发 → 约 4–5 周开发 + 1 周集成测试）。

---

## 一、Phase 0 范围（6 个工作包 + 门禁）

| WP | 名称 | 核心目标 | 任务数 |
|----|------|----------|--------|
| WP0 | 架构纠偏与契约冻结 | 冻结安全模型、状态机、API 契约，不带着争议编码 | T1–T8 |
| WP1 | 身份、Session 和 Tenant 安全 | Server 端租户隔离 + Valkey Session + CSRF + 委托身份 + Session 安全 | T1–T6 |
| WP2 | Tenant 最小运营闭环 | 创建/配额/模型权限/暂停/归档 + Provisioning Saga | T1–T4 |
| WP3 | 模型和配置收敛闭环 | Desired/Active Revision + 三维度状态 + Config Draft/Activate/Rollback + Rollout 并发控制 | T1–T5 |
| WP4 | Job 和 Asset 运营闭环 | Job 全维度详情 + 日志归档 + Event Timeline + Asset Health API | T1–T5 |
| WP5 | Operation、Audit 和 Steward | Operation Reject/Cancel + Audit Correlation + Steward 真实巡检 + Finding 持久化 + 全链路追踪 | T1–T6 |
| WP6 | 测试、迁移和硬化 | 跨租户矩阵 + 故障注入 + E2E + Schema 比对 + 验收证据包 | T1–T6 |

---

## 二、WP0：架构纠偏与契约冻结

**门禁：不允许带着以下任一未决争议开始编码。**

### WP0-T1：安全模型 ADR

产出文档 `.agent/adr/ADR-011-control-center-security.md`，冻结：

```
用户登录 → Server 签发 Token（含 principal_id, tenant_id, roles, scopes, security_version, expires_at）
  → BFF 存入 Valkey Session（key=sess_id, value={token, principal_id, tenant_id, csrf_token, ...}, TTL=3600）
  → BFF 设置 HttpOnly + Secure + SameSite=Lax cookie

用户请求 → BFF 从 cookie 提取 session_id → Valkey 查 session → 取 user token
  → BFF 用 user token 调 Server（Authorization: Bearer <user_token>）
  → Server 从 Token 解析 SecurityContext（principal_id, tenant_id, roles, scopes, security_version）
  → 校验 security_version >= principal.current_security_version（否则 401 强制重新登录）
  → 所有查询自动追加 WHERE tenant_id = ctx.tenant_id

用户 token 过期 → Server 返回 401 → BFF 返回 401 → 前端跳转 Login
  （禁止 fallback 到 BFF_TOKEN）

Platform Admin 跨租户查看 → 请求带 target_tenant_id 参数
  → Server 校验 ctx.has_scope("tenant:cross")
  → 查询使用 target_tenant_id 而非 ctx.tenant_id
```

**禁止**：
- BFF 注入 `X-Tenant-Id` 作为可信身份来源
- BFF_TOKEN 作为用户请求 fallback
- 前端做租户过滤

### WP0-T2：Model Desired/Active 状态机

```
Deployment 状态：
  DRAFT → DISABLED → ENABLING → ACTIVE → DISABLING → DISABLED
                                     ↓
                               FAILED / DRIFTED

Config Revision 状态（不可变，append-only）：
  DRAFT → VALIDATED → APPLYING → ACTIVE
                             ↓
                       FAILED → ROLLED_BACK

收敛流程：
  Control Plane 写 Desired Revision
    → Outbox 事件
    → Reconciler 拉取 Desired
    → 调用 ModelServing Apply
    → ModelServing 上报 Active Revision
    → Control Plane 比对 Desired == Active → CONVERGED
    → 否则 → DRIFTED，触发告警 + Steward Finding
```

**禁止**：`create_deployment` 直接同步调用 ModelServing register。

### WP0-T3：Operation 适用范围

| 操作 | 经 Operation？ | 风险等级 | 审批？ |
|------|---------------|---------|--------|
| 创建 Model Definition | 否（直接 + Audit） | — | — |
| Enable/Disable Deployment | ✅ | low | 否 |
| 创建/删除 Route | ✅ | low | 否 |
| 激活 Config Revision | ✅ | low | 否 |
| 回滚 Config | ✅ | medium | 是（影响运行中服务） |
| 创建 Tenant | ✅ | medium | 是 |
| Suspend/Archive Tenant | ✅ | high | 是 |
| Reindex Asset | ✅ | low | 否 |
| Delete Asset | ✅ | high | 是 |
| Retry Job | ✅ | low | 否 |

### WP0-T4：Steward 调用契约

```
Steward → Control Plane Service API（HTTP）
  ├─ ReconciliationService.get_outbox_backlog()
  ├─ ReconciliationService.get_binding_drift()
  ├─ ConfigurationService.get_config_drift()
  ├─ JobService.list_jobs(status="LOST")
  ├─ AssetService.list_assets(status="DEGRADED")
  └─ InstanceService.list_instances()

禁止：Steward 直连 PostgreSQL
```

### WP0-T5：API 契约冻结

产出 `docs/api-spec/v0.2.1/control-center-phase0.yaml`，覆盖所有新增/修改端点。

### WP0-T6：数据迁移方案

| 变更 | 迁移 |
|------|------|
| Session 内存 → Valkey | 无数据迁移，BFF 重启后旧 session 自然失效，用户重新登录 |
| 旧 BFF_TOKEN 模式 | 部署后旧 token 不再被接受（Server 端校验 token 类型） |
| Operation 新增 REJECTED 状态 | `ALTER TYPE` 或新增行值，向后兼容 |
| Model Deployment 新状态 | 现有 `enabled` 记录映射为 `ACTIVE`，`disabled` 映射为 `DISABLED` |
| Config Revision 表 | 已有，无需迁移 |
| principal_tenant_membership 表 | 新建表，从现有 user_tenant 关系迁移 |
| security_version 列 | `ALTER TABLE principals ADD COLUMN security_version BIGINT DEFAULT 0` |
| steward_findings 表 | 新建表，无历史数据迁移 |

### WP0-T7：Principal–Tenant Membership 模型

**问题**：v2 未定义多租户成员关系数据模型，Principal 与 Tenant 的 Membership 关系不明确。

**产出**：ADR + 数据模型 + 迁移脚本

```
principals（已有，增强）
  + security_version BIGINT NOT NULL DEFAULT 0  -- 权限变更时递增，使旧 Token 失效

principal_tenant_memberships（新建）
  id UUID PK
  principal_id UUID FK → principals
  tenant_id UUID FK → tenants
  role_binding_id UUID FK → role_bindings
  membership_status VARCHAR(32)  -- ACTIVE / INVITED / REVOKED
  invited_by UUID FK → principals
  invited_at TIMESTAMP
  joined_at TIMESTAMP
  revoked_at TIMESTAMP
  UNIQUE(principal_id, tenant_id)
```

**语义**：
- 一个 Principal 可属于多个 Tenant（多租户成员）
- Principal 登录时选择 Tenant（或默认第一个 ACTIVE membership）
- Platform Admin 的 membership 跨所有 Tenant
- Revoke membership → 递增 `principal.security_version` → 所有该 Principal 的 Token 立即失效

**迁移**：从现有 `user_tenant` 关系表导入，`membership_status = 'ACTIVE'`。

### WP0-T8：Token 权限即时生效（Security Version / Opaque Token）

**问题**：v2 的 Token 签发后权限变更无法即时生效，需等 Token 自然过期。

**方案**：Security Version 机制

```
Token 内嵌 security_version（签发时 principal.security_version 的快照）
  → 每次请求 Server 校验 token.security_version == principal.security_version
  → 不匹配 → 401（强制重新登录）
  → 匹配 → 正常处理

权限变更触发：
  - Role Binding 变更 → principal.security_version++
  - Membership Revoke → principal.security_version++
  - Tenant Suspend → 该 Tenant 下所有 Principal 的 security_version++
  - Token 显式 Revoke → 加入 Valkey revocation list（TTL = token 剩余有效期）
```

**Valkey revocation list**：
- Key: `cc:revoked:{jti}`（jti = Token 唯一 ID）
- Value: `1`
- TTL: Token 剩余有效期
- 每次请求校验 jti 不在 revocation list 中

**禁止**：
- Server 端不做 security_version 校验（必须做）
- 用黑名单替代 security_version（黑名单只作为补充，处理单 Token 显式撤销）

---

## 三、WP1：身份、Session 和 Tenant 安全

### WP1-T1：Session 迁移到 Valkey

| 文件 | 改动 |
|------|------|
| `bff/app.py` | 删除 `_sessions` dict；新增 `_session_get/set/del` 调用 Valkey |
| `bff/app.py` | Session ID 用 `secrets.token_urlsafe(32)` 生成 |
| `bff/app.py` | Session 存储 `{token, principal_id, tenant_id, roles, csrf_token, security_version, created_at, last_access, jti}` |
| `bff/app.py` | Valkey key: `cc:session:{sid}`, TTL=3600 |
| `control/pyproject.toml` | 加 `redis>=5.0` |
| `docker-compose.yml` | `control-center` 加 `VALKEY_HOST=lakemind-valkey` |

**安全要求**：
- Session ID 足够随机（256 bit）
- 绝对过期 + 闲置过期
- Logout 删除 Valkey key
- Cookie: HttpOnly + Secure（生产）+ SameSite=Lax + Path=/
- 登录时 Session Rotation（防 Fixation）

### WP1-T2：BFF 委托身份

| 文件 | 改动 |
|------|------|
| `bff/app.py` | `_cp_call` 使用 `session["token"]` 作为 Authorization Bearer |
| `bff/app.py` | `_cp_call` 不再注入 `X-Tenant-Id` |
| `bff/app.py` | Server 返回 401 → BFF 返回 401（不 fallback） |
| `bff/app.py` | BFF_TOKEN 仅用于 `/health` 和服务注册 |

### WP1-T3：Server 端 Tenant 隔离

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../api/assets.py` | `get_bindings`、`get_lineage` 加 `ctx = get_security_context(request)` + 租户过滤 |
| `LakeMindServer/src/.../api/operations.py` | `get`、`cancel` 加安全上下文 + 租户过滤 |
| `LakeMindServer/src/.../api/models.py` | 所有端点加安全上下文；非平台管理员只能看本租户模型 |
| `LakeMindServer/src/.../api/audit.py` | 确认已有租户隔离（已有） |
| `LakeMindServer/src/.../api/configuration.py` | 加安全上下文，租户 scope 隔离 |

**Platform Admin 跨租户**：
- 新增 `target_tenant_id` query 参数
- Server 校验 `ctx.has_scope("tenant:cross")`
- 使用 `target_tenant_id` 查询

### WP1-T4：CSRF 防护

| 文件 | 改动 |
|------|------|
| `bff/app.py` | 登录成功生成 `csrf_token = secrets.token_urlsafe(32)`，存入 Session（Valkey） |
| `bff/app.py` | 所有 unsafe methods（POST/PUT/PATCH/DELETE）校验 `X-CSRF-Token` header == session.csrf_token |
| `bff/app.py` | 同时校验 `Origin` header |
| `bff/app.py` | 登录和 Session Rotation 时重新生成 csrf_token |
| `bff/app.py` | Logout 删除 csrf_token |
| `bff/app.py` | **页面刷新恢复**：GET 请求时从 Valkey Session 读取 csrf_token，通过 `X-CSRF-Token` response header 返回前端 |
| `frontend/src/api/client.ts` | 登录响应提取 csrf_token，存入内存变量（非 localStorage） |
| `frontend/src/api/client.ts` | **刷新恢复**：应用初始化时调 `GET /auth/csrf` 获取当前 session 的 csrf_token |
| `frontend/src/api/client.ts` | axios 拦截器自动注入 `X-CSRF-Token` header |

**CSRF 刷新恢复流程**：
```
页面刷新 → 前端内存变量丢失 → 应用初始化
  → GET /auth/csrf（带 HttpOnly cookie）
  → BFF 从 Valkey Session 读取 csrf_token
  → 返回 X-CSRF-Token header
  → 前端存入内存变量
  → 后续 unsafe 请求正常携带
```

### WP1-T5：移除密码提示 + 删除 Echo WebSocket

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/Login.tsx` | 移除 placeholder 中的密码提示 |
| `bff/app.py` | 删除 `/ws` echo 端点（不再为废弃端点做安全加固） |

### WP1-T6：Session 撤销/失效/Valkey 安全

**问题**：v2 只定义了基本 Session 存储，未覆盖撤销、并发失效、滑动过期等安全场景。

| 文件 | 改动 |
|------|------|
| `bff/app.py` | **滑动过期**：每次请求 `last_access = now()`，若 `now() - last_access > idle_timeout` → 失效 |
| `bff/app.py` | **绝对过期**：`created_at + max_lifetime` 不可超过，即使滑动也未过期 |
| `bff/app.py` | **并发失效**：Logout 时除删除当前 Session 外，递增 `principal.security_version`（WP0-T8）使该 Principal 所有 Session 的 Token 失效 |
| `bff/app.py` | **Token Revoke → Session 失效**：Server 返回 401（security_version 不匹配）→ BFF 删除 Session → 返回 401 |
| `bff/app.py` | **Valkey 连接安全**：TLS（生产）、连接池、`requirepass` |
| `bff/app.py` | **Session 数据最小化**：Session 只存 `{sid, token, principal_id, tenant_id, csrf_token, security_version, jti, timestamps}`，不存敏感用户信息 |

**Session 生命周期状态机**：
```
ACTIVE → IDLE_TIMEOUT（Valkey TTL 过期，自然消失）
ACTIVE → EXPLICIT_LOGOUT（删除 Valkey key + security_version++）
ACTIVE → TOKEN_REVOKED（security_version 不匹配 → BFF 删除 Session）
ACTIVE → ABSOLUTE_EXPIRY（max_lifetime 到期 → 删除）
```

---

## 四、WP2：Tenant 最小运营闭环

### WP2-T1：Tenant API v2

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../api/tenants.py` | 新建：`POST /api/v1/tenants`、`GET /api/v1/tenants`、`GET /api/v1/tenants/{id}`、`PUT /api/v1/tenants/{id}` |
| 同文件 | `POST /{id}/suspend`、`POST /{id}/resume`、`POST /{id}/archive` |
| 同文件 | 所有端点加 `require_action(Action.TENANT_MANAGE)` |
| `LakeMindServer/src/.../app.py` | 注册 `/api/v1/tenants` 路由 |

**创建 Tenant 流程（Saga 编排，详见 WP2-T4）**：
```
POST /tenants {name, admin_principal_id, quotas, allowed_models, config_template}
  → 创建 Operation（PROVISION_TENANT, medium risk）
  → 审批通过 → 执行 Saga（WP2-T4）
  → Saga 成功 → Tenant ACTIVE
  → Saga 失败 → 补偿回滚
  → Audit
```

**生命周期**：`PROVISIONING → ACTIVE → SUSPENDED → ARCHIVED`
- **不实现物理 DELETE**（涉及 Asset/Job/Memory/Secret/Token 级联，需 Blast Radius + 审批 + 异步清理）

### WP2-T2：Tenant 前端

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/Tenants.tsx` | 新建：列表 + 创建向导 + 详情 |
| 创建向导 | Step1 基本信息 → Step2 管理员 → Step3 配额 → Step4 允许模型 → Step5 预览 |
| 详情页 | Overview + Members + Quotas + Entitlements + 最近 Jobs + Audit |
| `frontend/src/router.tsx` | 新增 `/organization/tenants` 路由 |
| `frontend/src/components/AppLayout.tsx` | 菜单新增"组织管理" |

### WP2-T3：BFF 代理

| 文件 | 改动 |
|------|------|
| `bff/app.py` | 新增 `/tenants` GET/POST、`/tenants/{id}` GET/PUT、`/tenants/{id}/suspend|resume|archive` POST |

### WP2-T4：Tenant Provisioning Saga + 幂等 + 补偿

**问题**：v2 的 Tenant 创建流程执行顺序错误（先创建 Tenant 记录再创建依赖资源），且无补偿机制。

**Saga 编排（正确执行顺序）**：

```
Step 1: 校验
  → 校验 name 唯一性
  → 校验 admin_principal_id 存在
  → 校验 quotas 合法
  → 校验 allowed_models 存在

Step 2: 创建 Principal + Membership（WP0-T7）
  → 若 admin_principal_id 已存在 → 创建 principal_tenant_membership
  → 若不存在 → 创建 Principal + Membership
  → 补偿：删除 Membership（和新建的 Principal）

Step 3: 创建 Config Scope（从 template）
  → INSERT config_scopes（tenant_id, template_values）
  → 补偿：DELETE config_scopes WHERE tenant_id

Step 4: 创建 Secret Namespace
  → INSERT secret_namespaces（tenant_id）
  → 补偿：DELETE secret_namespaces WHERE tenant_id

Step 5: 创建 Tenant 记录（最后）
  → INSERT tenants（id, name, status=PROVISIONING, quotas, allowed_models）
  → 补偿：DELETE tenants WHERE id

Step 6: 激活 Tenant
  → UPDATE tenants SET status=ACTIVE
  → 补偿：UPDATE tenants SET status=PROVISIONING_FAILED

Step 7: Audit + 通知
  → INSERT audit_log
  → 通知管理员
```

**幂等性**：
- 每个 Saga 有唯一 `saga_id`（= Operation ID）
- 每步有 `step_index` + `status`（PENDING/EXECUTING/DONE/COMPENSATED/FAILED）
- 重试时跳过已 DONE 的步骤
- Saga 状态持久化到 `tenant_provisioning_sagas` 表

**补偿策略**：
- 补偿按逆序执行（Step 5 → Step 4 → Step 3 → Step 2）
- 补偿幂等（可重试）
- 补偿失败 → Saga 状态 = COMPENSATION_FAILED → 告警 + 人工介入

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../services/tenant_provisioning_saga.py` | 新建：Saga 编排器 + 步骤定义 + 补偿逻辑 |
| `LakeMindServer/src/.../models/tenant_saga.py` | 新建：Saga 状态模型 + 持久化 |
| `LakeMindServer/src/.../services/tenant_service.py` | `create_tenant` 调用 Saga 编排器 |

---

## 五、WP3：模型和配置收敛闭环

### WP3-T1：Model Deployment Desired/Active

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../services/model_management_service.py` | `create_deployment` 状态默认 `DRAFT`，不调 ModelServing |
| 同文件 | 新增 `enable_deployment`：创建 Operation（low risk）→ Outbox 事件 → Reconciler apply |
| 同文件 | 新增 `disable_deployment`：同上 |
| `LakeMindServer/src/.../services/reconciler.py` | 新建：拉取 Desired Revision → 调 ModelServing `/v1/models/register` 或 `/v1/models/{id}` (DELETE) → 上报 Active → 比对 |
| `LakeMindServer/src/.../api/models.py` | `GET /deployments/{id}` 返回 `{desired_state, active_state, test_state, readiness_state, convergence_status}` |

**收敛状态**：
```
CONVERGED: desired == active
CONVERGING: apply 已提交，等待上报
DRIFTED: desired != active 且超过阈值时间
FAILED: apply 返回错误
```

### WP3-T2：Model Route API + UI

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../api/models.py` | `POST /routes` → `create_route`（经 Operation） |
| 同文件 | `DELETE /routes/{route_id}`（经 Operation + 影响检查） |
| 同文件 | `POST /profiles/resolve` 返回 `{primary, fallbacks, resolve_trace}` |
| `bff/app.py` | 新增 Route 代理路由 |
| `frontend/src/pages/ModelServing.tsx` | Profiles Tab 内嵌 Route Builder |

**Route Builder 校验**：
- 主路由唯一性（一个 Profile 一个非 fallback 主路由）
- Deployment 必须 `ACTIVE` + `healthy`
- Profile 与 Model Type 兼容
- Embedding Space 维度兼容
- 删除 Route 前显示影响（哪些 Job/Skill 使用该 Profile）
- Resolve Preview（输入 Profile 名 → 显示解析结果）

### WP3-T3：Config 编辑闭环

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/Configuration.tsx` | 重写：按 Scope 分组 → 显示 effective_value + source + revision |
| 同文件 | 编辑按钮 → Schema 驱动表单（类型/范围/枚举校验）→ `PUT /configuration/{scope}` 创建 DRAFT revision |
| 同文件 | Revision 列表 → Diff 视图（old vs new）→ 激活按钮 → `POST /revisions/{id}/activate`（经 Operation） |
| 同文件 | 回滚按钮 → 明确 Rollback Operation + 审计原因 |
| `bff/app.py` | 新增 Config 代理路由 |

**Revision 不可变原则**（详见 WP3-T5）：
- Revision 创建后内容不可修改（append-only）
- 只能创建新 Revision 替代旧 Revision
- 激活操作只改变 `active_revision_id` 指针，不修改 Revision 内容

### WP3-T4：Model Test/Readiness/Active 三维度状态拆分

**问题**：v2 只有 Desired/Active 二维度，无法区分"模型文件可用"、"部署就绪"、"运行时实际状态"。

**三维度定义**：

| 维度 | 含义 | 上报方 | 触发时机 |
|------|------|--------|----------|
| **Test** | 模型文件可用性测试（文件存在、可加载、推理可执行） | ModelServing | Deployment 创建/更新时 |
| **Readiness** | 部署就绪检查（资源充足、依赖满足、配置正确） | ModelServing | Enable 操作时 |
| **Active** | 运行时实际状态（正在服务、推理延迟、错误率） | ModelServing | 持续上报（心跳） |

**状态组合**：

```
Test:       UNKNOWN → TESTING → PASSED / FAILED
Readiness:  UNKNOWN → CHECKING → READY / NOT_READY
Active:     UNKNOWN → STARTING → SERVING / DEGRADED / STOPPED

Deployment 综合状态推导：
  Test=FAILED → Deployment=FAILED（不进入 Readiness）
  Test=PASSED + Readiness=NOT_READY → Deployment=ENABLING
  Test=PASSED + Readiness=READY + Active=STARTING → Deployment=ENABLING
  Test=PASSED + Readiness=READY + Active=SERVING → Deployment=ACTIVE
  Test=PASSED + Readiness=READY + Active=DEGRADED → Deployment=DRIFTED
  Test=PASSED + Readiness=READY + Active=STOPPED → Deployment=DRIFTED
```

**API**：
```
GET /deployments/{id}/health
→ {
    test: {status, checked_at, error},
    readiness: {status, checked_at, error},
    active: {status, reported_at, metrics: {latency_p99, error_rate, qps}},
    composite: {state, convergence_status}
  }
```

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../services/model_management_service.py` | 三维度状态存储 + 综合推导 |
| `LakeMindServer/src/.../api/models.py` | `GET /deployments/{id}/health` 端点 |
| `LakeMindModelServing/src/.../api/health.py` | Test/Readiness/Active 上报端点 |
| `LakeMindModelServing/src/.../services/model_health.py` | 新建：三维度检查逻辑 |
| `frontend/src/pages/ModelServing.tsx` | Deployment 详情显示三维度状态卡片 |

### WP3-T5：Config Rollout + 不可变 Revision + 并发控制

**问题**：v2 将 Rollout 混在 Config 编辑闭环中，未定义不可变性约束和并发控制。

**Revision 不可变**：
- `config_revisions` 表内容字段写入后不可 UPDATE（数据库触发器或应用层守卫）
- 只能 INSERT 新 Revision
- `active_revision_id` 是指针，激活操作只更新指针

**Rollout 状态机**（独立于 Revision 状态）：
```
Rollout:
  INITIATED → VALIDATING → APPLYING → ROLLED_OUT
                              ↓
                        ROLLED_BACK

  INITIATED → CANCELLED（仅在 VALIDATING 阶段可取消）
```

**并发控制（乐观锁）**：
```
config_scopes 表增加列：
  active_revision_id UUID
  rollout_version BIGINT NOT NULL DEFAULT 0  -- 乐观锁

激活流程：
  POST /revisions/{id}/activate
    → 读取 scope.rollout_version = V
    → CAS: UPDATE config_scopes SET active_revision_id={id}, rollout_version=V+1
           WHERE scope_id={scope_id} AND rollout_version=V
    → affected_rows == 0 → 409 Conflict（另一 Rollout 已进行）
    → affected_rows == 1 → Rollout INITIATED → Reconciler 推送 → ROLLED_OUT
```

**回滚**：
- 回滚 = 激活旧 Revision（创建新 Rollout，目标 = 旧 Revision ID）
- 回滚也是 Rollout，经 Operation（medium risk，需审批）
- 回滚后 `active_revision_id` 指向旧 Revision

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../services/configuration_service.py` | 不可变守卫 + 乐观锁 + Rollout 状态机 |
| `LakeMindServer/src/.../api/configuration.py` | `POST /revisions/{id}/activate` 加并发控制 + 409 |
| `LakeMindServer/src/.../models/config_revision.py` | Rollout 模型 + 不可变校验 |
| `LakeMindServer/migrations/` | `config_scopes` 加 `rollout_version` 列 |

---

## 六、WP4：Job 和 Asset 运营闭环

### WP4-T1：Job 详情（8 Tab）

| Tab | 数据源 | 后端改动 |
|-----|--------|----------|
| Summary | `GET /jobs/{id}` | 已有 |
| Timeline | `GET /jobs/{id}/timeline` | **新增**：从 audit_log + job_attempts + job_events 构造时间线（详见 WP4-T4） |
| Attempts | `GET /jobs/{id}/attempts` | 已有 |
| Inputs & Parameters | `GET /jobs/{id}/result` 中的 inputs | 已有 |
| Model & Secret Bindings | `GET /jobs/{id}` 中的 model_profile, resolved_deployment, secret_refs | **增强**：Job 记录中补充绑定信息 |
| Logs | `GET /jobs/{id}/logs` | **新增**：RUNNING → Ray 实时日志；FINISHED → S3 归档日志（详见 WP4-T3）；LOST → 显示丢失原因 |
| Artifacts | `GET /jobs/{id}/result` 中的 artifacts | 已有 |
| Audit | `GET /audit?resource_id={id}` | 已有 |

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../api/jobs_v2.py` | 新增 `GET /{id}/logs`、`GET /{id}/timeline` |
| `LakeMindServer/src/.../services/job_service.py` | 新增 `get_logs`（优先归档，fallback 实时）、`get_timeline` |
| `bff/app.py` | 新增代理路由 |
| `frontend/src/pages/Jobs.tsx` | 新增详情 Drawer：8 Tab 布局 |

**Logs 安全**：
- Secret 脱敏（正则替换 API key、token 等）
- 分页/流式读取（不在浏览器一次加载全部）
- 限制最大返回大小
- 支持下载

### WP4-T2：Asset 详情

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../api/assets.py` | `get_bindings`、`get_lineage` 加安全上下文（WP1-T3 已覆盖） |
| `bff/app.py` | 确认代理路由已有 |
| `frontend/src/pages/Assets.tsx` | 新增详情 Drawer |

**Asset 详情内容**：
- Header: name, type, version, status, tenant, owner, health
- Overview: description, source, created_at, updated_at
- Bindings: binding_type, provider, required, status, checksum, version, last_sync, last_error
- Lineage: DAG 可视化（upstream + downstream）
- Quality: 完整性, 可检索性, 可执行性, drift（详见 WP4-T5）
- Events & Audit: 统一时间线
- Actions: Reindex, Repair（经 Operation）

### WP4-T3：Job 日志归档 + Retention

**问题**：v2 只提到"FINISHED → S3 归档日志"但未定义归档机制和保留策略。

**归档流程**：
```
Job FINISHED/FAILED
  → JobService 触发日志归档
  → 从 Ray worker 收集日志（stdout/stderr）
  → Secret 脱敏
  → 写入 S3: s3://lakemind-job-logs/{tenant_id}/{job_id}/{attempt_id}.log.gz
  → 更新 job_runs.log_uri
  → 删除 Ray worker 本地日志
```

**Retention 策略**：
- S3 Lifecycle 规则：`lakemind-job-logs/` 前缀
  - 30 天 → transition to S3 IA
  - 90 天 → expire + delete
- 可按 Tenant 配置不同 Retention（Config Scope `job.log_retention_days`）
- 归档前检查 `job.log_uri` 是否已存在（幂等）

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../services/job_log_service.py` | 新建：归档 + 脱敏 + S3 写入 |
| `LakeMindServer/src/.../services/job_service.py` | Job 完成时触发归档 |
| `docker-compose.yml` 或 SeaweedFS 配置 | S3 Lifecycle 规则 |

### WP4-T4：Job Event/Timeline 完整性

**问题**：v2 的 Timeline 只从 audit_log + job_attempts 构造，缺少结构化事件溯源。

**job_events 表（新建）**：
```
job_events
  id UUID PK
  job_id UUID FK → jobs
  attempt_id UUID FK → job_runs
  event_type VARCHAR(64)  -- CREATED/QUEUED/STARTED/MODEL_RESOLVED/SECRET_LOADED/RUNNING/HEARTBEAT/COMPLETED/FAILED/CANCELLED/TIMED_OUT
  event_seq BIGINT  -- 单调递增（因果排序）
  occurred_at TIMESTAMP
  payload JSONB
  correlation_id UUID
  cause_event_id UUID  -- 可选：因果链前驱事件
```

**事件发布点**：
- JobService 的每个状态变更发布对应事件
- Ray worker 心跳发布 HEARTBEAT 事件
- Model 解析发布 MODEL_RESOLVED 事件（含 resolved_deployment_id）
- Secret 加载发布 SECRET_LOADED 事件

**Timeline 构造**：
```
GET /jobs/{id}/timeline
  → 合并 job_events + audit_log + job_attempts
  → 按 occurred_at 排序
  → 按 event_seq 因果排序（同时间戳时）
  → 返回统一时间线（含事件类型 + 来源 + payload）
```

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../models/job_event.py` | 新建：job_events 模型 |
| `LakeMindServer/src/.../services/job_event_service.py` | 新建：事件发布 + Timeline 构造 |
| `LakeMindServer/src/.../services/job_service.py` | 各状态变更点发布事件 |
| `LakeMindServer/migrations/` | 新建 job_events 表 |

### WP4-T5：Asset Health/Quality 后端 API

**问题**：v2 的 Asset 详情提到 Quality 四维度但未定义后端 API。

**四维度评分**：

| 维度 | 含义 | 检测方式 |
|------|------|----------|
| **完整性** | 资产文件存在、元数据完整、无缺失字段 | 检查 S3 对象存在 + PG 元数据非空 + 必填字段校验 |
| **可检索性** | 向量索引存在、可查询、结果非空 | 检查 LanceDB 表存在 + sample query 返回结果 |
| **可执行性** | Skill 可解析、依赖满足、dry-run 通过 | 检查 Skill YAML 解析 + 依赖检查 + dry-run |
| **Drift** | 内容与上次索引一致、checksum 匹配 | 对比当前 checksum vs 已记录 checksum |

**API**：
```
GET /assets/{id}/health
→ {
    overall: "healthy" | "degraded" | "unhealthy",
    dimensions: {
      completeness: {score: 0-1, status, details},
      retrievability: {score: 0-1, status, details},
      executability: {score: 0-1, status, details},
      drift: {score: 0-1, status, details, last_checked, drift_details}
    },
    last_checked_at,
    recommendations: ["reindex", "repair", "update_metadata"]
  }
```

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../services/asset_health_service.py` | 新建：四维度检测逻辑 |
| `LakeMindServer/src/.../api/assets.py` | `GET /assets/{id}/health` 端点 |
| `bff/app.py` | 代理路由 |
| `frontend/src/pages/Assets.tsx` | 详情 Drawer 中 Health Tab 调用 |

---

## 七、WP5：Operation、Audit 和 Steward

### WP5-T1：Operation 状态机增强

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../services/operation_service.py` | 新增 `REJECTED` 状态 |
| 同文件 | 状态机：`APPROVAL_REQUIRED → REJECTED`；`PENDING/APPROVAL_REQUIRED → CANCELLED` |
| 同文件 | `reject(op_id, principal_id, reason)` |
| 同文件 | `cancel` 加状态机守卫 + reason |
| 同文件 | 审批人与发起人隔离校验 |
| `LakeMindServer/src/.../api/operations.py` | 新增 `POST /{id}/reject`；所有端点加安全上下文 |
| `bff/app.py` | 新增 reject 代理 |
| `frontend/src/pages/Operations.tsx` | 详情 Drawer（请求原因 + 影响分析 + 执行步骤 + 日志） |

**前端按钮状态机（v3 修正 #6）**：

| Operation 状态 | 可用按钮 |
|----------------|----------|
| PENDING | Cancel + 详情 |
| APPROVAL_REQUIRED | Approve + Reject + Cancel + 详情 |
| EXECUTING | 禁用所有操作按钮 + 详情 |
| COMPLETED | 详情 |
| FAILED | Retry + 详情 |
| REJECTED | 详情 |
| CANCELLED | 详情 |

### WP5-T2：Audit Correlation

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../api/audit.py` | 新增 query 参数：`action`, `result`, `request_id`, `correlation_id`, `operation_id`, `job_id` |
| `LakeMindServer/src/.../api/audit.py` | 导出端点同步增加过滤参数 |
| `frontend/src/pages/Audit.tsx` | 新增过滤栏：event_type + action + result + 日期范围 + correlation_id 搜索 |
| 同文件 | 表格分页 + 排序 + 导出 |

### WP5-T3：Steward 前端接入

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/Steward.tsx` | 重写：移除 WebSocket，改用 REST |
| 同文件 | 三区域：巡检摘要（findings 列表 + severity Tag）+ 对话窗（POST /steward/chat）+ 建议动作 |
| `bff/app.py` | 新增 `GET /steward/inspection`、`POST /steward/chat`、`POST /steward/suggest` 代理到 Steward:3002 |

### WP5-T4：Steward 真实巡检

| 文件 | 改动 |
|------|------|
| `steward/steward_service.py` | `_check_outbox_backlog` → 调用 `GET /api/v1/operations?status=APPROVAL_REQUIRED&stale=true`（或 ReconciliationService API） |
| 同文件 | `_check_binding_drift` → 调用 ReconciliationService `GET /api/v1/assets?drifted=true`（对比 Desired vs Physical） |
| 同文件 | `_check_config_drift` → 调用 `GET /api/v1/configuration/drifts`（对比 Desired Revision vs Instance Active Revision） |

**禁止**：Steward 直连 PostgreSQL

**巡检 Finding 结构**：
```json
{
  "category": "outbox_backlog",
  "severity": "warning",
  "title": "3 个 Outbox 事件积压超过 1 小时",
  "evidence": [{"event_id": "...", "age_minutes": 75, "retry_count": 3}],
  "affected_objects": [{"type": "tenant", "id": "retail"}],
  "suggested_action": "run_reconciler",
  "confidence": "high"
}
```

### WP5-T5：Steward Finding 持久化/去重/状态机

**问题**：v2 的 Finding 是临时生成的，不持久化，无法追踪处理状态。

**steward_findings 表（新建）**：
```
steward_findings
  id UUID PK
  category VARCHAR(64)
  severity VARCHAR(32)  -- info / warning / critical
  title TEXT
  evidence JSONB
  affected_objects JSONB
  suggested_action VARCHAR(128)
  confidence VARCHAR(32)
  
  fingerprint VARCHAR(64)  -- 去重键（hash of category + affected_objects + title）
  
  status VARCHAR(32)  -- OPEN / ACKNOWLEDGED / RESOLVED / SUPPRESSED
  acknowledged_by UUID FK → principals
  acknowledged_at TIMESTAMP
  resolved_at TIMESTAMP
  resolution_note TEXT
  
  first_seen_at TIMESTAMP
  last_seen_at TIMESTAMP
  occurrence_count INT  -- 同一 fingerprint 重复出现次数
  
  created_at TIMESTAMP
  updated_at TIMESTAMP
```

**去重逻辑**：
- 每次巡检生成 Finding → 计算 `fingerprint = hash(category + affected_objects + title)`
- 查询 `steward_findings WHERE fingerprint = X AND status = 'OPEN'`
- 已存在 → `occurrence_count++`, `last_seen_at = now()`
- 不存在 → INSERT 新 Finding

**状态机**：
```
OPEN → ACKNOWLEDGED（人工确认，记录 acknowledged_by）
ACKNOWLEDGED → RESOLVED（问题已修复或已处理）
OPEN → RESOLVED（自动检测到问题消失）
OPEN/ACKNOWLEDGED → SUPPRESSED（人工抑制，不再告警）
SUPPRESSED → OPEN（取消抑制）
```

| 文件 | 改动 |
|------|------|
| `LakeMindServer/src/.../models/steward_finding.py` | 新建：Finding 模型 |
| `LakeMindServer/src/.../services/steward_finding_service.py` | 新建：去重 + 状态机 + 持久化 |
| `LakeMindServer/src/.../api/steward.py` | `GET /findings`, `POST /findings/{id}/acknowledge`, `POST /findings/{id}/resolve`, `POST /findings/{id}/suppress` |
| `steward/steward_service.py` | 巡检结果通过 API 写入 steward_findings |
| `LakeMindServer/migrations/` | 新建 steward_findings 表 |

### WP5-T6：Request/Correlation ID 全链路传播

**问题**：v2 未定义请求追踪 ID 的生成和传播机制。

**传播链**：
```
前端 → BFF → Server → MCP / ModelServing / Steward
  每跳携带 X-Request-Id + X-Correlation-Id
```

**生成规则**：
- `X-Request-Id`：每个入站请求唯一（BFF 生成或前端生成）
- `X-Correlation-Id`：同一用户操作的所有请求共享（登录时生成，存入 Session）
- Server 收到后写入 `audit_log.request_id` + `audit_log.correlation_id`
- Server 发出子请求（调 MCP/ModelServing）时传播两个 header
- Steward 巡检的 Finding 携带 `correlation_id` 关联到触发巡检的请求

| 文件 | 改动 |
|------|------|
| `bff/app.py` | 生成/传播 X-Request-Id + X-Correlation-Id |
| `LakeMindServer/src/.../middleware/request_id.py` | 新建：提取/生成 request_id + correlation_id，注入 context |
| `LakeMindServer/src/.../api/audit.py` | audit_log 写入 request_id + correlation_id |
| `frontend/src/api/client.ts` | axios 拦截器生成 X-Request-Id |

---

## 八、WP6：测试、迁移和硬化

### WP6-T1：自动化测试

| 测试类型 | 覆盖范围 |
|----------|----------|
| 跨租户矩阵 | 两个租户 session 调所有资源 API，验证互不可见 |
| CSRF 负向 | 无 token / 错误 token / 跨域 Origin → 403 |
| Session 撤销 | Logout → 旧 session 失效；Token revoke → session 失效 |
| Tenant 隔离 | Platform admin 跨租户 → 正常；普通用户 → 403 |
| Model 收敛 | 创建 Deployment → Enable → ModelServing 注册 → Active；模拟失败 → FAILED/DRIFTED |
| Config Rollback | 激活 → 生效 → 回滚 → 恢复 → 审计有记录 |
| Operation 并发 | 同一 Operation 并发 Approve + Reject → 幂等 |
| Steward 故障注入 | 插入积压/漂移 → Steward 发现 → 建议 → Operation |
| Audit Correlation | 从 Job → Operation → Audit → Config Revision 可追踪 |

### WP6-T2：数据迁移验证

| 迁移项 | 验证 |
|--------|------|
| Operation REJECTED 状态 | 新增 enum 值，旧数据不受影响 |
| Deployment 新状态 | 现有 `enabled` → `ACTIVE`，`disabled` → `DISABLED` |
| Session | 旧内存 session 自然失效，用户重新登录 |
| BFF Token 模式 | 旧 BFF_TOKEN 不再被用户请求接受 |
| principal_tenant_memberships | 从 user_tenant 迁移后 membership 正确 |
| security_version | 所有 principal 初始为 0，Token 正常通过 |
| steward_findings | 新建空表，巡检后正确写入 |
| job_events | 新建空表，新 Job 正确发布事件 |
| rollout_version | config_scopes 初始为 0，首次激活正常 |

### WP6-T3：回滚验证

- 代码回滚后数据库迁移是否兼容（新 enum 值不影响旧代码）
- 新前后端不混用（BFF 版本检查）

### WP6-T4：前端 E2E + 浏览器安全测试

**问题**：v2 只有后端自动化测试，缺少前端 E2E 和浏览器安全测试。

**E2E 测试（Playwright）**：

| 场景 | 步骤 | 期望 |
|------|------|------|
| 登录流程 | 输入凭据 → 提交 → 跳转 Dashboard | Cookie 设置 + CSRF token 获取 |
| 跨租户隔离 | Tenant A 登录 → 访问 Tenant B 资产 URL | 403 或空结果 |
| CSRF 刷新恢复 | 登录 → 刷新页面 → POST 请求 | 不 403（csrf 从 /auth/csrf 恢复） |
| Tenant 创建向导 | 5 步填写 → 提交 → 审批 → 执行 | Tenant ACTIVE |
| Config 编辑 → 激活 → 回滚 | 编辑 → 激活 → 验证生效 → 回滚 → 验证恢复 | 审计有记录 |
| Operation 审批 | APPROVAL_REQUIRED → Approve → 执行 → COMPLETED | 状态正确流转 |
| Steward 巡检 | 触发巡检 → 查看 Findings → Acknowledge | Finding 状态更新 |
| Model 三维度状态 | 创建 Deployment → Enable → 查看健康 | 三维度状态卡片正确显示 |

**浏览器安全测试（OWASP ZAP 基线扫描）**：
- 对 BFF 基地址执行主动扫描
- 检查：CSRF、XSS、Open Redirect、Clickjacking、Security Headers
- 生成 HTML 报告，纳入验收证据

| 文件 | 改动 |
|------|------|
| `control/frontend/e2e/` | 新建：Playwright 测试目录 |
| `control/frontend/e2e/*.spec.ts` | E2E 测试用例 |
| `control/frontend/playwright.config.ts` | Playwright 配置 |
| `scripts/security/zap-baseline.sh` | OWASP ZAP 基线扫描脚本 |

### WP6-T5：API 契约与前后端 Schema 自动比对

**问题**：v2 冻结了 API 契约但没有自动化比对机制，前后端 Schema 可能漂移。

**比对流程**：
```
1. Server 启动时导出 OpenAPI spec → docs/api-spec/v0.2.1/control-center-phase0.yaml
2. CI 中：
   a. 从 Server /openapi.json 拉取实际 spec
   b. 与冻结 spec 比对（oasdiff）
   c. 有 breaking change → fail
   d. 有 additive change → warn
3. 前端：
   a. 从 OpenAPI spec 生成 TS 类型（openapi-typescript）
   b. 与前端实际使用的 API client 类型比对
   c. 不匹配 → fail
```

**工具链**：
- `oasdiff`：OpenAPI spec breaking change 检测
- `openapi-typescript`：从 spec 生成 TS 类型
- `tsdiff`：TS 类型比对

| 文件 | 改动 |
|------|------|
| `scripts/verify/api-contract-check.sh` | 新建：spec 比对脚本 |
| `control/frontend/src/api/generated/` | 从 OpenAPI 生成的 TS 类型 |
| `.github/workflows/` 或 CI 配置 | 加入 API 契约检查步骤 |

### WP6-T6：验收证据包 + 发布门禁报告

**问题**：v2 有门禁清单但无自动化证据收集，验收依赖人工确认。

**证据包结构**：
```
reports/acceptance/v0.2.1-{build_id}/
  ├── manifest.json           # 证据包清单（build_id, git_sha, timestamp, environment）
  ├── test-results/
  │   ├── unit-tests.xml      # 单元测试结果（JUnit XML）
  │   ├── integration-tests.xml
  │   ├── e2e-tests.xml
  │   └── security-scan.html  # OWASP ZAP 报告
  ├── api-contract/
  │   ├── frozen-spec.yaml    # 冻结的 API spec
  │   ├── actual-spec.yaml    # 实际导出的 spec
  │   └── diff-report.html    # 差异报告
  ├── migrations/
  │   ├── applied.log         # 已执行的迁移
  │   └── rollback-test.log   # 回滚测试结果
  ├── gate-report/
  │   ├── G0-security.md      # 安全门禁检查结果
  │   ├── G1-management.md    # 管理闭环门禁
  │   ├── G2-runtime.md       # 运行闭环门禁
  │   ├── G3-steward.md       # Steward 门禁
  │   └── G4-release.md       # 发布门禁
  └── sign-off.md             # 人工签字确认
```

**自动化收集**：
- CI pipeline 在测试阶段结束后自动收集所有证据
- 门禁报告自动生成（每个门禁项 → pass/fail + 证据链接）
- 任何 fail → 阻止发布

| 文件 | 改动 |
|------|------|
| `scripts/verify/collect-evidence.py` | 新建：证据收集脚本 |
| `scripts/verify/gate-check.py` | 新建：门禁自动化检查 |
| `reports/acceptance/` | 证据包输出目录 |

---

## 九、依赖关系与执行顺序

```
WP0（契约冻结，T1–T8）
  ↓
WP1（安全基础，T1–T6）
  ├─ T1 Session→Valkey
  ├─ T2 BFF 委托身份
  ├─ T3 Server Tenant 隔离
  ├─ T4 CSRF（含刷新恢复）
  ├─ T5 密码提示 + 删 WS
  └─ T6 Session 撤销/失效安全
  ↓
WP2（Tenant，T1–T4）── 依赖 WP1-T3, WP0-T7
WP3（模型+配置，T1–T5）── 依赖 WP1
WP4（Job+Asset，T1–T5）── 依赖 WP1-T3
WP5（Operation+Audit+Steward，T1–T6）── 依赖 WP1, WP3
  ↓
WP6（测试+迁移+硬化，T1–T6）── 依赖 WP1~WP5
```

**执行批次**：

| 批次 | 工作包 | 说明 |
|------|--------|------|
| Batch 1 | WP0 | 契约冻结（T1–T8），不编码 |
| Batch 2 | WP1 | 安全基础（T1–T6） |
| Batch 3 | WP2 + WP3 + WP4 | 并行，互不依赖 |
| Batch 4 | WP5 | 依赖 WP3（Reconciler）+ WP4（job_events） |
| Batch 5 | WP6 | 全量测试 + 验收 + 证据包 |

---

## 十、工作量估算（v3 修订）

| WP | 任务 | 建议人日 |
|----|------|----------|
| WP0 | T1–T6（v2 已有） | 3–5 |
| WP0 | T7 Membership 模型 | 1–2 |
| WP0 | T8 Security Version | 1–2 |
| WP1 | T1–T5（v2 已有） | 8–12 |
| WP1 | T6 Session 安全增强 | 2–3 |
| WP2 | T1–T3（v2 已有） | 5–7 |
| WP2 | T4 Provisioning Saga | 3–4 |
| WP3 | T1–T3（v2 已有） | 6–9 |
| WP3 | T4 三维度状态 | 2–3 |
| WP3 | T5 Config Rollout 并发控制 | 2–3 |
| WP4 | T1–T2（v2 已有） | 6–9 |
| WP4 | T3 日志归档 + Retention | 2–3 |
| WP4 | T4 Event/Timeline 完整性 | 2–3 |
| WP4 | T5 Asset Health API | 2–3 |
| WP5 | T1–T4（v2 已有） | 4–6 |
| WP5 | T5 Finding 持久化/状态机 | 2–3 |
| WP5 | T6 Request/Correlation ID | 1–2 |
| WP6 | T1–T3（v2 已有） | 8–12 |
| WP6 | T4 前端 E2E + 安全测试 | 3–4 |
| WP6 | T5 API 契约 Schema 比对 | 1–2 |
| WP6 | T6 验收证据包 | 2–3 |
| 文档/部署/验收修复 | — | 3–5 |
| **合计** | | **66–92 人日** |

3 名开发人员 → 约 4–5 周开发 + 1 周集成测试。

---

## 十一、门禁

### G0：安全门禁

- [ ] 用户请求不使用 BFF Token fallback
- [ ] Tenant 只从 Server SecurityContext 解析
- [ ] 所有资源 API 通过跨租户测试矩阵
- [ ] Session 可撤销，Valkey TTL 生效
- [ ] CSRF + Origin 校验覆盖所有 unsafe methods
- [ ] CSRF 刷新后可恢复（不 403）
- [ ] 无匿名 WebSocket（echo 已删除）
- [ ] Cookie: HttpOnly + Secure + SameSite
- [ ] Token 权限变更即时生效（security_version 校验）
- [ ] Membership Revoke → Token 立即失效

### G1：管理闭环门禁

- [ ] Tenant 可创建（含配额/模型权限/Config Scope）、暂停、归档
- [ ] Tenant Provisioning Saga 可补偿、幂等
- [ ] Config 可 Draft → Validate → Activate → Rollback
- [ ] Config Revision 不可变，Rollout 有并发控制
- [ ] Operation 支持 Approve + Reject + Cancel + 详情
- [ ] Operation 前端按钮状态机正确
- [ ] Audit 支持 Correlation 追踪
- [ ] 所有管理写操作经 Operation 或 Audit

### G2：运行闭环门禁

- [ ] Deployment: DRAFT → ENABLING → ACTIVE，失败 → FAILED/DRIFTED
- [ ] Model 三维度状态（Test/Readiness/Active）正确上报和推导
- [ ] ModelServing 注册失败 → Deployment 显示 DRIFTED
- [ ] Route 可创建/删除/Resolve，校验兼容性
- [ ] Job 详情可解释失败（8 Tab 完整）
- [ ] Job 日志归档到 S3，Retention 生效
- [ ] Job Event/Timeline 完整（事件溯源 + 因果排序）
- [ ] Asset 详情可查看 Binding + Lineage + 执行 Repair
- [ ] Asset Health 四维度评分正确

### G3：Steward 门禁

- [ ] Outbox/Binding/Config Drift 语义正确（故障注入验证）
- [ ] Steward 不直连数据库
- [ ] 高风险动作不能绕过 Operation
- [ ] Finding 附证据 + 影响对象 + 建议动作
- [ ] Finding 持久化、去重、状态机（OPEN → ACKNOWLEDGED → RESOLVED）
- [ ] Request/Correlation ID 全链路传播

### G4：发布门禁

- [ ] 自动化测试全通过
- [ ] 前端 E2E 全通过
- [ ] OWASP ZAP 基线扫描无 P0/P1
- [ ] 数据迁移通过
- [ ] 回滚通过
- [ ] API 契约 Schema 比对无 breaking change
- [ ] 验收证据包完整生成
- [ ] 无 P0/P1
- [ ] Control Center 与 Server 版本一致
- [ ] API 契约文档完成

---

## 十二、不包含的范围（Phase 1+）

Phase 0 不包含，需在 Phase 1+ 实施：

- 新信息架构（一级导航重组）
- Mission Control 首页重做
- 全局搜索 + Command Palette
- 实时事件流（SSE/WebSocket 推送）
- Alert / Incident / Runbook
- Resource / Capacity / Budget
- Control Graph / Blast Radius
- Steward LLM 驱动对话
- OIDC / SSO 集成
- Embedding Space 管理 UI
- Model Test Console
- Saved Views / User Preferences
- 暗色模式 / i18n

---

## 十三、Phase 1–3 总体路线（概要）

### Phase 1：Control Center 1.0（统一控制中心）

- 新信息架构落地（8 个一级导航）
- Mission Control 首页
- 全局搜索 + Command Palette
- 实时事件流
- Alert / Incident / Runbook
- Resource / Capacity
- Saved Views
- Steward Context Panel（对象页内嵌助手）

### Phase 2：智能治理

- LakeMind Control Graph
- Blast Radius 影响分析
- Steward 证据化 RCA
- Auto-Governance 策略
- Predictive Capacity
- Cost Attribution
- Policy Simulation
- Automated Postmortem

### Phase 3：多节点适配（v0.3）

- Node / Cluster 管理
- 多 Ray Cluster
- 多 ModelServing Replica
- HA Control Plane
- 分布式 Config Rollout
- Failover / Node Drain

---

## 十四、验收场景（故障注入）

| 场景 | 操作 | 期望 |
|------|------|------|
| 跨租户隔离 | Tenant A session 调 `/assets` | 只返回 Tenant A 资产 |
| Token 过期 | 等待 token 过期 → 调 API | 401 → 跳转 Login（不 fallback） |
| Session 撤销 | Logout → 用旧 cookie 调 API | 401 |
| 权限即时生效 | Revoke membership → 用旧 token 调 API | 401（security_version 不匹配） |
| CSRF | 无 token POST | 403 |
| CSRF 刷新恢复 | 登录 → 刷新页面 → POST | 不 403（csrf 从 /auth/csrf 恢复） |
| Model 收敛 | 创建 Deployment → Enable | DRAFT → ENABLING → ACTIVE |
| Model 三维度 | ModelServing 关闭 → Enable | Test=PASSED, Readiness=NOT_READY → Deployment=ENABLING |
| Model 失败 | ModelServing 关闭 → Enable | ENABLING → FAILED → DRIFTED |
| Config 回滚 | 激活 revision 18 → 回滚到 17 | 值恢复 → 审计有记录 |
| Config 并发 | 同时激活两个 revision | 一个成功，一个 409 Conflict |
| Tenant Saga | 创建 Tenant → 模拟 Step 3 失败 | 补偿回滚 Step 2 → 无残留 |
| Operation Reject | Approve + Reject 并发 | 幂等，一个成功一个 409 |
| Operation 按钮 | EXECUTING 状态的 Operation | 所有操作按钮禁用 |
| Steward Outbox | 插入积压事件 | Steward 发现 → Finding → 建议 run_reconciler |
| Steward Binding Drift | 删除物理 binding | Steward 发现 → Finding → 建议 repair |
| Steward Config Drift | 实例保持旧 revision | Steward 发现 → Finding → 建议 reload |
| Steward Finding 去重 | 同一问题巡检两次 | occurrence_count=2，不重复创建 |
| Steward Finding 状态 | Acknowledge → 问题修复 | OPEN → ACKNOWLEDGED → RESOLVED |
| Job 日志归档 | Job FINISHED → 查 logs | 返回 S3 归档日志 |
| Job Event Timeline | Job 经历多个状态 → 查 timeline | 事件按因果排序完整显示 |
| Asset Health | 资产文件缺失 → 查 health | completeness.score < 1, status=unhealthy |
| Audit Correlation | 从 Job → Audit | 可追踪到 Operation + Config Revision |
| Request ID 传播 | 前端请求 → 查 audit | request_id + correlation_id 正确记录 |
| API 契约比对 | 修改 Server API 不更新 spec | CI fail（breaking change detected） |
| 验收证据包 | CI 运行完成 | reports/acceptance/ 目录完整 |
