# ADR-002: PostgreSQL 为唯一事实源

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 配置散落在 `engines.yaml` + `.env` + 代码默认值，元数据在 PG，引擎状态在各自系统。存在多重事实源，导致配置不一致和状态判断困难。

## 决策

PostgreSQL 是 Control Plane 和资产账本的唯一事实源。所有资产元数据、Job 状态、配置 Revision、Secret、用户/租户/Token 均以 PG 为准。引擎状态（Ray / Lance / S3）不作为存在性依据。

## 理由

- PG 已是元数据存储，扩展为唯一事实源成本最低
- 引擎状态不可靠（Ray Job 可能丢失、S3 对象可能延迟一致）
- 单一事实源简化 Reconciler 逻辑：PG 为 Desired，引擎为 Actual，偏差即 Drift
- 配置 Revision 需要 ACID 事务保证，PG 天然支持

## 影响

- ConfigurationService / SecretService / JobService 均以 PG 为主存储
- ReconciliationService 以 PG 为基准扫描引擎偏差
- 引擎故障不导致数据丢失（PG 保留元数据）

## 替代方案

1. **多事实源 + 同步**：复杂度高，一致性难保证。未选择
2. **专用元数据服务（Gravitino）**：已决定不引入（见 ADR-012）

## 参考

设计方案 §5.2 / AGENTS.md §6 原则 3
