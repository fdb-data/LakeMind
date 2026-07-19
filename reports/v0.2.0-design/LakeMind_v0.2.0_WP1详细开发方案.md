# LakeMind v0.2.0 WP1 详细开发方案

> **工作包：WP1 — 架构与契约基础**  
> **阶段：A（设计冻结）**  
> **周期：第 1-2 周（10 个工作日）**  
> **估算：24 SP**  
> **目标：形成 v0.2.0 的稳定逻辑架构和外部契约，为后续 WP2-WP9 提供"地基"**  
> **依据：[设计方案](./LakeMind_v0.2.0_设计方案.md) §3-§5, §7-§13 / [开发方案](./LakeMind_v0.2.0_开发方案.md) §2.1**  
> **日期：2026-07-13**

---

## 0. WP1 概述

### 0.1 在全局计划中的位置

```
阶段 A (W1-W2)
  └── WP1 架构与契约基础  ← 本文档
        │
        ├── 产出: 四平面文档 + API v1 spec + ADR 1-15 + Provider 契约 + 文档冲突消除
        │
        ▼ 门禁 M0: 设计冻结评审
        │
阶段 B (W3-W6)
  └── WP2 Control Plane 与安全
```

WP1 是**纯设计工作包**，不写业务代码，但产出物将直接指导 WP2-WP9 的全部实现。WP1 的质量决定整个 v0.2.0 的成败。

### 0.2 任务清单

| Task ID | 任务 | SP | 工日 | 依赖 |
|---------|------|----|------|------|
| WP1-T01 | 编写四平面架构文档 | 3 | 3 | — |
| WP1-T02 | 定义 Application Service 边界 | 3 | 3 | T01 |
| WP1-T03 | 制定 API v1 规范 | 4 | 4 | T02 |
| WP1-T04 | 统一资源 ID 与 URI 规范 | 2 | 2 | T02 |
| WP1-T05 | 统一错误模型 | 2 | 2 | T03 |
| WP1-T06 | Operation / 事件 / 幂等规范 | 2 | 2 | T03 |
| WP1-T07 | MCP 与 REST 共享语义方案 | 2 | 2 | T02 |
| WP1-T08 | 编写 ADR 1-15 | 3 | 3 | T01-T07 |
| WP1-T09 | 消除文档定位冲突 | 2 | 2 | T08 |
| WP1-T10 | 内部 Provider 契约定义 | 1 | 1 | T02 |
| **合计** | | **24** | **24** | |

### 0.3 人员配置

| 角色 | 人数 | 职责 |
|------|------|------|
| 架构师 / Tech Lead | 1 | 主笔 T01/T02/T08/T09，评审全部 |
| 后端工程师 A | 1 | 主笔 T03/T04/T05 |
| 后端工程师 B | 1 | 主笔 T06/T07/T10 |
| 全员 | 3 | ADR 评审 + 文档评审 |

### 0.4 现状基线（来自代码库勘察）

| 维度 | v0.1.0 现状 | v0.2.0 目标 |
|------|-------------|-------------|
| REST API | 56 端点，`/api/v1/storage/*` + `/api/v1/compute/*` + `/api/v1/cognitive/*` + `/api/v1/metadata/*` + `/api/v1/system/*` | 统一为 `/api/v1/{资源}` 资源化 API |
| 认证 | 单一全局 API Key（`auth.py` 硬编码比较） | Security Context + Token 哈希 + RBAC |
| 租户 | `X-Tenant-Id` Header 自由声明，默认 `"default"` | Server 端强制解析，不可伪造 |
| MCP 工具 | AssetMCP 23 + DataMCP 24 + AdminMCP 21 = 68 tools | MCP 降为协议适配层，调用同一 Application Service |
| 数据库 | 9 张表，单文件 `01-age.sql` 幂等创建，无迁移框架 | 27+ 张表，Alembic 迁移 |
| Provider 抽象 | 10 个 `typing.Protocol`（`protocols.py`），但 `LLMPlugin` 无注册实现 | 10 个 Provider 契约正式定义，移除 vestigial LLMPlugin |
| 配置 | `engines.yaml` + `.env` + 代码默认值 | Configuration Service + Revision + 作用域 |
| 文档 | `docs/` 13 文件；AGENTS.md 与代码存在工具数偏差 | 全部对齐，定位冲突消除 |

---

## 1. WP1-T01：编写四平面架构文档

> **SP：3 | 工日：3 | 依赖：无 | 主笔：架构师**

### 1.1 目标

产出 v0.2.0 四平面架构的正式文档，明确每个平面的职责、组件归属、Trust Boundary 和禁止事项。

### 1.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/architecture/v0.2.0/four-planes.md` | 四平面定义 + 组件归属 + Trust Boundary + 禁止事项 + 依赖规则 |
| `docs/architecture/v0.2.0/trust-boundary.md` | 信任边界图 + 跨平面调用规则 + 身份传递链 |
| `docs/architecture/v0.2.0/component-mapping.md` | v0.1.0 现有组件 → v0.2.0 平面归属映射表 |

### 1.3 详细执行步骤

#### 步骤 1.1：编写四平面定义（1 工日）

基于设计方案 §4.1-§4.2，编写以下内容：

**四平面总表**（直接引用设计方案 §4.1 表格，补充"调用方向"列）：

| 平面 | 核心职责 | 调用方向 |
|------|----------|----------|
| Access Plane | 协议适配、请求校验、入口 | → Control Plane |
| Control Plane | 身份、安全、资产、Job、配置、治理 | → Data & Index Plane（通过 Provider） |
| Data & Index Plane | 保存数据、索引、缓存、投影 | 不主动调用其他平面 |
| Execution Plane | 执行 Job、模型推理、解析 | → Data & Index Plane（受控契约）；← Control Plane（调度） |

**组件归属表**（基于设计方案 §4.2 + 代码库勘察结果）：

| 组件 | v0.1.0 位置 | v0.2.0 平面 | 备注 |
|------|-------------|-------------|------|
| LakeMindAssetMCP (8401) | LakeMindMCP/ | Access Plane | 23 tools → 降为协议适配层 |
| LakeMindDataMCP (8402) | LakeMindMCP/ | Access Plane | 24 tools → 受控数据访问 |
| LakeMindAdminMCP (8403) | LakeMindMCP/ | Access Plane | 21 tools → 调用 Operation Service |
| LakeMindServer REST API (10823) | LakeMindServer/ | Access Plane + Control Plane | 拆分：路由层 → Access；Service 层 → Control |
| LakeMindControlCenter | LakeMindMonitor/ 演进 | Access Plane | BFF + 前端 |
| LakeMindSteward | LakeMindSteward/ | Control Plane | 受控治理 Agent |
| LakeMindModelServing (10824) | LakeMindModelServing/ | Execution Plane | 运行执行；配置归 Control Plane |
| Ray Head + Workers | docker-compose | Execution Plane | 受控 Execution Backend |
| PostgreSQL | docker-compose | Data & Index Plane | 同时是 Control Plane 事实源 |
| SeaweedFS / S3 | docker-compose | Data & Index Plane | 对象存储 |
| Lance / LanceDB | LakeMindServer plugins | Data & Index Plane | 向量索引 |
| Iceberg | LakeMindServer plugins | Data & Index Plane | 表格式 |
| Valkey | docker-compose | Data & Index Plane | KV 缓存 |
| PG Graph (graph_nodes/edges) | LakeMindServer plugins | Data & Index Plane | 图投影（Experimental） |

#### 步骤 1.2：编写 Trust Boundary 文档（1 工日）

内容大纲：

