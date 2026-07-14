# ADR-014: 配置 Revision + Desired/Active

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 配置无版本控制，变更直接生效。无法回滚、无审计、无变更原因记录。生产环境配置变更风险高。

## 决策

配置采用 Revision + Desired/Active 模型。每次变更产生新 Revision（DRAFT），激活后变为 ACTIVE。支持回滚到任意 Revision。Desired 是最新激活的配置，Active 是实例实际运行的配置。

## 理由

- 配置变更需要审计（谁、何时、为什么、改了什么）
- 回滚能力是生产环境基本要求
- Desired/Active 分离支持热更新和一致性检查
- Reconciler 检查 Desired vs Active 偏差

## 影响

- 新增 ConfigurationService + `/api/v1/configuration/*` API
- 配置变更流程：set() → Revision(DRAFT) → activate() → Operation → ACTIVE
- Reconciler 扫描 Desired vs Active 偏差
- 详见 `docs/architecture/v0.2.0/application-services.md` §2.7

## 替代方案

1. **GitOps**：配置存 Git。未选择：v0.2.0 单节点，Git 增加流程复杂度
2. **直接覆盖**：v0.1.0 方式。未选择：无回滚、无审计

## 参考

设计方案 §9.1 / ADR-002 / ADR-009
