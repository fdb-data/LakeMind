# 部署运维

## 部署模式

### 单机 docker-compose（v0.2.0）

适用于开发、测试、小规模生产（≤50 Agent）。

#### 一键启动

```bash
# 启动全部服务（数据平面 + 3 MCP + ModelServing + ControlCenter + Ray）
docker compose --env-file .env --profile ray --profile all up -d

# 本地开发（先 build 再 up）
docker buildx bake core --load
docker compose -f docker-compose.yml -f docker-compose.build.yml --env-file .env --profile ray --profile all up -d --no-build
```

#### 不启动 Ray

```bash
docker compose --env-file .env --profile all up -d    # 不加 --profile ray
```

此时 `compute.distributed` 使用 `embedded` 插件（需在 engines.yaml 中切换）。

#### 选择性启动 MCP

```bash
docker compose --env-file .env --profile asset up -d    # 只启动 AssetMCP
docker compose --env-file .env --profile data up -d     # 只启动 DataMCP
docker compose --env-file .env --profile admin up -d    # 只启动 AdminMCP
```

### 停止与清理

```bash
# 停止全部
docker compose --env-file .env --profile ray --profile all down

# 清理数据卷（谨慎！）
docker compose --env-file .env --profile ray --profile all down -v
```

## 容器清单

| 容器 | 镜像 | 端口 | CPU | 内存 |
|------|------|------|-----|------|
| lakemind-server-api | lakemind/server-api:latest | 10823 | ~1% | 443 MB |
| lakemind-model-serving | lakemind/model-serving:latest | 10824 | ~2% | 500 MB |
| lakemind-postgres | postgres:16 | 5432 | ~0% | 35 MB |
| lakemind-seaweedfs | chrislusf/seaweedfs:latest | 8333/8888/9333 | ~0.4% | 90 MB |
| lakemind-valkey | valkey/valkey:8.0 | 6379 | ~2.5% | 23 MB |
| lakemind-ray-head | rayproject/ray:2.41.0-py312 | 8265 | ~12% | 871 MB |
| lakemind-ray-worker-1 | rayproject/ray:2.41.0-py312 | — | ~4% | 334 MB |
| lakemind-ray-worker-2 | rayproject/ray:2.41.0-py312 | — | ~7% | 420 MB |
| lakemind-asset-mcp | lakemind/mcp-suite:latest | 8401 | ~0.2% | 47 MB |
| lakemind-data-mcp | lakemind/mcp-suite:latest | 8402 | ~0.2% | 47 MB |
| lakemind-admin-mcp | lakemind/mcp-suite:latest | 8403 | ~0.2% | 44 MB |
| lakemind-control-center | lakemind/control-center:latest | 3000 | ~1% | 120 MB |

## 引擎切换

所有引擎通过 `LakeMindServer/config/engines.yaml` 切换，改完重启 server-api：

```bash
docker compose --env-file .env up -d --force-recreate server-api
```

### 常见切换场景

**Ray → Embedded（降级）**：

```yaml
compute:
  distributed:
    plugin: embedded    # 改这一行
    config: {}
```

**memory plugin 切换**：

```yaml
cognitive:
  memory:
    plugin: basic
    config:
      model_serving_url: "http://lakemind-model-serving:10824"
```

## 健康检查

```bash
# 全引擎健康
curl http://localhost:10823/api/v1/system/health

# ModelServing 健康
curl http://localhost:10824/health

# Ray 集群状态
docker exec lakemind-ray-head ray status

# 容器状态
docker ps --filter "name=lakemind"
```

## 日志查看

```bash
docker logs lakemind-server-api -f --tail 50
docker logs lakemind-asset-mcp -f --tail 50
docker logs lakemind-ray-head -f --tail 50
```

## 故障排查

### server-api 启动失败

```bash
docker logs lakemind-server-api 2>&1 | tail -20
```

常见原因：
- PostgreSQL 未就绪 → 检查 `docker ps | grep postgres`
- engines.yaml 语法错误 → 检查 YAML 缩进
- 环境变量未设置 → 检查 `.env` 文件

### Ray 连接失败

```bash
# 检查 Ray head 是否运行
docker ps | grep ray-head

# 检查版本匹配
docker exec lakemind-server-api python -c "import ray; print(ray.__version__)"
docker exec lakemind-ray-head python -c "import ray; print(ray.__version__)"
```

版本必须一致（2.41.0）。如果不一致，重建 server-api 镜像。

### LLM 网关 401/429

- 401 → API key 未设置或错误，检查 `.env` 和 `docker exec lakemind-model-serving env | grep MAAS`
- 429 → API 限流，降低请求频率

### MCP 连接 server-api 失败

```bash
# 检查 server-api 是否运行
curl http://localhost:10823/api/v1/system/health

# 检查 MCP 日志
docker logs lakemind-asset-mcp 2>&1 | tail -20
```

