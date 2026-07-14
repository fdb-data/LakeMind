# LakeMind v0.2.0 基线版本清单

> 生成日期：2026-07-14
> 所有组件版本号固定，不允许遗漏或降级。

## 1. 基础设施组件

| 组件 | 基线版本 | 镜像/来源 | 说明 |
|------|---------|-----------|------|
| PostgreSQL | 16.4 | `lakemind/postgres-age:16.4` (基于 `postgres:16`) | 含 AGE 图扩展 |
| SeaweedFS | 3.101 | `chrislusf/seaweedfs:3.101` | S3 兼容对象存储 |
| Valkey | 8.0.9 | `valkey/valkey:8.0.9` | Redis 兼容 KV |
| Ray | 2.41.0 | `lakemind/ray:2.41.0-py3.12` | 分布式计算 |
| Python | 3.12 | `python:3.12-slim` | 运行时基础 |
| Node.js | 20 | `node:20-alpine` | 前端构建 |
| nginx | 1.26.3 | Debian trixie 仓库 | ControlCenter 反向代理 |
| supervisor | 4.2.5 | Debian trixie 仓库 | ControlCenter 进程管理 |

## 2. 数据平面（LakeMindServer）

| 组件 | 基线版本 | 说明 |
|------|---------|------|
| lakemind-server | 0.2.0 | REST API 网关 |
| FastAPI | 0.139.0 | Web 框架 |
| uvicorn | 0.50.0 | ASGI 服务器 |
| pydantic | 2.13.4 | 数据校验 |
| psycopg2-binary | 2.9.12 | PG 驱动 |
| boto3 | 1.43.40 | S3 客户端 |
| redis | 8.0.1 | Valkey 客户端 |
| pyarrow | 24.0.0 | Arrow 列式 |
| pyiceberg | 0.11.1 | Iceberg 表格式 |
| lancedb | 0.34.0 | 向量数据库 |
| pylance | 8.0.0 | Lance 列式 |
| duckdb | 1.5.4 | 即席 SQL |
| fastembed | 0.8.0 | 嵌入模型 |
| ray | 2.41.0 | 分布式计算 |
| alembic | 1.18.5 | 数据库迁移 |
| sqlalchemy | 2.0+ | ORM |
| ulid-py | 1.1.0 | ULID 生成 |
| cryptography | 49.0.0 | 加密 |
| httpx | 0.28.1 | HTTP 客户端 |
| numpy | 2.5.1 | 数值计算 |

## 3. 模型平面（LakeMindModelServing）

| 组件 | 基线版本 | 说明 |
|------|---------|------|
| lakemind-model-serving | 0.1.0 | 统一模型服务 |
| litellm | 1.91.1 | LLM 网关 |
| fastembed | 0.8.0 | 嵌入 (jinaai/jina-embeddings-v2-base-zh, dim=768) |
| funasr | 1.3.14 | 语音识别 (SenseVoice-Small) |
| torch | 2.13.0+cpu | PyTorch (CPU) |
| torchaudio | 2.11.0+cpu | 音频处理 |
| transformers | 5.13.1 | 模型推理 |
| tokenizers | 0.22.2 | 分词 |
| sentencepiece | 0.2.2 | 分词 |
| librosa | 0.11.0 | 音频分析 |
| numba | 0.66.0 | JIT 编译 |
| scipy | 1.18.0 | 科学计算 |
| numpy | 2.4.6 | 数值计算 |
| modelscope | 1.38.1 | 模型下载 |
| omegaconf | 2.3.1 | 配置管理 |
| hydra-core | 1.3.4 | 配置框架 |
| kaldiio | 2.18.1 | Kaldi I/O |
| jieba | 0.42.1 | 中文分词 |
| python-multipart | 0.32.0 | 文件上传 |

## 4. 运行平面 — 3 MCP

| 组件 | 基线版本 | 说明 |
|------|---------|------|
| lakemind-asset-mcp | 0.1.0 | 资产面 MCP (23 tools) |
| lakemind-data-mcp | 0.1.0 | 数据面 MCP (18 tools) |
| lakemind-admin-mcp | 0.1.0 | 管理面 MCP (17 tools) |
| mcp | 1.28.1 | MCP SDK |
| pydantic | 2.13.4 | 数据校验 |
| httpx | 0.28.1 | HTTP 客户端 |
| PyYAML | 6.0.3 | YAML 解析 |