```
1. 信任边界定义
   - 每个平面有明确信任级别
   - Access Plane：最不可信（外部输入）
   - Control Plane：可信（已认证）
   - Data & Index Plane：可信（仅被 Control Plane 调用）
   - Execution Plane：半可信（受控代码，非控制面密钥）

2. 跨平面调用规则
   - Access → Control：必须携带 SecurityContext
   - Control → Data：通过 Provider 抽象，不直连引擎 SDK
   - Control → Execution：通过 JobService，不直连 Ray API
   - Execution → Data：通过受控契约（Asset Binding + Secret Ref）
   - 禁止：Access → Data（绕过 Control Plane）
   - 禁止：Execution → Control（反向调用控制面）

3. 身份传递链
   Token → Access Plane 解析 → SecurityContext → Control Plane 鉴权
   → Job 提交时生成 Job Identity → Execution Plane 使用 Job Identity

4. 网络边界
   - 对外暴露：MCP (8401-8403) + REST API (10823) + Control Center (3000)
   - 内部仅：PostgreSQL (5432) + SeaweedFS (8333) + Valkey (6379) + Ray (8265) + ModelServing (10824)
   - Agent 不可直连内部端口
```

#### 步骤 1.3：编写组件映射表（1 工日）

对 v0.1.0 每个代码模块，标注 v0.2.0 归属和改造方向：

| v0.1.0 模块 | v0.2.0 归属 | 改造方向 |
|-------------|-------------|----------|
| `app.py` (FastAPI + 路由) | Access Plane | 路由保留，认证中间件升级 |
| `auth.py` (API Key 比较) | Access Plane → Control Plane | 替换为 SecurityContext 解析 → AuthorizationService |
| `config.py` (YAML 加载) | Control Plane | 替换为 Configuration Service + Bootstrap |
| `engines.py` (引擎初始化) | Control Plane → Data Plane | Provider 工厂保留，初始化由 Control Plane 管理 |
| `api/*.py` (11 路由模块) | Access Plane | 路由保留，handler 改为调用 Application Service |
| `plugins/protocols.py` (10 Protocol) | Data Plane 契约 | 正式化为 Provider 契约（T10） |
| `plugins/registry.py` | Data Plane | Provider 注册表 |
| `plugins/storage/*` | Data & Index Plane | 保留，通过 Provider 抽象被调用 |
| `plugins/cognitive/*` | Data & Index Plane | Memory 保留；LLM 移除（归 ModelServing）；Embedding 归 ModelServing |
| `plugins/compute/*` | Execution Plane | Ray compute 保留为 ExecutionBackend 实现 |

### 1.4 评审标准

- [ ] 四平面职责无重叠；
- [ ] 每个组件有且仅有一个平面归属；
- [ ] Trust Boundary 调用规则无矛盾；
- [ ] 组件映射表覆盖 v0.1.0 全部模块；
- [ ] 文档经全员评审通过。

---

## 2. WP1-T02：定义 Application Service 边界

> **SP：3 | 工日：3 | 依赖：T01 | 主笔：架构师**

### 2.1 目标

定义 12 个 Application Service 的接口签名、职责边界和依赖关系，作为 Control Plane 的核心骨架。

### 2.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/architecture/v0.2.0/application-services.md` | 12 Service 接口定义 + 依赖图 + 职责边界 |

### 2.3 12 个 Application Service

基于设计方案 §4.4，定义每个 Service 的接口签名：

#### 2.3.1 AssetService

```
职责：资产公共生命周期、版本、Binding、血缘和状态
接口：
  create_asset(tenant, type, name, source, metadata) → Asset
  get_asset(asset_id) → Asset
  list_assets(tenant, type?, status?, page) → Page[Asset]
  update_asset(asset_id, metadata) → Asset
  delete_asset(asset_id) → Operation  # 异步
  get_bindings(asset_id) → List[Binding]
  get_lineage(asset_id) → LineageGraph
  reindex(asset_id) → Operation
依赖：PostgreSQL, ObjectStorageProvider, VectorIndexProvider
```

#### 2.3.2 KnowledgeService

```
职责：Knowledge 创建、摄入、解析、索引、检索和删除
接口：
  ingest(tenant, name, content, source_type, parser?) → Operation
  search(tenant, query, kb_name?, filters?, top_k) → List[SearchResult]
  get_concept(kb_name, concept_id) → Concept
  list_concepts(tenant, kb_name, filters?, page) → Page[Concept]
  reindex(kb_name) → Operation
依赖：AssetService, ObjectStorageProvider, VectorIndexProvider, ModelProvider(embedding)
```

#### 2.3.3 SkillService

```
职责：Skill 注册、校验、发布、版本、撤销和检索
接口：
  register(tenant, manifest, code_package) → Skill (DRAFT)
  validate(skill_id) → ValidationResult
  publish(skill_id) → Skill (PUBLISHED)  # 不可变
  revoke(skill_id, reason) → Skill (REVOKED)
  get_skill(name, version) → Skill
  list_skills(tenant, filters?, page) → Page[Skill]
  search_skills(query, top_k) → List[SearchResult]
依赖：AssetService, ObjectStorageProvider, VectorIndexProvider
```

#### 2.3.4 MemoryService

```
职责：Memory 写入、检索、更新、过期、归档和删除（mem0 风格 8 方法）
接口：
  add(tenant, messages, metadata) → Memory
  search(tenant, query, filters?, top_k) → List[Memory]
  get(memory_id) → Memory
  list(tenant, filters?, page) → Page[Memory]
  update(memory_id, content) → Memory
  delete(memory_id) → void
  clear(tenant, filters?) → int  # 返回清除数
  history(memory_id) → List[MemoryEvent]
依赖：AssetService, VectorIndexProvider, KVProvider, ModelProvider(embedding+llm)
```

#### 2.3.5 JobService

```
职责：Job 提交、状态、尝试、重试、取消、结果和恢复
接口：
  submit(tenant, skill_ref, inputs, params, model_profile?, resource_overrides?) → JobRun
  get_job(job_id) → JobRun
  list_jobs(tenant, status?, page) → Page[JobRun]
  cancel(job_id) → JobRun
  retry(job_id) → JobRun  # 新 Attempt
  get_result(job_id) → Artifact
  get_attempts(job_id) → List[JobAttempt]
依赖：SkillService, ModelManagementService, SecretService, ExecutionBackend
```

#### 2.3.6 ModelManagementService

```
职责：模型定义、部署、Profile、路由和配置版本
接口：
  create_model(definition) → ModelDefinition
  create_deployment(model_id, deployment_config) → ModelDeployment
  create_profile(name, route_config) → ModelProfile
  resolve_profile(profile_name, tenant?) → ResolvedRoute  # → 具体 Deployment
  list_models() → List[ModelDefinition]
  list_deployments(model_id?) → List[ModelDeployment]
  enable_deployment(deployment_id) → Operation
  disable_deployment(deployment_id) → Operation
依赖：SecretService, ConfigurationService
```

#### 2.3.7 ConfigurationService

```
职责：配置 Schema、作用域、默认值、校验、Revision、激活、回滚
接口：
  get(scope, key) → ConfigValue
  set(scope, key, value, reason) → ConfigRevision
  get_revision(revision_id) → ConfigRevision
  activate(revision_id) → Operation
  rollback(revision_id) → Operation
  list_revisions(scope?, page) → Page[ConfigRevision]
  get_effective(scope) → Dict  # 合并优先级后的有效配置
依赖：PostgreSQL
```

#### 2.3.8 AuthorizationService

```
职责：身份、角色、动作和资源授权
接口：
  authenticate(token) → SecurityContext
  authorize(security_context, action, resource) → bool
  check_tenant(security_context, tenant_id) → bool  # 租户隔离
  list_roles(tenant?) → List[Role]
  assign_role(principal_id, role_id, tenant_id) → void
依赖：PostgreSQL
```

#### 2.3.9 SecretService

```
职责：Secret 保存、引用、使用授权、版本和轮换
接口：
  create(scope, name, value) → SecretRef  # 返回引用，不返回明文
  get_ref(scope, name) → SecretRef
  resolve(ref, requester_identity) → SecretValue  # 仅授权方可调用
  rotate(scope, name) → SecretRef  # 新版本
  list(scope?) → List[SecretMetadata]  # 不含明文
  log_usage(ref, requester, purpose) → void
依赖：PostgreSQL（加密存储）, 主密钥（外部引用）
```

