# LakeMindControlCenter 功能设计总结

> 2026-07-15 · v0.2.0 · 统一管理入口

---

## 一、定位

LakeMindControlCenter 是 LakeMind 的**统一管理入口**，替代 v0.1.0 的 Monitor + Steward 两个独立服务。单镜像、单端口（:3000），内含三个进程。

## 二、运行架构

```
                    :3000
                  ┌──────┐
                  │ nginx │
                  └──┬────┘
            ┌────────┼────────┐
            ▼        ▼        ▼
       :3001 BFF  :3002 Steward  静态文件
       (FastAPI)  (FastAPI)      (React SPA)
            │        │
            ▼        ▼
   LakeMindServer    LakeMindServer
   (:10823 REST)     (:10823 REST)
```

| 进程 | 端口 | 职责 | 技术栈 |
|------|------|------|--------|
| nginx | 3000 | 反向代理 + 静态文件 | nginx |
| BFF | 3001 | 认证/会话 + REST 透传 | FastAPI + httpx |
| Steward | 3002 | 巡检 + 建议 + 对话 | FastAPI + httpx |

- **supervisord** 管理三进程生命周期
- **单 Dockerfile** 多阶段构建（Node 构建前端 + Python 构建 BFF/Steward）
- Python 依赖：`fastapi`, `uvicorn`, `httpx`, `pydantic`（极轻量）

## 三、认证与会话

```
用户 → Login 页面 → POST /auth/login
  │
  ├─ BFF SHA-256(password) → Server /api/v1/security/auth/login
  ├─ Server 验证 → 返回 {token, role, tenant_id}
  ├─ BFF 创建内存 session: {username, token, role, tenant_id}
  └─ 设置 httponly cookie (session_id, 1h, SameSite=Lax)
```

| 项 | 实现 |
|---|---|
| 会话存储 | BFF 内存 dict（重启丢失，无 Valkey/Redis） |
| 密码传输 | BFF 端 SHA-256 哈希后传给 Server |
| 控制面认证 | BFF 用 `LAKEMIND_BFF_TOKEN` Bearer 调 Server |
| 租户隔离 | 仅 `/jobs*` 和 `/overview` 传递 `X-Tenant-Id` |
| 前端守卫 | `AppLayout` 每次路由变化调 `GET /overview`，401 → 跳转 Login |

### 已知限制

- 会话内存存储，BFF 重启后所有用户需重新登录
- 除 Jobs 外，其他页面数据**跨租户可见**
- 登录页 placeholder 泄露默认密码提示
- 无 CSRF token（依赖 httponly + SameSite cookie）

## 四、页面功能清单（10 页）

### 4.1 Overview（仪表盘）

| 能力 | 数据源 |
|------|--------|
| 实例数 | `GET /overview` → instances count |
| 资产总数 | → assets_total |
| 作业总数 | → jobs_total（租户隔离） |
| 最近审计 | → recent_audit（5 条） |

**只读**，四个 Statistic 卡片 + 审计表格。

### 4.2 Assets（资产）

| 能力 | 数据源 |
|------|--------|
| 资产列表 | `GET /assets?page_size=100` |

表格列：asset_id, name, asset_type, tenant_id, status, created_at。**只读**。

**未使用的 BFF 端点**：`/assets/{id}/bindings`、`/assets/{id}/lineage`（后端已实现，前端未接入）。

### 4.3 Jobs（作业）

| 能力 | 数据源 | 操作 |
|------|--------|------|
| 作业列表 | `GET /jobs?page_size=100` | — |
| 重试 | — | `POST /jobs/{id}/retry` |
| 取消 | — | `POST /jobs/{id}/cancel` |

表格列：job_id, status, tenant_id, initiator_id, created_at。状态 Tag 颜色：SUCCEEDED 绿 / FAILED 红 / RUNNING 蓝。

### 4.4 Models（模型管理）

三个 Tab：

#### Tab 1: Model Definitions（模型定义）

| 字段 | 说明 | 示例 |
|------|------|------|
| name | 模型名 | `gpt-4o` |
| model_type | 类型 | `chat` / `completion` / `embedding` / `asr` |
| provider_family | 提供商族 | `openai`, `fastembed`, `faster-whisper` |
| capabilities | 能力（逗号分隔） | `chat,vision` |
| context_length | 上下文长度 | `128000` |
| embedding_dim | 嵌入维度 | `1536` |
| metadata | JSON 元数据 | `{"litellm_model": "openai/gpt-4o"}` |

`POST /models/definitions` → Server `model_definitions` 表。

#### Tab 2: Deployments（部署实例）

