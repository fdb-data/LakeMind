# 使用手册

LakeMindServer 平台的日常操作指南：启动停止、服务访问、数据管理、验证脚本使用。

---

## 1. 启动与停止

所有命令在 `LakeMindServer/` 目录下执行。

### 1.1 启动

```bash
docker compose --env-file .env up -d
```

### 1.2 查看状态

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 1.3 查看日志

```bash
# 全部服务
docker compose logs -f

# 单个服务
docker compose logs -f seaweedfs
docker compose logs -f gravitino
docker compose logs -f dragonfly

# 最近 100 行
docker compose logs --tail 100 gravitino
```

### 1.4 停止（保留数据）

```bash
docker compose stop
```

容器停止但数据卷保留。重新启动：

```bash
docker compose start
```

### 1.5 停止并删除容器（保留数据）

```bash
docker compose down
```

数据卷（`data/` 目录）保留。重新 `up -d` 即恢复。

### 1.6 停止并删除容器和数据（清空全部）

```bash
docker compose down -v
# 同时清理 bind mount 数据：
rm -rf data/seaweedfs/* data/gravitino/* data/dragonfly/*
```

> **警告**：此操作不可逆，会丢失所有 S3 对象、Gravitino 元数据、Dragonfly KV。

### 1.7 重启单个服务

```bash
docker compose restart seaweedfs
docker compose restart gravitino
docker compose restart dragonfly
```

---

## 2. SeaweedFS（S3 存储）使用

### 2.1 连接信息

| 项 | 值 |
|----|-----|
| Endpoint | `http://localhost:8333` |
| Access Key | admin（见 `.env`） |
| Secret Key | admin123456（见 `.env`） |
| Region | us-east-1 |
| 签名 | S3v4 + path-style |

### 2.2 用 boto3 操作

```python
import boto3
from botocore.client import Config

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:8333",
    aws_access_key_id="admin",
    aws_secret_access_key="admin123456",
    region_name="us-east-1",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

# 建桶
s3.create_bucket(Bucket="my-bucket")

# 上传
s3.put_object(Bucket="my-bucket", Key="data/file.txt", Body=b"hello")

# 下载
resp = s3.get_object(Bucket="my-bucket", Key="data/file.txt")
print(resp["Body"].read())

# 列表
for obj in s3.list_objects_v2(Bucket="my-bucket").get("Contents", []):
    print(obj["Key"], obj["Size"])

# 删除
s3.delete_object(Bucket="my-bucket", Key="data/file.txt")
s3.delete_bucket(Bucket="my-bucket")
```

### 2.3 用 aws-cli 操作

```bash
aws --endpoint-url http://localhost:8333 s3 mb s3://my-bucket
aws --endpoint-url http://localhost:8333 s3 ls
aws --endpoint-url http://localhost:8333 s3 cp file.txt s3://my-bucket/
```

### 2.4 SeaweedFS 管理端口

| 端口 | 用途 |
|------|------|
| 9333 | Master（拓扑、Volume 分配） |
| 8080 | Volume（数据读写，一般不直接访问） |
| 8888 | Filer（文件目录 HTTP 接口） |
| 8333 | **S3 Gateway（主要使用）** |

查看集群状态：浏览器打开 `http://localhost:9333/`。

---

## 3. Apache Gravitino（元数据编目）使用

### 3.1 连接信息

| 项 | 值 |
|----|-----|
| REST API | `http://localhost:8090/api` |
| Iceberg REST | `http://localhost:9001` |

### 3.2 Metalake / Catalog / Schema / Fileset 操作

