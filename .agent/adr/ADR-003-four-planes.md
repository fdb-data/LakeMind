# ADR-003: 四平面架构

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 无明确平面边界，代码中 MCP 直连底层引擎（S3/Lance/PG），REST API handler 包含业务逻辑，认证中间件与业务逻辑混合。导致代码耦合高、测试困难、安全边界不清晰。

## 决策

采用四平面逻辑架构：Access Plane / Control Plane / Data & Index Plane / Execution Plane。每个平面有明确职责、信任级别和调用方向约束。

## 理由

- 明确边界降低耦合：Access 不含业务逻辑，Control 不直连引擎
- 信任级别指导安全设计：最不可信的 Access 不接触密钥
- 调用方向约束防止反向依赖：Execution 不调用 Control
- 为 WP2-WP9 实现提供清晰骨架

## 影响

- REST API handler 拆分为路由层（Access）+ Service 层（Control）
- MCP 降为协议适配层，调用同一 Application Service
- Provider 抽象正式化为 Data Plane 契约
- 详见 `docs/architecture/v0.2.0/four-planes.md`

## 替代方案

1. **三层架构（API/Service/DAO）**：经典但无法区分执行层和存储层。未选择
2. **微服务**：每 Service 独立进程。未选择：v0.2.0 是单节点部署，微服务增加运维复杂度

## 参考

设计方案 §4.1-§4.3 / `docs/architecture/v0.2.0/four-planes.md`