#### 2.3.10 OperationService

```
职责：统一执行管理和治理动作
接口：
  create(type, target, initiator, reason, risk_level) → Operation
  approve(operation_id, approver) → Operation
  execute(operation_id) → Operation  # 异步
  get(operation_id) → Operation
  list(status?, type?, page) → Page[Operation]
  cancel(operation_id) → Operation
依赖：AuditService, AuthorizationService
```

#### 2.3.11 AuditService

```
职责：记录安全、管理、资产、Job 和模型操作
接口：
  record(event_type, principal, resource, action, result, details) → AuditEvent
  query(filters, page) → Page[AuditEvent]
  export(filters) → Stream  # 导出
依赖：PostgreSQL
```

#### 2.3.12 ReconciliationService

```
职责：检查并修复资产、Job、配置和模型运行状态偏差
接口：
  scan_assets() → List[DriftReport]  # Binding 状态偏差
  scan_jobs() → List[DriftReport]  # Ray vs PG 状态偏差
  scan_config() → List[DriftReport]  # Desired vs Active Revision
  repair(drift_id) → Operation
  get_drifts(category?, page) → Page[DriftReport]
依赖：AssetService, JobService, ConfigurationService
```

### 2.4 依赖关系图

```
AuthorizationService ←── 所有 Service（鉴权前置）
AuditService ←── 所有 Service（审计后置）

AssetService ──→ ObjectStorageProvider, VectorIndexProvider
  ├── KnowledgeService
  ├── SkillService
  └── MemoryService

JobService ──→ SkillService, ModelManagementService, SecretService, ExecutionBackend

ModelManagementService ──→ SecretService, ConfigurationService

OperationService ──→ AuditService, AuthorizationService

ReconciliationService ──→ AssetService, JobService, ConfigurationService

ConfigurationService ──→ PostgreSQL（独立）
SecretService ──→ PostgreSQL + 主密钥（独立）
```

### 2.5 评审标准

- [ ] 12 个 Service 接口签名完整；
- [ ] Service 间依赖无循环（除 Audit/Auth 横切）；
- [ ] 每个 Service 有明确单一职责；
- [ ] 接口不泄漏底层引擎细节（无 S3 Key / Lance Path / Ray Job ID 在外部接口）；
- [ ] 依赖图可拓扑排序。

---

## 3. WP1-T03：制定 API v1 规范

> **SP：4 | 工日：4 | 依赖：T02 | 主笔：后端工程师 A**

### 3.1 目标

产出完整的 OpenAPI 3.1 规范，覆盖 v0.2.0 全部 REST API 端点。

### 3.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/api-spec/v0.2.0/openapi.yaml` | OpenAPI 3.1 完整规范 |
| `docs/api-spec/v0.2.0/README.md` | 渲染说明 + 变更规则 |

### 3.3 API 资源端点清单

基于设计方案 §12.2 + 当前 56 端点 + v0.2.0 新增需求，统一为资源化 API：

#### 3.3.1 资产 API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/assets` | 创建资产 | AssetService.create_asset |
| GET | `/api/v1/assets` | 列表（分页+过滤） | AssetService.list_assets |
| GET | `/api/v1/assets/{asset_id}` | 详情 | AssetService.get_asset |
| PATCH | `/api/v1/assets/{asset_id}` | 更新元数据 | AssetService.update_asset |
| DELETE | `/api/v1/assets/{asset_id}` | 删除（异步 Operation） | AssetService.delete_asset |
| GET | `/api/v1/assets/{asset_id}/bindings` | Binding 列表 | AssetService.get_bindings |
| GET | `/api/v1/assets/{asset_id}/lineage` | 血缘 | AssetService.get_lineage |
| POST | `/api/v1/assets/{asset_id}/reindex` | 重建索引 | AssetService.reindex |

#### 3.3.2 Knowledge API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/knowledge` | 摄入（异步 Operation） | KnowledgeService.ingest |
| GET | `/api/v1/knowledge` | 列表 | KnowledgeService.list_concepts |
| POST | `/api/v1/knowledge/search` | 检索 | KnowledgeService.search |
| GET | `/api/v1/knowledge/{kb_name}` | 知识库详情 | KnowledgeService |
| GET | `/api/v1/knowledge/{kb_name}/{concept_id}` | 概念详情 | KnowledgeService.get_concept |
| DELETE | `/api/v1/knowledge/{kb_name}` | 删除知识库 | KnowledgeService → AssetService |
| POST | `/api/v1/knowledge/{kb_name}/reindex` | 重建索引 | KnowledgeService.reindex |

#### 3.3.3 Skills API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/skills` | 注册（DRAFT） | SkillService.register |
| GET | `/api/v1/skills` | 列表 | SkillService.list_skills |
| POST | `/api/v1/skills/search` | 语义检索 | SkillService.search_skills |
| GET | `/api/v1/skills/{name}/{version}` | 详情 | SkillService.get_skill |
| POST | `/api/v1/skills/{name}/{version}/publish` | 发布 | SkillService.publish |
| POST | `/api/v1/skills/{name}/{version}/revoke` | 撤销 | SkillService.revoke |

#### 3.3.4 Memory API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/memories` | 添加 | MemoryService.add |
| POST | `/api/v1/memories/search` | 检索 | MemoryService.search |
| GET | `/api/v1/memories` | 列表 | MemoryService.list |
| GET | `/api/v1/memories/{memory_id}` | 详情 | MemoryService.get |
| PATCH | `/api/v1/memories/{memory_id}` | 更新 | MemoryService.update |
| DELETE | `/api/v1/memories/{memory_id}` | 删除 | MemoryService.delete |
| POST | `/api/v1/memories/clear` | 批量清除 | MemoryService.clear |
| GET | `/api/v1/memories/{memory_id}/history` | 历史 | MemoryService.history |

#### 3.3.5 Jobs API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/jobs` | 提交 | JobService.submit |
| GET | `/api/v1/jobs` | 列表 | JobService.list_jobs |
| GET | `/api/v1/jobs/{job_id}` | 详情 | JobService.get_job |
| POST | `/api/v1/jobs/{job_id}/cancel` | 取消 | JobService.cancel |
| POST | `/api/v1/jobs/{job_id}/retry` | 重试 | JobService.retry |
| GET | `/api/v1/jobs/{job_id}/result` | 结果 | JobService.get_result |
| GET | `/api/v1/jobs/{job_id}/attempts` | Attempt 列表 | JobService.get_attempts |

#### 3.3.6 Operations API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/operations` | 创建 | OperationService.create |
| GET | `/api/v1/operations` | 列表 | OperationService.list |
| GET | `/api/v1/operations/{op_id}` | 详情 | OperationService.get |
| POST | `/api/v1/operations/{op_id}/approve` | 审批 | OperationService.approve |
| POST | `/api/v1/operations/{op_id}/cancel` | 取消 | OperationService.cancel |

#### 3.3.7 Models API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/models` | 创建模型定义 | ModelManagementService.create_model |
| GET | `/api/v1/models` | 列表 | ModelManagementService.list_models |
| POST | `/api/v1/models/{model_id}/deployments` | 创建 Deployment | ModelManagementService.create_deployment |
| GET | `/api/v1/models/{model_id}/deployments` | Deployment 列表 | ModelManagementService.list_deployments |
| POST | `/api/v1/models/deployments/{dpl_id}/enable` | 启用 | ModelManagementService.enable |
| POST | `/api/v1/models/deployments/{dpl_id}/disable` | 禁用 | ModelManagementService.disable |
| POST | `/api/v1/models/profiles` | 创建 Profile | ModelManagementService.create_profile |
| GET | `/api/v1/models/profiles/{name}/resolve` | 解析路由 | ModelManagementService.resolve_profile |