```python
import json
import urllib.request

BASE = "http://localhost:8090/api"
METALAKE = "lakemind_metalake"

def req(method, url, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    if body:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=25) as resp:
        return resp.status, json.loads(resp.read())

# 创建 Metalake
req("POST", f"{BASE}/metalakes", {"name": METALAKE, "comment": "LakeMind"})

# 创建 Fileset Catalog（指向 S3）
req("POST", f"{BASE}/metalakes/{METALAKE}/catalogs", {
    "name": "cat_fs", "type": "fileset", "provider": "fileset",
    "comment": "文件编目",
    "properties": {
        "location": "s3a://lakemind-filesets/",
        "s3-access-key-id": "admin",
        "s3-secret-access-key": "admin123456",
        "s3-endpoint": "http://lakemind-seaweedfs:8333",
        "s3-region": "us-east-1",
        "s3-path-style-access": "true",
    },
})

# 创建 Schema
req("POST", f"{BASE}/metalakes/{METALAKE}/catalogs/cat_fs/schemas",
    {"name": "knowledge", "comment": "知识域"})

# 创建 Fileset
req("POST",
    f"{BASE}/metalakes/{METALAKE}/catalogs/cat_fs/schemas/knowledge/filesets",
    {"name": "docs", "storageLocation": "s3a://lakemind-filesets/knowledge/docs",
     "comment": "文档RAG"})
```

### 3.3 Gravitino Web UI

浏览器打开 `http://localhost:8090`，可可视化查看 metalake / catalog / schema 层级。

### 3.4 关键注意事项

- **S3 端点**：Gravitino 容器内访问 SeaweedFS 用 `http://lakemind-seaweedfs:8333`（容器名），不是 `localhost`。
- **path-style**：必须设 `s3-path-style-access=true`，SeaweedFS 不支持虚拟主机风格。
- **s3a://**：Fileset location 用 `s3a://` 协议头，不是 `s3://`。
- **Iceberg REST(9001)**：建表需 JDBC 后端（MySQL/PostgreSQL），MVP 不使用。结构化数据通过 PyIceberg 直连 S3。

---

## 4. Dragonfly（短期记忆 KV）使用

### 4.1 连接信息

| 项 | 值 |
|----|-----|
| Host | localhost |
| Port | 6379 |
| Password | 空（见 `.env`） |
| 协议 | Redis 7.4.0 兼容 |

### 4.2 用 redis-py 操作

```python
import redis

r = redis.Redis(host="localhost", port=6379, socket_timeout=5)

# 基本操作
r.set("key", "value")
r.get("key")  # b"value"

# 带 TTL（秒）
r.set("session:abc", "data", ex=3600)  # 1 小时后过期
r.ttl("session:abc")  # 剩余秒数

# 批量
r.mset({"k1": "v1", "k2": "v2"})
r.mget("k1", "k2")

# 删除
r.delete("key")
```

### 4.3 用 redis-cli 操作

```bash
# 通过容器内 redis-cli
docker exec -it lakemind-dragonfly redis-cli

# 或宿主机安装 redis-cli
redis-cli -p 6379
```

```
127.0.0.1:6379> SET lk:task "running"
127.0.0.1:6379> GET lk:task
127.0.0.1:6379> TTL lk:task
127.0.0.1:6379> KEYS lk:*
```

### 4.4 典型用途

| 场景 | Key 设计 | TTL |
|------|---------|-----|
| Agent 会话状态 | `session:{id}` | 3600s |
| 任务锁 | `lock:task:{name}` | 300s |
| 缓存查询结果 | `cache:{hash}` | 600s |
| 限流计数 | `rate:{ip}` | 60s |

---

## 5. 验证脚本

### 5.1 运行

```bash
python scripts/verify_services.py
```

### 5.2 验证内容

| 序号 | 测试项 | 验证内容 |
|------|--------|---------|
| 1 | SeaweedFS S3 CRUD | 建桶 → 上传 → 下载 → 列表 → 删除 → 删桶 |
| 2 | Dragonfly set/get/TTL | set → get → TTL 检查 → delete |
| 3 | Gravitino→S3 fileset | metalake → catalog → schema → fileset → S3 实际写入确认 |

### 5.3 环境变量覆盖

脚本支持通过环境变量覆盖默认值：

```bash
S3_ENDPOINT=http://localhost:8333 \
S3_ACCESS_KEY=admin \
S3_SECRET_KEY=admin123456 \
DRAGONFLY_PORT=6379 \
GRAVITINO_URI=http://localhost:8090 \
GRAVITINO_METALAKE=lakemind_metalake \
python scripts/verify_services.py
```

### 5.4 退出码

