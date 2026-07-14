# LakeMind v0.2.0 信任边界

> 日期：2026-07-13  
> 状态：accepted  
> 依据：[设计方案](../../../v0.2.0.design/LakeMind_v0.2.0_设计方案.md) §4.3

---

## 1. 信任边界定义

每个平面有明确信任级别，信任级别决定了该平面可访问的资源和可执行的操作：

| 平面 | 信任级别 | 可访问资源 | 不可访问资源 |
|------|----------|-----------|-------------|
| Access Plane | 最不可信 | 已解析的请求对象 | 数据库、对象存储、密钥 |
| Control Plane | 可信 | 全部 Service、Provider 抽象 | 引擎 SDK 直接调用 |
| Data & Index Plane | 可信 | 数据文件、索引、缓存 | 业务逻辑、外部请求 |
| Execution Plane | 半可信 | 声明的 Asset Binding、声明 Secret Ref | 控制面密钥、其他 Job 数据 |

---

## 2. 跨平面调用规则

### 2.1 允许的调用方向

```
Access Plane ──→ Control Plane
  条件：必须携带 SecurityContext（由 Token 解析生成）
  内容：请求参数 + SecurityContext

Control Plane ──→ Data & Index Plane
  条件：通过 Provider 抽象（ObjectStorageProvider / VectorIndexProvider / ...）
  内容：逻辑参数（asset_id / binding_id），不含物理路径

Control Plane ──→ Execution Plane
  条件：通过 JobService.submit()
  内容：Skill 引用 + 输入参数 + Secret 引用 + 资源配额

Execution Plane ──→ Data & Index Plane
  条件：通过受控契约（Asset Binding + Secret Ref）
  内容：仅能访问 Job 声明的 Asset 和 Secret
```

### 2.2 禁止的调用方向

| 禁止方向 | 原因 |
|----------|------|
| Access → Data & Index | 外部请求不可绕过 Control Plane 直连数据层 |
| Execution → Control | 执行层不可反向调用控制面 Service（如 AuthorizationService） |
| Data & Index → 任何平面 | 数据层不主动调用其他平面，仅被动响应 |
| Access → Execution | 外部请求不可直接调度执行层 |

---

## 3. 身份传递链

```
                    ┌──────────────────────────────────────────────────┐
                    │              身份传递链                           │
                    └──────────────────────────────────────────────────┘

  Agent/Client
       │
       │ Bearer Token
       ▼
  Access Plane ──── 解析 Token ──→ SecurityContext {
       │              principal_id: prn_xxx
       │              tenant_id: ten_xxx
       │              scopes: [read, write, ...]
       │              channel: rest | mcp | control_center | steward
       │            }
       ▼
  Control Plane ──── 鉴权 ──→ AuthorizationService.authorize(ctx, action, resource)
       │
       │ Job 提交
       ▼
  JobService.submit() ──── 生成 Job Identity ──→ {
       │                      job_id: job_xxx
       │                      tenant_id: ten_xxx
       │                      principal_id: prn_xxx
       │                      skill_ref: lake://skills/{name}@{version}
       │                      secret_refs: [secret://scope/name, ...]
       │                    }
       ▼
  Execution Plane ──── 使用 Job Identity 访问声明的 Asset 和 Secret
```

### 3.1 SecurityContext 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| principal_id | string | `prn_{ulid}`，发起者 ID |
| tenant_id | string | `ten_{ulid}`，租户 ID |
| scopes | string[] | 权限范围 |
| channel | enum | `rest` / `mcp` / `control_center` / `steward` / `system` |
| request_id | string | 请求追踪 ID |
| correlation_id | string? | 跨服务关联 ID |

---

## 4. 网络边界

### 4.1 对外暴露端口

| 端口 | 组件 | 协议 | 认证 |
|------|------|------|------|
| 8401 | LakeMindAssetMCP | MCP (SSE) | Bearer Token |
| 8402 | LakeMindDataMCP | MCP (SSE) | Bearer Token |
| 8403 | LakeMindAdminMCP | MCP (SSE) | Bearer Token |
| 10823 | LakeMindServer REST API | HTTP/JSON | Bearer Token |
| 3000 | LakeMindControlCenter | HTTP | Session + RBAC |

### 4.2 内部端口（不对外暴露）

| 端口 | 组件 | 协议 | 访问者 |
|------|------|------|--------|
| 5432 | PostgreSQL | TCP | Control Plane Service |
| 8333 | SeaweedFS | S3 API | ObjectStorageProvider |
| 6379 | Valkey | RESP | CacheProvider |
| 8265 | Ray Dashboard | HTTP | JobService（仅 submit/status） |
| 10001 | Ray Head | TCP | Ray Workers |
| 10824 | LakeMindModelServing | HTTP/JSON | ModelProvider |

### 4.3 网络隔离规则

- Agent 不可直连内部端口（5432 / 8333 / 6379 / 8265 / 10824）
- Execution Plane 不可访问 Control Plane 的数据库连接
- MCP 服务器通过 REST API (10823) 调用 Control Plane，不直连数据库
- Control Center 通过 REST API (10823) + MCP (8401-8403) 访问平台

---

## 5. 评审标准

- [x] 信任边界定义覆盖全部四个平面
- [x] 跨平面调用规则无矛盾
- [x] 身份传递链完整（Token → SecurityContext → Job Identity）
- [x] 网络边界明确区分对外暴露和内部端口
- [x] 禁止的调用方向有明确原因