| 字段 | 说明 | 示例 |
|------|------|------|
| model_id | 关联定义 | 选择已有 Definition |
| provider | 提供商 | `openai` |
| endpoint | 推理地址 | `https://api.openai.com/v1/chat/completions` |
| secret_ref | 密钥引用 | `secret://default/openai-api-key` |
| priority | 优先级 | `100` |
| timeout_ms | 超时 | `30000` |
| max_concurrency | 最大并发 | `10` |

`POST /models/deployments` → Server `model_deployments` 表。可 Enable/Disable。

#### Tab 3: Profiles（路由配置）

| 字段 | 说明 | 示例 |
|------|------|------|
| name | Profile 名 | `default` |
| description | 描述 | `默认路由` |

`POST /models/profiles` → Server `model_profiles` 表。

#### ⚠️ 关键缺口

| 缺口 | 影响 |
|------|------|
| Deployment 创建后**不注册到 ModelServing 运行时** | litellm gateway 不知道新模型，实际调用失败 |
| `model_routes`（绑定 Deployment → Profile）**无 UI 无 API** | Profile 是空壳，`resolve_profile` 查不到路由 |
| 控制面 `model_definitions` 与运行面 `model_registry` **无同步** | 两套独立表，双写缺失 |

### 4.5 Services（服务实例）

| 能力 | 数据源 |
|------|--------|
| 实例列表 | `GET /instances` |

表格列：instance_id, service_type, version, endpoint, health_status, last_heartbeat。**只读**。

### 4.6 Configuration（配置）

| 能力 | 数据源 |
|------|--------|
| 配置查看 | `GET /configuration` |

AntD Descriptions 展示扁平 key/value。**只读**，过滤掉对象值。

### 4.7 Security（安全）

| 能力 | 数据源 |
|------|--------|
| 主体列表 | `GET /security/principals` |

表格列：principal_id, principal_type, tenant_id, status。**只读**。

### 4.8 Operations（运维审批）

| 能力 | 数据源 | 操作 |
|------|--------|------|
| 待审批列表 | `GET /operations?page_size=100` | — |
| 批准 | — | `POST /operations/{id}/approve` |

表格列：operation_id, op_type, target_resource, status, risk_level, initiator_id。仅 PENDING 状态显示 Approve 按钮。

### 4.9 Audit（审计日志）

| 能力 | 数据源 |
|------|--------|
| 审计列表 | `GET /audit?page_size=100` |

表格列：audit_id, event_type, action, result, principal_id, tenant_id, resource_id, created_at。**只读**。

### 4.10 Steward（巡检对话）

**前端**：WebSocket 连接 BFF `/ws`（echo 端点），聊天 UI。

**后端**（Steward FastAPI，nginx `/steward/` 转发）：

| 端点 | 功能 |
|------|------|
| `GET /inspection` | 运行 6 项巡检，返回报告 |
| `GET /inspection/last` | 返回缓存报告 |
| `POST /suggest` | 对 finding 建议动作 |
| `POST /chat` | 模板对话（含巡检摘要） |

#### 巡检项

| 检查 | 状态 | 说明 |
|------|------|------|
| 服务健康 | ✅ 已实现 | 检查 instance health_status ≠ healthy |
| 降级资产 | ✅ 已实现 | 检查 assets status=DEGRADED |
| 丢失作业 | ✅ 已实现 | 检查 jobs status=LOST |
| Outbox 积压 | 🔲 stub | 返回空 |
| 绑定漂移 | 🔲 stub | 返回空 |
| 配置漂移 | 🔲 stub | 返回空 |

#### 建议动作

- **低风险**（6 种）：retry_embedding, rebuild_index, sync_ray_status 等 → 自动执行
- **高风险**（9 种）：delete_asset, revoke_token, stop_service 等 → 创建 Operations 审批

#### ⚠️ 前端未接入

前端 Steward 页面连接的是 BFF `/ws` echo 端点，**不是** Steward `/chat` REST 端点。用户在聊天窗看到的只是 echo 回复，不是巡检结果。

## 五、BFF 路由全清单

