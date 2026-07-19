# LakeMind v0.2.0 镜像构建与交付加速方案

> 建设目标：提高首次交付、日常开发和 CI/CD 构建速度，同时保证镜像可复现、可发布、可回滚

---

## 1. 执行摘要

LakeMind v0.2.0 当前构建慢的主要原因，并不是容器数量本身，而是以下问题叠加：

1. **Compose、Dockerfile 与 CI 发布对象不一致**：v0.2.0 已将管理面合并为 `LakeMindControlCenter`，但 CI 仍构建旧的 `LakeMindMonitor` 和 `LakeMindSteward`，却没有构建和发布 `control-center`。
2. **默认 Compose 不能完整从源码构建，也不能可靠从仓库拉取**：只有 PostgreSQL AGE 和 ControlCenter 声明了 `build`；Server、Ray、三个 MCP、ModelServing 只引用本地短镜像名，其中 ModelServing 还设置了 `pull_policy: never`。
3. **Compose 镜像名与 GitHub Actions 发布地址不一致**：Compose 使用 `lakemind/server-api:v2`，CI 发布到 `ghcr.io/fdb-data/lakemind/server-api:*`。
4. **构建说明要求关闭 BuildKit**，直接放弃了现代 Docker 的缓存挂载、外部缓存、并行构建和 Bake 能力。
5. **所有 Python 服务都没有依赖锁文件**，并且普遍在安装依赖前复制源码，导致普通代码修改触发依赖重新解析和安装。
6. **ModelServing 继承 `server-api:latest`**，把两个业务服务错误地串成父子镜像，造成镜像膨胀、串行构建和版本耦合。
7. **三个 MCP 使用几乎完全相同的依赖，却重复构建三个镜像**。
8. **GitHub Actions 的 `type=gha` 缓存没有设置独立 `scope`**。多个镜像默认写入同一缓存作用域，可能相互覆盖。
9. **多个构建上下文缺少 `.dockerignore`**。其中 `LakeMindServer` 构建 Server API 时会携带 `docker/postgres-age/age-src`；真实开发机上的 `data/`、模型缓存和数据库目录也可能进入构建上下文。
10. **ControlCenter 前端没有提交 `package-lock.json`**，Dockerfile 使用 `npm install`，每次构建都可能重新解析依赖树。

本方案不建议继续增加大量自定义基础镜像，而是采用：

> **部署与构建分离 + 自研镜像收敛 + 官方镜像优先 + 依赖锁定 + BuildKit 分层缓存 + 按变更构建。**

改造后，LakeMind 核心自研镜像建议收敛为 5 个：

| 镜像 | 职责 |
|---|---|
| `postgres-age` | PostgreSQL 16 + Apache AGE，低频构建 |
| `server-api` | LakeMind 数据与认知资产服务 |
| `model-serving` | 模型网关、嵌入与语音服务 |
| `mcp-suite` | 同一镜像运行 Asset、Data、Admin 三个 MCP 容器 |
| `control-center` | React 前端 + BFF + Steward 管理面 |

Ray 直接使用经过验证并固定 digest 的官方 `rayproject/ray` 镜像；SeaweedFS 和 Valkey 继续使用官方或上游镜像。`meeting-agent` 作为示例镜像独立发布，不进入核心镜像组。

---

## 2. v0.2.0 源码现状复核

### 2.1 当前统一 Compose 的实际构建能力

根目录 `docker-compose.yml` 中：

- `postgres`：有 `build`；
- `control-center`：有 `build`；
- `server-api`：只有 `image: lakemind/server-api:v2`；
- `ray-head`、`ray-worker`：只有 `image: lakemind/ray:2.41.0-py3.12`；
- 三个 MCP：只有 `lakemind/*-mcp:0.1.0`；
- `model-serving`：只有 `lakemind/model-serving:v2`，并设置 `pull_policy: never`。

因此当前注释中的命令：

```bash

docker compose --env-file LakeMindServer/.env --profile ray --profile all up -d --build
```

并不会构建 Server、Ray、三个 MCP 和 ModelServing。若本机事先没有这些镜像，系统无法完整启动。

### 2.2 镜像版本标记不统一

当前 Compose 同时存在：

- `v2`；
- `0.1.0`；
- `16.4`；
- `2.41.0-py3.12`。

当前 CI 又同时发布：

- `latest`；
- Git commit SHA；
- `0.1.0`；
- `v<release-version>`；
- 固定的 `16`。