### 端口冲突

LakeMind 使用以下端口，确保未被占用：

| 端口 | 容器 | 检查命令 |
|------|------|----------|
| 10823 | server-api | `netstat -tlnp \| grep 10823` |
| 10824 | model-serving | `netstat -tlnp \| grep 10824` |
| 8401 | asset-mcp | `netstat -tlnp \| grep 8401` |
| 8402 | data-mcp | `netstat -tlnp \| grep 8402` |
| 8403 | admin-mcp | `netstat -tlnp \| grep 8403` |
| 3000 | control-center | `netstat -tlnp \| grep 3000` |
| 5432 | postgres | `netstat -tlnp \| grep 5432` |
| 8333 | seaweedfs | `netstat -tlnp \| grep 8333` |
| 6379 | valkey | `netstat -tlnp \| grep 6379` |
| 8265 | ray dashboard | `netstat -tlnp \| grep 8265` |

如果端口被占用，修改对应 `docker-compose.yml` 中的端口映射。

### Docker 镜像拉取失败

```bash
# 检查 Docker 网络和 DNS
docker pull python:3.12-slim

# 配置国内镜像加速（如需要）
# /etc/docker/daemon.json
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
```

### 内存不足

```bash
# 检查可用内存
free -h    # Linux
# 或
docker stats --no-stream

# 如果内存不足，可以不启动 Ray
cd LakeMindServer
docker compose --env-file .env up -d    # 不加 --profile ray
```

### Docker 网络不存在

```bash
# 错误：network lakemind-server_lakemind not found
# 原因：LakeMindServer 未先启动
# 解决：按顺序启动
docker compose --env-file .env --profile ray --profile all up -d
```

### BuildKit 兼容问题

```bash
# 如果 build 报 BuildKit 相关错误，禁用 BuildKit
export DOCKER_BUILDKIT=0    # Linux/macOS
$env:DOCKER_BUILDKIT=0      # PowerShell
```

## 验证脚本

```bash
python scripts/verify_full.py                          # L0-L9 全分层，286/286 PASS（主验证脚本）
```

期望：297/297 PASS

## 性能调优

### Ray 集群

```env
# .env
RAY_HEAD_CPUS=8        # 增加 head CPU
RAY_WORKER_CPUS=8      # 增加 worker CPU
```

增加 worker 数量：

```yaml
# docker-compose.yml
ray-worker:
  deploy:
    replicas: 4        # 从 2 改为 4
```

### PostgreSQL 连接池

```yaml
storage:
  metadata:
    config:
      pool_size: 50    # 从 20 增加到 50
```

### MCP 水平扩展

```bash
# 启动多个 AssetMCP 副本
cd LakeMindMCP
docker compose --profile asset up -d --scale asset-mcp=3 --build
```

## 运维操作

### 扩容服务

**增加 Ray worker**：

```yaml
# LakeMindServer/docker-compose.yml
ray-worker:
  deploy:
    replicas: 4        # 从 2 改为 4
```

```bash
cd LakeMindServer
docker compose --env-file .env --profile ray up -d
```

**增加 MCP 副本**：

```bash
cd LakeMindMCP
docker compose --profile asset up -d --scale asset-mcp=3 --build
```

### 查看日志

```bash
# 实时跟踪
docker logs -f lakemind-server-api
docker logs -f lakemind-asset-mcp
docker logs -f lakemind-ray-head

# 查看最近 100 行
docker logs --tail 100 lakemind-server-api

# 查看指定时间后的日志
docker logs --since 2026-07-12T10:00:00 lakemind-server-api
```

### 数据备份

**PostgreSQL 备份**：

```bash
docker exec lakemind-postgres pg_dump -U lakemind lakemind > backup_$(date +%Y%m%d).sql
```

**SeaweedFS 备份**：

```bash
# SeaweedFS 数据存储在 volume 中
docker run --rm -v lakemind-server_seaweedfs_data:/data -v $(pwd):/backup alpine tar czf /backup/seaweedfs_$(date +%Y%m%d).tar.gz /data
```

**全量备份**：

```bash
# 备份所有 LakeMind 数据卷
docker run --rm -v lakemind-server_postgres_data:/pg -v lakemind-server_seaweedfs_data:/sw -v lakemind-server_lance_data:/lance -v $(pwd):/backup alpine tar czf /backup/lakemind_full_$(date +%Y%m%d).tar.gz /pg /sw /lance
```

### 数据恢复

```bash
# PostgreSQL 恢复
docker exec -i lakemind-postgres psql -U lakemind lakemind < backup_20260712.sql
```

### 清理

```bash
# 停止全部容器
docker compose --env-file .env --profile ray --profile all down

# 清理数据卷（谨慎！不可恢复）
docker compose --env-file .env --profile ray --profile all down -v

# 清理镜像
docker image prune -a --filter "name=lakemind"
```