#### 3.3.8 Configuration API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| GET | `/api/v1/configuration` | 获取有效配置 | ConfigurationService.get_effective |
| GET | `/api/v1/configuration/{scope}` | 按作用域获取 | ConfigurationService.get |
| PUT | `/api/v1/configuration/{scope}` | 设置（产生 Revision） | ConfigurationService.set |
| GET | `/api/v1/configuration/revisions` | Revision 历史 | ConfigurationService.list_revisions |
| POST | `/api/v1/configuration/revisions/{rev_id}/activate` | 激活 | ConfigurationService.activate |
| POST | `/api/v1/configuration/revisions/{rev_id}/rollback` | 回滚 | ConfigurationService.rollback |

#### 3.3.9 Security API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| POST | `/api/v1/security/tokens` | 签发 Token | AuthorizationService |
| DELETE | `/api/v1/security/tokens/{token_id}` | 撤销 Token | AuthorizationService |
| GET | `/api/v1/security/tokens` | Token 列表 | AuthorizationService |
| GET | `/api/v1/security/roles` | 角色列表 | AuthorizationService |
| POST | `/api/v1/security/secrets` | 创建 Secret | SecretService.create |
| GET | `/api/v1/security/secrets` | Secret 元数据列表 | SecretService.list |
| POST | `/api/v1/security/secrets/{name}/rotate` | 轮换 | SecretService.rotate |

#### 3.3.10 Audit API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| GET | `/api/v1/audit` | 查询审计事件 | AuditService.query |
| GET | `/api/v1/audit/export` | 导出 | AuditService.export |

#### 3.3.11 Instances API

| 方法 | 路径 | 说明 | 对应 Service |
|------|------|------|-------------|
| GET | `/api/v1/instances` | 实例列表 | InstanceRegistry |
| GET | `/api/v1/instances/{instance_id}` | 实例详情 | InstanceRegistry |

#### 3.3.12 Health API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 平台健康（无需认证） |

**合计：约 65 个端点**（v0.1.0 的 56 个 + 新增约 9 个 + 路径重组）

### 3.4 统一约定

在 OpenAPI spec 的 `components` 中定义：

#### 3.4.1 认证

```yaml
securitySchemes:
  BearerAuth:
    type: http
    scheme: bearer
    bearerFormat: opaque  # 非 JWT，数据库哈希校验
security:
  - BearerAuth: []
```

#### 3.4.2 通用 Header

| Header | 必需 | 说明 |
|--------|------|------|
| `Authorization: Bearer {token}` | 是 | 认证 |
| `X-Request-Id` | 否 | 请求追踪（自动生成如缺） |
| `X-Correlation-Id` | 否 | 跨服务关联 |
| `X-Idempotency-Key` | 否 | 幂等键（POST 操作） |

> **注意**：`X-Tenant-Id` / `X-Agent-Id` / `X-Scopes` **不再由调用方声明**，由 Token 解析得到。

#### 3.4.3 分页

```yaml
# 请求参数
page: integer  # 默认 1
page_size: integer  # 默认 20, 最大 100
sort: string  # 格式: field:asc|desc

# 响应包装
PageResponse:
  type: object
  properties:
    items: array
    total: integer
    page: integer
    page_size: integer
    has_next: boolean
```

#### 3.4.4 异步 Operation 响应

```yaml
AsyncOperationResponse:
  type: object
  properties:
    operation_id: string  # op_xxx
    resource_id: string   # ast_xxx / job_xxx
    status: string        # PENDING
    message: string
```

#### 3.4.5 时间格式

所有时间字段使用 ISO 8601 UTC：`2026-07-13T10:30:00Z`

### 3.5 v0.1.0 端点迁移映射

| v0.1.0 路径 | v0.2.0 路径 | 变化 |
|-------------|-------------|------|
| `/api/v1/storage/objects/{bucket}/{key}` | `/api/v1/assets` (创建) + DataMCP 受控访问 | 资产化，不直接操作 S3 |
| `/api/v1/storage/tables/*` | `/api/v1/assets` (type=table) + DataMCP | 资产化 |
| `/api/v1/storage/vectors/*` | 内部 Provider，不直接暴露 | 通过 Knowledge/Memory Service |
| `/api/v1/storage/kv/*` | 内部 Provider | 通过 Memory Service（临时态） |
| `/api/v1/storage/graph/*` | Experimental，保留但标记 | 不作为核心验收 |
| `/api/v1/compute/sql/` | DataMCP 受控访问 | 不直接暴露 |
| `/api/v1/compute/jobs/*` | `/api/v1/jobs/*` | JobService 一等资源 |
| `/api/v1/cognitive/memory/*` | `/api/v1/memories/*` | 资产化 |
| `/api/v1/metadata/tenants` | `/api/v1/security/tenants` | 归 Security |
| `/api/v1/metadata/users` | `/api/v1/security/users` | 归 Security |
| `/api/v1/metadata/tokens` | `/api/v1/security/tokens` | 归 Security |
| `/api/v1/metadata/secrets` | `/api/v1/security/secrets` | 归 Security |
| `/api/v1/metadata/asset-types` | 移除（v0.2.0 固定 3 类型 + Experimental） | — |
| `/api/v1/system/health` | `/api/v1/health` | 简化 |
| `/api/v1/system/nodes` | `/api/v1/instances` | Instance Registry |
| `/api/v1/system/metrics` | Control Center BFF 聚合 | 不直接暴露 |

### 3.6 评审标准

- [ ] OpenAPI spec 可通过 `swagger-cli validate` 校验；
- [ ] 所有端点有认证、错误响应、分页定义；
- [ ] 端点路径无冲突；
- [ ] v0.1.0 迁移映射表完整；
- [ ] 异步 Operation 端点返回 `operation_id`。

---

## 4. WP1-T04：统一资源 ID 与 URI 规范

> **SP：2 | 工日：2 | 依赖：T02 | 主笔：后端工程师 A**

### 4.1 目标

定义统一的资源 ID 生成规则和逻辑 URI 语法，确保物理路径不作为外部契约。

### 4.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/architecture/v0.2.0/resource-id-uri.md` | ID 前缀 + 生成规则 + URI grammar + 物理 ID 不外泄规则 |

### 4.3 ID 前缀规范

| 资源 | 前缀 | 生成规则 | 示例 |
|------|------|----------|------|
| Asset | `ast_` | 前缀 + ULID | `ast_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Job Run | `job_` | 前缀 + ULID | `job_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Job Attempt | `atm_` | 前缀 + ULID | `atm_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Artifact | `art_` | 前缀 + ULID | `art_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Operation | `op_` | 前缀 + ULID | `op_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Principal | `prn_` | 前缀 + ULID | `prn_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Tenant | `ten_` | 前缀 + ULID | `ten_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Model | `mdl_` | 前缀 + ULID | `mdl_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Deployment | `dpl_` | 前缀 + ULID | `dpl_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Binding | `bnd_` | 前缀 + ULID | `bnd_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Config Revision | `cfgr_` | 前缀 + ULID | `cfgr_01H8X7K2M3P4Q5R6S7T8V9W0X` |
| Audit Event | `aud_` | 前缀 + ULID | `aud_01H8X7K2M3P4Q5R6S7T8V9W0X` |

**ULID 选择理由**：26 字符 Crockford Base32，时间排序，无冲突，比 UUID 更可读。

### 4.4 逻辑 URI Grammar

```
lake://knowledge/{name}@{version}       # 知识库概念
lake://knowledge/{name}                 # 知识库（最新版本）
lake://skills/{name}@{version}          # Skill 版本
lake://skills/{name}                    # Skill（最新版本）
lake://memory/{memory_id}               # Memory 条目
lake://assets/{asset_id}                # 通用资产
lake://jobs/{job_id}                    # Job Run
lake://jobs/{job_id}/attempts/{atm_id}  # Job Attempt
lake://artifacts/{art_id}               # Artifact
model://{profile}                       # 模型 Profile（meeting-asr / knowledge-embedding / ...）
model://{profile}@{deployment_id}       # 具体 Deployment
secret://{scope}/{name}                 # Secret 引用
operation://{op_id}                     # Operation
```

