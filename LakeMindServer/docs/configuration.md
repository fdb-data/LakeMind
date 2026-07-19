# 配置手册

> **⚠️ 部分内容过期**：本文档仍包含 Apache Gravitino 相关配置。Gravitino 已被 PostgreSQL 16 替代（PG SQL catalog）。相关内容仅作历史参考。

LakeMindServer 全部配置文件的说明与调优指引。

---

## 1. 配置文件总览

```
LakeMindServer/
  .env                      # 环境变量（从 .env.example 复制）
  config/
    seaweedfs/s3.json       # SeaweedFS S3 网关身份
    versions.yaml           # 版本配套表（只读参考）
  docker-compose.yml        # 服务编排（一般不改，通过 .env 调参）
  data/                     # 数据目录（bind mount，运行时生成）
```

配置优先级：`.env` 环境变量 > `docker-compose.yml` 默认值。

---

## 2. `.env` 环境变量详解

### 2.1 SeaweedFS

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SEAWEEDFS_IMAGE` | `chrislusf/seaweedfs:latest` | 镜像地址。建议固定为 `chrislusf/seaweedfs:4.37` |
| `SEAWEEFS_MASTER_PORT` | 9333 | Master 节点端口（拓扑管理） |
| `SEAWEEFS_VOLUME_PORT` | 8080 | Volume 节点端口（数据读写） |
| `SEAWEEFS_FILER_PORT` | 8888 | Filer 端口（文件目录接口） |
| `SEAWEEFS_S3_PORT` | 8333 | **S3 Gateway 端口（主要使用）** |
| `S3_ENDPOINT` | `http://localhost:8333` | S3 端点 URL（供 boto3 / PyIceberg / Lance 使用） |
| `S3_ACCESS_KEY` | admin | S3 Access Key，须与 `s3.json` 一致 |
| `S3_SECRET_KEY` | admin123456 | S3 Secret Key，须与 `s3.json` 一致 |

> **注意**：变量名中是 `SEAWEEFS`（单个 F），这是历史命名，保持一致即可。

**S3 端点供容器内访问时**用 `http://lakemind-seaweedfs:8333`（容器名），供宿主机访问用 `http://localhost:8333`。

### 2.2 Apache Gravitino

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GRAVITINO_IMAGE` | `apache/gravitino:1.3.0` | 镜像地址 |
| `GRAVITINO_PORT` | 8090 | Gravitino REST API 端口 |
| `GRAVITINO_ICEBERG_REST_PORT` | 9001 | Iceberg REST Catalog 协议端口 |
| `GRAVITINO_MEM` | `-Xms1g -Xmx2g -XX:MaxMetaspaceSize=512m` | JVM 内存参数 |

**内存调优建议：**

| 场景 | GRAVITINO_MEM |
|------|---------------|
| MVP / 开发 | `-Xms1g -Xmx2g -XX:MaxMetaspaceSize=512m`（默认） |
| 元数据较多 | `-Xms2g -Xmx4g -XX:MaxMetaspaceSize=1g` |
| 低内存机器 | `-Xms512m -Xmx1g -XX:MaxMetaspaceSize=256m` |

### 2.3 Valkey

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VALKEY_IMAGE` | `valkey/valkey:8.0` | 镜像地址 |
| `VALKEY_PORT` | 6379 | Redis 兼容端口 |
| `VALKEY_PASSWORD` | （空） | 访问密码。**生产环境必须设置** |

### 2.4 嵌入式引擎

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LANCE_DB_URI` | `lance:///data/lance` | Lance 数据目录 URI |

嵌入式引擎（PyIceberg / Lance / LanceDB / DuckDB / Daft）不在容器中运行，通过以下方式访问平台：
- **S3**：使用 `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY`
- **Valkey**：使用 `VALKEY_HOST` / `VALKEY_PORT` / `VALKEY_PASSWORD`
- **Gravitino**：使用 `GRAVITINO_URI`（默认 `http://localhost:8090`）

