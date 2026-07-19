# LakeMind v0.2.0 WP2~WP9 详细开发方案

> **文档性质：WP2-WP9 各工作包的详细开发方案，含任务拆解、交付物、执行步骤、日程、门禁**  
> **依据：[设计方案](./LakeMind_v0.2.0_设计方案.md) / [开发方案](./LakeMind_v0.2.0_开发方案.md) / [WP1详细方案](./LakeMind_v0.2.0_WP1详细开发方案.md)**  
> **前置条件：WP1 已完成，M0 门禁通过（13/13 PASS）**  
> **日期：2026-07-13**

---

## 目录

- [WP2：Control Plane 与安全](#wp2)
- [WP3：Asset Runtime](#wp3)
- [WP4：Job Runtime 与 Ray](#wp4)
- [WP5：ModelServing 管理](#wp5)
- [WP6：LakeMind Control Center](#wp6)
- [WP7：Steward 治理](#wp7)
- [WP8：Meeting Agent Golden Path](#wp8)
- [WP9：工程与发布](#wp9)
- [跨 WP 综合管理](#cross-wp)

---

<a id="wp2"></a>
# WP2：Control Plane 与安全

> **阶段：B（第 3-6 周）**  
> **估算：48 SP**  
> **依赖：WP1（M0 通过）**  
> **目标：建立可信身份、授权、配置、Secret、审计和管理操作的基础设施**

---

## WP2.0 概述

### 在全局计划中的位置

```
阶段 A (W1-W2) → M0 PASS
  └── WP1 架构与契约基础 ✅
        │
        ▼
阶段 B (W3-W6) ← 本文档
  └── WP2 Control Plane 与安全
        │
        ▼ 门禁 M1: Control Plane 端到端跑通
        │
阶段 C (W7-W11)
  └── WP3 Asset Runtime
```

### 任务清单

| 子流 | Task ID | 任务 | SP | 依赖 |
|------|---------|------|----|------|
| S1 数据库迁移 | WP2-T01 | 统一迁移机制 | 2 | WP1 |
| | WP2-T02 | Control Plane 核心 schema | 4 | T01 |
| S2 身份与授权 | WP2-T03 | Security Context 实现 | 3 | T02 |
| | WP2-T04 | 统一 Token 体系 | 3 | T03 |
| | WP2-T05 | RBAC + 资源级授权 | 4 | T03 |
| | WP2-T06 | 租户隔离强制 | 3 | T05 |
| | WP2-T07 | Protected Namespace | 2 | T06 |
| S3 配置与实例 | WP2-T08 | Configuration Service | 4 | T02 |
| | WP2-T09 | 配置优先级解析 | 2 | T08 |
| | WP2-T10 | Instance Registry | 2 | T02 |
| | WP2-T11 | 配置生效模式 | 2 | T08 |
| S4 Secret | WP2-T12 | Secret Service | 3 | T02 |
| | WP2-T13 | Secret 最小注入 | 2 | T12 |
| S5 审计与 Operation | WP2-T14 | Audit Service | 3 | T02 |
| | WP2-T15 | Operation Service | 3 | T14 |
| | WP2-T16 | Outbox 基础 | 3 | T02 |
| S6 网络与集成 | WP2-T17 | 网络边界调整 | 2 | T10 |
| | WP2-T18 | REST API 认证中间件 | 2 | T05 |
| | WP2-T19 | 跨租户隔离测试 | 2 | T06 |
| **合计** | | | **48** | |

### 人员配置

| 角色 | 人数 | 职责 |
|------|------|------|
| 后端工程师 A（Control Plane） | 1 | T01-T07（迁移 + 身份 + 授权 + 隔离） |
| 后端工程师 B（Config/Secret） | 1 | T08-T13（配置 + 实例 + Secret） |
| 后端工程师 C（Audit/Op/Net） | 1 | T14-T19（审计 + Operation + Outbox + 网络） |
| 安全顾问 | 0.5 | L3 安全测试评审 + T19 验收 |

### v0.1.0 基线

| 维度 | v0.1.0 现状 | v0.2.0 目标 |
|------|-------------|-------------|
| 认证 | `auth.py` 单一全局 API Key 硬编码比较 | SecurityContext + Token 哈希 + RBAC |
| 租户 | `X-Tenant-Id` Header 自由声明，默认 `"default"` | Server 端 Token 解析强制，不可伪造 |
| 数据库 | 9 张表，单文件 `01-age.sql` 幂等创建 | 12 张 Control Plane 表 + Alembic 迁移 |
| 配置 | `engines.yaml` + `.env` + 代码默认值 | ConfigurationService + Revision + 作用域 |
| Secret | PG 明文存储 `secrets` 表 | PG 加密 + 主密钥外部引用 + secret_ref |
| 审计 | 无 | AuditService + 全覆盖审计点 |
| 网络 | Docker Compose 共享网络，内部端口对外 | 内部端口隔离，Service Identity |

---

## WP2-T01：统一迁移机制

> **SP：2 | 依赖：WP1 | 主笔：工程师 A**

### 目标

引入 Alembic 迁移框架，替代 v0.1.0 的单文件 `01-age.sql` 幂等创建方式，建立版本化 schema 管理。

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `LakeMindServer/alembic.ini` | Alembic 配置 |
| `LakeMindServer/migrations/env.py` | 迁移环境 |
| `LakeMindServer/migrations/script.py.mako` | 迁移模板 |
| `LakeMindServer/migrations/versions/001_initial_schema.py` | v0.1.0 现有 9 表的基线迁移 |
| `LakeMindServer/src/lakemind_server/db.py` | 数据库连接管理 |

### 执行步骤

1. **安装 Alembic**，在 `LakeMindServer/` 下初始化 `alembic init migrations`
2. **配置 `alembic.ini`**：`sqlalchemy.url` 从环境变量读取，`target_metadata` 指向模型
3. **编写基线迁移 `001_initial_schema.py`**：将 v0.1.0 的 `01-age.sql` 中 9 张表转为 Alembic `op.create_table` 调用
4. **编写 `db.py`**：统一 `asyncpg` 连接池管理，替代各插件中散落的 PG 连接创建
5. **验证**：`alembic upgrade head` 在空库上成功；`alembic downgrade base` 清理干净

### 评审标准

- [ ] `alembic upgrade head` 在空库成功
- [ ] `alembic downgrade base` 回滚干净
- [ ] 基线迁移覆盖 v0.1.0 全部 9 张表
- [ ] `db.py` 提供统一连接池

---

## WP2-T02：Control Plane 核心 schema

> **SP：4 | 依赖：T01 | 主笔：工程师 A**

### 目标

创建 v0.2.0 Control Plane 的 12 张核心表。

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `migrations/versions/002_control_plane.py` | 12 张 Control Plane 表迁移 |
| `src/lakemind_server/models/identity.py` | principals, tenants, roles, role_bindings, tokens |
| `src/lakemind_server/models/config.py` | config_revisions, config_values |
| `src/lakemind_server/models/secret.py` | secrets |
| `src/lakemind_server/models/audit.py` | audit_log, operations |
| `src/lakemind_server/models/instance.py` | instance_registry |
| `src/lakemind_server/models/outbox.py` | outbox |

### 数据库表定义

#### `principals`

```sql
CREATE TABLE principals (
    principal_id   TEXT PRIMARY KEY,        -- prn_{ulid}
    principal_type TEXT NOT NULL,           -- user|agent|service_account|steward|system_worker
    name           TEXT NOT NULL,
    tenant_id      TEXT NOT NULL,           -- ten_{ulid}
    status         TEXT NOT NULL DEFAULT 'active',
    metadata       JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `tenants`

```sql
CREATE TABLE tenants (
    tenant_id   TEXT PRIMARY KEY,           -- ten_{ulid}
    name        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'active',
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `roles`

```sql
CREATE TABLE roles (
    role_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,              -- platform_admin|tenant_admin|agent|steward|readonly
    permissions JSONB NOT NULL,             -- ["asset:create","asset:read",...]
    is_builtin  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `role_bindings`

```sql
CREATE TABLE role_bindings (
    binding_id   TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    role_id      TEXT NOT NULL REFERENCES roles(role_id),
    tenant_id    TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(principal_id, role_id, tenant_id)
);
```

#### `tokens`

```sql
CREATE TABLE tokens (
    token_id     TEXT PRIMARY KEY,          -- tok_{ulid}
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    tenant_id    TEXT NOT NULL,
    token_hash   TEXT NOT NULL,             -- SHA-256 哈希
    scopes       JSONB NOT NULL,
    expires_at   TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tokens_hash ON tokens(token_hash) WHERE revoked_at IS NULL;
```

#### `audit_log`

```sql
CREATE TABLE audit_log (
    audit_id     TEXT PRIMARY KEY,          -- aud_{ulid}
    event_type   TEXT NOT NULL,
    principal_id TEXT,
    tenant_id    TEXT,
    resource_id  TEXT,
    action       TEXT NOT NULL,
    result       TEXT NOT NULL,             -- success|denied|error
    details      JSONB DEFAULT '{}',
    request_id   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant_time ON audit_log(tenant_id, created_at DESC);
```

#### `operations`

```sql
CREATE TABLE operations (
    operation_id      TEXT PRIMARY KEY,     -- op_{ulid}
    op_type           TEXT NOT NULL,
    target_resource   TEXT NOT NULL,
    initiator_id      TEXT NOT NULL,
    initiator_channel TEXT NOT NULL,        -- rest|mcp|control_center|steward|system
    reason            TEXT,
    risk_level        TEXT NOT NULL DEFAULT 'LOW',
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approver_id       TEXT,
    status            TEXT NOT NULL DEFAULT 'PENDING',
    result            JSONB,
    failure_reason    TEXT,
    audit_event_ids   JSONB DEFAULT '[]',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `config_revisions`

```sql
CREATE TABLE config_revisions (
    revision_id  TEXT PRIMARY KEY,          -- cfgr_{ulid}
    scope        TEXT NOT NULL,             -- platform|tenant:{id}|agent:{id}|service:{id}
    values       JSONB NOT NULL,
    schema_version TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    reason       TEXT,
    parent_revision_id TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ
);
```

#### `config_values`

```sql
CREATE TABLE config_values (
    id           BIGSERIAL PRIMARY KEY,
    revision_id  TEXT NOT NULL REFERENCES config_revisions(revision_id),
    key          TEXT NOT NULL,
    value        JSONB NOT NULL,
    effective_mode TEXT NOT NULL DEFAULT 'HOT_RELOAD'
);
```

#### `secrets`

```sql
CREATE TABLE secrets (
    secret_id    TEXT PRIMARY KEY,
    scope        TEXT NOT NULL,             -- platform|tenant:{id}|model:{id}
    name         TEXT NOT NULL,
    encrypted_value BYTEA NOT NULL,         -- AES-256-GCM
    version      INTEGER NOT NULL DEFAULT 1,
    created_by   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    rotated_at   TIMESTAMPTZ,
    UNIQUE(scope, name, version)
);
```

#### `instance_registry`

```sql
CREATE TABLE instance_registry (
    instance_id      TEXT PRIMARY KEY,
    service_type     TEXT NOT NULL,
    version          TEXT NOT NULL,
    endpoint         TEXT NOT NULL,
    capabilities     JSONB DEFAULT '[]',
    active_revision_id TEXT,
    last_heartbeat   TIMESTAMPTZ,
    health_status    TEXT NOT NULL DEFAULT 'unknown',
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `outbox`

```sql
CREATE TABLE outbox (
    event_id        TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,
    aggregate_id    TEXT NOT NULL,
    aggregate_type  TEXT NOT NULL,
    payload         JSONB NOT NULL,
    correlation_id  TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 5,
    next_retry_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ
);
CREATE INDEX idx_outbox_pending ON outbox(status, next_retry_at) WHERE status = 'PENDING';
```

### 执行步骤

1. **编写 SQLAlchemy 模型**：为每张表创建 ORM 模型
2. **编写 Alembic 迁移 `002_control_plane.py`**
3. **种子数据**：内置角色（`platform_admin` / `tenant_admin` / `agent` / `steward` / `readonly`）和默认租户
4. **验证**：`alembic upgrade head` 成功；种子数据可查询

### 评审标准

- [ ] 12 张表全部创建成功
- [ ] 内置角色和默认租户种子数据就位
- [ ] 索引覆盖高频查询路径
- [ ] `alembic downgrade` 可回滚

---

## WP2-T03：Security Context 实现

> **SP：3 | 依赖：T02 | 主笔：工程师 A**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/security/context.py` | SecurityContext dataclass |
| `src/lakemind_server/security/middleware.py` | FastAPI 认证中间件 |
| `src/lakemind_server/security/token_parser.py` | Token 解析逻辑 |

### SecurityContext 定义

```python
@dataclass(frozen=True)
class SecurityContext:
    principal_id: str          # prn_{ulid}
    principal_type: str        # user|agent|service_account|steward|system_worker
    tenant_id: str             # ten_{ulid}
    roles: list[str]
    scopes: list[str]
    token_id: str              # tok_{ulid}
    request_id: str
    correlation_id: str | None
```

### 执行步骤

1. **编写 `context.py`**：定义 `SecurityContext` dataclass + `from_token()` 工厂方法
2. **编写 `token_parser.py`**：SHA-256 哈希 → 查 `tokens` 表 → 校验 `revoked_at` + `expires_at` → 关联 `principals` + `role_bindings` + `roles`
3. **编写 `middleware.py`**：FastAPI Dependency，从 `Authorization: Bearer {token}` 提取 → 解析 → 注入 `request.state.security_context`
4. **移除 `auth.py`** 中的 API Key 比较逻辑，保留 Bootstrap Token 兼容
5. **单元测试**：有效 / 过期 / 撤销 / 缺失 / 伪造

### 评审标准

- [ ] SecurityContext 包含设计方案 §8.2 全部字段
- [ ] Token 哈希校验，不存明文
- [ ] 撤销实时生效
- [ ] `X-Tenant-Id` Header 不再影响 SecurityContext

---

## WP2-T04：统一 Token 体系

> **SP：3 | 依赖：T03 | 主笔：工程师 A**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/services/authorization_service.py` | AuthorizationService（Token 部分） |
| `src/lakemind_server/api/security.py` | Security REST API |

### 执行步骤

1. **`issue_token()`**：生成随机 Token → SHA-256 哈希存表 → 返回明文仅一次
2. **`revoke_token()`**：`UPDATE tokens SET revoked_at = now()` → 审计 `auth.token_revoked`
3. **`list_tokens()`**：返回元数据列表（不含明文）
4. **REST API**：`POST/DELETE/GET /api/v1/security/tokens`
5. **Bootstrap Token**：首次部署创建 `platform_admin` + 初始 Token
6. **MCP 共享**：3 个 MCP 的 `lakemind_mcp_common/auth.py` 调用同一 Token 解析

### 评审标准

- [ ] Token 签发返回明文仅一次，DB 只存哈希
- [ ] 撤销后所有入口（REST + 3 MCP）立即拒绝
- [ ] 签发和撤销产生审计事件

---

## WP2-T05：RBAC + 资源级授权

> **SP：4 | 依赖：T03 | 主笔：工程师 A**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/security/actions.py` | 26 个动作枚举 |
| `src/lakemind_server/security/policy.py` | 资源级策略规则 |
| `src/lakemind_server/services/authorization_service.py` | 补充 authorize() / check_tenant() |

### 动作枚举（设计方案 §8.4）

```
asset:create|read|update|delete
knowledge:ingest|search|reindex
skill:register|publish|execute|revoke
memory:add|read|update|delete|clear
job:submit|read|cancel|retry
model:read|configure|use
secret:use|rotate
operation:request|approve
config:read|write|activate
audit:read
```

### 执行步骤

1. **编写 `actions.py`**：26 个动作枚举
2. **`authorize(ctx, action, resource?)`**：检查 `ctx.scopes` 包含 action + 资源级规则（`asset:delete` 校验 `resource.tenant_id == ctx.tenant_id`）
3. **`check_tenant(ctx, tenant_id)`**：不匹配 → 403 `TENANT_SCOPE_VIOLATION`；`platform_admin` 可跨租户
4. **内置角色权限映射**：`platform_admin`（全部）/ `tenant_admin`（租户内全部）/ `agent`（asset:read + knowledge:* + skill:read+execute + memory:* + job:*）/ `steward`（*:read + operation:request）/ `readonly`（*:read）
5. **FastAPI Dependency `require_action(action)`**

### 评审标准

- [ ] 26 个动作全部有角色映射
- [ ] Skill 读取与执行权限分离
- [ ] 跨租户返回 `TENANT_SCOPE_VIOLATION`
- [ ] `platform_admin` 可跨租户

---

## WP2-T06：租户隔离强制

> **SP：3 | 依赖：T05 | 主笔：工程师 A**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/security/tenant_isolation.py` | 租户路径解析 |

### 执行步骤

1. **路径生成**：
   - S3 Key: `ten_{tenant}/ast_{asset}/bnd_{binding}/{filename}`
   - Lance URI: `ten_{tenant}/ast_{asset}/vector`
   - Iceberg Namespace: `ten_{tenant}.{asset_type}`
   - Valkey Key: `ten_{tenant}:{key}`
2. **修改存储插件**：bucket/key 参数由 Service 层传入已解析路径
3. **移除 MCP 层租户拼接**：3 MCP 的 `X-Tenant-Id` 仅传递 Token，租户由 Server 从 SecurityContext 获取
4. **Service 层强制**：每个方法首行 `check_tenant(ctx, resource.tenant_id)`
5. **集成测试**：Tenant A 创建资产 → Tenant B 读取 → 403

### 评审标准

- [ ] S3/Lance/Iceberg/Valkey 路径全部包含租户前缀
- [ ] MCP 不再拼接租户路径
- [ ] 伪造 Header 不改变 SecurityContext

---

## WP2-T07：Protected Namespace

> **SP：2 | 依赖：T06 | 主笔：工程师 A**

### 执行步骤

1. **`is_protected(key)` → 检查 key 是否以 `ten_{tenant}/ast_` 开头**
2. **DataMCP 集成**：`s3_put` / `s3_delete` 调用前校验 Protected Namespace
3. **REST API 集成**：`/api/v1/storage/objects/*` 写端点校验
4. **单元测试**：受保护路径拒绝 / 非受保护允许 / 所有者可写自己路径

### 评审标准

- [ ] DataMCP `s3_put` / `s3_delete` 不覆盖 `ten_*/ast_*` 路径
- [ ] 资产所有者可写自己路径

---

## WP2-T08：Configuration Service

> **SP：4 | 依赖：T02 | 主笔：工程师 B**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/services/configuration_service.py` | ConfigurationService |
| `src/lakemind_server/config/schema.py` | 配置 Schema |
| `src/lakemind_server/api/configuration.py` | Configuration REST API |

### 配置 Schema

```python
CONFIG_SCHEMA = {
    "platform": {
        "job.default_timeout": {"type": "int", "default": 3600, "min": 60, "max": 86400},
        "job.default_retries": {"type": "int", "default": 3, "min": 0, "max": 10},
        "memory.default_retention_days": {"type": "int", "default": 90},
        "asset.max_size_mb": {"type": "int", "default": 1024},
        "steward.auto_governance_enabled": {"type": "bool", "default": False},
        "steward.auto_action_level": {"type": "str", "default": "observe", "enum": ["observe", "low_risk"]},
    },
    "tenant": {
        "job.max_concurrent": {"type": "int", "default": 10, "min": 1, "max": 100},
        "job.max_cpu": {"type": "float", "default": 4.0},
        "job.max_memory_mb": {"type": "int", "default": 8192},
        "memory.retention_days": {"type": "int", "default": 90},
        "asset.capacity_mb": {"type": "int", "default": 10240},
    },
}
```

### 执行步骤

1. **实现 ConfigurationService**：`get` / `set`（产生 Revision）/ `get_effective`（合并优先级）/ `activate` / `rollback` / `list_revisions`
2. **安全配置不可覆盖**：`tenant_id` / `secret` 权限 / `skill` 可信状态标记 `immutable = True`
3. **REST API**：6 个端点（GET/PUT configuration, GET/POST revisions）
4. **审计**：`set` / `activate` / `rollback` 全部产生审计事件

### 评审标准

- [ ] 配置变更产生新 Revision
- [ ] 优先级合并正确
- [ ] 安全配置不可被下层覆盖
- [ ] 回滚可恢复

---

## WP2-T09：配置优先级解析

> **SP：2 | 依赖：T08 | 主笔：工程师 B**

### 执行步骤

1. **`resolve(tenant_id, agent_id?, service_id?)`**：合并 `defaults → platform → tenant → agent/service → job overrides`
2. **安全配置跳过下层覆盖**
3. **Job 覆盖校验**：只允许覆盖 CPU/内存/超时，且在租户上限内
4. **缓存**：Valkey 缓存（TTL 60s），Revision 变更时失效

### 评审标准

- [ ] 4 层优先级合并正确
- [ ] 安全配置不可覆盖
- [ ] Job 覆盖不突破租户配额

---

## WP2-T10：Instance Registry

> **SP：2 | 依赖：T02 | 主笔：工程师 B**

### 执行步骤

1. **实现 InstanceRegistry**：`register` / `heartbeat` / `list_instances` / `get_instance`
2. **超时判定**：`last_heartbeat < now() - 30s` → `unhealthy`
3. **各服务启动自注册**：LakeMindServer / 3 MCP / ModelServing
4. **REST API**：`GET /api/v1/instances`
5. **心跳定时器**：每 10s 发送

### 评审标准

- [ ] 服务启动自动注册
- [ ] 心跳超时标记 unhealthy
- [ ] Active Revision 上报正确

---

## WP2-T11：配置生效模式

> **SP：2 | 依赖：T08 | 主笔：工程师 B**

### 执行步骤

1. **3 种模式**：`HOT_RELOAD`（Valkey pub/sub 通知）/ `COMPONENT_RELOAD`（产生 reload 事件）/ `SERVICE_RESTART`（标记 restart_required）
2. **Desired/Active 收敛检测**：比较 `config_revisions.is_active` 与 `instance_registry.active_revision_id`
3. **不一致 → Control Center 告警**

### 评审标准

- [ ] 3 种生效模式正确处理
- [ ] Desired/Active 不一致可检测

---

## WP2-T12：Secret Service

> **SP：3 | 依赖：T02 | 主笔：工程师 B**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/services/secret_service.py` | SecretService |
| `src/lakemind_server/security/crypto.py` | AES-256-GCM 加密 |

### 执行步骤

1. **`crypto.py`**：AES-256-GCM `encrypt` / `decrypt`，主密钥从 `LAKEMIND_MASTER_KEY` 环境变量读取
2. **SecretService**：`create`（加密存储）/ `get_ref`（返回引用）/ `resolve`（权限校验 + 解密）/ `rotate`（新版本）/ `list`（元数据）/ `log_usage`
3. **REST API**：`POST/GET /api/v1/security/secrets` + `POST rotate` — **不返回明文**
4. **迁移 v0.1.0 明文 Secret**（WP9-T04 执行）

### 评审标准

- [ ] Secret 加密存储，主密钥不存 PG
- [ ] API 不返回明文
- [ ] `resolve()` 需权限校验
- [ ] 轮换创建新版本

---

## WP2-T13：Secret 最小注入

> **SP：2 | 依赖：T12 | 主笔：工程师 B**

### 执行步骤

1. **`resolve_job_secrets(skill_manifest, caller_ctx, job_purpose)`**：只解析 Skill 声明的 Secret + 校验 `secret:use` 权限
2. **控制面全局密钥不注入 Ray**（除非 HIGH 风险审批）
3. **审计**：记录注入了哪些 Secret Ref（不记录明文）

### 评审标准

- [ ] Job 只获得声明的 Secret
- [ ] 控制面主密钥不注入 Ray
- [ ] 未声明的不注入

---

## WP2-T14：Audit Service

> **SP：3 | 依赖：T02 | 主笔：工程师 C**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/services/audit_service.py` | AuditService |
| `src/lakemind_server/api/audit.py` | Audit REST API |

### 审计点清单（§8.7）

```
auth.login / auth.token_issued / auth.token_revoked
authz.allowed / authz.denied
asset.create / asset.update / asset.delete / asset.state_change
skill.publish / skill.revoke / skill.execute
job.submit / job.cancel / job.retry / job.result
secret.use / secret.rotate
model.route_change / model.deployment_change / model.config_change
steward.suggestion / steward.auto_action
operation.approved / operation.rejected
config.activated / config.rolled_back
```

### 执行步骤

1. **`record()`**：写入 `audit_log`，自动填充 `request_id` / `timestamp`
2. **`query()`**：按 `event_type` / `principal_id` / `tenant_id` / `resource_id` / 时间范围 + 分页
3. **`export()`**：流式 JSONL 导出
4. **REST API**：`GET /api/v1/audit` + `GET /api/v1/audit/export`
5. **集成到各 Service**：关键方法调用 `audit_service.record()`

### 评审标准

- [ ] 覆盖 §8.7 全部审计点
- [ ] 查询支持多维度过滤
- [ ] 审计写入不阻塞主请求

---

## WP2-T15：Operation Service

> **SP：3 | 依赖：T14 | 主笔：工程师 C**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/services/operation_service.py` | OperationService |
| `src/lakemind_server/api/operations.py` | Operations REST API |

### 执行步骤

1. **状态机**（WP1-T06）：`create`（HIGH → `APPROVAL_REQUIRED`）/ `approve` / `execute` / `cancel`
2. **Operation handler 注册**：`asset_delete` → AssetService.delete_asset / `skill_publish` → SkillService.publish / ...
3. **REST API**：5 个端点
4. **审计**：全部状态变更有审计
5. **通知**：`APPROVAL_REQUIRED` → `operation.approval_required` 事件

### 评审标准

- [ ] 状态机转换无非法路径
- [ ] HIGH 风险操作需审批
- [ ] `approval_required` 事件正确产生

---

## WP2-T16：Outbox 基础

> **SP：3 | 依赖：T02 | 主笔：工程师 C**

### 交付物

| 文件路径 | 内容 |
|----------|------|
| `src/lakemind_server/outbox/worker.py` | Outbox Worker |
| `src/lakemind_server/outbox/handlers.py` | 事件 handler 注册 |

### 执行步骤

1. **Worker**：`SELECT ... FOR UPDATE SKIP LOCKED LIMIT 10` → 标记 `PROCESSING` → 调用 handler → `DONE` / 失败指数退避重试
2. **handler 注册**：`event_type → callable(payload)`，通过 `event_id` 幂等
3. **Service 层集成**：Application Service 在 PG 事务中同时写业务数据 + Outbox 事件
4. **Worker 启动**：LakeMindServer 启动 2 个 Worker 协程
5. **监控**：积压 > 100 → 告警

### 评审标准

- [ ] `SKIP LOCKED` 避免竞争
- [ ] 失败指数退避重试
- [ ] handler 幂等
- [ ] Outbox 与业务数据同事务

---

## WP2-T17：网络边界调整

> **SP：2 | 依赖：T10 | 主笔：工程师 C**

### 执行步骤

1. **Docker Compose**：`internal` 网络（PG/SeaweedFS/Valkey/Ray Dashboard/ModelServing 内部）+ `external` 网络（MCP/REST/Control Center）
2. **Ray Dashboard 8265 不对外**
3. **Service Identity**：每服务从 Bootstrap 读取自己的 `service_identity`，`lakemind_mcp_common/client.py` 使用 Service Identity
4. **移除共享 `LAKEMIND_API_KEY`**

### 评审标准

- [ ] PG/SeaweedFS/Valkey/Ray Dashboard 端口不对外
- [ ] 服务间使用 Service Identity
- [ ] 共享 API Key 已移除

---

## WP2-T18：REST API 认证中间件

> **SP：2 | 依赖：T05 | 主笔：工程师 C**

### 执行步骤

1. **全局中间件**：所有 `/api/v1/*` 需有效 Token（例外：`/api/v1/health`）
2. **端点授权**：每个端点添加 `Depends(require_action(Action.XXX))`，覆盖全部 67 端点
3. **v0.1.0 旧路径**：保留但标记 deprecated
4. **错误响应**：统一 WP1-T05 错误模型

### 评审标准

- [ ] 全部端点（除 health）需认证
- [ ] 每个端点有对应 Action
- [ ] 错误响应符合 WP1-T05

---

## WP2-T19：跨租户隔离测试

> **SP：2 | 依赖：T06 | 主笔：工程师 C + 安全顾问**

### 测试场景

| 场景 | 操作 | 期望 |
|------|------|------|
| S1 | Tenant A 创建资产 → Tenant B 读取 | 403 |
| S2 | Tenant A 删除 Tenant B 资产 | 403 |
| S3 | 伪造 `X-Tenant-Id` + Tenant A Token | SecurityContext 仍为 A |
| S4 | Token 撤销后调用 | 401 |
| S5 | Token 撤销后 MCP 调用 | 401 |
| S6 | 无 Token 调用 | 401 |
| S7 | 过期 Token | 401 |
| S8 | Tenant A Secret 被 Tenant B resolve | 403 |
| S9 | Tenant A Job 被 Tenant B cancel | 403 |
| S10 | platform_admin 跨租户 | 200 |

### 评审标准

- [ ] 10 个场景全部通过
- [ ] 伪造 Header 不改变 SecurityContext
- [ ] Token 撤销实时生效

---

## WP2 日程计划

### 第 3 周（W3）— S1 数据库迁移

| 日 | 人员 | 任务 | 产出 |
|----|------|------|------|
| W3-D1 | 工程师 A | T01：Alembic 接入 + 基线迁移 | `alembic.ini` + `001` |
| W3-D2 | 工程师 A | T01 验证 + T02 开始 | T01 完成 |
| W3-D3 | 工程师 A | T02：12 表 SQLAlchemy 模型 | 模型文件 |
| W3-D4 | 工程师 A | T02：迁移 + 种子数据 | `002_control_plane.py` |
| W3-D5 | 工程师 A | T02 验证 + 评审 | **T02 完成** |

### 第 4 周（W4）— S2 身份与授权

| 日 | 人员 | 任务 | 产出 |
|----|------|------|------|
| W4-D1 | 工程师 A | T03：SecurityContext + Token 解析 | `context.py` + `middleware.py` |
| W4-D2 | 工程师 A | T03 测试 + T04：Token 签发/撤销 | **T03 完成** |
| W4-D3 | 工程师 A | T04：REST API + MCP 共享 | **T04 完成** |
| W4-D4 | 工程师 A | T05：RBAC + 动作枚举 + 策略 | `actions.py` + `policy.py` |
| W4-D5 | 工程师 A | T05 测试 + T06：租户隔离 | T05 评审 |

### 第 5 周（W5）— S3 配置 + S4 Secret

| 日 | 人员 | 任务 | 产出 |
|----|------|------|------|
| W5-D1 | 工程师 A | T06 + T07：隔离 + Protected NS | **T06-T07 完成** |
| W5-D1 | 工程师 B | T08：ConfigurationService + Schema | `configuration_service.py` |
| W5-D2 | 工程师 B | T08：REST API + 审计 | **T08 完成** |
| W5-D3 | 工程师 B | T09：优先级 + T10：Instance Registry | **T09 完成** |
| W5-D4 | 工程师 B | T10 + T11：生效模式 | **T10-T11 完成** |
| W5-D5 | 工程师 B | T12：SecretService | **T12 进行中** |

### 第 6 周（W6）— S4 完成 + S5 + S6

| 日 | 人员 | 任务 | 产出 |
|----|------|------|------|
| W6-D1 | 工程师 B | T12 + T13：Secret 最小注入 | **T12-T13 完成** |
| W6-D1 | 工程师 C | T14：AuditService | `audit_service.py` |
| W6-D2 | 工程师 C | T14 + T15：OperationService | **T14 完成** |
| W6-D3 | 工程师 C | T15 + T16：Outbox Worker | **T15 完成** |
| W6-D4 | 工程师 C | T16 + T17：网络 + T18：REST 中间件 | **T16-T18 完成** |
| W6-D5 | 工程师 C + 全员 | T19：跨租户测试 + **M1 门禁** | **T19 完成** |

### 门禁 M1 评审清单

- [ ] `alembic upgrade head` 成功，12 表就位
- [ ] Token 签发 → 认证 → 授权 → 审计 端到端
- [ ] Token 撤销在 REST + 3 MCP 全部入口实时生效
- [ ] 伪造 `X-Tenant-Id` 不改变 SecurityContext
- [ ] Configuration Revision 变更可回滚
- [ ] Secret API 不返回明文
- [ ] 审计覆盖 §8.7 全部审计点
- [ ] Operation 状态机正确，HIGH 风险需审批
- [ ] Outbox Worker 正常消费
- [ ] 跨租户隔离 10 场景通过
- [ ] Ray Dashboard 端口不对外
- [ ] 内置角色权限映射正确

---

## WP2 交付物汇总

### 新增文件

```
LakeMindServer/
  ├── alembic.ini
  ├── migrations/{env.py, script.py.mako, versions/001_initial_schema.py, 002_control_plane.py}
  └── src/lakemind_server/
      ├── db.py
      ├── models/{identity.py, config.py, secret.py, audit.py, instance.py, outbox.py}
      ├── security/{context.py, middleware.py, token_parser.py, actions.py, policy.py,
      │             tenant_isolation.py, protected_namespace.py, crypto.py, secret_injection.py}
      ├── services/{authorization_service.py, configuration_service.py, secret_service.py,
      │             audit_service.py, operation_service.py, instance_registry.py}
      ├── config/{schema.py, resolver.py, effect_mode.py}
      ├── outbox/{worker.py, handlers.py}
      └── api/{security.py, configuration.py, audit.py, operations.py, instances.py}

LakeMindMCP/lakemind_mcp_common/{auth.py, client.py}
tests/{unit/*, integration/*, security/*}
```

### 修改文件

```
LakeMindServer/src/lakemind_server/{app.py, auth.py, api/*.py, api/secrets.py}
LakeMindServer/src/lakemind_server/plugins/storage/{object/seaweedfs.py, vector/lancedb.py}
docker/docker-compose.yml
```

---

## WP2 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Alembic 迁移与 v0.1.0 手动 SQL 冲突 | 高 | 基线迁移精确还原，`alembic stamp head` |
| RBAC 权限映射遗漏 | 中 | 内置角色覆盖全部 26 动作，逐角色测试 |
| Secret 主密钥管理不当 | 高 | 主密钥仅环境变量，不存 PG，不记日志 |
| Outbox Worker 单点 | 中 | v0.2.0 单节点可接受 |
| 网络隔离破坏现有依赖 | 中 | 逐步调整，先加 `internal` 再移除端口 |

---

<a id="wp3"></a>
# WP3：Asset Runtime

> **阶段：C（第 7-11 周）**  
> **估算：52 SP**  
> **依赖：WP1, WP2（M1 通过）**  
> **目标：让 Knowledge、Skill、Memory 真正成为可版本化、可审计、可恢复的平台资产**

---

## WP3.0 概述

### 任务清单

| 子流 | Task ID | 任务 | SP | 依赖 |
|------|---------|------|----|------|
| S1 Asset Core | WP3-T01 | Asset Core schema | 3 | WP2 |
| | WP3-T02 | Asset Binding schema | 2 | T01 |
| | WP3-T03 | 资产状态机 | 3 | T01 |
| | WP3-T04 | AssetService 公共接口 | 3 | T03 |
| | WP3-T05 | 版本与 Revision | 2 | T03 |
| | WP3-T06 | 血缘记录 | 2 | T01 |
| S2 Knowledge | WP3-T07 | Knowledge 模型与 schema | 2 | T04 |
| | WP3-T08 | Knowledge 摄入流程 | 4 | T07 |
| | WP3-T09 | Knowledge 检索 | 3 | T08 |
| | WP3-T10 | Embedding 失败处理 | 2 | T08 |
| | WP3-T11 | Knowledge 重建索引 | 2 | T09 |
| S3 Skill | WP3-T12 | Skill 模型与 schema | 3 | T04 |
| | WP3-T13 | Skill 生命周期 | 2 | T12 |
| | WP3-T14 | Skill 校验 | 2 | T13 |
| | WP3-T15 | Skill 检索 | 2 | T13 |
| S4 Memory | WP3-T16 | Memory 模型与 schema | 3 | T04 |
| | WP3-T17 | 临时态 vs 持久态分离 | 2 | T16 |
| | WP3-T18 | Memory CRUD | 3 | T17 |
| | WP3-T19 | Memory 过期与归档 | 2 | T18 |
| S5 一致性 | WP3-T20 | Outbox Worker（资产） | 3 | WP2-T16 |
| | WP3-T21 | Reconciler | 3 | T20 |
| | WP3-T22 | 异步删除 | 3 | T21 |
| | WP3-T23 | 故障注入测试 | 2 | T22 |
| **合计** | | | **52** | |

### 人员配置

| 角色 | 职责 |
|------|------|
| 工程师 A | T01-T06 + T20-T23（Asset Core + 一致性） |
| 工程师 B | T07-T11（Knowledge） |
| 工程师 C | T12-T19（Skill + Memory） |

---

## WP3-T01：Asset Core schema

> **SP：3 | 依赖：WP2 | 主笔：工程师 A**

### 交付物

- `migrations/versions/003_asset_core.py` — `assets` 表
- `src/lakemind_server/models/asset.py` — Asset 模型

### `assets` 表

```sql
CREATE TABLE assets (
    asset_id      TEXT PRIMARY KEY,       -- ast_{ulid}
    tenant_id     TEXT NOT NULL,
    asset_type    TEXT NOT NULL,          -- knowledge|skill|memory
    name          TEXT NOT NULL,
    version       TEXT NOT NULL DEFAULT '1.0.0',
    schema_version TEXT NOT NULL DEFAULT '1',
    status        TEXT NOT NULL DEFAULT 'DRAFT',
    owner_id      TEXT NOT NULL,
    created_by    TEXT NOT NULL,
    visibility    TEXT NOT NULL DEFAULT 'private',
    classification TEXT,
    source_type   TEXT,
    source_uri    TEXT,
    checksum      TEXT,
    retention_policy JSONB DEFAULT '{}',
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ
);
CREATE INDEX idx_assets_tenant_type ON assets(tenant_id, asset_type, status);
CREATE INDEX idx_assets_name_version ON assets(tenant_id, asset_type, name, version);
```

### 评审标准

- [ ] 覆盖设计方案 §9.2 全部公共字段
- [ ] ULID 前缀格式
- [ ] 索引覆盖高频查询

---

## WP3-T02：Asset Binding schema

> **SP：2 | 依赖：T01 | 主笔：工程师 A**

### `asset_bindings` 表

```sql
CREATE TABLE asset_bindings (
    binding_id    TEXT PRIMARY KEY,       -- bnd_{ulid}
    asset_id      TEXT NOT NULL REFERENCES assets(asset_id),
    binding_type  TEXT NOT NULL,          -- ORIGINAL_OBJECT|PARSED_CONTENT|CHUNK_DATA|VECTOR_INDEX|GRAPH_PROJECTION|TABLE_DATASET|SKILL_PACKAGE|JOB_ARTIFACT
    provider      TEXT NOT NULL,
    physical_uri  TEXT NOT NULL,          -- 内部，不外泄
    binding_version TEXT NOT NULL DEFAULT '1',
    checksum      TEXT,
    status        TEXT NOT NULL DEFAULT 'PENDING',
    is_required   BOOLEAN NOT NULL DEFAULT TRUE,
    metadata      JSONB DEFAULT '{}',
    last_error    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `reconciler_state` 表

```sql
CREATE TABLE reconciler_state (
    id              BIGSERIAL PRIMARY KEY,
    scan_category   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    drift_type      TEXT NOT NULL,
    drift_details   JSONB DEFAULT '{}',
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);
```

### 评审标准

- [ ] 8 种 Binding 类型定义
- [ ] `is_required` 标记 Required vs Optional

---

## WP3-T03：资产状态机

> **SP：3 | 依赖：T01 | 主笔：工程师 A**

### 状态转换规则

```
DRAFT → CREATING → PROCESSING → READY (全部 Required Binding READY)
                               → DEGRADED (Required OK + Optional 失败)
                               → FAILED (Required 失败)
READY → DEPRECATED → DELETING → DELETED
任何状态 → DELETING → DELETED (异步删除)
```

### 执行步骤

1. **`transition(current, target, context) → new_state`**
2. **事件发射**：`asset.processing` / `asset.ready` / `asset.degraded` / `asset.deleted`
3. **READY 严格判定**：全部 `is_required = TRUE` Binding 为 READY
4. **审计**：每次转换写 `audit_log`

### 评审标准

- [ ] 无非法转换
- [ ] READY 要求全部 Required Binding 完成
- [ ] 每次转换有事件 + 审计

---

## WP3-T04：AssetService 公共接口

> **SP：3 | 依赖：T03 | 主笔：工程师 A**

### 交付物

- `src/lakemind_server/services/asset_service.py`
- `src/lakemind_server/api/assets.py` — 8 个 REST 端点

### 接口

```
create_asset(ctx, type, name, source, metadata) → Asset
get_asset(ctx, asset_id) → Asset
list_assets(ctx, type?, status?, page) → Page[Asset]
update_asset(ctx, asset_id, metadata) → Asset
delete_asset(ctx, asset_id) → Operation  # 异步
get_bindings(ctx, asset_id) → List[Binding]
get_lineage(ctx, asset_id) → LineageGraph
reindex(ctx, asset_id) → Operation
```

### 评审标准

- [ ] 8 方法 + 8 端点
- [ ] 物理路径不外泄
- [ ] 删除为异步 Operation
- [ ] 全部操作有授权 + 审计

---

## WP3-T05：版本与 Revision

> **SP：2 | 依赖：T03 | 主笔：工程师 A**

### 三级版本语义

| 版本类型 | 触发 | 影响 |
|----------|------|------|
| 内容版本 | 内容变化 | 新 Asset 记录 |
| Metadata Revision | 元数据小改 | 更新 metadata + updated_at |
| Binding Version | 重建索引 | 仅更新 binding_version |

### 评审标准

- [ ] Skill 发布后不可变
- [ ] 重建索引不改变内容版本

---

## WP3-T06：血缘记录

> **SP：2 | 依赖：T01 | 主笔：工程师 A**

### `asset_lineage` 表

```sql
CREATE TABLE asset_lineage (
    lineage_id     TEXT PRIMARY KEY,
    asset_id       TEXT NOT NULL,
    source_type    TEXT NOT NULL,         -- asset|job_run|skill|model|config
    source_id      TEXT NOT NULL,
    source_version TEXT,
    relation       TEXT NOT NULL,         -- derived_from|generated_by|extracted_from|reindexed_from
    details        JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 评审标准

- [ ] 覆盖 §9.11 全部关系
- [ ] 自动记录
- [ ] 血缘图可查询

---

## WP3-T07：Knowledge 模型与 schema

> **SP：2 | 依赖：T04 | 主笔：工程师 B**

### `knowledge_meta` 表

```sql
CREATE TABLE knowledge_meta (
    asset_id          TEXT PRIMARY KEY REFERENCES assets(asset_id),
    kb_name           TEXT NOT NULL,
    parser_version    TEXT,
    embedding_space_id TEXT,
    chunk_config      JSONB DEFAULT '{}',
    index_status      TEXT NOT NULL DEFAULT 'PENDING',
    concept_count     INTEGER DEFAULT 0,
    total_chunks      INTEGER DEFAULT 0
);
```

### Binding 类型

Knowledge 资产有 4 Required + 1 Optional Binding：
- `ORIGINAL_OBJECT`（S3）— Required
- `PARSED_CONTENT`（S3）— Required
- `CHUNK_DATA`（S3/Lance）— Required
- `VECTOR_INDEX`（Lance）— Required
- `GRAPH_PROJECTION`（PG Graph）— Optional

---

## WP3-T08：Knowledge 摄入流程

> **SP：4 | 依赖：T07 | 主笔：工程师 B**

### 交付物

- `src/lakemind_server/services/knowledge_service.py` — `ingest()`
- `src/lakemind_server/outbox/knowledge_handlers.py`
- `src/lakemind_server/api/knowledge.py`

### 摄入流程

```
1. API 上传 → AssetService.create_asset(CREATING) + Outbox asset.created
2. Worker 消费：
   2a. 写 S3 原始 → Binding(ORIGINAL_OBJECT, READY)
   2b. 解析 → 写 S3 → Binding(PARSED_CONTENT, READY)
   2c. Chunk → Binding(CHUNK_DATA, READY)
   2d. Embedding → Lance → Binding(VECTOR_INDEX, READY)
3. 全部 Required READY → 状态机转 READY
4. 任一 Required 失败 → FAILED 或 DEGRADED
```

### 评审标准

- [ ] 5 步全部实现
- [ ] Outbox 事件驱动
- [ ] 全部 Required Binding READY 才 READY
- [ ] 幂等键防重复

---

## WP3-T09：Knowledge 检索

> **SP：3 | 依赖：T08 | 主笔：工程师 B**

### 执行步骤

1. **`search(ctx, query, kb_name?, filters?, top_k)`**：Embedding query → Lance 检索 → 过滤 `status IN (READY, DEGRADED)` → 返回 `List[SearchResult]`
2. **`get_concept()` / `list_concepts()`**
3. **不返回 FAILED/DELETING/DELETED**
4. **DEGRADED 资产可检索但携带警告**
5. **来源追溯**：每个结果关联 `asset_id` → 可查血缘

### 评审标准

- [ ] FAILED/DELETED 不返回
- [ ] 租户隔离
- [ ] 来源追溯可查

---

## WP3-T10：Embedding 失败处理

> **SP：2 | 依赖：T08 | 主笔：工程师 B**

### 执行步骤

1. **Embedding 失败**：Binding(VECTOR_INDEX, FAILED) + 不写零向量 + 资产 DEGRADED
2. **保留原始内容**
3. **后台重试**：Reconciler 扫描 DEGRADED + VECTOR_INDEX FAILED → 重试

### 评审标准

- [ ] 不写零向量
- [ ] 资产 DEGRADED 而非 READY
- [ ] 后台重试机制

---

## WP3-T11：Knowledge 重建索引

> **SP：2 | 依赖：T09 | 主笔：工程师 B**

### 执行步骤

1. **`reindex(ctx, kb_name) → Operation`**：旧 Binding DELETED → 重新 Chunk + Embed → 新 Binding（version +1）
2. **不改变内容版本**
3. **支持 Embedding Space 变更**

---

## WP3-T12：Skill 模型与 schema

> **SP：3 | 依赖：T04 | 主笔：工程师 C**

### `skill_meta` 表

```sql
CREATE TABLE skill_meta (
    asset_id          TEXT PRIMARY KEY REFERENCES assets(asset_id),
    manifest          JSONB NOT NULL,
    code_checksum     TEXT NOT NULL,
    entry_point       TEXT NOT NULL,
    input_schema      JSONB NOT NULL,
    output_schema     JSONB NOT NULL,
    dependencies      JSONB DEFAULT '[]',
    permissions       JSONB DEFAULT '[]',
    model_profiles    JSONB DEFAULT '[]',
    secret_declarations JSONB DEFAULT '[]',
    resource_needs    JSONB DEFAULT '{}',
    network_needs     JSONB DEFAULT '{}',
    trust_level       TEXT NOT NULL DEFAULT 'untrusted',
    publish_status    TEXT NOT NULL DEFAULT 'DRAFT',
    published_by      TEXT,
    published_at      TIMESTAMPTZ
);
```

### 评审标准

- [ ] 覆盖 §9.6 全部字段
- [ ] Manifest 结构完整

---

## WP3-T13：Skill 生命周期

> **SP：2 | 依赖：T12 | 主笔：工程师 C**

### 状态转换

```
DRAFT → VALIDATING → PUBLISHED → DEPRECATED
                                  → REVOKED
```

### 执行步骤

1. **`register()`**：创建 Asset + skill_meta + S3 代码包 → DRAFT
2. **`validate()`**：DRAFT → VALIDATING → 校验（T14）
3. **`publish()`**：VALIDATING → PUBLISHED + 不可变
4. **`revoke()`**：→ REVOKED，不可执行

### 评审标准

- [ ] PUBLISHED 后不可变
- [ ] REVOKED 不可执行
- [ ] 全部变更有审计

---

## WP3-T14：Skill 校验

> **SP：2 | 依赖：T13 | 主笔：工程师 C**

### 校验内容

1. **Manifest 校验**：必填字段 + SemVer 版本 + 合法权限
2. **代码 Checksum**：SHA-256
3. **依赖安全扫描**：基础检查
4. **Schema 校验**：JSON Schema 合法性

### 评审标准

- [ ] 非法 Skill 不能 PUBLISH

---

## WP3-T15：Skill 检索

> **SP：2 | 依赖：T13 | 主笔：工程师 C**

### 交付物

- `src/lakemind_server/services/skill_service.py` — `get_skill()` / `list_skills()` / `search_skills()`
- `src/lakemind_server/api/skills.py` — 6 个 REST 端点

### 评审标准

- [ ] 读取权限与执行权限分离（`skill:read` ≠ `skill:execute`）
- [ ] 不返回代码包内容

---

## WP3-T16：Memory 模型与 schema

> **SP：3 | 依赖：T04 | 主笔：工程师 C**

### `memory_meta` 表

```sql
CREATE TABLE memory_meta (
    asset_id            TEXT PRIMARY KEY REFERENCES assets(asset_id),
    memory_type         TEXT NOT NULL,     -- working|session|agent_private|user|org_shared
    subject             TEXT,
    scope               TEXT NOT NULL,
    source              TEXT NOT NULL,     -- chat|job|extraction|manual
    content             TEXT NOT NULL,
    importance          REAL DEFAULT 0.5,
    retention           TEXT DEFAULT 'permanent',
    expiration          TIMESTAMPTZ,
    access_scope        TEXT DEFAULT 'private',
    embedding_status    TEXT DEFAULT 'PENDING',
    consolidation_status TEXT DEFAULT 'none',
    revision            INTEGER NOT NULL DEFAULT 1
);
```

### Memory 类型

- Working / Session → Valkey TTL（临时态，不进 `assets`）
- Agent Private / User / Org Shared → `assets` + `memory_meta`（持久态）

---

## WP3-T17：临时态 vs 持久态分离

> **SP：2 | 依赖：T16 | 主笔：工程师 C**

### 执行步骤

1. **临时态**：`add_working(session_id, key, value, ttl)` → Valkey `SET ... EX`，不创建 Asset
2. **持久态**：`add(ctx, messages, metadata)` → 创建 Asset + memory_meta + Embedding → 走 Outbox + 状态机

### 评审标准

- [ ] Working/Session 使用 Valkey TTL
- [ ] 持久 Memory 走 Asset 生命周期

---

## WP3-T18：Memory CRUD

> **SP：3 | 依赖：T17 | 主笔：工程师 C**

### mem0 风格 8 方法

```
add(ctx, messages, metadata) → Memory     # LLM 事实抽取 + 哈希去重
search(ctx, query, filters?, top_k) → List[Memory]
get(memory_id) → Memory
list(ctx, filters?, page) → Page[Memory]
update(memory_id, content) → Memory       # revision +1 + 重新 Embedding
delete(memory_id) → void                  # 异步
clear(ctx, filters?) → int
history(memory_id) → List[MemoryEvent]
```

### 交付物

- `src/lakemind_server/services/memory_service.py`
- `src/lakemind_server/api/memories.py` — 8 个 REST 端点

### 评审标准

- [ ] 8 方法全部实现
- [ ] LLM 事实抽取 + 哈希去重
- [ ] update 增加 revision

---

## WP3-T19：Memory 过期与归档

> **SP：2 | 依赖：T18 | 主笔：工程师 C**

### 执行步骤

1. **TTL 过期清理**：定时任务查 `retention = 'temporary' AND expiration < now()` → 批量删除
2. **归档**：`consolidation_status = 'archived'`，不参与默认 search
3. **保留期限**：从 ConfigurationService 读 `memory.retention_days`

---

## WP3-T20：Outbox Worker（资产）

> **SP：3 | 依赖：WP2-T16 | 主笔：工程师 A**

### 事件 handler

| 事件 | handler | 操作 |
|------|---------|------|
| `asset.created` | 写 S3 原始 → Binding(ORIGINAL_OBJECT) |
| `asset.processing` | 解析 → Chunk → Embedding → Binding |
| `asset.delete_requested` | 清除全部 Binding → DELETED |
| `asset.reindex_requested` | 清除旧 Binding → 重新 Chunk + Embed |

### 评审标准

- [ ] 4 handler 全部实现
- [ ] Binding 状态正确更新
- [ ] 幂等执行
- [ ] 状态机联动

---

## WP3-T21：Reconciler

> **SP：3 | 依赖：T20 | 主笔：工程师 A**

### 扫描规则

| 类型 | 检测 | 修复 |
|------|------|------|
| `binding_missing` | READY 但 Binding 不存在 | 标记 DEGRADED |
| `status_mismatch` | Binding READY 但 S3/Lance 对象不存在 | Binding FAILED |
| `stale_deleting` | DELETING 超时 | 重试删除 |
| `index_lost` | VECTOR_INDEX READY 但 Lance 表丢失 | FAILED + reindex |
| `degraded_retryable` | DEGRADED + 可重试 | 重试 Embedding |

### 执行步骤

1. **`scan_assets() → List[DriftReport]`**：每 5 分钟扫描
2. **`repair(drift_id) → Operation`**
3. **drift 记录到 `reconciler_state`**

---

## WP3-T22：异步删除

> **SP：3 | 依赖：T21 | 主笔：工程师 A**

### 删除流程

```
1. delete_asset() → DELETING + Outbox asset.delete_requested
2. Worker 消费：
   2a. 撤销引用（标记下游 source_deleted）
   2b. 清除全部 Binding（S3/Lance/Graph）
   2c. 全部 DELETED → 资产 DELETED
3. 失败 → 保持 DELETING + Reconciler 重试
```

### 评审标准

- [ ] 清除全部 Binding
- [ ] 失败保持 DELETING
- [ ] 血缘引用处理

---

## WP3-T23：故障注入测试

> **SP：2 | 依赖：T22 | 主笔：工程师 A**

### 测试场景

| 场景 | 故障 | 期望 |
|------|------|------|
| F1 | Embedding 失败 | DEGRADED，不写零向量 |
| F2 | Lance 丢失 | Reconciler → reindex |
| F3 | S3 delete 失败 | 保持 DELETING |
| F4 | Outbox 重启 | 不重复执行 |
| F5 | 双重摄入 | 返回缓存响应 |
| F6 | READY 后 Binding 丢失 | DEGRADED |

### 评审标准

- [ ] 6 场景全部通过

---

## WP3 日程计划

| 周 | 任务 | 产出 |
|----|------|------|
| W7 | T01-T06 | Asset Core + Binding + 状态机 + AssetService + 版本 + 血缘 |
| W8 | T07-T11 | Knowledge 模型 + 摄入 + 检索 + Embedding 失败 + reindex |
| W9 | T12-T15 + T20 开始 | Skill 模型 + 生命周期 + 校验 + 检索 |
| W10 | T16-T19 | Memory 模型 + 临时/持久 + CRUD + 过期 |
| W11 | T20-T23 | Outbox Worker + Reconciler + 异步删除 + 故障注入 + **M2** |

### 门禁 M2 评审清单

- [ ] 7 张新表就位（assets, asset_bindings, asset_lineage, knowledge_meta, skill_meta, memory_meta, reconciler_state）
- [ ] 资产状态机转换正确
- [ ] Knowledge 摄入端到端：上传 → READY + 4 Binding READY
- [ ] Embedding 失败 → DEGRADED，不写零向量
- [ ] Skill 发布后不可变，REVOKED 不可执行
- [ ] Memory 8 方法端到端
- [ ] 临时态 Valkey，持久态走 Asset 生命周期
- [ ] Reconciler 检测 5 种 drift
- [ ] 异步删除清除全部 Binding 或保持 DELETING
- [ ] 故障注入 6 场景通过

---

<a id="wp4"></a>
# WP4：Job Runtime 与 Ray

> **阶段：D（第 12-15 周，与 WP5 并行）**  
> **估算：36 SP**  
> **依赖：WP1, WP2, WP3（M2 通过）**  
> **目标：建立受控、可审计、可恢复的任务运行时**

---

## WP4.0 概述

### 任务清单

| 子流 | Task ID | 任务 | SP | 依赖 |
|------|---------|------|----|------|
| S1 Job 模型 | WP4-T01 | Job Run / Attempt schema | 3 | WP3 |
| | WP4-T02 | Job 状态机 | 2 | T01 |
| | WP4-T03 | Artifact 模型 | 2 | T01 |
| S2 JobService | WP4-T04 | Job 提交 API | 3 | T02 |
| | WP4-T05 | Skill 执行资格校验 | 2 | T04 |
| | WP4-T06 | 资源配额 | 2 | T04 |
| | WP4-T07 | Secret 与模型绑定 | 3 | T04 |
| S3 Execution | WP4-T08 | ExecutionBackend 抽象 | 2 | T02 |
| | WP4-T09 | RayExecutionBackend | 3 | T08 |
| | WP4-T10 | Job 状态同步 | 2 | T09 |
| S4 恢复 | WP4-T11 | 重试/取消/超时 | 2 | T10 |
| | WP4-T12 | Server 重启恢复 | 2 | T10 |
| | WP4-T13 | 日志归档 | 2 | T03 |
| | WP4-T14 | Artifact 资产化 | 2 | T13 |
| | WP4-T15 | 可复现性记录 | 2 | T07 |
| **合计** | | | **36** | |

### v0.1.0 基线

| 维度 | v0.1.0 | v0.2.0 |
|------|--------|--------|
| Job | DataMCP 5 个 Ray 工具直连 | JobService 一等能力 |
| 状态 | Ray 为事实源 | PG 为事实源 |
| 安全 | 任意 eval 入口 | 只执行 PUBLISHED Skill |
| Secret | 全环境变量传入 | 最小注入 |
| 恢复 | 无 | 重启恢复 + Lost 检测 |

---

## WP4-T01：Job Run / Attempt schema

> **SP：3 | 依赖：WP3 | 主笔：工程师 A**

### `job_runs` 表

```sql
CREATE TABLE job_runs (
    job_id          TEXT PRIMARY KEY,       -- job_{ulid}
    tenant_id       TEXT NOT NULL,
    skill_asset_id  TEXT NOT NULL REFERENCES assets(asset_id),
    skill_version   TEXT NOT NULL,
    skill_checksum  TEXT NOT NULL,
    initiator_id    TEXT NOT NULL,
    inputs          JSONB NOT NULL,
    params          JSONB DEFAULT '{}',
    model_binding   JSONB,                  -- {profile, model_id, deployment_id, revision, embedding_space_id}
    secret_refs     JSONB DEFAULT '[]',
    resource_final  JSONB NOT NULL,
    status          TEXT NOT NULL DEFAULT 'SUBMITTED',
    config_revision_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX idx_jobs_tenant_status ON job_runs(tenant_id, status);
```

### `job_attempts` 表

```sql
CREATE TABLE job_attempts (
    attempt_id      TEXT PRIMARY KEY,       -- atm_{ulid}
    job_id          TEXT NOT NULL REFERENCES job_runs(job_id),
    attempt_number  INTEGER NOT NULL,
    ray_job_id      TEXT,                   -- Ray 原始 ID（内部）
    status          TEXT NOT NULL DEFAULT 'QUEUED',
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    duration_ms     INTEGER,
    error_message   TEXT,
    resource_used   JSONB,
    UNIQUE(job_id, attempt_number)
);
```

### 评审标准

- [ ] `job_runs` 记录 Skill 版本 + Checksum + 模型绑定 + Secret Ref + 配置 Revision
- [ ] `job_attempts` 记录 Ray Job ID 映射

---

## WP4-T02：Job 状态机

> **SP：2 | 依赖：T01 | 主笔：工程师 A**

### 状态转换

```
SUBMITTED → QUEUED → RUNNING → SUCCEEDED
                           → FAILED (→ 重试 = 新 Attempt)
                           → TIMED_OUT
                           → CANCELLING → CANCELLED
                           → LOST (Reconciler)
```

### 评审标准

- [ ] 无非法转换
- [ ] 重试产生新 Attempt
- [ ] LOST 由 Reconciler 检测

---

## WP4-T03：Artifact 模型

> **SP：2 | 依赖：T01 | 主笔：工程师 A**

### `job_artifacts` 表

```sql
CREATE TABLE job_artifacts (
    artifact_id     TEXT PRIMARY KEY,       -- art_{ulid}
    job_id          TEXT NOT NULL REFERENCES job_runs(job_id),
    attempt_id      TEXT NOT NULL REFERENCES job_attempts(attempt_id),
    artifact_type   TEXT NOT NULL,          -- transcript|summary|knowledge_extract|log|result|model_output
    uri             TEXT NOT NULL,
    checksum        TEXT,
    size_bytes      BIGINT,
    can_assetize    BOOLEAN NOT NULL DEFAULT FALSE,
    asset_id        TEXT REFERENCES assets(asset_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## WP4-T04：Job 提交 API

> **SP：3 | 依赖：T02 | 主笔：工程师 A**

### 交付物

- `src/lakemind_server/services/job_service.py`
- `src/lakemind_server/api/jobs.py` — 7 个 REST 端点

### 提交流程

```
1. 接收 submit(skill_ref, inputs, params, model_profile?, resource_overrides?)
2. 权限校验：job:submit + skill:execute
3. Skill 资格校验（T05）
4. 资源配额计算（T06）
5. Secret + 模型绑定解析（T07）
6. 创建 job_runs（SUBMITTED）→ QUEUED
7. 提交到 ExecutionBackend
8. 审计 + 事件 job.submitted
```

### 评审标准

- [ ] 9 步全部实现
- [ ] 幂等键防重复
- [ ] 审计 + 事件

---

## WP4-T05：Skill 执行资格校验

> **SP：2 | 依赖：T04 | 主笔：工程师 A**

### 执行步骤

1. 校验 Skill `publish_status = PUBLISHED` + 未 REVOKED
2. 校验 `trust_level` 或显式授权
3. **移除任意 eval 入口**：删除 v0.1.0 任意函数/源码执行路径

### 评审标准

- [ ] 只执行 PUBLISHED Skill
- [ ] 任意 eval 入口已移除
- [ ] REVOKED 不可执行

---

## WP4-T06：资源配额

> **SP：2 | 依赖：T04 | 主笔：工程师 A**

### 执行步骤

1. **`resolve_resources(skill_default, tenant_limit, job_override) → final`**
   - `final.cpu = min(override or default, tenant_limit)`
   - 超限 → 403 `JOB_RESOURCE_DENIED`
2. **并发限制**：租户 RUNNING Job < `max_concurrent`

---

## WP4-T07：Secret 与模型绑定

> **SP：3 | 依赖：T04 | 主笔：工程师 A**

### 执行步骤

1. **Secret 解析**：`SecretInjection.resolve_job_secrets()`（WP2-T13）
2. **模型绑定**：`ModelManagementService.resolve_profile()` → `{model_id, deployment_id, revision, embedding_space_id}` → 固定到 `job_runs.model_binding`
3. **后续模型切换不影响历史 Job**
4. **可复现性记录**：Skill 版本 + Checksum + 模型 + 配置 Revision + Secret Ref 版本

### 评审标准

- [ ] Secret 最小注入
- [ ] 模型绑定固定
- [ ] 后续切换不影响历史

---

## WP4-T08：ExecutionBackend 抽象

> **SP：2 | 依赖：T02 | 主笔：工程师 B**

### Protocol（WP1-T10）

```python
class ExecutionBackend(Protocol):
    def submit(self, job_id, skill_package_uri, entry_point, inputs, params, resources, secrets, model_binding) -> str: ...
    def cancel(self, backend_job_id) -> None: ...
    def get_status(self, backend_job_id) -> str: ...
    def get_logs(self, backend_job_id) -> str: ...
    def get_result(self, backend_job_id) -> dict: ...
```

### 评审标准

- [ ] 5 方法 Protocol
- [ ] 不泄漏 Ray 特有字段

---

## WP4-T09：RayExecutionBackend

> **SP：3 | 依赖：T08 | 主笔：工程师 B**

### 交付物

- `src/lakemind_server/plugins/compute/distributed/ray_execution_backend.py`

### 执行步骤

1. **`submit()`**：下载 Skill 包 → 构建 Ray Job 配置 → Secret 作为环境变量 → `ray.job_submission.submit()`
2. **`cancel()`** / `get_status()` / `get_logs()` / `get_result()`
3. **LakeMind Job ID ↔ Ray Job ID 映射**：`job_attempts.ray_job_id`
4. **资源映射**：`cpu/memory` → `num_cpus/num_gbs`

### 评审标准

- [ ] Ray Job 提交成功
- [ ] 状态映射正确
- [ ] Ray Job ID 不外泄

---

## WP4-T10：Job 状态同步

> **SP：2 | 依赖：T09 | 主笔：工程师 B**

### 执行步骤

1. **定时同步**：每 10s 查 `job_attempts WHERE status IN (QUEUED, RUNNING)` → 查 Ray 状态 → 更新 PG
2. **PG 为事实源**：Ray 状态同步到 PG，不反向
3. **Lost 检测**：Ray 中 Job 不存在 + PG 状态 RUNNING → 标记 LOST

### 评审标准

- [ ] PG 为事实源
- [ ] Lost 检测正确

---

## WP4-T11：重试/取消/超时

> **SP：2 | 依赖：T10 | 主笔：工程师 B**

### 执行步骤

1. **重试**：`retry(job_id)` → 新 Attempt → QUEUED
2. **取消**：`cancel(job_id)` → CANCELLING → `ExecutionBackend.cancel()` → CANCELLED
3. **超时**：定时检查 `RUNNING + duration > timeout` → TIMED_OUT

---

## WP4-T12：Server 重启恢复

> **SP：2 | 依赖：T10 | 主笔：工程师 B**

### 执行步骤

1. **启动扫描**：`SELECT * FROM job_runs WHERE status IN (QUEUED, RUNNING)` → 查 Ray 状态
2. **Ray 中存在** → 恢复状态
3. **Ray 中不存在** → 标记 LOST
4. **CANCELLING** → 查 Ray → CANCELLED

### 评审标准

- [ ] 重启后 Job 状态可恢复
- [ ] Ray 丢失标记 LOST

---

## WP4-T13：日志归档

> **SP：2 | 依赖：T03 | 主笔：工程师 B**

### 执行步骤

1. Job 完成 → `ExecutionBackend.get_logs()` → 写 S3 → 创建 `job_artifacts`（type=log）
2. Result URI 注册到 `job_artifacts`

---

## WP4-T14：Artifact 资产化

> **SP：2 | 依赖：T13 | 主笔：工程师 B**

### 执行步骤

1. **`assetize(artifact_id) → Asset`**：Artifact → 注册为 Knowledge 或 Memory
2. 创建 Asset + Binding(JOB_ARTIFACT)
3. 血缘记录：`derived_from: job_run`

### 评审标准

- [ ] Artifact 可注册为 Knowledge/Memory
- [ ] 血缘关联

---

## WP4-T15：可复现性记录

> **SP：2 | 依赖：T07 | 主笔：工程师 B**

### 固定记录

```
Skill 版本 + 包 Checksum + 输入资产版本 + 参数 + 环境/依赖版本
+ 模型 ID + Deployment + Revision + 配置 Revision + Secret 引用版本
```

### 评审标准

- [ ] 全部复现信息固定在 Job Run
- [ ] Secret 引用版本记录（不记录明文）

---

## WP4 日程计划

| 周 | 任务 | 产出 |
|----|------|------|
| W12 | T01-T03 | Job/Attempt/Artifact schema + 状态机 |
| W13 | T04-T07 | JobService + 资格 + 配额 + 绑定 |
| W14 | T08-T10 | ExecutionBackend + Ray + 状态同步 |
| W15 | T11-T15 | 恢复 + 日志 + 资产化 + 可复现 + **M3** |

### 门禁 M3 评审清单（WP4 部分）

- [ ] Skill/JobRun/Attempt/Artifact 边界清晰
- [ ] 只执行 PUBLISHED Skill
- [ ] 任意 eval 入口已移除
- [ ] Job 不获控制面全部环境变量
- [ ] Secret 最小注入
- [ ] 重试/取消/超时/LOST 全部支持
- [ ] Server 重启后 Job 状态可恢复
- [ ] Ray 状态异常被 Reconciler 发现
- [ ] Artifact 可资产化

---

<a id="wp5"></a>
# WP5：ModelServing 管理

> **阶段：D（第 12-15 周，与 WP4 并行）**  
> **估算：28 SP**  
> **依赖：WP1, WP2（M1 通过）**  
> **目标：将模型服务纳入统一 Control Plane 管理**

---

## WP5.0 概述

### 任务清单

| 子流 | Task ID | 任务 | SP | 依赖 |
|------|---------|------|----|------|
| S1 模型领域 | WP5-T01 | Model Definition schema | 2 | WP2 |
| | WP5-T02 | Model Deployment schema | 2 | T01 |
| | WP5-T03 | Model Profile / Alias | 2 | T01 |
| | WP5-T04 | Model Route | 2 | T03 |
| | WP5-T05 | Embedding Space | 2 | T01 |
| S2 配置运行 | WP5-T06 | 模型管理 API | 3 | T04 |
| | WP5-T07 | Secret Ref 替换 | 1 | T02 |
| | WP5-T08 | models.yaml 导入 | 2 | T06 |
| | WP5-T09 | 配置加载 | 2 | T06 |
| | WP5-T10 | 配置生效模式 | 2 | T09 |
| S3 Job 绑定 | WP5-T11 | Job 模型绑定解析 | 2 | T04 |
| | WP5-T12 | 模型管理 Operation | 2 | T10 |
| | WP5-T13 | 实例健康上报 | 1 | T09 |
| **合计** | | | **28** | |

---

## WP5-T01：Model Definition schema

> **SP：2 | 依赖：WP2 | 主笔：工程师 B**

### `model_definitions` 表

```sql
CREATE TABLE model_definitions (
    model_id         TEXT PRIMARY KEY,      -- mdl_{ulid}
    name             TEXT NOT NULL,
    model_type       TEXT NOT NULL,         -- llm|embedding|asr|multimodal
    capabilities     JSONB NOT NULL,        -- ["chat","vision"]
    provider_family  TEXT NOT NULL,         -- openai|anthropic|funasr|fastembed
    context_length   INTEGER,
    embedding_dim    INTEGER,
    modalities       JSONB DEFAULT '["text"]',
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## WP5-T02：Model Deployment schema

> **SP：2 | 依赖：T01 | 主笔：工程师 B**

### `model_deployments` 表

```sql
CREATE TABLE model_deployments (
    deployment_id    TEXT PRIMARY KEY,      -- dpl_{ulid}
    model_id         TEXT NOT NULL REFERENCES model_definitions(model_id),
    provider         TEXT NOT NULL,
    endpoint         TEXT NOT NULL,
    secret_ref       TEXT NOT NULL,         -- secret://{scope}/{name}
    status           TEXT NOT NULL DEFAULT 'enabled',  -- enabled|disabled
    priority         INTEGER NOT NULL DEFAULT 100,
    timeout_ms       INTEGER DEFAULT 30000,
    max_concurrency  INTEGER DEFAULT 10,
    health_status    TEXT NOT NULL DEFAULT 'unknown',
    config_revision_id TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 评审标准

- [ ] API Key → Secret Ref，不保存明文

---

## WP5-T03：Model Profile / Alias

> **SP：2 | 依赖：T01 | 主笔：工程师 B**

### `model_profiles` 表

```sql
CREATE TABLE model_profiles (
    profile_id       TEXT PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,  -- meeting-asr|knowledge-embedding|lake-chat-default
    description      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## WP5-T04：Model Route

> **SP：2 | 依赖：T03 | 主笔：工程师 B**

### `model_routes` 表

```sql
CREATE TABLE model_routes (
    route_id         TEXT PRIMARY KEY,
    profile_name     TEXT NOT NULL,
    deployment_id    TEXT NOT NULL REFERENCES model_deployments(deployment_id),
    priority         INTEGER NOT NULL DEFAULT 100,
    is_fallback      BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id        TEXT,                  -- NULL = 全局，非 NULL = 租户覆盖
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## WP5-T05：Embedding Space

> **SP：2 | 依赖：T01 | 主笔：工程师 B**

### `embedding_spaces` 表

```sql
CREATE TABLE embedding_spaces (
    space_id         TEXT PRIMARY KEY,
    model_id         TEXT NOT NULL REFERENCES model_definitions(model_id),
    model_revision   TEXT NOT NULL,
    dimension        INTEGER NOT NULL,
    normalize        BOOLEAN NOT NULL DEFAULT TRUE,
    distance_metric  TEXT NOT NULL DEFAULT 'cosine',
    index_version    INTEGER NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 评审标准

- [ ] 不兼容模型不可 Fallback

---

## WP5-T06：Control Plane 模型管理 API

> **SP：3 | 依赖：T04 | 主笔：工程师 B**

### 交付物

- `src/lakemind_server/services/model_management_service.py`
- `src/lakemind_server/api/models.py` — 8 个 REST 端点

### 接口

```
create_model(definition) → ModelDefinition
create_deployment(model_id, config) → ModelDeployment
create_profile(name, route_config) → ModelProfile
resolve_profile(profile_name, tenant?) → ResolvedRoute
list_models() / list_deployments()
enable_deployment(id) / disable_deployment(id) → Operation
```

### 评审标准

- [ ] CRUD 全部产生 Revision
- [ ] 全部管理动作可审计

---

## WP5-T07：Secret Ref 替换

> **SP：1 | 依赖：T02 | 主笔：工程师 B**

### 执行步骤

1. Deployment 中 API Key → `secret_ref`
2. `resolve_profile()` 时通过 `SecretService.resolve()` 获取实际密钥
3. 不保存明文

---

## WP5-T08：models.yaml 导入

> **SP：2 | 依赖：T06 | 主笔：工程师 B**

### 执行步骤

1. **首次部署 / 开发环境**：解析 `models.yaml` → 导入 PG（model_definitions + deployments + profiles + routes）
2. **导入后**：YAML 不覆盖动态配置
3. **Bootstrap 标记**：导入的记录标记 `source = bootstrap`

---

## WP5-T09：ModelServing 配置加载

> **SP：2 | 依赖：T06 | 主笔：工程师 B**

### 执行步骤

1. **ModelServing 启动** → 拉取 Desired Revision → 加载配置
2. **上报 Active Revision** → Instance Registry
3. **配置包含**：模型定义 + Deployment + Profile + Route + Embedding Space

### 评审标准

- [ ] ModelServing 加载 Desired Revision
- [ ] 上报 Active Revision

---

## WP5-T10：配置生效模式

> **SP：2 | 依赖：T09 | 主笔：工程师 B**

### 3 种模式

- `HOT_RELOAD`：路由/优先级/外部 Endpoint/超时 → Valkey pub/sub 通知
- `MODEL_RELOAD`：本地模型/Batch/模型参数 → 产生 reload 事件
- `SERVICE_RESTART`：设备/缓存/Runtime → 标记 restart_required

---

## WP5-T11：Job 模型绑定解析

> **SP：2 | 依赖：T04 | 主笔：工程师 B**

### 执行步骤

1. Skill 声明 `model_profiles: ["meeting-asr"]`
2. `resolve_profile("meeting-asr", tenant_id)` → `{model_id, deployment_id, revision, embedding_space_id}`
3. 固定到 `job_runs.model_binding`
4. 后续默认模型切换不影响历史 Job

### 评审标准

- [ ] Job 记录实际模型和 Deployment
- [ ] 后续切换不影响历史

---

## WP5-T12：模型管理 Operation

> **SP：2 | 依赖：T10 | 主笔：工程师 B**

### 执行步骤

1. 切换默认模型 / 禁用 Deployment / Reload → Operation Service
2. 校验目标 Deployment 健康 + Embedding 兼容性
3. 创建 Revision → 下发 → 验证 → 激活 → 审计

### 评审标准

- [ ] 高影响动作通过 Operation Service
- [ ] Embedding 兼容性检查

---

## WP5-T13：实例健康上报

> **SP：1 | 依赖：T09 | 主笔：工程师 B**

### 执行步骤

1. ModelServing 实例 → Instance Registry：健康 / 延迟 / 错误率 / 当前 Revision
2. 健康检查失败 → `model.deployment_unhealthy` 事件

---

## WP5 日程计划

| 周 | 任务 | 产出 |
|----|------|------|
| W12 | T01-T05 | 5 张模型领域表 |
| W13 | T06-T08 | 管理 API + Secret Ref + YAML 导入 |
| W14 | T09-T11 | 配置加载 + 生效模式 + Job 绑定 |
| W15 | T12-T13 | 模型 Operation + 健康上报 + **M3** |

### 门禁 M3 评审清单（WP5 部分）

- [ ] Model Definition / Deployment / Profile / Route / Embedding Space 概念分离
- [ ] Provider 密钥使用 Secret Ref
- [ ] ModelServing 加载 Desired Revision 并上报 Active Revision
- [ ] Job 记录实际模型和 Deployment
- [ ] 不兼容 Embedding 模型不能写入同一向量空间
- [ ] 模型管理动作可审计

---

<a id="wp6"></a>
# WP6：LakeMind Control Center

> **阶段：E（第 16-18 周）**  
> **估算：34 SP**  
> **依赖：WP2, WP3, WP4, WP5**  
> **目标：将 LakeMindMonitor 演进为统一全局管理入口**

---

## WP6.0 概述

### 任务清单

| 子流 | Task ID | 任务 | SP | 依赖 |
|------|---------|------|----|------|
| S1 基础设施 | WP6-T01 | 目录合并 | 2 | WP2 |
| | WP6-T02 | 管理员认证 | 3 | T01 |
| | WP6-T03 | BFF 架构 | 2 | T02 |
| | WP6-T04 | 页面权限控制 | 1 | T02 |
| S2 10 页面 | WP6-T05 | Overview 页 | 2 | T03 |
| | WP6-T06 | Assets 页 | 3 | T03 |
| | WP6-T07 | Jobs 页 | 3 | T03 |
| | WP6-T08 | Model Serving 页 | 3 | T03 |
| | WP6-T09 | Services 页 | 2 | T03 |
| | WP6-T10 | Configuration 页 | 2 | T03 |
| | WP6-T11 | Security 页 | 2 | T03 |
| | WP6-T12 | Operations 页 | 2 | T03 |
| | WP6-T13 | Audit 页 | 1 | T03 |
| | WP6-T14 | Steward 页 | 2 | T03 |
| S3 集成 | WP6-T15 | 写操作 → Operation | 2 | T12 |
| | WP6-T16 | 审计集成 | 1 | T15 |
| **合计** | | | **34** | |

### v0.1.0 基线

| 维度 | v0.1.0 | v0.2.0 |
|------|--------|--------|
| 目录 | `LakeMindMonitor/` + `LakeMindSteward/` | `LakeMindControlCenter/`（前端 + BFF + Steward） |
| 认证 | 静态平台 Token | 管理员身份 + 会话 + 角色 |
| 架构 | 前端直连 MCP | BFF → Control Plane API |
| 页面 | Steward 对话 + 基本监控 | 10 个管理页面 |

---

## WP6-T01：目录合并

> **SP：2 | 依赖：WP2 | 主笔：前端工程师**

### 执行步骤

1. **创建 `LakeMindControlCenter/` 目录**：
   - `frontend/` — React/Vue 前端（从 `LakeMindMonitor/frontend/` 迁移）
   - `bff/` — BFF 后端（Express/FastAPI）
   - `steward/` — Steward 后端（从 `LakeMindSteward/` 迁移）
2. **迁移代码**：保持 git 历史
3. **Docker Compose 更新**：`LakeMindControlCenter` 替代 `LakeMindMonitor` + `LakeMindSteward`
4. **端口**：Control Center 前端 3000，BFF 3001，Steward 3002

---

## WP6-T02：管理员认证

> **SP：3 | 依赖：T01 | 主笔：前端工程师**

### 执行步骤

1. **管理员身份**：`principals` 表中 `principal_type = 'user'` + `role = 'platform_admin'` 或 `'tenant_admin'`
2. **会话管理**：BFF 维护管理员会话（cookie 或 JWT），不使用共享静态 Token
3. **BFF Service Identity**：BFF 使用独立 Service Account Token 与 Control Plane 通信
4. **登录页面**：用户名/密码 → BFF → AuthorizationService → 创建会话
5. **移除静态 Token**：删除 v0.1.0 的 `LAKEIND_MONITOR_TOKEN`

### 评审标准

- [ ] 管理员有身份和角色
- [ ] 不使用共享静态 Token
- [ ] BFF 使用 Service Identity

---

## WP6-T03：BFF 架构

> **SP：2 | 依赖：T02 | 主笔：前端工程师**

### 执行步骤

1. **BFF → Control Plane API**：所有数据通过 BFF 调用 `/api/v1/*` 获取
2. **不直连** PG / S3 / Ray / ModelServing
3. **聚合 API**：BFF 可聚合多个 Control Plane API 结果（如 Overview 页需要 health + assets + jobs + outbox 数据）
4. **WebSocket**：实时更新（Job 状态、Operation 状态）通过 BFF WebSocket 转发

### 评审标准

- [ ] BFF 不直连底层引擎
- [ ] 所有数据通过 Control Plane API

---

## WP6-T04：页面权限控制

> **SP：1 | 依赖：T02 | 主笔：前端工程师**

### 执行步骤

1. **路由守卫**：根据管理员角色控制页面可见性
2. **操作权限**：`platform_admin` 可见全部；`tenant_admin` 不可见 Security 页全局配置
3. **前端权限检查**：BFF 返回用户角色 → 前端路由过滤

---

## WP6-T05~T14：10 个页面

### T05 Overview 页（SP：2）

- 核心服务健康 / 资产总量 / Job 趋势 / Outbox 积压 / Reconciler 异常 / 安全事件 / 配置收敛
- BFF 聚合：`GET /api/v1/instances` + `GET /api/v1/assets` + `GET /api/v1/jobs` + `GET /api/v1/audit`

### T06 Assets 页（SP：3）

- Knowledge/Skill/Memory 分类 / 状态 / 版本 / Binding / 血缘
- DEGRADED + FAILED 高亮
- 触发 Operation：reindex / delete
- BFF：`GET /api/v1/assets` + `GET /api/v1/assets/{id}/bindings` + `GET /api/v1/assets/{id}/lineage`

### T07 Jobs 页（SP：3）

- Job Run + Attempt / Skill 绑定 / 状态 / 日志 / 结果
- 重试 / 取消 / 标记 LOST
- BFF：`GET /api/v1/jobs` + `POST /api/v1/jobs/{id}/retry` + `POST /api/v1/jobs/{id}/cancel`

### T08 Model Serving 页（SP：3）

- Models / Deployments / Routing / Runtime 四子页（§11.5）
- 启用/禁用/Reload → Operation
- BFF：`GET /api/v1/models` + deployments + profiles

### T09 Services 页（SP：2）

- 实例列表 / 版本 / 心跳 / Desired vs Active Revision / 健康
- BFF：`GET /api/v1/instances`

### T10 Configuration 页（SP：2）

- 平台/租户/Agent 配置 / 功能开关 / Schema / Revision / 变更历史 / 回滚
- BFF：`GET /api/v1/configuration` + `PUT` + `POST activate/rollback`

### T11 Security 页（SP：2）

- 用户/Agent/Service Account/租户/角色/Token/Secret 元数据/Skill 可信级别/策略/拒绝事件
- BFF：`GET /api/v1/security/*`

### T12 Operations 页（SP：2）

- Operation 列表 / 状态 / 审批 / 执行结果 / 审计
- BFF：`GET /api/v1/operations` + `POST approve`

### T13 Audit 页（SP：1）

- 审计事件查询 / 过滤 / 导出
- BFF：`GET /api/v1/audit` + `GET /api/v1/audit/export`

### T14 Steward 页（SP：2）

- Steward 对话 / 巡检结果 / 治理建议 / 待批准 Operation / 自动策略
- BFF → Steward 后端

---

## WP6-T15：写操作 → Operation Service

> **SP：2 | 依赖：T12 | 主笔：前端工程师**

### 执行步骤

1. **所有页面写操作**统一进入 Operation Service
2. **高风险操作**：二次确认弹窗 → 创建 Operation → 等待审批
3. **低风险操作**：直接执行 → Operation 自动 RUNNING → SUCCEEDED

### 评审标准

- [ ] 所有写操作通过 Operation Service
- [ ] 高风险有二次确认

---

## WP6-T16：审计集成

> **SP：1 | 依赖：T15 | 主笔：前端工程师**

### 执行步骤

1. 所有管理操作写入 Audit（BFF 自动调用 `audit_service.record()`）
2. Audit 页可查询全部管理操作

---

## WP6 日程计划

| 周 | 任务 | 产出 |
|----|------|------|
| W16 | T01-T04 | 目录合并 + 管理员认证 + BFF + 权限 |
| W17 | T05-T14 | 10 个页面 |
| W18 | T15-T16 + WP7 | Operation 集成 + 审计 + Steward + **M4** |

### 门禁 M4 评审清单（WP6 部分）

- [ ] 10 个页面全部可用
- [ ] 管理员有身份和角色，不使用共享 Token
- [ ] 所有写操作通过 Operation Service
- [ ] BFF 不直连底层引擎
- [ ] 高风险操作有二次确认/审批
- [ ] 管理操作全部有审计

---

<a id="wp7"></a>
# WP7：Steward 治理

> **阶段：E（第 18 周，与 WP6 后期并行）**  
> **估算：16 SP**  
> **依赖：WP2, WP6**  
> **目标：将 Steward 从管理对话工具升级为受控治理 Agent**

---

## WP7.0 概述

### 任务清单

| Task ID | 任务 | SP | 依赖 |
|---------|------|----|------|
| WP7-T01 | 独立 Service Identity | 2 | WP2 |
| WP7-T02 | Level 1 观察 | 3 | T01 |
| WP7-T03 | Level 2 低风险自动治理 | 3 | T02 |
| WP7-T04 | Level 3 高风险审批 | 2 | T03 |
| WP7-T05 | 治理策略配置 | 2 | T03 |
| WP7-T06 | 结果审计 | 1 | T04 |
| WP7-T07 | Control Center 集成 | 2 | WP6 |
| WP7-T08 | 不绕过审批 | 1 | T04 |
| **合计** | | **16** | |

---

## WP7-T01：独立 Service Identity

> **SP：2 | 依赖：WP2 | 主笔：工程师 C**

### 执行步骤

1. **Steward Service Account**：`principals` 表创建 `principal_type = 'steward'`
2. **Token**：签发独立 Token，绑定 `steward` 角色
3. **权限范围**：非超级管理员，只有 `*:read` + `operation:request` + 特定低风险动作
4. **不拥有控制面主密钥**

### 评审标准

- [ ] Steward 使用独立 Service Identity
- [ ] 非超级管理员

---

## WP7-T02：Level 1 观察

> **SP：3 | 依赖：T01 | 主笔：工程师 C**

### 巡检项目

- 服务健康（Instance Registry）
- DEGRADED 资产
- Lost Job
- Outbox 积压
- Binding 偏差（Reconciler）
- 配置偏差（Desired vs Active）

### 执行步骤

1. **定时巡检**：每 5 分钟执行一次
2. **诊断报告**：汇总异常 + 建议操作
3. **LangGraph 工作流**：巡检 → 分析 → 生成报告 → 写入 Steward 页面

### 评审标准

- [ ] 6 类巡检全部实现
- [ ] 诊断报告可查看

---

## WP7-T03：Level 2 低风险自动治理

> **SP：3 | 依赖：T02 | 主笔：工程师 C**

### 自动操作（策略授权范围内）

- 重试 Embedding
- 重建索引
- 同步 Ray 状态
- 运行 Reconciler
- 清理临时文件
- 执行已批准 Reload

### 执行步骤

1. **策略检查**：从 ConfigurationService 读 `steward.auto_action_level`
2. **`observe` 模式**：只报告不执行
3. **`low_risk` 模式**：自动执行上述操作
4. **每个自动操作**：创建 Operation（LOW 风险）→ 自动审批 → 执行 → 审计

### 评审标准

- [ ] 自动操作在策略范围内
- [ ] 每个操作有 Operation + 审计

---

## WP7-T04：Level 3 高风险审批

> **SP：2 | 依赖：T03 | 主笔：工程师 C**

### 高风险操作（创建待批准 Operation）

- 删除资产 / 撤销 Token / 修改安全策略 / 禁用模型 / 停止服务 / 取消关键 Job / 删除 Skill / 数据迁移 / 轮换平台 Secret

### 执行步骤

1. Steward 识别高风险需求 → 创建 Operation（HIGH 风险）→ `APPROVAL_REQUIRED`
2. Control Center Steward 页显示待批准 Operation
3. 管理员审批 → Operation 执行

### 评审标准

- [ ] 高风险操作必须审批
- [ ] Steward 不直接执行

---

## WP7-T05：治理策略配置

> **SP：2 | 依赖：T03 | 主笔：工程师 C**

### 执行步骤

1. **策略项**：`auto_action_level` / `allowed_actions` / `risk_threshold`
2. **Configuration Service 管理**：通过 Control Center Configuration 页配置
3. **策略变更产生 Revision + 审计**

---

## WP7-T06：结果审计

> **SP：1 | 依赖：T04 | 主笔：工程师 C**

### 执行步骤

1. 所有 Steward 动作写入 `audit_log`（`steward.suggestion` / `steward.auto_action`）
2. 关联 Operation ID

---

## WP7-T07：Control Center 集成

> **SP：2 | 依赖：WP6 | 主笔：工程师 C**

### 执行步骤

1. Steward 页面展示：对话 / 巡检结果 / 建议 / 待批准 Operation / 自动策略
2. 对话通过 BFF → Steward 后端
3. 巡检结果从 Steward 后端获取

---

## WP7-T08：不绕过审批

> **SP：1 | 依赖：T04 | 主笔：工程师 C**

### 评审标准

- [ ] LLM 判断不绕过 Operation 审批
- [ ] 不以系统提示词代替权限控制

---

## WP7 日程计划

| 周 | 任务 | 产出 |
|----|------|------|
| W18 | T01-T08 | 全部（与 WP6 后期并行） |

### 门禁 M4 评审清单（WP7 部分）

- [ ] Steward 使用独立 Service Identity，非超级管理员
- [ ] 三级动作模型清晰且可配置
- [ ] 高风险操作必须审批
- [ ] Steward 不直连数据库和引擎
- [ ] 所有动作有审计

---

<a id="wp8"></a>
# WP8：Meeting Agent Golden Path

> **阶段：F（第 19-20 周）**  
> **估算：18 SP**  
> **依赖：WP3, WP4, WP5, WP6**  
> **目标：以真实参考应用验证全部核心能力**

---

## WP8.0 概述

### 任务清单

| Task ID | 任务 | SP | 依赖 |
|---------|------|----|------|
| WP8-T01 | Meeting Skill 发布 | 2 | WP3, WP4 |
| WP8-T02 | 标准链路实现 | 4 | T01 |
| WP8-T03 | 安全验收场景 | 3 | T02 |
| WP8-T04 | 一致性验收场景 | 3 | T02 |
| WP8-T05 | 恢复验收场景 | 3 | T02 |
| WP8-T06 | 完整删除验收 | 1 | T02 |
| WP8-T07 | Control Center 可观察 | 2 | T02 |
| **合计** | | **18** | |

---

## WP8-T01：Meeting Skill 发布

> **SP：2 | 主笔：工程师 C**

### 执行步骤

1. **ASR Skill**：Manifest + 代码包 → register → validate → publish（PUBLISHED）
   - `model_profiles: ["meeting-asr"]`
   - `resource_needs: {cpu: 2, memory_mb: 4096, timeout: 1800}`
2. **摘要 Skill**：`model_profiles: ["meeting-summary"]`
3. **知识提取 Skill**：`model_profiles: ["knowledge-embedding"]`

### 评审标准

- [ ] 3 个 Skill 全部 PUBLISHED
- [ ] Manifest 完整

---

## WP8-T02：标准链路实现

> **SP：4 | 主笔：工程师 C**

### 14 步标准链路（§14.2）

```
1. 上传会议音频
2. 创建原始输入资产
3. 提交 ASR Job
4. Job 解析 meeting-asr Profile
5. 生成转写 Artifact
6. 提交摘要 + 知识提取 Job
7. 生成 Knowledge
8. Chunk + Embedding Binding
9. 提取 Memory
10. Knowledge + Memory 检索
11. 血缘展示
12. 失败重试
13. 完整删除
14. Control Center 观察
```

### 交付物

- `tests/e2e/test_meeting_golden_path.py`

### 评审标准

- [ ] 14 步全部跑通
- [ ] 端到端自动化测试

---

## WP8-T03：安全验收场景

> **SP：3 | 主笔：工程师 C + 安全顾问**

### 6 个场景（§14.3）

| 场景 | 期望 |
|------|------|
| 跨租户隔离 | Tenant A 无法读 Tenant B 会议 |
| 伪造 Header | 无法改变身份 |
| 无权限 Skill | 无法提交 Job |
| Secret 最小注入 | ASR Job 只获声明 Secret |
| 撤销 Skill | 不能运行 |
| Ray Dashboard 不暴露 | Agent 无法直连 |

### 交付物

- `tests/e2e/test_meeting_security.py`

---

## WP8-T04：一致性验收场景

> **SP：3 | 主笔：工程师 C**

### 7 个场景（§14.4）

| 场景 | 期望 |
|------|------|
| Embedding 失败 | DEGRADED |
| Ray 提交失败 | Job 记录失败 |
| 请求重试 | 不重复 |
| Lance 丢失 | 可重建 |
| 删除失败 | 保持 DELETING |
| ModelServing 不可用 | 明确失败 |
| 配置未同步 | 可发现 |

### 交付物

- `tests/e2e/test_meeting_consistency.py`

---

## WP8-T05：恢复验收场景

> **SP：3 | 主笔：工程师 C**

### 6 个场景（§14.5）

| 场景 | 期望 |
|------|------|
| Server 重启 | Job/资产状态可恢复 |
| Ray Job 丢失 | 标记 LOST |
| Outbox 重启 | 不重复 |
| Reconciler 修复 | Binding 修复 |
| ModelServing 重启 | 重新加载 Desired |
| Steward 发现异常 | 创建治理 Operation |

### 交付物

- `tests/e2e/test_meeting_recovery.py`

---

## WP8-T06：完整删除验收

> **SP：1 | 主笔：工程师 C**

### 执行步骤

1. Meeting 资产删除 → 全部 Binding 清理 → 血缘清理 → DELETED
2. 验证 S3 / Lance / PG 全部清理

---

## WP8-T07：Control Center 可观察

> **SP：2 | 主笔：工程师 C**

### 执行步骤

1. Meeting 全过程在 Control Center Assets/Jobs/Audit 页面可观察
2. 血缘图可视化
3. Operation 状态可追踪

---

## WP8 日程计划

| 周 | 任务 | 产出 |
|----|------|------|
| W19 | T01-T05 | Skill + 标准链路 + 安全/一致性/恢复验收 |
| W20 | T06-T07 | 完整删除 + Control Center 观察 + **M5** |

### 门禁 M5 评审清单（WP8 部分）

- [ ] Meeting Agent 14 步全部跑通
- [ ] 安全 6 场景通过
- [ ] 一致性 7 场景通过
- [ ] 恢复 6 场景通过
- [ ] 完整删除验证通过
- [ ] Control Center 可观察全过程

---

<a id="wp9"></a>
# WP9：工程与发布

> **阶段：F（贯穿全周期，集中收尾于第 19-20 周）**  
> **估算：20 SP**  
> **依赖：所有 WP**  
> **目标：使 v0.2.0 可重复部署、迁移和验证**

---

## WP9.0 概述

### 任务清单

| Task ID | 任务 | SP | 依赖 |
|---------|------|----|------|
| WP9-T01 | 数据库迁移脚本 | 2 | WP2 |
| WP9-T02 | Bootstrap 初始化 | 2 | WP2 |
| WP9-T03 | 默认密钥清理 | 1 | WP2 |
| WP9-T04 | v0.1 数据导入工具 | 2 | T01 |
| WP9-T05 | 测试体系 | 3 | All |
| WP9-T06 | 备份与恢复说明 | 1 | T01 |
| WP9-T07 | 发布文档 | 3 | All |
| WP9-T08 | Docker Compose 更新 | 2 | All |
| WP9-T09 | 版本标记 | 1 | All |
| WP9-T10 | 文档体系更新 | 3 | All |
| **合计** | | **20** | |

---

## WP9-T01：数据库迁移脚本

> **SP：2 | 主笔：DevOps**

### 交付物

- `migrations/versions/` 全量迁移脚本（001-010+）
- 每个迁移含 `up` / `down` / `verify`

### 评审标准

- [ ] v0.1.0 → v0.2.0 全量迁移成功
- [ ] 回滚脚本可用
- [ ] `verify.sql` 校验数据完整性

---

## WP9-T02：Bootstrap 初始化

> **SP：2 | 主笔：DevOps**

### 执行步骤

1. **首次部署向导**：初始化管理员 / 主密钥 / 默认配置 / 模型导入
2. **`scripts/bootstrap.py`**：
   - 创建 `platform_admin` Principal + Token
   - 生成主密钥提示（`LAKEMIND_MASTER_KEY`）
   - 导入默认配置 Revision
   - 导入 `models.yaml`
3. **交互式**：提示输入管理员用户名/密码

---

## WP9-T03：默认密钥清理

> **SP：1 | 主笔：DevOps**

### 执行步骤

1. 移除或强制更改：默认密码 / 默认 Token / 默认 API Key
2. Bootstrap 检查：如果检测到默认密钥 → 拒绝启动

### 评审标准

- [ ] 默认密钥全部移除或强制更改
- [ ] 检测到默认密钥时拒绝启动

---

## WP9-T04：v0.1 数据导入工具

> **SP：2 | 主笔：DevOps**

### 交付物

- `scripts/migrate_v01_to_v02.py`

### v0.1 → v0.2 数据映射

| v0.1 数据 | v0.2 目标 | 转换 |
|-----------|-----------|------|
| S3 知识文件 | `assets`(knowledge) + `asset_bindings` | 扫描 S3 → 创建资产 → Binding |
| Lance 向量表 | `asset_bindings`(VECTOR_INDEX) | 关联到已有资产 |
| PG memory_records | `assets`(memory) + `memory_meta` | 逐行迁移 |
| models.yaml | `model_definitions` + deployments + profiles + routes | YAML 解析导入 |
| .env / 静态 Token | `config_values` + `tokens` + `secrets` | 环境变量 → Config / Token |

### 评审标准

- [ ] v0.1.0 数据完整迁移
- [ ] 采样比对通过

---

## WP9-T05：测试体系

> **SP：3 | 主笔：DevOps + 全员**

### 交付物

- `scripts/verify_v0.2.0.py` — L0-L9 全分层测试

### 测试层级

| 层级 | 范围 | 覆盖 |
|------|------|------|
| L0 单元 | Service / 状态机 | 每个 Service 核心方法 |
| L1 契约 | API v1 / MCP | 所有端点契约 |
| L2 集成 | Service × PG × S3 × Lance | 资产 CRUD + Binding |
| L3 安全 | 认证 / 授权 / 隔离 | §18.2 |
| L4 一致性 | Outbox / Reconciler / 幂等 | §18.7 |
| L5 Job | 提交 / 执行 / 重试 / 恢复 | §18.4 |
| L6 Model | 模型管理 / 路由 / Revision | §18.5 |
| L7 端到端 | Meeting Golden Path | §14 |
| L8 恢复 | 重启 / 丢失 / Reconciler | §14.5 |
| L9 迁移 | v0.1 → v0.2 | 数据完整性 |

### 评审标准

- [ ] `scripts/verify_v0.2.0.py` L0-L9 全 PASS

---

## WP9-T06：备份与恢复说明

> **SP：1 | 主笔：DevOps**

### 交付物

- `docs/migration/backup-restore.md`

### 内容

- PG dump / S3 同步 / 配置导出
- 恢复步骤

---

## WP9-T07：发布文档

> **SP：3 | 主笔：全员**

### 交付物

```
docs/migration/upgrade-guide.md          # 升级指南
docs/security/deployment-guide.md        # 安全部署指南
docs/control-center/user-guide.md        # Control Center 使用说明
docs/skill-job/skill-publish-guide.md    # Skill 发布说明
docs/skill-job/job-execution-guide.md    # Job 执行说明
docs/model-serving/config-guide.md       # ModelServing 配置说明
docs/meeting-agent/golden-path.md        # Meeting Agent Golden Path
```

---

## WP9-T08：Docker Compose 更新

> **SP：2 | 主笔：DevOps**

### 执行步骤

1. **单节点完整部署** compose：Server + 3 MCP + Control Center + Steward + ModelServing + Ray + PG + SeaweedFS + Valkey
2. **网络隔离**：`internal` + `external`
3. **健康检查**：每个服务配置 healthcheck
4. **启动顺序**：PG → SeaweedFS → Valkey → Ray → Server → MCP → ModelServing → Control Center

### 评审标准

- [ ] 单节点部署可在一台主机完成
- [ ] 网络隔离正确
- [ ] 健康检查全部通过

---

## WP9-T09：版本标记

> **SP：1 | 主笔：DevOps**

### 执行步骤

1. `VERSION` → `0.2.0`
2. `CHANGELOG.md` 更新
3. Git tag `v0.2.0`

---

## WP9-T10：文档体系更新

> **SP：3 | 主笔：全员**

### 更新文件

```
AGENTS.md              # v0.2.0 包结构 + 定位
.agent/DESIGN.md       # 四平面 + Application Service + 资产 + Job + Model
.agent/SPEC.md         # 代码约定 + Docker + 迁移 + 验证
.agent/STATE.md        # v0.2.0 进度
README.md              # 定位 + 快速开始
README_agent.md        # Agent 接入指南
docs/api-reference/    # API v1 OpenAPI 渲染
docs/mcp-tools/        # MCP 工具说明
```

---

## WP9 日程计划

| 周 | 任务 | 产出 |
|----|------|------|
| W19 | T01-T04 | 迁移脚本 + Bootstrap + 密钥清理 + 数据导入 |
| W20 | T05-T10 | 测试体系 + 备份 + 文档 + Docker + 版本 + 文档更新 + **M5** |

### 门禁 M5 评审清单（WP9 部分）

- [ ] 全新单节点部署可在一台主机完成
- [ ] v0.1.0 数据可迁移
- [ ] 默认密钥全部清理
- [ ] `scripts/verify_v0.2.0.py` L0-L9 全 PASS
- [ ] 全部发布文档就绪
- [ ] VERSION = 0.2.0 + CHANGELOG + Git tag

---

<a id="cross-wp"></a>
# 跨 WP 综合管理

---

## 综合日程总览

```
阶段 B (W3-W6)   WP2 Control Plane          ████████░░  48 SP
阶段 C (W7-W11)  WP3 Asset Runtime          ██████████  52 SP
阶段 D (W12-W15) WP4 Job || WP5 Model       ████████░░  36+28 SP
阶段 E (W16-W18) WP6 Control Center + WP7   ██████░░░░  34+16 SP
阶段 F (W19-W20) WP8 Meeting + WP9 Release  ████░░░░░░  18+20 SP
                                            ─────────────────────
                                            总计 252 SP (18 周)
```

## 综合里程碑

| 里程碑 | 时间 | 标志 | 门禁检查 |
|--------|------|------|----------|
| M1 | W6 末 | Control Plane 可用 | Token + RBAC + Config + Audit + 隔离 |
| M2 | W11 末 | Asset Runtime 可用 | CRUD + Binding + 状态机 + Reconciler |
| M3 | W15 末 | Job + Model 可用 | Job 全链路 + 模型管理 |
| M4 | W18 末 | Control Center 可用 | 10 页面 + Steward 三级 |
| M5 | W20 末 | v0.2.0 发布 | Golden Pass + L0-L9 + 文档 |

## 综合依赖关系

```
WP1 ✅ → WP2 → WP3 → WP4 → WP8 → WP9
                ↘     ↗
                  WP5
                ↘
                  WP6 → WP7
```

并行窗口：
- WP4 ∥ WP5（阶段 D）
- WP7 ∥ WP6 后期（阶段 E）
- WP9 贯穿，集中收尾于阶段 F

## 综合数据库迁移顺序

```
001_initial_schema.py        # v0.1.0 基线（WP2-T01）
002_control_plane.py         # 12 Control Plane 表（WP2-T02）
003_asset_core.py            # assets 表（WP3-T01）
004_asset_binding.py         # asset_bindings + reconciler_state（WP3-T02）
005_asset_lineage.py         # asset_lineage（WP3-T06）
006_knowledge_meta.py        # knowledge_meta（WP3-T07）
007_skill_meta.py            # skill_meta（WP3-T12）
008_memory_meta.py           # memory_meta（WP3-T16）
009_job_runtime.py           # job_runs + job_attempts（WP4-T01）
010_job_artifacts.py         # job_artifacts（WP4-T03）
011_model_management.py      # 5 模型表（WP5-T01~T05）
```

## 综合风险登记

| ID | 风险 | WP | 影响 | 概率 | 缓解 |
|----|------|----|------|------|------|
| R1 | Alembic 迁移冲突 | WP2 | 高 | 中 | 基线迁移精确还原 + `alembic stamp head` |
| R2 | RBAC 权限遗漏 | WP2 | 中 | 中 | 内置角色覆盖 26 动作 + 逐角色测试 |
| R3 | v0.1→v0.2 数据迁移损坏 | WP9 | 高 | 中 | verify.sql + 全量备份 + 回滚 |
| R4 | Ray Job 状态同步不可靠 | WP4 | 中 | 中 | PG 事实源 + Reconciler 兜底 |
| R5 | 性能回退 | 全部 | 中 | 高 | benchmark + 连接池 + 异步非关键路径 |
| R6 | Control Center 前端超估 | WP6 | 中 | 中 | 优先核心 5 页面，其余可延后 |
| R7 | ModelServing 配置迁移破坏 | WP5 | 高 | 低 | 保留 YAML Bootstrap + 灰度切换 |
| R8 | Outbox Worker 瓶颈 | WP3 | 中 | 低 | SKIP LOCKED + 并行 Worker + 监控 |
| R9 | 文档滞后 | 全部 | 低 | 高 | 每个 WP DoD 含文档更新 |
| R10 | 范围蔓延 | 全部 | 高 | 中 | 严格遵循 §19 不做清单 + ADR |

## 综合验收标准映射

| 验收类别 | 设计方案节 | 负责 WP | 测试层级 |
|----------|-----------|---------|----------|
| 架构与契约 | §18.1 | WP1 ✅ | L1 |
| 安全 | §18.2 | WP2 | L3 |
| 资产 | §18.3 | WP3 | L2, L4 |
| Job 与 Ray | §18.4 | WP4 | L5 |
| ModelServing | §18.5 | WP5 | L6 |
| Control Center + Steward | §18.6 | WP6, WP7 | L2 |
| 一致性与恢复 | §18.7 | WP3, WP4 | L4, L8 |
| 文档与迁移 | §18.8 | WP9 | L9 |

## 团队配置

| 角色 | 人数 | 主要 WP |
|------|------|---------|
| 架构师 / Tech Lead | 1 | 全阶段评审 + ADR |
| 后端工程师 A | 1 | WP2, WP3（Asset Core + 一致性） |
| 后端工程师 B | 1 | WP3（Knowledge）, WP5 |
| 后端工程师 C | 1 | WP3（Skill+Memory）, WP4, WP7, WP8 |
| 前端工程师 | 1 | WP6 |
| DevOps / SRE | 1 | WP9 + Docker + 迁移 |
| 安全顾问 | 0.5 | WP2 安全评审 + L3 |

**最小团队**：3 人（1 架构师 + 2 后端），周期 ~28 周  
**推荐团队**：5-6 人，周期 ~20 周

## 关键路径

```
WP1 ✅ → WP2 → WP3 → WP4 → WP8 → WP9（发布）
```

关键路径上的任何延迟直接影响 M5 发布。WP5、WP6、WP7 有浮动空间。

---

> **本文档定义 WP2-WP9 的详细执行方案。待批准后开始 WP2 开发。**