### 4.5 物理 ID 不外泄规则

| 规则 | 说明 |
|------|------|
| S3 Key | 由 Server 根据 `ten_{tenant}/ast_{asset_id}/bnd_{binding_id}/{filename}` 生成，不作为 API 响应字段 |
| Lance URI | 由 Server 根据 `ten_{tenant}/ast_{asset_id}/vector` 生成，仅在 Binding 内部记录 |
| Iceberg Namespace | `ten_{tenant}.{asset_type}` 格式，由 Server 生成 |
| Ray Job ID | 内部映射，API 返回 `job_{ulid}`，不返回 Ray 原始 ID |
| PG 主键 | 内部自增或 ULID，API 返回逻辑 ID |

### 4.6 评审标准

- [ ] 所有资源类型有前缀定义；
- [ ] URI grammar 无歧义（可正则解析）；
- [ ] 物理 ID 不外泄规则覆盖全部引擎；
- [ ] 与 API v1 spec 中的 ID 格式一致。

---

## 5. WP1-T05：统一错误模型

> **SP：2 | 工日：2 | 依赖：T03 | 主笔：后端工程师 A**

### 5.1 目标

定义统一的错误响应格式和错误码枚举。

### 5.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/api-spec/v0.2.0/error-model.md` | 错误响应 schema + 错误码枚举 + 可重试性 |
| `docs/api-spec/v0.2.0/openapi.yaml` 补充 | `components.schemas.ErrorResponse` |

### 5.3 错误响应 Schema

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

### 5.4 错误码枚举

基于设计方案 §12.7，扩展为完整枚举：

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

### 5.5 评审标准

- [ ] 错误码覆盖设计方案 §12.7 全部 + 扩展场景；
- [ ] 每个错误码有明确 HTTP 状态码和可重试性；
- [ ] ErrorResponse schema 纳入 OpenAPI spec；
- [ ] `request_id` 在所有错误响应中存在。

---

## 6. WP1-T06：Operation / 事件 / 幂等规范

> **SP：2 | 工日：2 | 依赖：T03 | 主笔：后端工程师 B**

### 6.1 目标

定义 Operation 状态机、内部事件名和幂等键规则。

### 6.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/api-spec/v0.2.0/operation-events.md` | Operation 状态机 + 事件清单 + 幂等规则 |

### 6.3 Operation 状态机

```
PENDING ──→ APPROVAL_REQUIRED ──→ APPROVED ──→ RUNNING ──→ SUCCEEDED
  │              │                    │              │
  │              └──→ CANCELLED       │              └──→ FAILED
  │                                   │
  └──→ RUNNING (无需审批) ────────────┘
  
  任何状态 ──→ CANCELLED（由发起者或审批者取消）
```

状态转换规则：

| 当前状态 | 允许转换到 | 触发者 |
|----------|-----------|--------|
| PENDING | RUNNING | 系统（无需审批时自动） |
| PENDING | APPROVAL_REQUIRED | 系统（风险等级判定） |
| APPROVAL_REQUIRED | APPROVED | 审批人 |
| APPROVAL_REQUIRED | CANCELLED | 审批人 / 发起者 |
| APPROVED | RUNNING | 系统 |
| RUNNING | SUCCEEDED | 系统 |
| RUNNING | FAILED | 系统 |
| RUNNING | CANCELLED | 发起者（CANCELLING → CANCELLED） |

### 6.4 Operation 记录字段

| 字段 | 类型 | 说明 |
|------|------|------|
| operation_id | string | `op_{ulid}` |
| type | enum | `asset_delete` / `asset_reindex` / `skill_publish` / `skill_revoke` / `job_submit` / `model_reload` / `config_activate` / `config_rollback` / `secret_rotate` / `data_migration` / ... |
| target_resource | string | 逻辑 URI |
| initiator_id | string | `prn_{ulid}` |
| initiator_channel | enum | `rest` / `mcp` / `control_center` / `steward` / `system` |
| reason | string | 操作原因 |
| risk_level | enum | `LOW` / `MEDIUM` / `HIGH` |
| requires_approval | boolean | |
| approver_id | string? | `prn_{ulid}` |
| status | enum | 状态机 |
| result | json? | 执行结果 |
| failure_reason | string? | |
| audit_event_ids | string[] | 关联审计事件 |
| created_at / updated_at | timestamp | |

### 6.5 内部事件名清单

基于设计方案 §12.9：

| 事件名 | 触发 | 消费者 |
|--------|------|--------|
| `asset.created` | AssetService.create_asset | Outbox Worker |
| `asset.processing` | 资产进入 PROCESSING | Outbox Worker |
| `asset.ready` | 全部 Required Binding 完成 | Audit, Notification |
| `asset.degraded` | 可选 Binding 失败 | Audit, Reconciler |
| `asset.deleted` | 异步删除完成 | Audit |
| `job.submitted` | JobService.submit | Execution Backend |
| `job.running` | Execution Backend 开始执行 | Audit |
| `job.succeeded` | 执行成功 | Audit, Artifact 资产化 |
| `job.failed` | 执行失败 | Audit, Retry 判定 |
| `job.lost` | Reconciler 发现丢失 | Audit |
| `operation.approval_required` | Operation 需审批 | Control Center, Steward |
| `operation.succeeded` | Operation 成功 | Audit, 发起者通知 |
| `config.activated` | Configuration Revision 激活 | Instance Registry, 热更新 |
| `model.deployment_unhealthy` | ModelServing 健康检查失败 | Reconciler, Alert |

事件格式：

```json
{
  "event_id": "evt_{ulid}",
  "event_type": "asset.ready",
  "resource_id": "ast_{ulid}",
  "tenant_id": "ten_{ulid}",
  "timestamp": "2026-07-13T10:30:00Z",
  "payload": { ... },
  "correlation_id": "corr_{ulid}"
}
```

### 6.6 幂等键规则

| 规则 | 说明 |
|------|------|
| Header | `X-Idempotency-Key: {string}` |
| 适用操作 | 创建资产 / 摄入 Knowledge / 添加 Memory / 发布 Skill / 提交 Job / 删除资产 / 创建 Operation |
| 键范围 | 每个Principal 独立命名空间（相同 Principal + 相同 Key = 幂等） |
| 缓存 | PG 表 `idempotency_keys`：`(principal_id, key, request_hash, response, created_at)`，TTL 24h |
| 冲突处理 | 相同 Key + 不同 request body → `IDEMPOTENCY_CONFLICT` (409) |
| 相同 Key + 相同 request body | 返回缓存的原始响应 |

### 6.7 评审标准

- [ ] Operation 状态机无死锁状态；
- [ ] 事件名覆盖设计方案 §12.9 全部；
- [ ] 幂等规则覆盖设计方案 §12.6 全部操作；
- [ ] 事件格式包含 `event_id` / `correlation_id`。

---

## 7. WP1-T07：MCP 与 REST 共享语义方案

> **SP：2 | 工日：2 | 依赖：T02 | 主笔：后端工程师 B**

### 7.1 目标

定义 MCP tool → Application Service 的映射，消除 MCP 自编排，确保 MCP 与 REST 共享同一组 Service。

### 7.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/architecture/v0.2.0/mcp-service-mapping.md` | 3 MCP × 全部 tool → Service 映射表 + 改造方向 |

### 7.3 AssetMCP 映射（23 tools）

