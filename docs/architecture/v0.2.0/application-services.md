# LakeMind v0.2.0 Application Service 边界

> 日期：2026-07-13  
> 状态：accepted  
> 依据：[设计方案](../../../reports/v0.2.0-design/LakeMind_v0.2.0_设计方案.md) §4.4

---

## 1. 概述

Control Plane 包含 12 个 Application Service，每个 Service 有明确单一职责，通过 Provider 抽象访问 Data & Index Plane，不直连底层引擎。

---

## 2. Service 接口定义

### 2.1 AssetService

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

### 2.2 KnowledgeService

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

### 2.3 SkillService

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

### 2.4 MemoryService

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

### 2.5 JobService

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

### 2.6 ModelManagementService

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

### 2.7 ConfigurationService

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

### 2.8 AuthorizationService

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

### 2.9 SecretService

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

### 2.10 OperationService

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

### 2.11 AuditService

```
职责：记录安全、管理、资产、Job 和模型操作
接口：
  record(event_type, principal, resource, action, result, details) → AuditEvent
  query(filters, page) → Page[AuditEvent]
  export(filters) → Stream  # 导出
依赖：PostgreSQL
```

### 2.12 ReconciliationService

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

---

## 3. 依赖关系图

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

### 3.1 拓扑排序（初始化顺序）

```
1. ConfigurationService      （无依赖）
2. SecretService             （无依赖）
3. AuthorizationService      （无依赖）
4. AuditService              （无依赖）
5. AssetService              （依赖 Provider）
6. KnowledgeService          （依赖 AssetService）
7. SkillService              （依赖 AssetService）
8. MemoryService             （依赖 AssetService）
9. ModelManagementService    （依赖 SecretService, ConfigurationService）
10. JobService               （依赖 SkillService, ModelManagementService, SecretService）
11. OperationService         （依赖 AuditService, AuthorizationService）
12. ReconciliationService    （依赖 AssetService, JobService, ConfigurationService）
```

---

## 4. 职责边界约束

| 约束 | 说明 |
|------|------|
| 接口不泄漏底层引擎细节 | 外部接口不出现 S3 Key / Lance Path / Ray Job ID / Iceberg Namespace |
| Service 间依赖无循环 | 除 Audit/Auth 横切关注外，Service 间依赖可拓扑排序 |
| 每个 Service 单一职责 | 一个 Service 不做另一个 Service 的事情 |
| 异步操作返回 Operation | delete / reindex / publish / activate 等异步操作返回 `Operation`，不直接返回结果 |
| Provider 通过依赖注入 | Service 不自行创建 Provider 实例，由 Control Plane 统一注入 |

---

## 5. 评审标准

- [x] 12 个 Service 接口签名完整
- [x] Service 间依赖无循环（除 Audit/Auth 横切）
- [x] 每个 Service 有明确单一职责
- [x] 接口不泄漏底层引擎细节（无 S3 Key / Lance Path / Ray Job ID 在外部接口）
- [x] 依赖图可拓扑排序