这使“LakeMind v0.2.0 到底由哪些镜像版本组成”无法从 Compose 中唯一确定。

### 2.3 管理面已经合并，但发布流程仍停留在旧结构

v0.2.0 根 Compose 已采用：

```text
LakeMindControlCenter
├── React 前端
├── BFF
└── Steward
```

并通过 Nginx + Supervisor 形成单镜像管理面。

但 `.github/workflows/build.yml` 和 `release.yml` 仍然：

- 构建 `LakeMindMonitor`；
- 构建 `LakeMindSteward`；
- 不构建 `LakeMindControlCenter`。

这不仅浪费构建时间，而且会导致正式 Release 缺少 Compose 实际需要的镜像。

### 2.4 Python 镜像缓存层设计不合理

Server、ModelServing、三个 MCP、Steward 都采用类似顺序：

```dockerfile
COPY pyproject.toml ./
COPY src ./src
RUN pip install .
```

只要源码发生任何修改，`pip install` 层就会失效。Server 的依赖包含 PyArrow、PyIceberg、LanceDB、DuckDB、FastEmbed、Ray 等重依赖，重新解析与安装成本较高。

此外，MCP Dockerfile 设置了：

```dockerfile
PIP_NO_CACHE_DIR=1
```

这在没有 BuildKit cache mount 的情况下，会使依赖层失效后无法复用下载缓存。

### 2.5 ModelServing 存在不必要的业务镜像继承

当前：

```dockerfile
FROM lakemind/server-api:latest
```

ModelServing 因此继承 Server 的 PyIceberg、LanceDB、DuckDB、Ray 等依赖，同时 CI 必须等待 Server 构建完成。

另外，以下命令同时与 `pyproject.toml` 重复声明依赖：

```dockerfile
RUN pip install --no-cache-dir litellm>=1.40 funasr>=1.0 python-multipart>=0.0.9
```

未加引号的 `>` 在 shell 中还可能被解释为重定向符。该行应直接删除，所有依赖统一由锁文件安装。

### 2.6 Server 构建上下文携带无关 AGE 源码

上传源码中 `LakeMindServer` 目录约 8.5 MB，主要包含 `docker/postgres-age/age-src`。但 Server API Dockerfile 并不需要 AGE 源码。

真实开发环境中，`LakeMindServer/data` 还可能包含：

- PostgreSQL 数据；
- SeaweedFS 数据；
- Lance 文件；
- FastEmbed 缓存；
- Valkey 数据。

`.gitignore` 不会自动成为 `.dockerignore`，因此必须单独排除。

---

## 3. 建设目标与验收指标

### 3.1 交付目标

普通使用者只执行：

```bash

docker compose pull
docker compose up -d --no-build
```

即可启动系统，不在用户机器上编译 AGE、安装 Python 包或构建 React 前端。

### 3.2 开发目标

修改单个服务后，只重建对应镜像：

```bash

docker buildx bake server-api --load
docker compose up -d --no-deps server-api
```

未修改锁文件时，第三方依赖层必须命中缓存。

### 3.3 CI 目标

- 普通 PR 只构建受影响镜像；
- Release 构建完整核心镜像组；
- 每个镜像使用独立缓存作用域；
- CI 不再构建已经被 ControlCenter 替代的旧 Monitor、旧 Steward；
- Ray 不再由 LakeMind 重复安装和封装；
- 镜像可以通过版本号和 digest 精确复现。

### 3.4 镜像数量目标

```text
当前核心规划：
postgres-age + server-api + ray + 3 MCP + model-serving + control-center = 8 个自研镜像

改造后：
postgres-age + server-api + mcp-suite + model-serving + control-center = 5 个自研镜像
```

容器数量不必减少。三个 MCP 仍然是三个独立容器，只是复用同一个镜像和同一份依赖层。

---

## 4. 总体构建与交付架构