| MCP Tool | 当前实现 | v0.2.0 调用 Service | 改造方向 |
|----------|----------|---------------------|----------|
| `register_knowledge` | 自编排 S3+Lance+PG | KnowledgeService.ingest | 移除自编排，调用 Service |
| `ingest_knowledge` | 自编排 embed+link+S3 | KnowledgeService.ingest | 同上 |
| `search_knowledge` | 直接调 Lance | KnowledgeService.search | 同上 |
| `get_knowledge` | 直接调 S3 | KnowledgeService.get_concept | 同上 |
| `list_knowledge` | 直接调 PG | KnowledgeService.list | 同上 |
| `list_concepts` | 直接调 PG | KnowledgeService.list_concepts | 同上 |
| `delete_knowledge` | 自编排 S3+Lance+PG | AssetService.delete_asset | 异步 Operation |
| `add_memory` | 自编排 LLM+Lance+PG | MemoryService.add | 同上 |
| `search_memory` | 直接调 Lance | MemoryService.search | 同上 |
| `get_memory` | 直接调 PG | MemoryService.get | 同上 |
| `list_memory` | 直接调 PG | MemoryService.list | 同上 |
| `update_memory` | 直接调 PG | MemoryService.update | 同上 |
| `delete_memory` | 直接调 PG | MemoryService.delete | 同上 |
| `clear_memory` | 直接调 PG | MemoryService.clear | 同上 |
| `memory_history` | 直接调 PG | MemoryService.history | 同上 |
| `search_skill` | 直接调 Lance | SkillService.search_skills | 同上 |
| `register_skill` | 自编排 S3+Iceberg+Lance | SkillService.register | 同上 |
| `get_skill` | 直接调 S3 | SkillService.get_skill | 同上 |
| `list_skills` | 直接调 PG | SkillService.list_skills | 同上 |
| `delete_skill` | 自编排 S3+Iceberg+Lance | AssetService.delete_asset | 异步 Operation |
| `query_ontology` | 直接调 PG Graph | KnowledgeService（Experimental） | 标记 Experimental |
| `update_ontology` | 直接调 PG Graph | KnowledgeService（Experimental） | 标记 Experimental |
| `delete_ontology` | 直接调 PG Graph | KnowledgeService（Experimental） | 标记 Experimental |

### 7.4 DataMCP 映射（24 tools）

| MCP Tool | v0.2.0 调用 | 改造方向 |
|----------|-------------|----------|
| `query_table` | DataMCP → REST API（受控透传） | 保留透传，增加 Protected Namespace 校验 |
| `write_table` | DataMCP → REST API | 同上，破坏性操作需更严格权限 |
| `sql_query` | DataMCP → REST API | 保留 |
| `list_tables` / `describe_table` / `create_table` / `drop_table` | DataMCP → REST API | 保留，drop 需 Operation |
| `vector_search` | DataMCP → REST API | 保留只读 |
| `s3_get` / `s3_list` | DataMCP → REST API | 保留只读 |
| `s3_put` / `s3_delete` | DataMCP → REST API | **Protected Namespace 写保护**：不得覆盖 `ten_*/ast_*` 路径 |
| `kv_get` / `kv_set` / `kv_delete` / `kv_scan` | DataMCP → REST API | 保留，临时数据 |
| `graph_query` / `graph_update` | DataMCP → REST API | Experimental |
| `ray_submit_job` | **改为 JobService.submit** | 不直连 Ray，通过 JobService |
| `ray_job_status` | **改为 JobService.get_job** | 不直连 Ray |
| `ray_job_result` | **改为 JobService.get_result** | 不直连 Ray |
| `ray_job_cancel` | **改为 JobService.cancel** | 不直连 Ray |
| `ray_job_list` | **改为 JobService.list_jobs** | 不直连 Ray |
| `list_skill_jobs` | SkillService | 保留 |

**关键改造**：DataMCP 的 5 个 Ray 工具不再直连 Ray，统一改为调用 JobService。Ray Dashboard 不暴露给 Agent。

### 7.5 AdminMCP 映射（21 tools）

| MCP Tool | v0.2.0 调用 Service | 改造方向 |
|----------|---------------------|----------|
| `create_user` / `update_user` / `delete_user` / `list_users` | AuthorizationService | 通过 Operation Service |
| `create_tenant` / `update_tenant` / `delete_tenant` / `list_tenants` | AuthorizationService | 通过 Operation Service |
| `issue_token` / `revoke_token` / `list_tokens` | AuthorizationService | revoke 通过 Operation |
| `register_asset_type` / `unregister_asset_type` / `list_asset_types` | 移除（v0.2.0 固定类型） | 标记 Experimental |
| `get_platform_health` / `get_node_status` / `get_metrics` | InstanceRegistry + ReconciliationService | 只读 |
| `create_secret` / `update_secret` / `delete_secret` / `list_secrets` | SecretService | 通过 Operation Service |

### 7.6 共享 MCP 基础包

提取共享包 `LakeMindMCP/lakemind_mcp_common/`：

| 模块 | 职责 |
|------|------|
| `auth.py` | Token 解析 → SecurityContext（调用 AuthorizationService） |
| `client.py` | Control Plane REST Client（统一连接池、重试、Request ID） |
| `errors.py` | MCP 错误 → API 错误码映射 |
| `pagination.py` | MCP 分页参数 → API 分页参数 |
| `operation.py` | 异步 Operation 轮询辅助 |

### 7.7 评审标准

- [ ] 全部 68 个 MCP tool 有明确 Service 映射；
- [ ] 无 MCP tool 直接操作底层引擎（S3/Lance/PG/Ray）；
- [ ] DataMCP Ray 工具改为 JobService；
- [ ] AdminMCP 写操作全部通过 Operation Service；
- [ ] 共享 MCP 基础包设计合理。

---

## 8. WP1-T08：编写 ADR 1-15

> **SP：3 | 工日：3 | 依赖：T01-T07 | 主笔：架构师**

### 8.1 目标

编写 15 条架构决策记录，作为 v0.2.0 的设计决策锚点。

### 8.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `.agent/adr/ADR-001-lakemind-positioning.md` | LakeMind 定位 |
| `.agent/adr/ADR-002-postgres-source-of-truth.md` | PG 事实源 |
| `.agent/adr/ADR-003-four-planes.md` | 四平面架构 |
| `.agent/adr/ADR-004-mcp-adapter-only.md` | MCP 协议适配层 |
| `.agent/adr/ADR-005-asset-scope.md` | 资产范围 |
| `.agent/adr/ADR-006-asset-binding-consistency.md` | Binding + 最终一致性 |
| `.agent/adr/ADR-007-job-skill-attempt-artifact.md` | Job 分离 |
| `.agent/adr/ADR-008-ray-execution-backend.md` | Ray 为首选 Backend |
| `.agent/adr/ADR-009-model-config-control-plane.md` | ModelServing 配置归 Control Plane |
| `.agent/adr/ADR-010-control-center.md` | Control Center 取代 Monitor |
| `.agent/adr/ADR-011-steward-three-level.md` | Steward 三级治理 |
| `.agent/adr/ADR-012-gravitino-ranger-deferred.md` | Gravitino/Ranger 延后 |
| `.agent/adr/ADR-013-protected-namespace.md` | DataMCP Protected Namespace |
| `.agent/adr/ADR-014-config-revision.md` | 配置 Revision + Desired/Active |
| `.agent/adr/ADR-015-secret-reference.md` | Secret 引用 + 最小权限 |

### 8.3 ADR 模板

每条 ADR 使用以下格式：

```markdown
# ADR-XXX: 标题

> 状态：proposed → accepted  
> 日期：2026-07-XX  
> 决策者：[姓名]

## 背景

[为什么要做这个决策？当前什么问题需要解决？]

## 决策

[决策内容是什么？]

## 理由

[为什么选择这个方案？]

## 影响

[这个决策带来什么后果？对哪些组件有影响？]

## 替代方案

[考虑过但未选择的方案，及未选择的原因]

## 参考

[设计方案章节链接]
```

### 8.4 各 ADR 内容要点

