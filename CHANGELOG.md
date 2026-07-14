# Changelog

## v0.2.0 (2025-07-14)

### Breaking Changes
- Auth: `LAKEMIND_V2_AUTH=1` enables new RBAC middleware (v0.1.0 API Key still works when unset)
- DataMCP: 5 Ray tools replaced by JobService (`/api/v1/jobs/*`)
- `execute_skill` removed — replaced by JobService.submit(skill_ref, inputs)

### New Features

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

#### WP6: Control Center
- LakeMindControlCenter/ directory (frontend + BFF + steward)
- BFF: FastAPI, session-based admin auth, Control Plane API proxy
- 10 pages: Overview, Assets, Jobs, ModelServing, Services, Configuration, Security, Operations, Audit, Steward
- WebSocket for real-time updates

#### WP7: Steward Governance
- Independent Service Identity (non-superadmin)
- 3-level action model: observe / low_risk auto / high_risk approval
- 6 inspection categories: service health, degraded assets, lost jobs, outbox, binding drift, config drift
- Policy-driven auto-action level

#### WP8: Meeting Agent Golden Path
- 3 Meeting Skills: meeting-asr, meeting-summary, knowledge-extract
- E2E tests: golden path (14 steps), security (6), consistency (7), recovery (6)

#### WP9: Engineering & Release
- Alembic migrations: 001-006 (baseline + control plane + assets + job runtime + models)
- Bootstrap script: admin principal + token + master key
- v0.1→v0.2 migration tool
- L0-L9 verification script

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
