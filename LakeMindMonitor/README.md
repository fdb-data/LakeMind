# LakeMindMonitor

LakeMind 面向人类的专业可观测性控制台。只读展示 + Steward 对话。

## 架构

```
Express BFF (server.js)          # API 代理层 → 3 MCP + Steward
├── public/                      # Vue 3 + Element Plus 构建产物
└── frontend/                    # Vue 3 + Vite + Pinia 源码
    └── src/views/
        ├── Dashboard.vue        # 系统总览（12容器+11引擎+资产计数）
        ├── Asset.vue            # 认知资产（知识/技能/记忆/本体）
        ├── Data.vue             # 数据引擎（Iceberg/向量/S3/KV/图）
        ├── Admin.vue            # 管理只读（租户/用户/Token/类型/健康）
        └── Chat.vue             # Steward 对话 + 巡检面板
```

## 5 页功能

| 页面 | 功能 |
|------|------|
| **Dashboard** | 12 容器状态网格 + 11 引擎健康矩阵 + 资产/数据/平台计数 + 15s 自动刷新 |
| **Asset** | 4 Tab：知识库（概念数/类型分布）、技能（名称/描述/标签）、记忆（总数/最近条目）、本体（节点/边） |
| **Data** | 5 Tab：Iceberg 表（schema 描述）、向量表、S3 对象（前缀过滤）、KV（前缀扫描）、图概览 |
| **Admin** | 5 Tab：租户、用户、Token（脱敏只读）、资产类型、平台健康（引擎+节点）— **无任何写操作** |
| **Chat** | Steward 对话 UI + 6 快捷指令 + 巡检面板（引擎健康矩阵）+ localStorage 历史 |

## API 路由

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/dashboard/overview` | GET | 聚合端点：容器+引擎+资产+数据+平台 |
| `/api/asset/*` | GET | 认知资产（knowledge/skills/memory/ontology） |
| `/api/data/*` | GET | 数据引擎（tables/vectors/s3/kv/graph） |
| `/api/admin/*` | GET | 管理只读（health/nodes/metrics/tenants/users/tokens/asset-types） |
| `/api/chat` | POST | Steward 对话代理 |
| `/api/inspect` | POST | Steward 巡检代理 |
| `/api/steward/health` | GET | Steward 连通性检测 |

## 启动

```bash
# 前端构建（本地）
cd LakeMindMonitor/frontend && npm install && npm run build
cp -r dist/* ../public/

# 容器启动
cd LakeMindMonitor && docker compose up -d --build
```

访问 http://localhost:3000

## 技术栈

| 层 | 选型 |
|----|------|
| BFF | Express + node:20-alpine |
| 前端 | Vue 3 + Vite + Element Plus + Pinia + vue-router |
| 主题 | 深色主题（GitHub Dark 风格） |