| ADR | 背景 | 决策 | 影响 |
|-----|------|------|------|
| 001 | v0.1.0 文档中"平台不执行 Skill"与"Ray Job 一等能力"冲突 | LakeMind 是认知资产平台 + 受控 Job Runtime，非通用 Agent Runtime | 统一 Skill/Job/权限/产品边界 |
| 002 | 配置散落多处的多重事实源 | PG 为 Control Plane 和资产账本唯一事实源 | 引擎状态不作为存在性依据 |
| 003 | v0.1.0 无明确平面边界 | 四平面逻辑架构 | 代码依赖/身份/网络符合平面边界 |
| 004 | MCP 自编排底层操作 | MCP 降为协议适配层 | MCP 调用同一 Application Service |
| 005 | 资产类型不明确 | Knowledge/Skill/Memory 核心资产，Ontology Experimental | 不开放任意动态资产类型 |
| 006 | 跨存储无分布式事务 | Asset Binding + Outbox + Reconciler | 最终一致性可观测 |
| 007 | Ray 状态与 LakeMind Job 混合 | Skill/JobRun/Attempt/Artifact 分离 | PG 为 Job 事实源 |
| 008 | Ray 定位不清晰 | Ray 为首选 ExecutionBackend | 抽象避免 Ray 字段泄漏 |
| 009 | ModelServing 独立管理配置 | 配置归 Control Plane | ModelServing 只负责运行 |
| 010 | Monitor 是只读 Dashboard | Control Center 统一管理入口 | 管理员身份 + Operation |
| 011 | Steward 可能拥有宽泛权限 | 三级受控治理 | 高风险需审批 |
| 012 | 过早引入增加复杂度 | 延后到 v0.3.0+/企业版 | v0.2.0 用 PG 驱动 |
| 013 | DataMCP 可能破坏资产路径 | Protected Namespace | DataMCP 不得覆盖受管理路径 |
| 014 | 配置无版本控制 | Revision + Desired/Active | 配置变更可回滚 |
| 015 | Secret 可能明文存储或全量注入 | 引用 + 最小权限 | Job 只获声明 Secret |

### 8.5 评审标准

- [ ] 15 条 ADR 全部按模板编写；
- [ ] 每条 ADR 有背景/决策/理由/影响/替代方案；
- [ ] ADR 之间无矛盾；
- [ ] ADR 引用设计方案章节准确。

---

## 9. WP1-T09：消除文档定位冲突

> **SP：2 | 工日：2 | 依赖：T08 | 主笔：架构师**

### 9.1 目标

消除现有文档中"平台完全不执行 Skill"与"Ray Job 是平台一等能力"的冲突描述，统一为"受控 Job Runtime"表述。

### 9.2 需更新的文件清单

| 文件 | 冲突点 | 修正方向 |
|------|--------|----------|
| `AGENTS.md` §1 | "不是 Agent 执行平台" + "execute_skill 已移除" | 改为"不是通用 Agent Runtime，但提供受控 Job Runtime" |
| `AGENTS.md` §7 | "execute_skill 已移除 — 平台只存取不执行" | 改为"execute_skill 已移除，改为 JobService 受控执行" |
| `README.md` | 项目定位描述 | 与 AGENTS.md §1 对齐 |
| `README_agent.md` | Agent 接入描述 | 增加 Job 提交说明 |
| `.agent/DESIGN.md` | 设计规范中的定位 | 与设计方案 §2.2 对齐 |
| `docs/architecture.md` | 架构描述 | 更新为四平面引用 |
| `docs/mcp-tools.md` | MCP 工具数（AGENTS.md 说 18/17，实际 24/21） | 更新为实际数 |
| `docs/develop-guide.md` | 开发指南 | 增加 Application Service 层说明 |

### 9.3 统一表述

在所有文档中使用以下标准表述：

> **LakeMind 不是通用 Agent Runtime，不负责运行 Agent 的完整推理循环、业务决策和自主行为；但 LakeMind 提供受控 Job Runtime，用于执行 Agent 触发的、以 Skill 为定义的确定性或可复现任务。**

### 9.4 MCP 工具数修正

| MCP | AGENTS.md 记载 | 实际 | 修正为 |
|-----|---------------|------|--------|
| AssetMCP | 23 tools | 23 | 23（正确） |
| DataMCP | 18 tools | 24 | 24 |
| AdminMCP | 17 tools | 21 | 21 |

### 9.5 评审标准

- [ ] 全部 8 个文件已更新；
- [ ] 无残留"平台只存取不执行"表述；
- [ ] 无残留"execute_skill 已移除 — 平台只存取不执行"表述；
- [ ] MCP 工具数与代码一致；
- [ ] 全部文档使用统一表述。

---

## 10. WP1-T10：内部 Provider 契约定义

> **SP：1 | 工日：1 | 依赖：T02 | 主笔：后端工程师 B**

### 10.1 目标

将 v0.1.0 的 `protocols.py` 中 10 个 `typing.Protocol` 正式化为 v0.2.0 Provider 契约文档。

### 10.2 交付物

| 文件路径 | 内容 |
|----------|------|
| `docs/architecture/v0.2.0/provider-contracts.md` | 10 个 Provider 契约定义 |

### 10.3 Provider 契约清单

基于设计方案 §12.8 + 当前 `protocols.py`：

| Provider | v0.1.0 Protocol | v0.2.0 变化 | 用途 |
|----------|-----------------|-------------|------|
| ObjectStorageProvider | `ObjectStoragePlugin` | 保留，增加 `protected_prefix` 校验 | S3/SeaweedFS |
| TableStorageProvider | `TabularStoragePlugin` | 保留 | Iceberg |
| VectorIndexProvider | `VectorStoragePlugin` | 保留，增加 `embedding_space_id` 参数 | Lance/LanceDB |
| GraphProjectionProvider | `GraphStoragePlugin` | 保留，标记 Experimental | PG Graph |
| CacheProvider | `KVStoragePlugin` | 保留 | Valkey |
| ExecutionBackend | `DistributedComputePlugin` | **重命名 + 简化**：submit/cancel/get_status/get_logs/get_result | Ray |
| ModelProvider | `EmbeddingPlugin` + `LLMPlugin` | **合并**：chat/embed/asr/list_models/health | ModelServing |
| AuthorizationProvider | 无（新增） | 新增：authenticate/authorize/check_tenant | PG 驱动 |
| SecretProvider | 无（新增） | 新增：create/get_ref/resolve/rotate/list/log_usage | PG 加密 |
| ConfigurationProvider | 无（新增） | 新增：get/set/get_revision/activate/rollback/get_effective | PG 驱动 |

### 10.4 关键改造

1. **ExecutionBackend 简化**：v0.1.0 的 `DistributedComputePlugin` 有 7 个方法（submit/status/result/submit_skill_job/get_job_status/cancel_job/health），v0.2.0 简化为 5 个标准方法，`submit_skill_job` 和 `get_job_status` 合并到 JobService 层。

2. **ModelProvider 合并**：v0.1.0 的 `LLMPlugin` 无注册实现（vestigial），`EmbeddingPlugin` 仅 fastembed。v0.2.0 合并为 `ModelProvider`，由 ModelServing 统一实现 chat/embed/asr。

3. **新增 3 个 Provider**：AuthorizationProvider、SecretProvider、ConfigurationProvider 对应 v0.2.0 新增的 Control Plane 能力。

### 10.5 Provider 契约不外泄规则

- API 响应中不出现 `s3_key` / `lance_uri` / `ray_job_id` / `iceberg_namespace` 等物理标识；
- Provider 接口方法签名使用逻辑参数（`asset_id` / `binding_id`），物理路径由 Service 层解析；
- Provider 实现细节（SeaweedFS endpoint / Lance DB path / Ray cluster URL）不出现在 OpenAPI spec 中。

### 10.6 评审标准

- [ ] 10 个 Provider 契约全部定义；
- [ ] ExecutionBackend 简化为 5 方法；
- [ ] ModelProvider 合并 chat/embed/asr；
- [ ] 新增 3 个 Provider 有完整接口；
- [ ] 不外泄规则明确。

