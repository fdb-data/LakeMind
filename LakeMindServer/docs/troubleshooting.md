# 故障排查手册

> **⚠️ 部分内容过期**：本文档仍包含 Apache Gravitino 故障排查。Gravitino 已被 PostgreSQL 16 替代，相关排查内容仅作历史参考。

LakeMindServer 常见问题的诊断与解决方法。

---

## 1. 容器无法启动

### 1.1 端口被占用

**现象**：`docker compose up -d` 报 `port is already allocated`。

**诊断**：
```bash
# 查看占用端口的进程
netstat -ano | findstr :8333
netstat -ano | findstr :8090
netstat -ano | findstr :6379
```

**解决**：
- 方案 A：修改 `.env` 中对应端口变量，换用空闲端口。
- 方案 B：停止占用端口的进程。

### 1.2 镜像拉取失败

**现象**：`docker compose pull` 超时或 `image not found`。

**诊断**：
```bash
docker pull chrislusf/seaweedfs:latest
docker pull apache/gravitino:1.3.0
docker pull valkey/valkey:8.0
```

**解决**：
- 配置国产镜像源（见[安装手册](installation.md#12-国产镜像加速可选但推荐)）。
- Gravitino 镜像较大（1.6 GB），用 `curl` 断点续传 + `docker load`（见[安装手册](installation.md#41-gravitino-镜像拉取失败的处理)）。

### 1.3 数据目录权限问题

**现象**：容器启动后立即退出，日志报 `permission denied`。

**解决**：
```bash
# Windows 一般无此问题。Linux/Mac 下：
chmod -R 777 data/
docker compose restart
```

---

## 2. 验证脚本失败

### 2.1 `[FAIL] SeaweedFS S3 CRUD`

**原因 A：SeaweedFS 未就绪**

```bash
docker logs lakemind-seaweedfs --tail 20
# 等待出现 "S3 gateway" 字样后重试
```

**原因 B：S3 凭据不匹配**

检查 `.env` 中的 `S3_ACCESS_KEY` / `S3_SECRET_KEY` 是否与 `config/seaweedfs/s3.json` 一致。

**原因 C：boto3 未安装**

```bash
pip install boto3
```

### 2.2 `[FAIL] Valkey set/get/TTL`

**原因 A：Valkey 未就绪**

```bash
docker logs lakemind-valkey --tail 20
# 等待出现 "Ready" 字样后重试
```

**原因 B：redis-py 未安装**

```bash
pip install redis
```

### 2.3 `[FAIL] Gravitino->S3 fileset 集成`

**原因 A：Gravitino 未就绪**

```bash
curl http://localhost:8090/api/version
# 应返回 {"code":0,"version":{"version":"1.3.0",...}}
```

**原因 B：Gravitino 连不上 SeaweedFS**

Gravitino 容器内通过 `lakemind-seaweedfs:8333` 访问 S3。确认两容器在同一网络：
```bash
docker network inspect lakemind_lakemind | grep -A5 Containers
```

**原因 C：S3 桶创建失败（BucketAlreadyOwnedByYou）**

脚本已做幂等处理，正常不会报此错。如仍出现，确认 boto3 版本：
```bash
pip show boto3 | grep Version
# 应 >= 1.43
```

**原因 D：fileset location 格式错误**

fileset 的 `storageLocation` 必须用 `s3a://` 协议头，不是 `s3://`：
```
正确：s3a://lakemind-filesets/knowledge/docs
错误：s3://lakemind-filesets/knowledge/docs
```

---

## 3. Gravitino 特定问题

### 3.1 Iceberg REST (9001) 建表报错

**现象**：通过端口 9001 创建 Iceberg 表时报 JDBC 相关错误。

**原因**：Iceberg REST Catalog 建表需要 JDBC 后端（MySQL/PostgreSQL），MVP 未配置。

**解决**：MVP 阶段不通过 9001 建表。结构化数据使用 PyIceberg 直连 S3：
```python
from pyiceberg.catalog import load_catalog
catalog = load_catalog("default", **{
    "type": "sql",
    "uri": "sqlite:///lake.db",  # 或 MySQL
    "warehouse": "s3://lakemind-iceberg/",
    "s3.endpoint": "http://localhost:8333",
    "s3.access-key-id": "admin",
    "s3.secret-access-key": "admin123456",
})
```

### 3.2 Gravitino 内存不足

**现象**：日志报 `OutOfMemoryError` 或容器被 OOM Kill。

**诊断**：
```bash
docker stats lakemind-gravitino
docker logs lakemind-gravitino 2>&1 | grep -i "memory\|oom"
```

**解决**：在 `.env` 中调大 JVM 内存：
```bash
GRAVITINO_MEM=-Xms2g -Xmx4g -XX:MaxMetaspaceSize=1g
```
重启：`docker compose restart gravitino`

---

## 4. SeaweedFS 特定问题

### 4.1 S3 操作报 403

**原因**：S3 凭据不匹配或权限不足。

**诊断**：
```bash
# 确认 s3.json 中的 actions 列表
cat config/seaweedfs/s3.json
```

确保用户有 `Admin`, `Read`, `Write`, `List`, `Tagging`, `Delete` 权限。

### 4.2 Volume 空间不足

**现象**：上传报 `volume is full` 或 `no free volume`。

**原因**：`docker-compose.yml` 中 `volume.max=100` 限制 100 个 Volume（每个 30GB）。

**解决**：修改 `docker-compose.yml` 中 `-volume.max=100` 为更大值，重启 SeaweedFS。

### 4.3 Filer LevelDB 损坏

**现象**：SeaweedFS 启动报 LevelDB 相关错误。

**解决**：
```bash
docker compose down
rm -rf data/seaweedfs/filerldb2/
docker compose up -d
```
> 此操作丢失 Filer 元数据（文件目录树），S3 对象数据在 Volume 中仍存在但需重新建桶。

---

## 5. Valkey 特定问题

### 5.1 内存锁定失败

**现象**：日志报 `mlock failed` 或 `Cannot allocate memory`。

**解决**：`docker-compose.yml` 已设 `ulimits.memlock: -1`。如仍失败，检查 Docker Desktop 内存限制。

### 5.2 RDB 加载失败

**现象**：Valkey 启动报 RDB 文件损坏。

**解决**：
```bash
docker compose down
rm -rf data/valkey/*
docker compose up -d
```

---

## 6. Windows 特定问题

### 6.1 PowerShell 中文乱码

**现象**：验证脚本输出中文乱码。

**解决**：
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001
```

这是显示问题，不影响脚本逻辑和验证结果。

### 6.2 bind mount 性能

**现象**：Windows 下 bind mount 读写比 Linux 慢。

**原因**：Docker Desktop 通过 WSL2 → NTFS 转发，有性能损耗。

**解决**：MVP 阶段可接受。生产环境建议在 Linux 主机部署，或用 Docker 命名卷（性能更好但数据不直接可见）。

### 6.3 容器时间不正确

**现象**：容器内时间与宿主机不一致。

**解决**：Docker Desktop 默认同步宿主机时间，一般无此问题。如出现，确认 WSL2 时间同步：
```bash
wsl -e date
```

---

## 7. 通用诊断流程

遇到未知问题时，按以下顺序排查：

```
1. docker ps                          → 容器是否都在运行？
2. docker compose logs --tail 50      → 有无错误日志？
3. docker stats                       → 资源使用是否异常？
4. curl 各端口                        → 服务是否可达？
5. python scripts/verify_services.py  → 端到端是否通过？
6. 查阅本手册对应章节
7. 查阅组件官方文档
```

---

## 8. 收集诊断信息

如需寻求帮助，收集以下信息：

```bash
echo "=== Docker ==="
docker version
docker compose version
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo "=== Logs (last 30 lines each) ==="
docker compose logs --tail 30

echo "=== Config ==="
cat .env
cat config/seaweedfs/s3.json

echo "=== Verify ==="
python scripts/verify_services.py

echo "=== Versions ==="
cat config/versions.yaml
```
