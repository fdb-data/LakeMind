# LakeMind v0.2.0 组件映射表

> 日期：2026-07-13  
> 状态：accepted  
> 依据：代码库勘察结果 + [设计方案](../../../v0.2.0.design/LakeMind_v0.2.0_设计方案.md) §4.2

---

## 1. v0.1.0 代码模块 → v0.2.0 平面归属

| v0.1.0 模块 | v0.2.0 归属 | 改造方向 |
|-------------|-------------|----------|
| `app.py` (FastAPI + 路由) | Access Plane | 路由保留，认证中间件升级为 SecurityContext 解析 |
| `auth.py` (API Key 比较) | Access Plane → Control Plane | 替换为 SecurityContext 解析 → AuthorizationService |
| `config.py` (YAML 加载) | Control Plane | 替换为 ConfigurationService + Bootstrap |
| `engines.py` (引擎初始化) | Control Plane → Data Plane | Provider 工厂保留，初始化由 Control Plane 管理 |
| `api/objects.py` (5 endpoints) | Access Plane | 路由保留，handler 改为调用 AssetService |
| `api/tables.py` (7 endpoints) | Access Plane | 路由保留，handler 改为调用 AssetService (type=table) |
| `api/vectors.py` (6 endpoints) | Access Plane | 内部 Provider，不直接暴露；通过 Knowledge/Memory Service |
| `api/kv.py` (4 endpoints) | Access Plane | 内部 Provider；通过 Memory Service（临时态） |
| `api/graph.py` (5 endpoints) | Access Plane | Experimental，保留但标记 |
| `api/sql.py` (1 endpoint) | Access Plane | DataMCP 受控访问，不直接暴露 |
| `api/jobs.py` (6 endpoints) | Access Plane | 改为 `/api/v1/jobs/*`，调用 JobService |
| `api/memory.py` (8 endpoints) | Access Plane | 改为 `/api/v1/memories/*`，调用 MemoryService |
| `api/metadata.py` (14 endpoints) | Access Plane | 拆分：用户/租户/Token → Security API；asset-types → 移除 |
| `api/secrets.py` (4 endpoints) | Access Plane | 改为 `/api/v1/security/secrets`，调用 SecretService |
| `api/system.py` (3 endpoints) | Access Plane | health → `/api/v1/health`；nodes → `/api/v1/instances`；metrics → BFF |
| `api/llm.py` (未挂载) | Execution Plane | 已移至 ModelServing，不挂载 |
| `api/embedding.py` (未挂载) | Execution Plane | 已移至 ModelServing，不挂载 |
| `plugins/protocols.py` (11 Protocol) | Data Plane 契约 | 正式化为 Provider 契约（详见 [provider-contracts.md](./provider-contracts.md)） |
| `plugins/registry.py` | Data Plane | Provider 注册表 |
| `plugins/storage/seaweedfs.py` | Data & Index Plane | 保留，通过 ObjectStorageProvider 抽象被调用 |
| `plugins/storage/iceberg.py` | Data & Index Plane | 保留，通过 TableStorageProvider 抽象被调用 |
| `plugins/storage/lance.py` | Data & Index Plane | 保留，通过 VectorIndexProvider 抽象被调用 |
| `plugins/storage/valkey.py` | Data & Index Plane | 保留，通过 CacheProvider 抽象被调用 |
| `plugins/storage/graph.py` | Data & Index Plane | 保留，Experimental |
| `plugins/storage/metadata.py` | Data & Index Plane | 保留，PG 驱动 |
| `plugins/cognitive/memory/basic.py` | Control Plane → Data Plane | MemoryService 调用 MemoryProvider；memory_history 表保留 |
| `plugins/cognitive/embedding.py` | Execution Plane | 归 ModelServing（fastembed） |
| `plugins/cognitive/llm.py` | Execution Plane | 移除（归 ModelServing litellm） |
| `plugins/compute/duckdb.py` | Data & Index Plane | 保留，即席计算 |
| `plugins/compute/ray.py` | Execution Plane | Ray compute 保留为 ExecutionBackend 实现 |

---

## 2. MCP 服务器映射

| MCP 服务器 | v0.1.0 位置 | v0.2.0 平面 | 工具数 | 改造方向 |
|-----------|-------------|-------------|--------|----------|
| LakeMindAssetMCP | LakeMindMCP/LakeMindAssetMCP/ | Access Plane | 23 | 降为协议适配层，调用 Application Service |
| LakeMindDataMCP | LakeMindMCP/LakeMindDataMCP/ | Access Plane | 24 | 受控数据访问，Ray 工具改为 JobService |
| LakeMindAdminMCP | LakeMindMCP/LakeMindAdminMCP/ | Access Plane | 21 | 写操作通过 OperationService |

---

## 3. 数据库表映射

| v0.1.0 表 | v0.2.0 归属 | 改造方向 |
|-----------|-------------|----------|
| `tenants` | Control Plane | 保留，扩展字段 |
| `users` | Control Plane | 保留，扩展字段 |
| `tokens` | Control Plane | 保留，改为哈希存储 |
| `asset_types` | Control Plane | 移除（v0.2.0 固定 3 类型 + Experimental） |
| `tenant_secrets` | Control Plane | 保留，扩展为 SecretService |
| `secret_access_log` | Control Plane | 保留，归 AuditService |
| `ray_jobs` | Control Plane | 保留，扩展为 JobService 事实源 |
| `graph_nodes` | Data & Index Plane | 保留，Experimental |
| `graph_edges` | Data & Index Plane | 保留，Experimental |
| `memory_history` | Data & Index Plane | 保留，MemoryService 使用 |
| `iceberg_tables` | Data & Index Plane | 保留，Iceberg catalog |
| `iceberg_namespace_properties` | Data & Index Plane | 保留，Iceberg catalog |

---

## 4. Docker 容器映射

| 容器 | v0.2.0 平面 | 改造方向 |
|------|-------------|----------|
| lakemind-server | Access + Control | 拆分路由层和 Service 层 |
| lakemind-asset-mcp | Access | 降为协议适配层 |
| lakemind-data-mcp | Access | 受控数据访问 |
| lakemind-admin-mcp | Access | 写操作通过 OperationService |
| lakemind-steward | Control | 受控治理 Agent |
| lakemind-monitor → lakemind-control-center | Access | BFF + 前端 |
| lakemind-model-serving | Execution | 配置归 Control Plane |
| postgres | Data & Index | 保留 |
| seaweedfs-master | Data & Index | 保留 |
| seaweedfs-volume | Data & Index | 保留 |
| seaweedfs-filer | Data & Index | 保留 |
| valkey | Data & Index | 保留 |
| ray-head | Execution | 保留 |
| ray-worker (×2) | Execution | 保留 |

---

## 5. 评审标准

- [x] 组件映射表覆盖 v0.1.0 全部代码模块（app.py / auth.py / config.py / engines.py / api/*.py / plugins/**/*.py）
- [x] 组件映射表覆盖全部 MCP 服务器
- [x] 组件映射表覆盖全部数据库表
- [x] 组件映射表覆盖全部 Docker 容器
- [x] 每个组件有且仅有一个平面归属