```text
                    ┌──────────────────────────────┐
                    │ 上游/官方镜像                 │
                    │ Python / Node / PostgreSQL    │
                    │ Ray / SeaweedFS / Valkey      │
                    └──────────────┬───────────────┘
                                   │ 固定版本与 digest
                                   ▼
                    ┌──────────────────────────────┐
                    │ BuildKit / Buildx Bake        │
                    │ 锁文件 + 分层构建 + 远程缓存 │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      ┌──────────────┐    ┌────────────────┐   ┌────────────────┐
      │ 稳定基础组件 │    │ 核心业务镜像   │   │ 可选示例镜像   │
      │ postgres-age │    │ server-api     │   │ meeting-agent  │
      │              │    │ model-serving  │   │                │
      │              │    │ mcp-suite      │   │                │
      │              │    │ control-center │   │                │
      └──────┬───────┘    └───────┬────────┘   └────────────────┘
             └─────────────────────┼──────────────────────┐
                                   ▼                      ▼
                         GHCR / 企业 Harbor       Build Cache Registry
                                   │
                                   ▼
                       image-only docker-compose.yml
```

核心原则：

1. **Compose 负责运行，不承担正式镜像构建。**
2. **Bake 负责构建，是本地和 CI 的唯一构建定义。**
3. **依赖锁文件决定依赖层，源码变化只影响应用层。**
4. **多个服务可以复用同一镜像，不必为每个容器创建独立镜像。**
5. **稳定基础组件低频构建，业务镜像按变更增量构建。**

---

## 5. Compose 改造方案

## 5.1 默认 `docker-compose.yml` 改为纯运行文件

默认 Compose 中删除所有 `build`，并使用完整 Registry 地址。

建议在根目录 `.env.example` 增加：

```dotenv
LAKEMIND_REGISTRY=ghcr.io/fdb-data/lakemind
LAKEMIND_VERSION=0.2.0
POSTGRES_AGE_VERSION=16.4-age-v0.2.0
PULL_POLICY=missing

# Ray 官方镜像必须在合并前验证具体 tag，并固定 digest
RAY_IMAGE=rayproject/ray:<verified-2.41.0-py312-tag>@sha256:<verified-digest>
```

核心服务改为：

```yaml
services:
  postgres:
    image: ${LAKEMIND_REGISTRY}/postgres-age:${POSTGRES_AGE_VERSION}
    pull_policy: ${PULL_POLICY:-missing}

  server-api:
    image: ${LAKEMIND_REGISTRY}/server-api:${LAKEMIND_VERSION}
    pull_policy: ${PULL_POLICY:-missing}

  ray-head:
    image: ${RAY_IMAGE}
    pull_policy: ${PULL_POLICY:-missing}

  ray-worker:
    image: ${RAY_IMAGE}
    pull_policy: ${PULL_POLICY:-missing}

  asset-mcp:
    image: ${LAKEMIND_REGISTRY}/mcp-suite:${LAKEMIND_VERSION}
    command: ["python", "-m", "lakemind_asset_mcp"]
    pull_policy: ${PULL_POLICY:-missing}

  data-mcp:
    image: ${LAKEMIND_REGISTRY}/mcp-suite:${LAKEMIND_VERSION}
    command: ["python", "-m", "lakemind_data_mcp"]
    pull_policy: ${PULL_POLICY:-missing}

  admin-mcp:
    image: ${LAKEMIND_REGISTRY}/mcp-suite:${LAKEMIND_VERSION}
    command: ["python", "-m", "lakemind_admin_mcp"]
    pull_policy: ${PULL_POLICY:-missing}

  model-serving:
    image: ${LAKEMIND_REGISTRY}/model-serving:${LAKEMIND_VERSION}
    pull_policy: ${PULL_POLICY:-missing}

  control-center:
    image: ${LAKEMIND_REGISTRY}/control-center:${LAKEMIND_VERSION}
    pull_policy: ${PULL_POLICY:-missing}
```

必须删除：

```yaml
pull_policy: never
```

并删除顶部“禁用 BuildKit”的说明。

正式部署命令统一为：

```bash

docker compose --env-file .env pull
docker compose --env-file .env --profile ray --profile all up -d --no-build
```

### 5.2 增加 `docker-compose.build.yml`

开发环境通过覆盖文件将正式镜像标签替换为本地 `dev` 标签：

```yaml
services:
  postgres:
    image: lakemind/postgres-age:dev

  server-api:
    image: lakemind/server-api:dev

  ray-head:
    image: ${RAY_IMAGE}

  ray-worker:
    image: ${RAY_IMAGE}

  asset-mcp:
    image: lakemind/mcp-suite:dev

  data-mcp:
    image: lakemind/mcp-suite:dev

  admin-mcp:
    image: lakemind/mcp-suite:dev

  model-serving:
    image: lakemind/model-serving:dev

  control-center:
    image: lakemind/control-center:dev
```

构建仍由 Bake 执行，避免 Compose 中重复维护多套构建参数：

