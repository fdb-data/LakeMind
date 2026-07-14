# LakeMind API v1 规范

> 日期：2026-07-13  
> 状态：accepted

---

## 1. 概述

本目录包含 LakeMind v0.2.0 的完整 OpenAPI 3.1 规范。

- **规范文件**：`openapi.yaml`
- **端点数量**：约 65 个
- **认证**：Bearer Token（opaque，数据库哈希校验）
- **基础路径**：`/api/v1/`

## 2. 渲染

```bash
# 使用 swagger-ui 渲染
npx @redocly/cli preview-docs openapi.yaml

# 或使用 swagger-codegen
npx swagger-ui-express openapi.yaml
```

## 3. 校验

```bash
npx @redocly/cli lint openapi.yaml
```

## 4. 变更规则

- v0.2.0 内 API 路径不变更（设计冻结）
- 新增端点只能追加，不修改已有端点路径
- 字段新增必须可选（不破坏向后兼容）
- 错误码新增追加到枚举末尾

## 5. v0.1.0 端点迁移映射

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
