# LakeMindServer

多模智能数据湖服务器平台。MVP 单机部署的 docker-compose 与全部组件配置在此目录。

## 目录结构

```
LakeMindServer/
  docker-compose.yml          # SeaweedFS + PostgreSQL + Valkey + Ray 单机编排
  .env.example                # 镜像/端口/凭据/内存（复制为 .env 后按需修改）
  config/
    seaweedfs/s3.json         # S3 网关身份
    versions.yaml             # 版本配套表
  scripts/
    verify_services.py        # 平台集成验证（S3 / Valkey）
    verify_scenario.py        # 端到端真实场景验证（5 数据域全覆盖）
  docs/                       # 手册目录
    installation.md           # 安装手册
    configuration.md          # 配置手册
    usage.md                  # 使用手册
    troubleshooting.md        # 故障排查手册
  data/                       # 数据目录（bind mount，运行时生成，.gitignore 忽略）
```

## 快速开始

```bash
cd LakeMindServer
cp .env.example .env
docker compose --env-file .env up -d
pip install boto3 redis
python scripts/verify_services.py
```

预期：3/3 PASS。

### 端到端真实场景验证

```bash
pip install pyiceberg[sql-sqlite] pylance lancedb duckdb daft pyarrow
python scripts/verify_scenario.py
```

预期：29/29 PASS。覆盖全部 5 个数据域：

| 数据域 | 引擎 | 验证内容 |
|--------|------|---------|
| 结构化数据 | Iceberg + S3 + DuckDB | 建表→写入20条日志→读取→聚合查询→失败率分析 |
| 知识/文档 RAG | S3 + Lance + LanceDB | 上传文档→向量化→语义检索→S3取原文 |
| 短期记忆 | Valkey | 会话状态→多轮更新→任务锁(NX)→缓存 |
| 长期记忆 | Lance + Iceberg | 向量写入→元信息小表→双表lance_uri关联→语义检索 |
| Skills | S3 + Iceberg + LanceDB | 技能文件存储→元信息编目→语义检索→加载代码 |

## 文档

| 文档 | 内容 |
|------|------|
| [安装手册](docs/installation.md) | 从零搭建：前置条件、镜像拉取、启动、验证 |
| [配置手册](docs/configuration.md) | 全部配置文件说明、参数调优、端口分配 |
| [使用手册](docs/usage.md) | 日常操作：启停、S3/Valkey 访问、数据管理 |
| [故障排查](docs/troubleshooting.md) | 常见问题诊断与解决 |

## 组件

| 组件 | 端口 | 用途 |
|------|------|------|
| SeaweedFS | 9333/8080/8888/8333 | 统一存储底座（S3 兼容） |
| PostgreSQL | 5432 | 统一元数据（Iceberg catalog + 图 + 用户/租户/Token） |
| Valkey | 6379 | 短期/工作记忆（TTL KV，Redis 兼容） |

嵌入式引擎（PyIceberg / Lance+LanceDB / DuckDB / fastembed）在 server-api 进程内运行。
Ray 3 节点已实现，Apache Ranger / Trino 生产阶段再引入。

## 版本

详见 [config/versions.yaml](config/versions.yaml)。