```bash

docker buildx bake core --load

docker compose \
  -f docker-compose.yml \
  -f docker-compose.build.yml \
  --env-file LakeMindServer/.env \
  --profile ray \
  --profile all \
  up -d --no-build
```

---

## 6. 自研镜像收敛方案

### 6.1 三个 MCP 合并为一个 `mcp-suite` 镜像

三个 MCP 当前依赖高度一致：

- MCP SDK；
- Pydantic；
- PyYAML；
- structlog；
- httpx；
- 部分服务使用 pydantic-settings。

建议在 `LakeMindMCP/` 增加统一构建入口：

```text
LakeMindMCP/
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── LakeMindAssetMCP/
├── LakeMindDataMCP/
└── LakeMindAdminMCP/
```

统一镜像安装三个包，Compose 通过不同 `command` 启动不同模块。

优势：

- Python 基础镜像只拉取一次；
- 依赖只解析和安装一次；
- CI 由三个 Job 收敛为一个 Job；
- 三个 MCP 镜像 digest 完全一致，排查环境差异更简单；
- 不改变三个 MCP 的网络、端口、健康检查与独立扩缩容能力。

仅当未来某个 MCP 引入大型独占依赖、不同 Python 版本或独立发布节奏时，再拆回独立镜像。

### 6.2 Ray 改用官方镜像

当前 `Dockerfile.ray` 只做两件事：

1. 安装 `build-essential`；
2. 安装 `ray[default]==2.41.0` 和 NumPy。

这与官方 Ray 镜像的职责重复。建议删除 LakeMind 的 Ray 构建 Job，使用经过测试的官方镜像，并固定 digest。

若未来需要额外 Ray 运行依赖，应以官方 Ray 镜像为父镜像创建一个薄扩展层，而不是从 `python:3.12-slim` 重新安装完整 Ray。

### 6.3 保留 ControlCenter 单镜像

v0.2.0 已将前端、BFF 和 Steward 合并为一个管理面交付单元。就当前版本而言，三者版本一致、同时发布，保留单镜像可以减少构建和部署复杂度。

但应删除或归档旧的独立发布路径：

- `LakeMindMonitor` 不进入核心 CI；
- `LakeMindSteward` 不进入核心 CI；
- README、部署文档和 Release 清单统一指向 `LakeMindControlCenter`。

### 6.4 Server 与 ModelServing 必须保持独立

这两个服务的依赖特征和生命周期不同：

- Server：PyIceberg、LanceDB、DuckDB、Ray、数据库与对象存储访问；
- ModelServing：LiteLLM、FastEmbed、FunASR、FFmpeg、模型缓存。

二者不应通过业务镜像继承共享依赖。应通过 BuildKit 缓存、Python 包缓存或内部包代理共享下载结果。

---

## 7. Python 构建加速方案

### 7.1 引入锁文件

建议采用 uv，并分别维护：

```text
LakeMindServer/uv.lock
LakeMindModelServing/uv.lock
LakeMindMCP/uv.lock
LakeMindControlCenter/control/uv.lock
```

构建必须使用冻结模式，锁文件与 `pyproject.toml` 不一致时直接失败，不允许 CI 临时解析出一套新版本。

### 7.2 通用多阶段 Dockerfile

Server 建议改造为：

```dockerfile
# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:<approved-digest>
ARG UV_IMAGE=ghcr.io/astral-sh/uv:<approved-version>@sha256:<approved-digest>

FROM ${UV_IMAGE} AS uv-bin

FROM ${PYTHON_IMAGE} AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv-bin /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONDONTWRITEBYTECODE=1

# 第一层：只安装第三方依赖
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 第二层：复制频繁变化的业务代码
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime
WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LAKE_CONFIG=/etc/lakemind/engines.yaml

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/migrations /app/migrations

EXPOSE 10823
CMD ["python", "-m", "lakemind_server"]
```

效果：

- 代码修改不会让第三方依赖层失效；
- 编译器只存在于 builder，不进入运行镜像；
- 本地 BuildKit 可以复用 uv 下载缓存；
- 正式镜像只包含运行时依赖。

### 7.3 ModelServing 独立构建

ModelServing 改为独立 Python 基础镜像，不再：

```dockerfile
FROM lakemind/server-api:latest
```

并删除 Dockerfile 中重复的 `pip install litellm...`。LiteLLM、FunASR、FastEmbed 等全部写入 `pyproject.toml`，由 `uv.lock` 唯一决定版本。

