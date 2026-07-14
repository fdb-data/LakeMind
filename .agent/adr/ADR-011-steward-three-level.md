# ADR-011: Steward 三级受控治理

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 的 Steward 可能拥有宽泛权限（通过 AdminMCP 直接执行管理操作），无审批流程。高风险操作（删除资产、轮换 Secret、回滚配置）可能被 Steward 自动执行。

## 决策

Steward 采用三级受控治理：L1 只读巡检 / L2 低风险自动修复 / L3 高风险人工审批。高风险操作必须经 OperationService 审批流程。

## 理由

- 自动化治理需要安全边界
- 高风险操作（删除、轮换、回滚）不应自动执行
- 三级模型平衡自动化效率和安全
- 与 OperationService 审批流程集成

## 影响

- Steward 巡检结果产生 DriftReport
- L2 修复自动执行（如重试失败 Binding）
- L3 操作创建 Operation（risk_level=HIGH），等待人工审批
- 详见 `docs/architecture/v0.2.0/application-services.md` §2.10 / §2.12

## 替代方案

1. **全自动治理**：未选择：高风险操作安全风险过大
2. **全人工治理**：未选择：L1/L2 自动化效率损失

## 参考

设计方案 §10.2 / ADR-001
