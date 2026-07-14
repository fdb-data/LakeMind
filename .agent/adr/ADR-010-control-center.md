# ADR-010: Control Center 取代 Monitor

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 的 LakeMindMonitor 是只读仪表板 + Steward 对话窗（Express），无管理能力。v0.2.0 需要统一管理入口：审批 Operation、管理用户/租户、查看审计、管理模型配置。

## 决策

LakeMindMonitor 演进为 LakeMindControlCenter，作为 Access Plane 的 BFF + 前端，提供管理入口。管理员通过 Control Center 执行管理操作，所有操作经过认证 + RBAC + Operation Service。

## 理由

- 管理操作需要 UI（审批、配置、审计查询）
- BFF 模式聚合多个 MCP + REST API，为前端提供定制接口
- 管理员身份 + RBAC 确保操作安全
- 破坏性操作通过 Operation Service 审批

## 影响

- LakeMindMonitor → LakeMindControlCenter
- 新增管理 UI：Operation 审批 / 配置管理 / 模型管理 / 审计查询
- Control Center 走 REST API (10823) + MCP (8401-8403)
- 详见 `docs/architecture/v0.2.0/four-planes.md` §1.1

## 替代方案

1. **保持 Monitor 只读 + CLI 管理**：未选择：CLI 无审计、无审批流
2. **独立管理服务**：未选择：增加部署复杂度

## 参考

设计方案 §10.1 / AGENTS.md §2
