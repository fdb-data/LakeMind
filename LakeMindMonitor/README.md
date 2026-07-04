# LakeMindMonitor

面向人类的只读可观测性控制台 + Steward 对话窗。仅装 MCP 客户端 SDK，全走 MCP（只读）。

> MVP 已实现。详见 [开发方案](开发方案.md)。

## 快速开始

```bash
cd ../LakeMindServer && docker compose --env-file .env up -d
cd ../LakeMindMCP   && docker compose up -d --build
cd ../LakeMindMonitor && docker compose up -d --build
# 访问 http://localhost:3000
```

## 验证

```bash
python scripts/verify_monitor.py
```
