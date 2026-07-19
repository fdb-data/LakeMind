# Changelog

## v0.2.0 (2026-07-19)

### Breaking Changes
- **LakeMindSteward/ + LakeMindMonitor/ 目录已删除** — 合并迁入 `LakeMindControlCenter/`（Steward 作为内嵌组件运行于 :3002，Monitor 仪表板迁为 Mission Control 页面）
- Auth: `LAKEMIND_V2_AUTH=1` enables new RBAC middleware (v0.1.0 API Key still works when unset)
- DataMCP: 5 Ray tools replaced by JobService (`/api/v1/jobs/*`)
- `execute_skill` removed — replaced by JobService.submit(skill_ref, inputs)

### New Features

#### ControlCenter（统一管理入口）
- LakeMindControlCenter/ 目录（前端 nginx :3000 + BFF FastAPI :3001 + Steward LangGraph :3002）
- 10 页面：Overview, Assets, Jobs, ModelServing, Services, Configuration, Security, Operations, Audit, Steward
- Mission Control：11 指标卡（统一了 v0.1.0 的 Monitor 仪表板）
- 模型配置与路由管理：Definition/Deployment/Profile/Route CRUD + 部署检测（Test 按钮）
- WebSocket for real-time updates

#### 模型管理（两层架构）
- Definition（逻辑层）+ Deployment（物理层），1:N 关系
- Profile 路由：model_profiles + model_routes 表，profile→deployment 映射（含 priority/is_fallback/tenant_id）
- 部署检测：POST /models/deployments/{id}/test — 按 model_type 发探测请求
- enable/disable 同时设置 status + desired_state

#### Meeting Agent v0.2.0（全链路验证通过）
- 浏览器录音 → ASR → 转写 → 纪要 → 知识 全链路走 MCP
- 133 chunks → 31 ASR SUCCEEDED → 30 段转写 → 6 版纪要 → 7 条知识 → REVIEW_REQUIRED
- 录音分片间隔 20 秒，实时纪要/知识（每 6 chunk 触发）
- 录音回放组件（ChunkPlayer），3 栏工作台（转写|纪要|知识）
- Skill v0.2.4：ASR timeout=300s, LLM 6 次重试, litellm Router timeout=120s

#### Bug 修复（ControlCenter 数据空白）
- Bug-6: security.py capabilities 修复
- Bug-7~13: BFF tenant_id, job_service ray_jobs 查询, platform_admin 跨租户, instances 注册心跳, monitoring 指标采集, ModelServing /models/definitions

#### WP2: Control Plane & Security
- RBAC: 5 builtin roles, 26 actions, SecurityContext + middleware
- Token management: SHA-256 hashed tokens, issue/revoke/list
- Tenant isolation: S3/Lance/Iceberg/Valkey key resolution
- Protected namespace: `lake://` scheme guard
- Configuration service: schema-validated, revision-based, rollback
- Instance registry: heartbeat + Desired/Active revision tracking
- Secret management: AES-256-GCM encryption, rotation, minimal injection
- Audit service: queryable audit log with export
- Operation service: state machine (DRAFT→APPROVAL_REQUIRED→APPROVED→RUNNING→SUCCEEDED/FAILED)
- Outbox: SKIP LOCKED + exponential backoff event processing
- Docker network isolation: `internal` network

#### WP3: Asset Runtime
- Asset state machine: CREATED→INITIALIZING→READY→DEGRADED→DELETING→DELETED
- AssetService: CRUD + bindings + lineage + reindex
- KnowledgeService: ingest/search/reindex (OKF format)
- SkillService: register/validate/publish/revoke (PUBLISHED-only execution)
- MemoryService: mem0-style 8 methods (add/search/get/list/update/delete/clear/history)
- ReconciliationService: scan assets/jobs/config for drift

#### WP4: Job Runtime
- Job schema: job_runs + job_attempts + job_artifacts
- Job state machine: SUBMITTED→QUEUED→RUNNING→SUCCEEDED/FAILED/TIMED_OUT/CANCELLED/LOST
- JobService: submit/cancel/retry/get_result/get_attempts
- ExecutionBackend Protocol + RayExecutionBackend
- JobSyncService: status sync + startup recovery + timeout detection
- JobArtifactService: create/list/assetize (Artifact → Knowledge/Memory)
- Resource quota: Skill default + tenant limit + job override
- Idempotency key support

#### WP5: ModelServing Management
- 5 model tables: definitions, deployments, profiles, routes, embedding_spaces
- ModelManagementService: CRUD + resolve_profile + enable/disable + YAML import
- Secret Ref replacement (no plaintext API keys)
- Config revision tracking for model changes

#### WP7: Steward Governance
- Independent Service Identity (non-superadmin)
- 3-level action model: observe / low_risk auto / high_risk approval
- 6 inspection categories: service health, degraded assets, lost jobs, outbox, binding drift, config drift
- Policy-driven auto-action level

### Infrastructure Changes
- 容器从 13 个（v0.1.0: 含独立 steward + monitor）→ 12 平台容器（v0.2.0: control-center 统一）
- 端口 3000 从 Monitor 变为 ControlCenter
- 端口 8500（Steward）内化为 ControlCenter :3002
- 5 个自研镜像：postgres-age, server-api, mcp-suite, model-serving, control-center

### Database Migrations
- 001_initial_schema: v0.1.0 baseline (10 tables)
- 002_control_plane: 12 CP tables + seed roles/tenant
- 003_asset_core: assets/bindings/lineage/reconciler
- 004_asset_types: knowledge_meta/skill_meta/memory_meta
- 005_job_runtime: job_runs/job_attempts/job_artifacts
- 006_model_management: model_definitions/deployments/profiles/routes/embedding_spaces

### Dependencies Added
- alembic>=1.13
- sqlalchemy>=2.0
- ulid-py>=2.0

---

## v0.1.0 (2025-07-12)

### Initial Release
- MVP：13 容器、10 引擎、58 MCP 工具、Ray 分布式计算
- 3 MCP 服务：AssetMCP (23 tools) + DataMCP (24 tools) + AdminMCP (21 tools)
- LakeMindServer：REST API 网关 (40+ 路径) + 10 引擎
- LakeMindModelServing：litellm + fastembed + FunASR
- LakeMindSteward + LakeMindMonitor（v0.2.0 已合并迁入 ControlCenter）
- examples/meeting-agent + examples/lakemind-connector
- L0-L9 验证：297/297 PASS
