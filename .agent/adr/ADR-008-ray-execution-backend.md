# ADR-008: Ray 为首选 ExecutionBackend

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 已实现 Ray 集成（3 节点 12 CPU），但 Ray 定位不清晰：是通用计算引擎还是 Job 执行后端？API 直接暴露 Ray 概念（`submit_skill_job` / `ray_job_id`）。

## 决策

Ray 为首选 ExecutionBackend，通过 `ExecutionBackend` Provider 抽象被 JobService 调用。Ray 概念不泄漏到外部接口。

## 理由

- Ray 已集成且验证通过，复用成本低
- Ray 支持 Skill 执行、资源管理、分布式调度
- Provider 抽象允许未来替换为其他后端（K8s / Dask）
- 简化为 5 方法（submit / cancel / get_status / get_logs / get_result）

## 影响

- ExecutionBackend Provider 简化（7 → 5 方法）
- API 返回 `job_{ulid}`，不返回 Ray Job ID
- DataMCP 的 5 个 Ray 工具改为调用 JobService
- 详见 `docs/architecture/v0.2.0/provider-contracts.md` §2.6

## 替代方案

1. **K8s Jobs**：未选择：v0.2.0 是单节点，K8s 过重
2. **本地进程执行**：未选择：无分布式能力

## 参考

设计方案 §8.2 / `docs/architecture/v0.2.0/provider-contracts.md` §2.6
