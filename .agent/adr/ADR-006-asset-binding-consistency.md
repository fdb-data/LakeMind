# ADR-006: Asset Binding + 最终一致性

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

资产数据跨多个存储（S3 + Lance + PG + Iceberg），无分布式事务保证。v0.1.0 在 MCP tool 内手动编排多存储操作，部分失败时留下不一致状态。

## 决策

采用 Asset Binding 模型 + Outbox + Reconciler 实现最终一致性。每个资产有多个 Binding（如 S3 Binding + Vector Binding），每个 Binding 独立状态管理。Outbox 保证事件投递，Reconciler 修复偏差。

## 理由

- 跨存储分布式事务代价极高（XA / 2PC），不适合对象存储 + 向量数据库
- Binding 模型将複杂度分解：每个 Binding 独立成功/失败
- Outbox 模式是成熟的最终一致性方案
- Reconciler 提供可观测性和自动修复

## 影响

- 资产状态：CREATING → PROCESSING → READY / DEGRADED / FAILED
- 新增 ReconciliationService 扫描 Binding 状态偏差
- Outbox Worker 投递事件
- 详见 `docs/architecture/v0.2.0/application-services.md` §2.1 / §2.12

## 替代方案

1. **Saga 模式**：补偿事务。未选择：跨 S3/Lance 补偿操作难以定义
2. **同步编排 + 重试**：v0.1.0 方式。未选择：部分失败时状态不一致

## 参考

设计方案 §7.4 / `docs/api-spec/v0.2.0/operation-events.md`
