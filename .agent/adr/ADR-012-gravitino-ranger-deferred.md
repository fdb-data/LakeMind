# ADR-012: Gravitino / Ranger 延后

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 原计划引入 Apache Gravitino（元数据目录）和 Apache Ranger（权限管理），但实际用 PG 替代了 Gravitino，权限用简单 API Key + scopes 实现。v0.2.0 需要决定是否引入。

## 决策

v0.2.0 不引入 Gravitino 和 Ranger。PG 驱动元数据和权限。延后到 v0.3.0+ 或企业版。

## 理由

- PG 已满足元数据需求（ADR-002）
- RBAC 用 PG 表 + AuthorizationService 实现，无需 Ranger 复杂度
- Gravitino 增加部署复杂度（额外组件 + 同步）
- Ranger 策略管理过重，v0.2.0 单节点场景 PG 驱动足够

## 影响

- AuthorizationService 用 PG 驱动 RBAC
- 不增加 Docker 容器
- 未来企业版可引入 Ranger 做细粒度权限

## 替代方案

1. **v0.2.0 引入 Gravitino + Ranger**：未选择：复杂度过高，单节点不需要
2. **引入 OpenFGA**：未选择：Zanzibar 模型过重

## 参考

AGENTS.md §4 "不引入" / ADR-002
