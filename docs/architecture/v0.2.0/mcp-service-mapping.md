# LakeMind v0.2.0 MCP 与 REST 共享语义方案

> 日期：2026-07-13  
> 状态：accepted  
> 依据：[设计方案](../../../reports/v0.2.0-design/LakeMind_v0.2.0_设计方案.md) §4.5

---

## 1. 概述

MCP 降为协议适配层，全部 68 个 tool 映射到 Application Service，与 REST API 共享同一组 Service。消除 MCP 自编排底层引擎。

---

## 2. AssetMCP 映射（23 tools）

### 2.1 Knowledge（7 tools）

| MCP Tool | 当前实现 | v0.2.0 调用 Service | 改造方向 |
|----------|----------|---------------------|----------|
| `register_knowledge` | 自编排 S3+Lance+PG | KnowledgeService.ingest | 移除自编排，调用 Service |
| `ingest_knowledge` | 自编排 embed+link+S3 | KnowledgeService.ingest | 同上 |
| `search_knowledge` | 直接调 Lance | KnowledgeService.search | 同上 |
| `get_knowledge` | 直接调 S3 | KnowledgeService.get_concept | 同上 |
| `list_knowledge` | 直接调 PG | KnowledgeService.list | 同上 |
| `list_concepts` | 直接调 PG | KnowledgeService.list_concepts | 同上 |
| `delete_knowledge` | 自编排 S3+Lance+PG | AssetService.delete_asset | 异步 Operation |

### 2.2 Memory（8 tools）

| MCP Tool | 当前实现 | v0.2.0 调用 Service | 改造方向 |
|----------|----------|---------------------|----------|
| `add_memory` | 自编排 LLM+Lance+PG | MemoryService.add | 移除自编排 |
| `search_memory` | 直接调 Lance | MemoryService.search | 同上 |
| `get_memory` | 直接调 PG | MemoryService.get | 同上 |
| `list_memory` | 直接调 PG | MemoryService.list | 同上 |
| `update_memory` | 直接调 PG | MemoryService.update | 同上 |
| `delete_memory` | 直接调 PG | MemoryService.delete | 同上 |
| `clear_memory` | 直接调 PG | MemoryService.clear | 同上 |
| `memory_history` | 直接调 PG | MemoryService.history | 同上 |

### 2.3 Skill（5 tools）

| MCP Tool | 当前实现 | v0.2.0 调用 Service | 改造方向 |
|----------|----------|---------------------|----------|
| `search_skill` | 直接调 Lance | SkillService.search_skills | 同上 |
| `register_skill` | 自编排 S3+Iceberg+Lance | SkillService.register | 同上 |
| `get_skill` | 直接调 S3 | SkillService.get_skill | 同上 |
| `list_skills` | 直接调 PG | SkillService.list_skills | 同上 |
| `delete_skill` | 自编排 S3+Iceberg+Lance | AssetService.delete_asset | 异步 Operation |

### 2.4 Ontology（3 tools，Experimental）

| MCP Tool | 当前实现 | v0.2.0 调用 Service | 改造方向 |
|----------|----------|---------------------|----------|
| `query_ontology` | 直接调 PG Graph | KnowledgeService（Experimental） | 标记 Experimental |
| `update_ontology` | 直接调 PG Graph | KnowledgeService（Experimental） | 标记 Experimental |
| `delete_ontology` | 直接调 PG Graph | KnowledgeService（Experimental） | 标记 Experimental |

---

## 3. DataMCP 映射（24 tools）

### 3.1 Iceberg Tables（7 tools）

| MCP Tool | v0.2.0 调用 | 改造方向 |
|----------|-------------|----------|
| `query_table` | DataMCP → REST API（受控透传） | 保留透传，增加 Protected Namespace 校验 |
| `write_table` | DataMCP → REST API | 同上，破坏性操作需更严格权限 |
| `sql_query` | DataMCP → REST API | 保留 |
| `list_tables` | DataMCP → REST API | 保留 |
| `describe_table` | DataMCP → REST API | 保留 |
| `create_table` | DataMCP → REST API | 保留 |
| `drop_table` | DataMCP → REST API | 保留，drop 需 Operation |

### 3.2 Vector（1 tool）

| MCP Tool | v0.2.0 调用 | 改造方向 |
|----------|-------------|----------|
| `vector_search` | DataMCP → REST API | 保留只读 |

### 3.3 S3（4 tools）

| MCP Tool | v0.2.0 调用 | 改造方向 |
|----------|-------------|----------|
| `s3_get` | DataMCP → REST API | 保留只读 |
| `s3_list` | DataMCP → REST API | 保留只读 |
| `s3_put` | DataMCP → REST API | **Protected Namespace 写保护**：不得覆盖 `ten_*/ast_*` 路径 |
| `s3_delete` | DataMCP → REST API | **Protected Namespace 写保护** |

