# LakeMindMonitor

人类只读仪表板 + Steward 对话窗。极轻 Express 应用，无自有 DB，无自有用户系统。

## 架构

```
Express (node:20-alpine)
├── public/index.html    # 静态页面（Dashboard / Asset / Data / Admin / Chat）
└── server.js            # API 代理层 → 3 MCP + Steward
```

## API 路由

| 路由 | 方法 | 代理目标 | 说明 |
|------|------|---------|------|
| `/` | GET | — | 静态页面 |
| `/api/health` | GET | 4 服务 /health | 平台健康 |
| `/api/asset/capabilities` | GET | AssetMCP resources/read | 资产能力图 |
| `/api/asset/knowledge` | GET | AssetMCP resources/read | 知识库列表 |
| `/api/asset/skills` | GET | AssetMCP resources/read | 技能列表 |
| `/api/asset/memory` | GET | AssetMCP resources/read | 记忆概况 |
| `/api/asset/ontology` | GET | AssetMCP resources/read | 本体列表 |
| `/api/data/tables` | GET | DataMCP tools/call | 表列表 |
| `/api/admin/health` | GET | AdminMCP tools/call | 平台健康详情 |
| `/api/admin/tenants` | GET | AdminMCP tools/call | 租户列表 |
| `/api/admin/users` | GET | AdminMCP tools/call | 用户列表 |
| `/api/admin/tokens` | GET | AdminMCP tools/call | Token 列表 |
| `/api/chat` | POST | Steward /chat | 对话 |
| `/api/inspect` | POST | Steward /inspect | 巡检 |

## 启动

```bash
cd LakeMindMonitor && docker compose up -d --build
```

访问 http://localhost:3000

## 验证

```bash
python scripts/verify_monitor.py   # 18/18 PASS
```