- `0`：全部通过
- `1`：有失败项

可用于 CI/CD 流水线。

---

## 5B. 端到端真实场景验证

### 5B.1 安装依赖

```bash
pip install pyiceberg[sql-sqlite] pylance lancedb duckdb daft pyarrow
```

### 5B.2 运行

```bash
python scripts/verify_scenario.py
```

### 5B.3 验证内容

场景：**智能客服 Agent 知识库系统**，覆盖方案中全部 5 个数据域：

| 序号 | 数据域 | 引擎 | 验证项数 | 验证内容 |
|------|--------|------|---------|---------|
| 1 | 结构化数据 | Iceberg + S3 + DuckDB | 6 | 建表→写入20条任务日志→读取→DuckDB COUNT/聚合/失败率分析 |
| 2 | 知识/文档 RAG | S3 + Lance + LanceDB | 5 | 上传4篇文档→128维向量→LanceDB检索→S3取原文（完整RAG流程） |
| 3 | 短期记忆 | Dragonfly | 7 | 会话状态读写→多轮更新→任务锁NX互斥→短期缓存TTL |
| 4 | 长期记忆 | Lance + Iceberg | 5 | 向量写入→Iceberg元信息小表→双表lance_uri关联→语义检索 |
| 5 | Skills | S3 + Iceberg + LanceDB | 6 | 技能文件存S3→元信息存Iceberg→LanceDB语义检索→加载代码 |

合计 **29 项**检查，全部通过即代表平台端到端可用。

---

## 6. 数据管理

### 6.1 查看数据目录

```bash
# SeaweedFS 数据
ls data/seaweedfs/

# Gravitino H2 数据库
ls data/gravitino/

# Dragonfly 持久化
ls data/dragonfly/
```

### 6.2 备份

```bash
# 简单备份：打包 data 目录
tar -czf lakemind-backup-$(date +%Y%m%d).tar.gz data/

# 或只备份 Gravitino 元数据（最关键）
tar -czf gravitino-backup-$(date +%Y%m%d).tar.gz data/gravitino/
```

### 6.3 恢复

```bash
docker compose down
tar -xzf lakemind-backup-20260630.tar.gz
docker compose up -d
```

### 6.4 清理 S3 中的验证测试数据

验证脚本会创建以下持久化数据（幂等，重复运行不报错）：

- S3 桶：`lakemind-filesets`
- Gravitino metalake：`lakemind_metalake`
- Gravitino catalog：`cat_fs`（fileset 类型）
- Gravitino schema：`knowledge`
- Gravitino fileset：`docs`

这些是平台基础元数据，**不建议清理**。如需重置：

```bash
# 删除 Gravitino 全部元数据
curl -X DELETE "http://localhost:8090/api/metalakes/lakemind_metalake?force=true"

# 删除 S3 桶
aws --endpoint-url http://localhost:8333 s3 rb s3://lakemind-filesets --force
```

---

## 7. 健康检查

### 7.1 快速健康检查

```bash
# 容器状态
docker ps --format "table {{.Names}}\t{{.Status}}"

# S3 可达
curl -s http://localhost:8333/ | head -1

# Gravitino 可达
curl -s http://localhost:8090/api/version | head -1

# Dragonfly 可达
docker exec lakemind-dragonfly redis-cli ping
```

### 7.2 完整验证

```bash
python scripts/verify_services.py
```

---

## 8. 容器内互访地址

容器之间通过 `lakemind` 网络互访，使用容器名：

| 从容器内访问 | 地址 |
|------------|------|
| SeaweedFS S3 | `http://lakemind-seaweedfs:8333` |
| Gravitino REST | `http://lakemind-gravitino:8090` |
| Gravitino Iceberg REST | `http://lakemind-gravitino:9001` |
| Dragonfly | `lakemind-dragonfly:6379` |

| 从宿主机访问 | 地址 |
|------------|------|
| SeaweedFS S3 | `http://localhost:8333` |
| Gravitino REST | `http://localhost:8090` |
| Gravitino Iceberg REST | `http://localhost:9001` |
| Dragonfly | `localhost:6379` |