| 方法 | 路径 | 认证 | 转发目标 | 租户隔离 |
|------|------|------|----------|----------|
| POST | `/auth/login` | — | Server `/api/v1/security/auth/login` | — |
| POST | `/auth/logout` | cookie | — | — |
| GET | `/overview` | session | 并行 3 请求 | ✅ jobs |
| GET | `/assets` | session | `/api/v1/assets` | ❌ |
| GET | `/assets/{id}` | session | `/api/v1/assets/{id}` | ❌ |
| GET | `/assets/{id}/bindings` | session | `/api/v1/assets/{id}/bindings` | ❌ |
| GET | `/assets/{id}/lineage` | session | `/api/v1/assets/{id}/lineage` | ❌ |
| GET | `/jobs` | session | `/api/v1/jobs` | ✅ |
| GET | `/jobs/{id}` | session | `/api/v1/jobs/{id}` | ✅ |
| POST | `/jobs/{id}/retry` | session | `/api/v1/jobs/{id}/retry` | ✅ |
| POST | `/jobs/{id}/cancel` | session | `/api/v1/jobs/{id}/cancel` | ✅ |
| GET | `/models` | session | `/api/v1/models/definitions` | ❌ |
| POST | `/models/definitions` | session | `/api/v1/models/definitions` | ❌ |
| GET | `/models/deployments` | session | `/api/v1/models/deployments` | ❌ |
| POST | `/models/deployments` | session | `/api/v1/models/deployments` | ❌ |
| POST | `/models/deployments/{id}/enable` | session | 同 | ❌ |
| POST | `/models/deployments/{id}/disable` | session | 同 | ❌ |
| GET | `/models/profiles` | session | `/api/v1/models/profiles` | ❌ |
| POST | `/models/profiles` | session | `/api/v1/models/profiles` | ❌ |
| POST | `/models/profiles/resolve` | session | `/api/v1/models/profiles/resolve` | ❌ |
| GET | `/instances` | session | `/api/v1/instances` | ❌ |
| GET | `/configuration` | session | `/api/v1/configuration` | ❌ |
| GET | `/security/principals` | session | `/api/v1/security/principals` | ❌ |
| GET | `/operations` | session | `/api/v1/operations` | ❌ |
| POST | `/operations/{id}/approve` | session | `/api/v1/operations/{id}/approve` | ❌ |
| GET | `/audit` | session | `/api/v1/audit` | ❌ |
| WS | `/ws` | — | echo | — |
| GET | `/health` | — | — | — |

## 六、前端未使用的后端能力

| 后端端点 | 状态 | 说明 |
|----------|------|------|
| `/assets/{id}/bindings` | BFF ✅ / 前端 ❌ | 资产绑定关系 |
| `/assets/{id}/lineage` | BFF ✅ / 前端 ❌ | 资产血缘 |
| `/models/profiles/resolve` | BFF ✅ / 前端 ❌ | Profile 路由解析 |
| Steward `/inspection` | ✅ / 前端 ❌ | 巡检报告 |
| Steward `/chat` | ✅ / 前端 ❌ | 巡检对话 |
| Steward `/suggest` | ✅ / 前端 ❌ | 建议动作 |

## 七、功能矩阵

| 页面 | 读 | 写 | 搜索 | 详情 | 分页 |
|------|----|----|------|------|------|
| Overview | ✅ | — | — | — | — |
| Assets | ✅ | — | — | ❌ | ✅ |
| Jobs | ✅ | ✅ retry/cancel | — | — | ✅ |
| Models | ✅ | ✅ create/enable/disable | — | — | ✅ |
| Services | ✅ | — | — | — | ✅ |
| Configuration | ✅ | — | — | — | — |
| Security | ✅ | — | — | — | ✅ |
| Operations | ✅ | ✅ approve | — | — | ✅ |
| Audit | ✅ | — | — | — | ✅ |
| Steward | ❌ echo | — | — | — | — |

## 八、已知问题与改进方向

### P0（功能缺失）

| 问题 | 影响 | 修复方向 |
|------|------|----------|
| Steward 前端接 echo，不接 `/chat` | 巡检对话不可用 | 前端改调 `/steward/chat` REST |
| Deployment 不注册到 ModelServing | 新增模型不可用 | Server `create_deployment` → 同步调 ModelServing `/v1/models/register` |
| `model_routes` 无 UI 无 API | Profile 是空壳 | 补 REST 端点 + 前端 Tab |

### P1（体验问题）

| 问题 | 修复方向 |
|------|----------|
| 会话内存存储，重启丢失 | 改用 Valkey 共享会话 |
| 跨租户数据可见 | 所有端点传递 `X-Tenant-Id` |
| Assets 无详情/绑定/血缘 | 接入已有 BFF 端点 |
| 无搜索/过滤 | 前端加 Search + Filter |
| 登录页泄露密码提示 | 移除 placeholder |

### P2（增强）

| 问题 | 修复方向 |
|------|----------|
| Steward 3 项巡检是 stub | 实现 outbox/binding/config drift 检查 |
| Configuration 只读 | 支持在线编辑配置 |
| 无模型路由可视化 | Profile → Deployment 路由图 |
| Steward 对话是模板 | 接入 ModelServing LLM 驱动对话 |
