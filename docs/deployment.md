# 部署运维

## 部署模式

### 单机 docker-compose（v0.1.0）

适用于开发、测试、小规模生产（≤50 Agent）。

#### 启动顺序

```bash
# 1. 数据平面（7 容器：server-api + postgres + seaweedfs + valkey + ray-head + 2 worker）
cd LakeMindServer
docker compose --env-file .env --profile ray up -d

# 2. 三个 MCP（3 容器）
cd LakeMindMCP
docker compose --profile all up -d --build

# 3. Steward + Monitor + ModelServing（3 容器）
cd LakeMindMonitor
docker compose up -d --build
```

#### 不启动 Ray

```bash
cd LakeMindServer
docker compose --env-file .env up -d    # 不加 --profile ray
```

此时 `compute.distributed` 使用 `embedded` 插件（需在 engines.yaml 中切换）。

#### 选择性启动 MCP

```bash
cd LakeMindMCP
docker compose --profile asset up -d --build    # 只启动 AssetMCP
docker compose --profile data up -d --build     # 只启动 DataMCP
docker compose --profile admin up -d --build    # 只启动 AdminMCP
```

### 停止与清理

```bash
# 停止全部
cd LakeMindMonitor && docker compose down
cd LakeMindMCP && docker compose --profile all down
cd LakeMindServer && docker compose --profile ray down

# 清理数据卷（谨慎！）
cd LakeMindServer && docker compose --profile ray down -v
```

## 容器清单

| 容器 | 镜像 | 端口 | CPU | 内存 |
|------|------|------|-----|------|
| lakemind-server-api | lakemind/server-api:latest | 10823 | ~1% | 443 MB |
| lakemind-model-serving | lakemind/model-serving:latest | 10824 | ~2% | 500 MB |
| lakemind-postgres | postgres:16 | 5432 | ~0% | 35 MB |
| lakemind-seaweedfs | chrislusf/seaweedfs:latest | 8333/8888/9333 | ~0.4% | 90 MB |
| lakemind-valkey | valkey/valkey:8.0 | 6379 | ~2.5% | 23 MB |
| lakemind-ray-head | lakemind/ray:2.41.0-py3.12 | 8265 | ~12% | 871 MB |
| lakemind-ray-worker-1 | lakemind/ray:2.41.0-py3.12 | — | ~4% | 334 MB |
| lakemind-ray-worker-2 | lakemind/ray:2.41.0-py3.12 | — | ~7% | 420 MB |
| lakemind-asset-mcp | lakemind-asset-mcp:latest | 8401 | ~0.2% | 47 MB |
| lakemind-data-mcp | lakemind-data-mcp:latest | 8402 | ~0.2% | 47 MB |
| lakemind-admin-mcp | lakemind-admin-mcp:latest | 8403 | ~0.2% | 44 MB |
| lakemind-steward | lakemind-steward:latest | 8500 | ~0.2% | 62 MB |
| lakemind-monitor | lakemind-monitor:latest | 3000 | ~0% | 21 MB |

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

## 验证脚本

```bash
python scripts/verify_full.py                          # L0-L9 全分层，297/297 PASS（主验证脚本）
python LakeMindServer/scripts/verify_pg_catalog.py     # 8 PG catalog
python LakeMindServer/scripts/verify_ray.py            # 12 Ray 分布式
python scripts/verify_llm.py                           # 10 LLM 网关
python LakeMindMonitor/scripts/verify_monitor.py       # 18 Monitor
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
