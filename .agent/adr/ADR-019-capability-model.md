# ADR-019: Capability 权限模型

> 状态：已批准  
> 日期：2026-07-16  
> 上下文：Phase 1A Core WP-C-Core-T1

## 背景

Phase 0 安全模型基于 `Action` 枚举（`security/actions.py`）和 `SecurityContext.has_scope(action)` 做粗粒度 scope 检查。前端无法从 `/auth/me` 获知当前 principal 可执行哪些操作，只能硬编码角色判断。Phase 1A 需要前端 Capability 驱动的路由守卫和导航动态生成。

## 决策

引入 **Capability** 层，作为 Action 的前端可消费投影：

```
Action（后端权限原语） → Capability（前端功能权限）
```

### Capability 定义

```python
class Capability(str, Enum):
    # Platform 级
    PLATFORM_ADMIN = "platform:admin"           # 全局管理
    TENANT_CREATE = "tenant:create"
    TENANT_SUSPEND = "tenant:suspend"
    TENANT_ARCHIVE = "tenant:archive"
    PLATFORM_VIEW_ALL = "platform:view_all"     # 跨租户只读

    # Tenant 级
    TENANT_MANAGE = "tenant:manage"             # 成员/配额/配置
    TENANT_VIEW = "tenant:view"

    # 资产
    ASSET_MANAGE = "asset:manage"               # create/update/delete
    ASSET_VIEW = "asset:view"

    # Job
    JOB_SUBMIT = "job:submit"
    JOB_MANAGE = "job:manage"                   # cancel/retry
    JOB_VIEW = "job:view"

    # Model
    MODEL_CONFIGURE = "model:configure"
    MODEL_VIEW = "model:view"

    # Config
    CONFIG_WRITE = "config:write"
    CONFIG_ACTIVATE = "config:activate"
    CONFIG_VIEW = "config:view"

    # Operation
    OPERATION_REQUEST = "operation:request"
    OPERATION_APPROVE = "operation:approve"
    OPERATION_VIEW = "operation:view"

    # Observability
    OBS_VIEW = "obs:view"                       # Metrics/健康
    OBS_MANAGE = "obs:manage"                   # 配置告警规则（Phase 1B）

    # Audit
    AUDIT_VIEW = "audit:view"

    # Search
    SEARCH_GLOBAL = "search:global"

    # Steward
    STEWARD_CHAT = "steward:chat"
```

### Action → Capability 映射

```python
ACTION_TO_CAPABILITY = {
    Action.ASSET_CREATE: Capability.ASSET_MANAGE,
    Action.ASSET_READ: Capability.ASSET_VIEW,
    Action.ASSET_UPDATE: Capability.ASSET_MANAGE,
    Action.ASSET_DELETE: Capability.ASSET_MANAGE,
    Action.JOB_SUBMIT: Capability.JOB_SUBMIT,
    Action.JOB_READ: Capability.JOB_VIEW,
    Action.JOB_CANCEL: Capability.JOB_MANAGE,
    Action.JOB_RETRY: Capability.JOB_MANAGE,
    Action.MODEL_READ: Capability.MODEL_VIEW,
    Action.MODEL_CONFIGURE: Capability.MODEL_CONFIGURE,
    Action.CONFIG_READ: Capability.CONFIG_VIEW,
    Action.CONFIG_WRITE: Capability.CONFIG_WRITE,
    Action.CONFIG_ACTIVATE: Capability.CONFIG_ACTIVATE,
    Action.OPERATION_REQUEST: Capability.OPERATION_REQUEST,
    Action.OPERATION_APPROVE: Capability.OPERATION_APPROVE,
    Action.AUDIT_READ: Capability.AUDIT_VIEW,
    # ...
}
```

### `/auth/me` 增强

```json
{
  "principal_id": "prn_admin_default",
  "principal_type": "user",
  "tenant_id": "ten_default",
  "roles": ["platform_admin"],
  "capabilities": ["platform:admin", "tenant:create", ...],
  "effective_permissions": {
    "tenant:create": true,
    "asset:manage": true,
    "job:submit": true,
    ...
  },
  "security_version": 0
}
```

`capabilities` 是扁平列表，前端用 `hasCapability(cap)` 判断。`effective_permissions` 是完整 map，用于批量检查。

### 角色内置 Capability

| 角色 | Capabilities |
|------|-------------|
| `platform_admin` | 全部 |
| `tenant_admin` | `tenant:manage`, `tenant:view`, `asset:manage`, `asset:view`, `job:*`, `model:configure`, `model:view`, `config:*`, `operation:*`, `obs:view`, `audit:view`, `search:global`, `steward:chat` |
| `agent` | `asset:view`, `job:submit`, `job:view`, `model:view`, `config:view`, `memory:*`, `search:global` |
| `viewer` | `*:view` (所有只读) |

## 理由

- **不替换 Action** — 后端继续用 `require_action(action)` 做权限执行，Capability 只是投影
- **前端零硬编码** — 路由守卫和导航菜单完全由 `/auth/me` 返回的 capabilities 驱动
- **角色可组合** — 自定义角色通过 role_bindings + capability 列表实现，不需要改代码

## 影响

- `security/actions.py` 新增 `Capability` 枚举 + `ACTION_TO_CAPABILITY` 映射
- `security/context.py` 新增 `SecurityContext.capabilities` 属性
- `api/security.py` 新增 `GET /auth/me` 端点（返回 capabilities + effective_permissions）
- BFF `/auth/me` 增强透传 capabilities
- 前端 `RouteGuard` + `useCapabilities()` hook
