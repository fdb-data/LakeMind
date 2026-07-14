# LakeMind v0.2.0 资源 ID 与 URI 规范

> 日期：2026-07-13  
> 状态：accepted  
> 依据：[设计方案](../../../v0.2.0.design/LakeMind_v0.2.0_设计方案.md) §12.3-§12.4

---

## 1. ID 前缀规范

所有资源 ID 使用 `前缀 + ULID` 格式。ULID 为 26 字符 Crockford Base32，时间排序，无冲突。

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

### 1.1 ULID 选择理由

- 26 字符 Crockford Base32，比 UUID 更可读
- 时间排序（前 10 字符编码毫秒时间戳），数据库索引友好
- 128 位随机性，无冲突风险
- Python `ulid-py` / `python-ulid` 库支持

### 1.2 ID 正则校验

```
^ast_[0-9A-HJKMNP-TV-Z]{26}$
^job_[0-9A-HJKMNP-TV-Z]{26}$
^atm_[0-9A-HJKMNP-TV-Z]{26}$
^art_[0-9A-HJKMNP-TV-Z]{26}$
^op_[0-9A-HJKMNP-TV-Z]{26}$
^prn_[0-9A-HJKMNP-TV-Z]{26}$
^ten_[0-9A-HJKMNP-TV-Z]{26}$
^mdl_[0-9A-HJKMNP-TV-Z]{26}$
^dpl_[0-9A-HJKMNP-TV-Z]{26}$
^bnd_[0-9A-HJKMNP-TV-Z]{26}$
^cfgr_[0-9A-HJKMNP-TV-Z]{26}$
^aud_[0-9A-HJKMNP-TV-Z]{26}$
```

---

## 2. 逻辑 URI Grammar

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

### 2.1 URI 解析规则

| URI 模式 | 解析为 |
|----------|--------|
| `lake://knowledge/{name}` | KnowledgeService.get_concept(kb_name=name) |
| `lake://knowledge/{name}@{version}` | KnowledgeService.get_concept(kb_name=name, version=version) |
| `lake://skills/{name}@{version}` | SkillService.get_skill(name=name, version=version) |
| `lake://memory/{memory_id}` | MemoryService.get(memory_id) |
| `lake://assets/{asset_id}` | AssetService.get_asset(asset_id) |
| `lake://jobs/{job_id}` | JobService.get_job(job_id) |
| `model://{profile}` | ModelManagementService.resolve_profile(profile) |
| `secret://{scope}/{name}` | SecretService.get_ref(scope, name) |
| `operation://{op_id}` | OperationService.get(op_id) |

---

## 3. 物理 ID 不外泄规则

| 规则 | 说明 |
|------|------|
| S3 Key | 由 Server 根据 `ten_{tenant}/ast_{asset_id}/bnd_{binding_id}/{filename}` 生成，不作为 API 响应字段 |
| Lance URI | 由 Server 根据 `ten_{tenant}/ast_{asset_id}/vector` 生成，仅在 Binding 内部记录 |
| Iceberg Namespace | `ten_{tenant}.{asset_type}` 格式，由 Server 生成 |
| Ray Job ID | 内部映射，API 返回 `job_{ulid}`，不返回 Ray 原始 ID |
| PG 主键 | 内部自增或 ULID，API 返回逻辑 ID |

### 3.1 API 响应禁止字段

以下字段不得出现在任何 API 响应或 MCP tool 返回中：

- `s3_key` / `s3_bucket` / `s3_endpoint`
- `lance_uri` / `lance_db_path`
- `ray_job_id` / `ray_submission_id`
- `iceberg_namespace` / `iceberg_location`
- `pg_id` / `pg_serial`
- `db_connection_string`

---

## 4. 评审标准

- [x] 所有资源类型有前缀定义（12 种）
- [x] URI grammar 无歧义（可正则解析）
- [x] 物理 ID 不外泄规则覆盖全部引擎（S3 / Lance / Iceberg / Ray / PG）
- [x] 与 API v1 spec 中的 ID 格式一致（OpenAPI pattern 字段）