FFmpeg 属于运行时依赖，保留在 runtime 阶段：

```dockerfile
FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

模型权重和模型缓存继续通过 volume 挂载，禁止打入镜像。

### 7.4 不再在 Dockerfile 中全局升级 pip

以下模式应移除：

```dockerfile
RUN pip install --upgrade pip && pip install .
```

原因：

- 每次基础镜像变化都可能得到不同 pip 版本；
- 增加网络访问与不可复现因素；
- uv 已承担解析、锁定与安装职责。

---

## 8. ControlCenter 构建加速

### 8.1 提交前端锁文件

`LakeMindControlCenter/frontend` 当前没有 `package-lock.json`。必须生成并提交：

```bash
cd LakeMindControlCenter/frontend
npm install
```

Dockerfile 改为：

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:20-alpine@sha256:<approved-digest> AS frontend-build
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY frontend/ ./
RUN npm run build
```

`npm ci` 只接受与 `package.json` 一致的锁文件，适用于 CI 和正式镜像构建。

### 8.2 Python 依赖移出 Dockerfile

当前 ControlCenter 直接在 Dockerfile 中写死 FastAPI、Uvicorn、httpx 和 Pydantic。建议增加：

```text
LakeMindControlCenter/control/pyproject.toml
LakeMindControlCenter/control/uv.lock
```

BFF 与 Steward 共用这套锁定依赖，业务代码仍在依赖层之后复制。

### 8.3 保持最终单镜像，但减少无关文件

ControlCenter 构建上下文增加 `.dockerignore`，排除：

```dockerignore
.git
**/node_modules
**/dist
**/__pycache__
**/*.pyc
.env
*.md
```

---

## 9. PostgreSQL AGE 构建优化

PostgreSQL AGE 属于稳定、低频变化的基础镜像，不应随每次业务提交重新编译。

### 9.1 使用多阶段编译

当前镜像在最终 PostgreSQL 镜像中保留了 `build-essential`、Flex、Bison 和开发包。建议：

```text
postgres:16 builder
  └── 编译 AGE，并安装到临时 DESTDIR

postgres:16 runtime
  └── 只复制 AGE 扩展产物
```

最终镜像只保留 PostgreSQL 和 AGE 运行文件。

### 9.2 独立版本

建议标签包含 PostgreSQL 版本和 AGE 源码版本，例如：

```text
postgres-age:16.4-age-1.5.0
```

该镜像仅在以下内容变化时构建：

- `LakeMindServer/docker/postgres-age/Dockerfile`；
- `age-src/**`；
- PostgreSQL 基础镜像 digest；
- 安全更新或人工触发的基础镜像刷新。

它不必在每个 LakeMind 应用版本发布时重复编译。

---

## 10. `.dockerignore` 设计

### 10.1 `LakeMindServer/.dockerignore`

```dockerignore
.git
.env
.venv
venv
__pycache__
**/__pycache__
**/*.pyc
**/*.pyo
**/*.egg-info
.pytest_cache
.mypy_cache
.ruff_cache

# 数据与模型缓存
data
**/data
**/*_cache

# Server API 构建不需要 AGE 源码
docker/postgres-age

# 非生产构建内容
tests
reports
docs
*.md
```

其中排除 `docker/postgres-age` 是 v0.2.0 源码结构下的重要优化。

### 10.2 `LakeMindModelServing/.dockerignore`

```dockerignore
.git
.env
.venv
__pycache__
**/*.pyc
data
**/*_cache
tests
*.md
```

### 10.3 `LakeMindMCP/.dockerignore`

```dockerignore
.git
**/.venv
**/__pycache__
**/*.pyc
**/*.egg-info
**/config
**/tests
*.md
```

MCP 配置在运行时通过 volume 挂载，不应复制到镜像。

### 10.4 `LakeMindControlCenter/.dockerignore`

```dockerignore
.git
.env
**/node_modules
**/dist
**/__pycache__
**/*.pyc
*.md
```

---

## 11. Buildx Bake 统一构建

根目录增加 `docker-bake.hcl`，作为本地和 CI 的唯一构建定义。

