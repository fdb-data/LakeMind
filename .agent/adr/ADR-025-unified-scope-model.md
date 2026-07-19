# ADR-025: 统一 Scope 模型

> 状态：已批准  
> 日期：2026-07-16  
> 上下文：Phase 1A Core WP-C-Core-T1

## 背景

Phase 0 中 scope 以字符串 `tenant:{tenant_id}` 形式散落在 config_revisions、operations、audit_log 等表中，没有统一的 scope 模型。Metrics、Events、Search Projections 等新子系统都需要 scope 过滤，但缺乏一致的定义。

## 决策

引入统一 Scope 模型，所有带 scope 的表和子系统共用：

```python
class ScopeType(str, Enum):
    PLATFORM = "PLATFORM"
    TENANT = "TENANT"

@dataclass(frozen=True)
class Scope:
    scope_type: ScopeType
    scope_id: str | None  # None when scope_type == PLATFORM

    def __str__(self) -> str:
        if self.scope_type == ScopeType.PLATFORM:
            return "PLATFORM"
        return f"TENANT:{self.scope_id}"

    def matches(self, ctx: SecurityContext) -> bool:
        if self.scope_type == ScopeType.PLATFORM:
            return ctx.is_platform_admin
        return ctx.can_access_tenant(self.scope_id)
```

### 数据库表示

所有带 scope 的表使用统一两列：

```sql
scope_type VARCHAR(16) NOT NULL DEFAULT 'TENANT',  -- PLATFORM | TENANT
scope_id   VARCHAR                                  -- NULL when PLATFORM
```

### 受影响表

| 表 | 现有 scope 表示 | 迁移 |
|----|----------------|------|
| `config_revisions` | `scope` TEXT (`tenant:xxx`) | 新增 scope_type + scope_id 列，迁移现有值 |
| `operations` | `scope` TEXT | 同上 |
| `audit_log` | `tenant_id` VARCHAR | 新增 scope_type + scope_id，保留 tenant_id 向后兼容 |
| `metrics_series` | (新建) | 直接使用 scope_type + scope_id |
| `event_stream` | (新建) | 直接使用 scope_type + scope_id |
| `search_projections` | (新建) | 直接使用 scope_type + scope_id |
| `notifications` | (新建) | 直接使用 scope_type + scope_id |

### 查询模式

```sql
-- Platform 级查询（仅 platform_admin）
WHERE scope_type = 'PLATFORM'

-- Tenant 级查询
WHERE scope_type = 'TENANT' AND scope_id = %s

-- 跨 scope 查询（platform_admin 可见全部）
-- 不加 scope 过滤
```

### SecurityContext 集成

```python
@dataclass(frozen=True)
class SecurityContext:
    # ... 现有字段 ...

    def accessible_scope_filter(self) -> dict:
        """返回 SQL WHERE 参数，用于 scope 过滤"""
        if self.is_platform_admin:
            return {}  # 无过滤
        return {"scope_type": "TENANT", "scope_id": self.tenant_id}
```

## 理由

- **一致性** — 所有子系统用相同模型，减少歧义
- **PLATFORM 级数据** — 系统健康、平台配置等不属于任何 Tenant 的数据有明确归属
- **查询效率** — 两列 + 索引比解析字符串前缀更高效
- **向后兼容** — 保留现有 `scope` TEXT 列，新列通过迁移填充

## 影响

- Migration 009 新增 scope_type + scope_id 列到现有表 + 迁移数据
- `security/context.py` 新增 `Scope` dataclass + `accessible_scope_filter()`
- 所有新表（metrics_series, event_stream, search_projections, notifications）使用统一 scope 列
