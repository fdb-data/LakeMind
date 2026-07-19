# LakeMind v0.2.0 错误模型

> 日期：2026-07-13  
> 状态：accepted  
> 依据：[设计方案](../../../reports/v0.2.0-design/LakeMind_v0.2.0_设计方案.md) §12.7

---

## 1. 错误响应 Schema

所有 API 端点在错误时返回统一格式：

```yaml
ErrorResponse:
  type: object
  required: [error]
  properties:
    error:
      type: object
      required: [code, message, request_id]
      properties:
        code: string          # 稳定错误码枚举
        message: string       # 人类可读信息
        request_id: string    # 请求追踪 ID
        resource_id: string   # 关联资源（可选）
        resource_status: string  # 资源当前状态（可选）
        retryable: boolean    # 是否可重试
        details: object       # 额外上下文（可选）
        correlation_id: string  # 跨服务关联（可选）
```

### 1.1 示例

```json
{
  "error": {
    "code": "ASSET_NOT_READY",
    "message": "Asset ast_01H8X7K2M3 is in PROCESSING status, please retry later",
    "request_id": "req_01H8X7K2M3P4Q5R6S7T8V9W0X",
    "resource_id": "ast_01H8X7K2M3P4Q5R6S7T8V9W0X",
    "resource_status": "PROCESSING",
    "retryable": false
  }
}
```

---

## 2. 错误码枚举

| 错误码 | HTTP | 可重试 | 说明 |
|--------|------|--------|------|
| `AUTHENTICATION_FAILED` | 401 | No | Token 无效或过期 |
| `TOKEN_REVOKED` | 401 | No | Token 已撤销 |
| `PERMISSION_DENIED` | 403 | No | 无权限 |
| `TENANT_SCOPE_VIOLATION` | 403 | No | 跨租户访问 |
| `RESOURCE_NOT_FOUND` | 404 | No | 资源不存在 |
| `ASSET_NOT_READY` | 409 | No | 资产未就绪（CREATING/PROCESSING） |
| `ASSET_DEGRADED` | 200 | No | 资产降级（响应中携带警告） |
| `ASSET_FAILED` | 409 | No | 资产失败 |
| `SKILL_NOT_PUBLISHED` | 409 | No | Skill 未发布或已撤销 |
| `SKILL_VERSION_IMMUTABLE` | 409 | No | 已发布 Skill 不可修改 |
| `JOB_RESOURCE_DENIED` | 403 | No | Job 资源配额不足 |
| `JOB_NOT_FOUND` | 404 | No | Job 不存在 |
| `MODEL_DEPLOYMENT_UNAVAILABLE` | 503 | Yes | 模型 Deployment 不可用 |
| `EMBEDDING_SPACE_MISMATCH` | 409 | No | Embedding 空间不兼容 |
| `CONFIG_REVISION_CONFLICT` | 409 | No | 配置 Revision 冲突 |
| `OPERATION_APPROVAL_REQUIRED` | 202 | No | Operation 需审批 |
| `OPERATION_NOT_APPROVED` | 403 | No | Operation 未获批准 |
| `IDEMPOTENCY_CONFLICT` | 409 | No | 幂等键冲突（相同 key 不同请求体） |
| `VALIDATION_FAILED` | 422 | No | 请求体校验失败 |
| `RATE_LIMITED` | 429 | Yes | 限流 |
| `INTERNAL_ERROR` | 500 | Yes | 内部错误 |
| `UPSTREAM_TIMEOUT` | 504 | Yes | 上游超时 |

---

## 3. 错误码分类

### 3.1 认证与授权（401/403）

| 错误码 | 触发场景 |
|--------|----------|
| `AUTHENTICATION_FAILED` | Token 无效、过期或格式错误 |
| `TOKEN_REVOKED` | Token 已被撤销 |
| `PERMISSION_DENIED` | Principal 无权限执行操作 |
| `TENANT_SCOPE_VIOLATION` | Principal 尝试访问非所属租户资源 |

### 3.2 资源状态（404/409）

| 错误码 | 触发场景 |
|--------|----------|
| `RESOURCE_NOT_FOUND` | 资源 ID 不存在 |
| `ASSET_NOT_READY` | 资产处于 CREATING/PROCESSING 状态 |
| `ASSET_DEGRADED` | 资产部分 Binding 失败，但可降级服务 |
| `ASSET_FAILED` | 资产处于 FAILED 状态 |
| `SKILL_NOT_PUBLISHED` | Skill 处于 DRAFT 或 REVOKED 状态 |
| `SKILL_VERSION_IMMUTABLE` | 尝试修改已发布 Skill |
| `JOB_NOT_FOUND` | Job ID 不存在 |

### 3.3 并发与冲突（409）

| 错误码 | 触发场景 |
|--------|----------|
| `EMBEDDING_SPACE_MISMATCH` | 向量维度或模型不兼容 |
| `CONFIG_REVISION_CONFLICT` | 配置 Revision 并发冲突 |
| `IDEMPOTENCY_CONFLICT` | 相同幂等键 + 不同请求体 |

### 3.4 操作与审批（202/403）

| 错误码 | 触发场景 |
|--------|----------|
| `OPERATION_APPROVAL_REQUIRED` | Operation 风险等级需要审批 |
| `OPERATION_NOT_APPROVED` | Operation 未获批准即尝试执行 |

### 3.5 基础设施（429/500/503/504）

| 错误码 | 触发场景 |
|--------|----------|
| `RATE_LIMITED` | 请求频率超限 |
| `INTERNAL_ERROR` | 未预期的内部错误 |
| `MODEL_DEPLOYMENT_UNAVAILABLE` | 模型 Deployment 不可用 |
| `UPSTREAM_TIMEOUT` | 上游服务超时 |

### 3.6 校验（422）

| 错误码 | 触发场景 |
|--------|----------|
| `VALIDATION_FAILED` | 请求体格式或字段校验失败 |

---

## 4. MCP 错误映射

MCP tool 错误使用相同错误码，映射为 MCP 错误响应：

| MCP 错误 | API 错误码 |
|----------|-----------|
| `ValueError` | `VALIDATION_FAILED` |
| `PermissionError` | `PERMISSION_DENIED` |
| `KeyError` | `RESOURCE_NOT_FOUND` |
| `TimeoutError` | `UPSTREAM_TIMEOUT` |
| 未分类异常 | `INTERNAL_ERROR` |

---

## 5. 评审标准

- [x] 错误码覆盖设计方案 §12.7 全部 + 扩展场景（22 个错误码）
- [x] 每个错误码有明确 HTTP 状态码和可重试性
- [x] ErrorResponse schema 纯入 OpenAPI spec（`components.schemas.ErrorResponse`）
- [x] `request_id` 在所有错误响应中存在