### 3.4 KV（4 tools）

| MCP Tool | v0.2.0 调用 | 改造方向 |
|----------|-------------|----------|
| `kv_get` | DataMCP → REST API | 保留，临时数据 |
| `kv_set` | DataMCP → REST API | 保留，临时数据 |
| `kv_delete` | DataMCP → REST API | 保留 |
| `kv_scan` | DataMCP → REST API | 保留 |

### 3.5 Graph（2 tools，Experimental）

| MCP Tool | v0.2.0 调用 | 改造方向 |
|----------|-------------|----------|
| `graph_query` | DataMCP → REST API | Experimental |
| `graph_update` | DataMCP → REST API | Experimental |

### 3.6 Ray Jobs（6 tools）— **关键改造**

| MCP Tool | v0.2.0 调用 | 改造方向 |
|----------|-------------|----------|
| `ray_submit_job` | **改为 JobService.submit** | 不直连 Ray，通过 JobService |
| `ray_job_status` | **改为 JobService.get_job** | 不直连 Ray |
| `ray_job_result` | **改为 JobService.get_result** | 不直连 Ray |
| `ray_job_cancel` | **改为 JobService.cancel** | 不直连 Ray |
| `ray_job_list` | **改为 JobService.list_jobs** | 不直连 Ray |
| `list_skill_jobs` | SkillService | 保留 |

**关键改造**：DataMCP 的 5 个 Ray 工具不再直连 Ray，统一改为调用 JobService。Ray Dashboard 不暴露给 Agent。

---

## 4. AdminMCP 映射（21 tools）

### 4.1 User（4 tools）

| MCP Tool | v0.2.0 调用 Service | 改造方向 |
|----------|---------------------|----------|
| `create_user` | AuthorizationService | 通过 OperationService |
| `update_user` | AuthorizationService | 通过 OperationService |
| `delete_user` | AuthorizationService | 通过 OperationService |
| `list_users` | AuthorizationService | 只读 |

### 4.2 Tenant（4 tools）

| MCP Tool | v0.2.0 调用 Service | 改造方向 |
|----------|---------------------|----------|
| `create_tenant` | AuthorizationService | 通过 OperationService |
| `update_tenant` | AuthorizationService | 通过 OperationService |
| `delete_tenant` | AuthorizationService | 通过 OperationService |
| `list_tenants` | AuthorizationService | 只读 |

### 4.3 Token（3 tools）

| MCP Tool | v0.2.0 调用 Service | 改造方向 |
|----------|---------------------|----------|
| `issue_token` | AuthorizationService | 直接 |
| `revoke_token` | AuthorizationService | 通过 OperationService |
| `list_tokens` | AuthorizationService | 只读 |

### 4.4 Asset Type（3 tools）

| MCP Tool | v0.2.0 调用 Service | 改造方向 |
|----------|---------------------|----------|
| `register_asset_type` | 移除（v0.2.0 固定类型） | 标记 Experimental |
| `unregister_asset_type` | 移除 | 标记 Experimental |
| `list_asset_types` | 移除 | 标记 Experimental |

### 4.5 Platform（3 tools）

| MCP Tool | v0.2.0 调用 Service | 改造方向 |
|----------|---------------------|----------|
| `get_platform_health` | InstanceRegistry + ReconciliationService | 只读 |
| `get_node_status` | InstanceRegistry | 只读 |
| `get_metrics` | InstanceRegistry | 只读 |

### 4.6 Tenant Secrets（4 tools）

| MCP Tool | v0.2.0 调用 Service | 改造方向 |
|----------|---------------------|----------|
| `create_secret` | SecretService | 通过 OperationService |
| `update_secret` | SecretService | 通过 OperationService |
| `delete_secret` | SecretService | 通过 OperationService |
| `list_secrets` | SecretService | 只读 |

---

## 5. 共享 MCP 基础包

提取共享包 `LakeMindMCP/lakemind_mcp_common/`：

| 模块 | 职责 |
|------|------|
| `auth.py` | Token 解析 → SecurityContext（调用 AuthorizationService） |
| `client.py` | Control Plane REST Client（统一连接池、重试、Request ID） |
| `errors.py` | MCP 错误 → API 错误码映射 |
| `pagination.py` | MCP 分页参数 → API 分页参数 |
| `operation.py` | 异步 Operation 轮询辅助 |

---

## 6. 评审标准

- [x] 全部 68 个 MCP tool 有明确 Service 映射（23 + 24 + 21 = 68）
- [x] 无 MCP tool 直接操作底层引擎（S3/Lance/PG/Ray）
- [x] DataMCP Ray 工具改为 JobService（5 个 ray_* 工具）
- [x] AdminMCP 写操作全部通过 OperationService
- [x] 共享 MCP 基础包设计合理（5 个模块）