```hcl
variable "REGISTRY" {
  default = "ghcr.io/fdb-data/lakemind"
}

variable "VERSION" {
  default = "dev"
}

variable "OUTPUT_TYPE" {
  default = "docker"
}

target "_common" {
  platforms = ["linux/amd64"]
  output = ["type=${OUTPUT_TYPE}"]
}

target "server-api" {
  inherits   = ["_common"]
  context    = "LakeMindServer"
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/server-api:${VERSION}"]
}

target "postgres-age" {
  inherits   = ["_common"]
  context    = "LakeMindServer/docker/postgres-age"
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/postgres-age:${VERSION}"]
}

target "mcp-suite" {
  inherits   = ["_common"]
  context    = "LakeMindMCP"
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/mcp-suite:${VERSION}"]
}

target "model-serving" {
  inherits   = ["_common"]
  context    = "LakeMindModelServing"
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/model-serving:${VERSION}"]
}

target "control-center" {
  inherits   = ["_common"]
  context    = "LakeMindControlCenter"
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/control-center:${VERSION}"]
}

group "core" {
  targets = [
    "postgres-age",
    "server-api",
    "mcp-suite",
    "model-serving",
    "control-center"
  ]
}

group "apps" {
  targets = [
    "server-api",
    "mcp-suite",
    "model-serving",
    "control-center"
  ]
}
```

本地构建全部核心镜像：

```bash
REGISTRY=lakemind VERSION=dev docker buildx bake core --load
```

只构建 Server：

```bash
REGISTRY=lakemind VERSION=dev docker buildx bake server-api --load
```

只构建业务镜像、不重新编译 AGE：

```bash
REGISTRY=lakemind VERSION=dev docker buildx bake apps --load
```

---

## 12. GitHub Actions 改造

### 12.1 修正构建对象

核心 CI 应构建：

```text
postgres-age
server-api
mcp-suite
model-serving
control-center
```

删除核心 CI 中的：

```text
ray
asset-mcp
data-mcp
admin-mcp
monitor
steward
```

其中：

- Ray 使用官方镜像；
- 三个 MCP 合并为 `mcp-suite`；
- Monitor、Steward 已并入 ControlCenter。

`meeting-agent` 放入独立的 `examples` Job，仅在示例目录变化或 Release 明确要求时构建。

### 12.2 按文件变化生成构建矩阵

建议变更映射：

| 变化路径 | 构建目标 |
|---|---|
| `LakeMindServer/src/**`、`pyproject.toml`、`uv.lock`、迁移文件 | `server-api` |
| `LakeMindServer/docker/postgres-age/**` | `postgres-age` |
| `LakeMindMCP/**` | `mcp-suite` |
| `LakeMindModelServing/**` | `model-serving` |
| `LakeMindControlCenter/**` | `control-center` |
| `docker-bake.hcl`、公共构建配置 | 全部核心镜像 |
| `examples/meeting-agent/**` | `meeting-agent` |
| Release tag | 全部正式镜像 |

普通文档修改不触发镜像构建。

### 12.3 为每个镜像设置独立缓存作用域

当前所有 Job 均使用：

```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

建议改为：

```yaml
cache-from: type=gha,scope=${{ matrix.target }}
cache-to: type=gha,mode=max,scope=${{ matrix.target }}
```

否则多个镜像默认使用同一个 `buildkit` scope，后写入的缓存可能覆盖前一个镜像的缓存。

### 12.4 增加 Registry Cache

为了让开发机和 CI 共享缓存，可在主分支额外写入 GHCR 缓存：

```yaml
cache-from: |
  type=gha,scope=${{ matrix.target }}
  type=registry,ref=ghcr.io/fdb-data/lakemind/buildcache:${{ matrix.target }}-main
cache-to: |
  type=gha,mode=max,scope=${{ matrix.target }}
  type=registry,ref=ghcr.io/fdb-data/lakemind/buildcache:${{ matrix.target }}-main,mode=max