---

## 3. `config/seaweedfs/s3.json` — S3 网关身份

```json
{
  "identities": [
    {
      "name": "admin",
      "credentials": [
        {
          "accessKey": "admin",
          "secretKey": "admin123456"
        }
      ],
      "actions": ["Admin", "Read", "Write", "List", "Tagging", "Delete"]
    }
  ]
}
```

### 修改 S3 凭据

1. 编辑 `s3.json`，修改 `accessKey` / `secretKey`。
2. 同步修改 `.env` 中的 `S3_ACCESS_KEY` / `S3_SECRET_KEY`。
3. 重启 SeaweedFS：
   ```bash
   docker compose restart seaweedfs
   ```

### 添加新用户

在 `identities` 数组中追加：

```json
{
  "name": "agent_reader",
  "credentials": [
    {"accessKey": "reader", "secretKey": "reader_pass"}
  ],
  "actions": ["Read", "List"]
}
```

---

## 4. `config/versions.yaml` — 版本配套表

此文件为只读参考，记录所有组件的实测版本与兼容性矩阵。详见文件内注释。

升级组件时：
1. 修改 `.env` 中的镜像 tag。
2. `docker compose pull && docker compose up -d`。
3. 重跑 `python ../scripts/verify_full.py`。
4. 更新 `versions.yaml` 中的版本号。

---

## 5. `docker-compose.yml` 编排说明

### 5.1 网络

所有容器在 `lakemind` bridge 网络内，可通过容器名互访：
- `lakemind-seaweedfs:8333`（S3）
- `lakemind-gravitino:8090`（REST）
- `lakemind-valkey:6379`（Redis 协议）

### 5.2 数据卷（bind mount）

| 服务 | 宿主机路径 | 容器内路径 |
|------|-----------|-----------|
| seaweedfs | `./data/seaweedfs` | `/data` |
| gravitino | `./data/gravitino` | `/gravitino/data` |
| valkey | `./data/valkey` | `/data` |

数据直接落在 `LakeMindServer/data/` 下，可随时查看、备份、清理。

### 5.3 重启策略

三个服务均设为 `restart: unless-stopped`，即：
- 容器异常退出会自动重启。
- `docker compose down` 不会自动重启。
- `docker compose stop` 后不会自动重启（需手动 `start`）。

### 5.4 依赖关系

```
gravitino depends_on seaweedfs
```

Gravitino 启动前会先启动 SeaweedFS。Valkey 无依赖，独立启动。

---

## 6. 端口分配一览

| 端口 | 服务 | 用途 | 容器内 |
|------|------|------|--------|
| 9333 | SeaweedFS | Master | 9333 |
| 8080 | SeaweedFS | Volume | 8080 |
| 8888 | SeaweedFS | Filer | 8888 |
| 8333 | SeaweedFS | **S3 Gateway** | 8333 |
| 8090 | Gravitino | **REST API** | 8090 |
| 9001 | Gravitino | Iceberg REST Catalog | 9001 |
| 6379 | Valkey | **Redis 兼容** | 6379 |

**端口冲突处理**：修改 `.env` 中对应变量即可，无需改 `docker-compose.yml`。

---

## 7. 生产环境配置差异

MVP 与生产环境的关键配置差异（供参考，MVP 阶段不需要执行）：

| 项 | MVP | 生产 |
|----|-----|------|
| Gravitino 后端 | H2（内嵌） | MySQL |
| Gravitino Iceberg REST | 无 JDBC 后端 | MySQL/PostgreSQL |
| Valkey 密码 | 空 | 必须设置 |
| S3 凭据 | admin/admin123456 | 强密码 + 多用户 |
| SeaweedFS | 单节点 | 多节点 + 副本 |
| 权限审计 | 无 | Apache Ranger |
| 分布式计算 | 无 | Ray |
| 即席查询引擎 | 无 | Trino |