---

## 11. 日程计划

### 11.1 第 1 周（W1）

| 日 | 人员 | 任务 | 产出 |
|----|------|------|------|
| W1-D1 | 架构师 | T01 步骤 1.1：四平面定义 | 四平面总表 + 组件归属表初稿 |
| W1-D1 | 工程师 A | T03 准备：梳理 v0.1.0 全部 56 端点 | 端点清单 |
| W1-D1 | 工程师 B | T07 准备：梳理 68 个 MCP tool | Tool 清单 |
| W1-D2 | 架构师 | T01 步骤 1.2：Trust Boundary | `trust-boundary.md` |
| W1-D2 | 工程师 A | T03 起草：OpenAPI spec 骨架 + 通用约定 | `openapi.yaml` 骨架 |
| W1-D2 | 工程师 B | T07 起草：MCP → Service 映射表初稿 | 映射表初稿 |
| W1-D3 | 架构师 | T01 步骤 1.3：组件映射表 | `component-mapping.md` → **T01 完成** |
| W1-D3 | 工程师 A | T03 资产 + Knowledge + Skills 端点 | OpenAPI spec 扩展 |
| W1-D3 | 工程师 B | T07 DataMCP + AdminMCP 映射 | 映射表扩展 |
| W1-D4 | 架构师 | T02：12 Service 接口定义 | `application-services.md` → **T02 完成** |
| W1-D4 | 工程师 A | T03 Memory + Jobs + Operations + Models 端点 | OpenAPI spec 扩展 |
| W1-D4 | 工程师 B | T07 共享 MCP 基础包设计 → **T07 完成** | `mcp-service-mapping.md` |
| W1-D5 | 架构师 | T02 依赖图 + 评审 | T02 评审通过 |
| W1-D5 | 工程师 A | T03 Configuration + Security + Audit + Instances + Health 端点 → **T03 完成** | `openapi.yaml` 完整 |
| W1-D5 | 工程师 B | T10：Provider 契约定义 → **T10 完成** | `provider-contracts.md` |

### 11.2 第 2 周（W2）

| 日 | 人员 | 任务 | 产出 |
|----|------|------|------|
| W2-D1 | 工程师 A | T04：资源 ID 与 URI 规范 → **T04 完成** | `resource-id-uri.md` |
| W2-D1 | 工程师 B | T06：Operation / 事件 / 幂等规范 → **T06 完成** | `operation-events.md` |
| W2-D2 | 工程师 A | T05：错误模型 → **T05 完成** | `error-model.md` + OpenAPI 补充 |
| W2-D2 | 工程师 B | T08 协助：ADR-001 ~ ADR-005 起草 | 5 条 ADR 初稿 |
| W2-D3 | 架构师 | T08：ADR-006 ~ ADR-010 | 5 条 ADR |
| W2-D3 | 工程师 B | T08 协助：ADR-011 ~ ADR-015 起草 | 5 条 ADR 初稿 |
| W2-D4 | 架构师 | T08：ADR 全部评审 + 修订 → **T08 完成** | 15 条 ADR 定稿 |
| W2-D4 | 全员 | T01-T08 交叉评审 | 评审记录 |
| W2-D5 | 架构师 | T09：消除文档定位冲突 → **T09 完成** | 8 个文件更新 |
| W2-D5 | 全员 | **M0 门禁评审** | 评审通过 / 待修复项 |

### 11.3 门禁 M0 评审清单

评审在 W2-D5 下午进行，全员参与：

- [ ] `four-planes.md` — 四平面职责无重叠，组件归属完整
- [ ] `trust-boundary.md` — 调用规则无矛盾
- [ ] `component-mapping.md` — 覆盖 v0.1.0 全部模块
- [ ] `application-services.md` — 12 Service 接口完整，依赖无循环
- [ ] `openapi.yaml` — `swagger-cli validate` 通过，约 65 端点
- [ ] `resource-id-uri.md` — ID 前缀 + URI grammar 无歧义
- [ ] `error-model.md` — 错误码覆盖全部场景
- [ ] `operation-events.md` — 状态机无死锁，事件/幂等完整
- [ ] `mcp-service-mapping.md` — 68 tool 全映射，无自编排
- [ ] `provider-contracts.md` — 10 Provider 契约完整
- [ ] ADR-001 ~ ADR-015 — 全部按模板，无矛盾
- [ ] 文档冲突消除 — 无残留冲突表述
- [ ] MCP 工具数与代码一致

---

## 12. 交付物汇总

### 12.1 新增文件

```
docs/architecture/v0.2.0/
  ├── four-planes.md                    # T01
  ├── trust-boundary.md                 # T01
  ├── component-mapping.md              # T01
  ├── application-services.md           # T02
  ├── mcp-service-mapping.md            # T07
  ├── resource-id-uri.md                # T04
  └── provider-contracts.md             # T10

docs/api-spec/v0.2.0/
  ├── openapi.yaml                      # T03
  ├── README.md                         # T03
  ├── error-model.md                    # T05
  └── operation-events.md               # T06

.agent/adr/
  ├── ADR-001-lakemind-positioning.md   # T08
  ├── ADR-002-postgres-source-of-truth.md
  ├── ADR-003-four-planes.md
  ├── ADR-004-mcp-adapter-only.md
  ├── ADR-005-asset-scope.md
  ├── ADR-006-asset-binding-consistency.md
  ├── ADR-007-job-skill-attempt-artifact.md
  ├── ADR-008-ray-execution-backend.md
  ├── ADR-009-model-config-control-plane.md
  ├── ADR-010-control-center.md
  ├── ADR-011-steward-three-level.md
  ├── ADR-012-gravitino-ranger-deferred.md
  ├── ADR-013-protected-namespace.md
  ├── ADR-014-config-revision.md
  └── ADR-015-secret-reference.md
```

**合计：7 架构文档 + 4 API 文档 + 15 ADR = 26 个新文件**

### 12.2 修改文件

```
AGENTS.md                               # T09
README.md                               # T09
README_agent.md                         # T09
.agent/DESIGN.md                        # T09
docs/architecture.md                    # T09
docs/mcp-tools.md                       # T09
docs/develop-guide.md                   # T09
```

**合计：7 个修改文件**

---

## 13. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| API 端点数量估算偏差（65 → 实际可能 70+） | 低 | OpenAPI spec 可增量扩展，不阻塞 M0 |
| ADR 评审争议导致延迟 | 中 | 争议项标记 `proposed`，不阻塞 M0；后续 ADR 修订 |
| 四平面边界在 WP2 实现中发现不可行 | 中 | ADR 允许 v0.2.0 内部微调，记录修订理由 |
| MCP tool 映射遗漏 | 低 | T07 评审时逐 tool 核对 |
| 文档更新与代码不同步 | 低 | T09 在 W2 末尾集中处理，基于最新代码库 |

---

## 14. M0 门禁通过后的交付

WP1 完成后，以下产物可直接指导 WP2-WP9：

| 产物 | 指导的 WP | 用途 |
|------|----------|------|
| `application-services.md` | WP2-WP7 | Service 接口实现依据 |
| `openapi.yaml` | WP2, WP6 | REST API 实现 + Control Center BFF |
| `error-model.md` | WP2-WP9 | 统一错误处理 |
| `operation-events.md` | WP2, WP3, WP4 | Operation + Outbox + 幂等实现 |
| `mcp-service-mapping.md` | WP2 (MCP 改造) | MCP 降级为适配层 |
| `provider-contracts.md` | WP3, WP4, WP5 | Provider 抽象实现 |
| `resource-id-uri.md` | WP2-WP9 | ID 生成 + URI 解析 |
| ADR 1-15 | 全部 | 设计决策锚点 |

---

> **WP1 是 v0.2.0 的设计地基。地基不牢，上层皆摇。M0 门禁通过后方可进入阶段 B。**