```

每个目标必须使用独立缓存引用，不允许所有镜像共同写入一个 cache tag。

### 12.5 统一版本标签

应用镜像建议同时发布：

```text
0.2.0
sha-<commit>
main
```

`latest` 可以作为可选易用别名，但正式 Compose 不引用 `latest`。

基础镜像采用独立版本：

```text
postgres-age:16.4-age-1.5.0
```

Release 产出一个版本清单，记录每个镜像的 digest。

### 12.6 删除不必要的 `load: true`

正式 Release Job 在 `push: true` 时不需要再将镜像载入 Runner 本地 Docker。需要本地集成测试时，应单独建立测试阶段或使用 OCI/local output，避免无意义的数据复制。

---

## 13. 镜像仓库和网络加速

### 13.1 优先使用 Registry Pull-through Cache

若开发或部署环境访问 Docker Hub 较慢，推荐在 Harbor、Nexus 或企业 Registry 中配置上游代理缓存，而不是在项目中写死不受控的公共镜像加速地址。

建议变量化：

```dotenv
LAKEMIND_REGISTRY=ghcr.io/fdb-data/lakemind
THIRDPARTY_REGISTRY=docker.io
```

内网环境可切换为：

```dotenv
LAKEMIND_REGISTRY=harbor.example.com/lakemind
THIRDPARTY_REGISTRY=harbor.example.com/proxy-dockerhub
```

### 13.2 Python 与 npm 镜像源可配置，不写死

允许通过构建环境设置：

```text
UV_INDEX_URL
UV_EXTRA_INDEX_URL
NPM_CONFIG_REGISTRY
```

私有仓库令牌使用 BuildKit secret mount，不通过 `ARG` 或 `ENV` 写入镜像历史。

### 13.3 固定 digest

正式构建的基础镜像建议采用：

```dockerfile
FROM python:3.12-slim-bookworm@sha256:<digest>
```

Release Compose 可额外生成 `docker-compose.lock.yml`，将所有应用和第三方镜像固定到 digest，用于验收、生产部署和回滚。

---

## 14. 推荐开发与交付流程

### 14.1 新开发机首次启动

```bash
# 1. 创建 Buildx builder
docker buildx create --name lakemind-builder --driver docker-container --use

# 2. 构建本地开发镜像
REGISTRY=lakemind VERSION=dev docker buildx bake core --load

# 3. 启动

docker compose \
  -f docker-compose.yml \
  -f docker-compose.build.yml \
  --env-file LakeMindServer/.env \
  --profile ray \
  --profile all \
  up -d --no-build
```

### 14.2 修改 Server 后

```bash
REGISTRY=lakemind VERSION=dev docker buildx bake server-api --load

docker compose \
  -f docker-compose.yml \
  -f docker-compose.build.yml \
  up -d --no-deps server-api
```

### 14.3 修改任意 MCP 后

```bash
REGISTRY=lakemind VERSION=dev docker buildx bake mcp-suite --load

docker compose \
  -f docker-compose.yml \
  -f docker-compose.build.yml \
  up -d --no-deps asset-mcp data-mcp admin-mcp
```

### 14.4 正式部署

```bash
cp .env.release .env

