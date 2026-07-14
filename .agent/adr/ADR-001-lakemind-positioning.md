# ADR-001: LakeMind 定位

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 文档中存在定位冲突：一方面声明"平台不执行 Skill"（`execute_skill` 已移除），另一方面 Ray Job 是平台一等能力（`/api/v1/compute/jobs/` + `submit_skill_job`）。这导致 Agent 接入时困惑：平台到底执不执行？

## 决策

LakeMind 是**认知资产平台 + 受控 Job Runtime**，不是通用 Agent Runtime。平台不负责运行 Agent 的完整推理循环、业务决策和自主行为；但提供受控 Job Runtime，用于执行 Agent 触发的、以 Skill 为定义的确定性或可复现任务。

## 理由

- 认知资产（知识/记忆/技能）的存取是核心价值，不可动摇
- Agent 需要一个可靠的执行环境来运行 Skill（确定性任务），完全不做执行会导致 Agent 必须自行管理 Ray/K8s，增加负担
- "受控"意味着 Job 以 Skill 为定义、有审批、有审计、有资源配额，不是任意代码执行
- 区别于通用 Agent Runtime（如 LangGraph Agent）：LakeMind 不做 Agent 的推理循环

## 影响

- 统一 Skill / Job / 权限 / 产品边界
- JobService 成为一等 Application Service
- `execute_skill` 不恢复，改为 `JobService.submit(skill_ref, inputs)`
- 文档统一表述为"受控 Job Runtime"

## 替代方案

1. **纯存取平台（不执行）**：Agent 自行管理执行环境。未选择：Agent 负担过重，且 Ray 集成已存在
2. **通用 Agent Runtime**：平台运行 Agent 推理循环。未选择：与"认知资产平台"定位冲突，且 Agent 框架多样性不适合统一

## 参考

设计方案 §2.2 / WP1-T09 统一表述