## 5. 管理平面（LakeMindControlCenter — 单镜像）

| 组件 | 基线版本 | 说明 |
|------|---------|------|
| lakemind-control-center | v2 | 合并镜像 (前端 + BFF + Steward) |
| FastAPI | 0.115.6 | BFF + Steward Web 框架 |
| uvicorn | 0.34.0 | ASGI 服务器 |
| httpx | 0.28.1 | HTTP 客户端 |
| pydantic | 2.11.3 | 数据校验 |
| React | 18.3.0 | 前端框架 |
| react-dom | 18.3.0 | React DOM |
| react-router-dom | 6.26.0 | 路由 |
| antd | 5.20.0 | UI 组件库 |
| @ant-design/icons | 5.4.0 | 图标 |
| axios | 1.7.0 | HTTP 客户端 |
| vite | 5.4.0 | 构建工具 |
| TypeScript | 5.5.0 | 类型系统 |

## 6. 容器清单（13 个）

| 序号 | 容器名 | 镜像 | 端口 | 平面 |
|------|--------|------|------|------|
| 1 | lakemind-seaweedfs | chrislusf/seaweedfs:3.101 | 8333 | 数据 |
| 2 | lakemind-postgres | lakemind/postgres-age:16.4 | — | 数据 |
| 3 | lakemind-valkey | valkey/valkey:8.0.9 | — | 数据 |
| 4 | lakemind-server-api | lakemind/server-api:v2 | 10823 | 数据 |
| 5 | lakemind-ray-head | lakemind/ray:2.41.0-py3.12 | — | 数据 |
| 6 | lakemind-ray-worker-1 | lakemind/ray:2.41.0-py3.12 | — | 数据 |
| 7 | lakemind-ray-worker-2 | lakemind/ray:2.41.0-py3.12 | — | 数据 |
| 8 | lakemind-asset-mcp | lakemind/asset-mcp:0.1.0 | 8401 | 运行 |
| 9 | lakemind-data-mcp | lakemind/data-mcp:0.1.0 | 8402 | 运行 |
| 10 | lakemind-admin-mcp | lakemind/admin-mcp:0.1.0 | 8403 | 运行 |
| 11 | lakemind-model-serving | lakemind/model-serving:v2 | 10824 | 模型 |
| 12 | lakemind-control-center | lakemind/control-center:v2 | 3000 | 管理 |
| — | ~~lakemind-migrate~~ | 已移除 | — | — |
| — | ~~lakemind-steward~~ | 已移除（被 ControlCenter 取代） | — | — |
| — | ~~lakemind-monitor~~ | 已移除（被 ControlCenter 取代） | — | — |
| — | ~~lakemind-cc-bff~~ | 已合并入 control-center | — | — |
| — | ~~lakemind-cc-steward~~ | 已合并入 control-center | — | — |
| — | ~~lakemind-cc-frontend~~ | 已合并入 control-center | — | — |

## 7. 已清理组件

| 组件 | 原因 |
|------|------|
| migrate 容器 | 一次性迁移容器，迁移已应用，不再需要 |
| standalone steward (v0.1) | 功能已由 ControlCenter 内 Steward 取代 |
| standalone monitor (v0.1) | 功能已由 ControlCenter 前端取代 |
| cc-frontend / cc-bff / cc-steward 三容器 | 合并为单镜像 `lakemind/control-center:v2` |

## 8. 版本锁定原则

1. **基线版本不允许降级** — 任何组件升级需经验证后更新基线
2. **不盲目使用 latest** — 所有镜像使用明确版本号
3. **Python 依赖锁定** — pyproject.toml 中 `>=` 约束在构建时冻结为实际版本
4. **前端依赖锁定** — package.json 中 `^` 约束在构建时冻结为实际版本
5. **基线变更流程** — 变更需更新本文件 + 重新验证 + 更新验证报告