docker compose pull
docker compose --profile ray --profile all up -d --no-build
```

正式部署机器不需要项目编译工具链。

---

## 15. 实施优先级

### P0：先修复交付正确性

1. 删除“禁用 BuildKit”的说明。
2. 默认 Compose 改为完整 GHCR 镜像地址。
3. 删除 ModelServing 的 `pull_policy: never`。
4. 所有应用镜像统一使用 `0.2.0` 版本变量。
5. CI 删除旧 Monitor、旧 Steward，增加 ControlCenter。
6. Compose、CI、Release 三处镜像名称完全一致。
7. `Dockerfile.v2` 若不再使用，应删除或移动到 `legacy/`。

### P1：建立可复现依赖层

1. Server、ModelServing、MCP Suite、ControlCenter Python 增加 `uv.lock`。
2. ControlCenter 前端增加 `package-lock.json`。
3. Python Dockerfile 使用多阶段构建。
4. 源码复制移动到依赖安装之后。
5. ModelServing 取消继承 Server。
6. 增加各构建上下文的 `.dockerignore`。

### P2：减少镜像与重复构建

1. 三个 MCP 合并为 `mcp-suite`。
2. Ray 改用官方固定 digest 镜像。
3. PostgreSQL AGE 改为低频独立构建。
4. 增加 `docker-bake.hcl`。
5. 本地与 CI 都使用 Bake。

### P3：CI 与供应链完善

1. 按路径变化生成构建矩阵。
2. GHA 缓存增加目标级 `scope`。
3. 增加每镜像独立 Registry Cache。
4. Release 生成 SBOM、provenance 和 digest 清单。
5. 增加基础镜像 digest 自动更新机制。
6. 为内网或跨境环境配置可信 Registry 代理缓存。

---

## 16. 验收清单

### 16.1 Compose 与镜像交付

- [ ] `docker compose config --images` 不出现无法从 Registry 获取的 `lakemind/*` 短镜像名。
- [ ] 默认 `docker-compose.yml` 不包含 `build`。
- [ ] 默认 Compose 不包含 `pull_policy: never`。
- [ ] 空白机器执行 `docker compose pull` 可以获得全部核心镜像。
- [ ] `docker compose up -d --no-build` 能完整启动 v0.2.0。
- [ ] 所有 LakeMind 应用镜像使用同一个 `LAKEMIND_VERSION=0.2.0`。

### 16.2 镜像收敛

- [ ] Asset、Data、Admin 三个 MCP 使用同一个 `mcp-suite` digest。
- [ ] Ray 使用经过验证并固定 digest 的官方镜像。
- [ ] 核心 CI 不再构建 `LakeMindMonitor` 和旧 `LakeMindSteward`。
- [ ] CI 能构建并发布 `control-center`。
- [ ] 核心自研镜像数量收敛为 5 个。

### 16.3 构建缓存

- [ ] 修改 Server 单个 `.py` 文件时，第三方依赖安装层显示 `CACHED`。
- [ ] 修改 ControlCenter React 源码时，`npm ci` 层命中缓存。
- [ ] 修改一个 MCP 时，只构建 `mcp-suite`。
- [ ] 修改业务代码不会重新编译 PostgreSQL AGE。
- [ ] 每个 CI 构建目标使用独立 GHA cache scope。
- [ ] 不同镜像不共享同一个可写 Registry Cache tag。

### 16.4 构建上下文与镜像内容

- [ ] Server API 构建上下文不包含 `docker/postgres-age`。
- [ ] 所有 `data/`、模型缓存、数据库文件均不进入构建上下文。
- [ ] Server、MCP 等运行镜像不包含 `build-essential`。
- [ ] ModelServing 镜像不再以 Server API 为父镜像。
- [ ] 模型权重不进入 ModelServing 镜像。
- [ ] ControlCenter 使用 `package-lock.json` + `npm ci`。
- [ ] 所有 Python 正式镜像使用冻结锁文件安装。

### 16.5 Release 可复现性

- [ ] Release 同时生成版本标签与 commit SHA 标签。
- [ ] Release 清单记录所有镜像 digest。
- [ ] 正式 Compose 不引用 `latest`。
- [ ] 可以用上一版 digest 清单完成整体回滚。
- [ ] 基础镜像版本或 digest 变化会触发安全重建。

---

## 17. 最终建议

LakeMind v0.2.0 不应继续沿用“每个服务各写一个 Dockerfile、每次 CI 全部重新构建、用户本地补齐镜像”的方式。

建议将构建体系明确划分为：

```text
运行定义：docker-compose.yml
开发覆盖：docker-compose.build.yml
构建定义：docker-bake.hcl
依赖事实：uv.lock / package-lock.json
交付事实：GHCR 镜像版本 + digest 清单
```

最终形成以下规则：

> **普通用户只拉镜像；开发者只重建变化镜像；CI 只构建受影响目标；Release 才执行完整、可审计的正式构建。**

在 v0.2.0 源码现状下，最优先的不是增加更多基础镜像，而是：

1. 修正 ControlCenter 与旧 Monitor/Steward 的发布错位；
2. 统一 Compose 与 GHCR 镜像地址和版本；
3. 开启 BuildKit，并为每个镜像设置独立缓存；
4. 通过锁文件和分层 Dockerfile稳定依赖层；
5. 将三个 MCP 收敛为一个镜像；
6. 取消 ModelServing 对 Server 镜像的继承；
7. 使用官方 Ray 镜像，避免重复封装。

完成以上改造后，LakeMind 的构建复杂度、冷启动依赖、CI Job 数量和重复网络下载都会明显下降，同时发布链条会比当前实现更可靠。

---

## 18. 官方技术依据

- [Docker：Optimize cache usage in builds](https://docs.docker.com/build/cache/optimize/)
- [Docker：Cache storage backends](https://docs.docker.com/build/cache/backends/)
- [Docker：GitHub Actions cache backend](https://docs.docker.com/build/cache/backends/gha/)
- [Docker：Compose Build Specification](https://docs.docker.com/reference/compose-file/build/)
- [Docker：Buildx Bake](https://docs.docker.com/build/bake/)
- [Astral uv：Using uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
- [npm：npm ci](https://docs.npmjs.com/cli/v8/commands/npm-ci/)
- [Ray：Official Ray Docker images](https://hub.docker.com/r/rayproject/ray)
