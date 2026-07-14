# ADR-007: Job / Skill / Attempt / Artifact 分离

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 的 Ray Job 状态与 LakeMind Job 混合：`ray_jobs` 表直接存储 Ray Job ID，Job 状态直接来自 Ray Dashboard。导致 Ray 故障时 Job 状态丢失，无法重试，无法追踪历史。

## 决策

将 Job 概念分离为四个实体：Skill（定义）→ JobRun（一次提交）→ JobAttempt（一次执行）→ Artifact（执行产物）。PG 为 Job 事实源，Ray 仅为执行后端。

## 理由

- Skill 是不可变定义，JobRun 是可变实例，分离符合领域建模
- JobAttempt 记录每次执行（含重试），便于调试和审计
- Artifact 资产化，可被后续 Job 引用
- PG 为事实源，Ray 故障不丢失 Job 元数据

## 影响

- `ray_jobs` 表扩展为 `job_runs` + `job_attempts` + `artifacts`
- JobService 接口：submit / get_job / cancel / retry / get_result / get_attempts
- retry 创建新 Attempt，不覆盖原 Attempt
- 详见 `docs/architecture/v0.2.0/application-services.md` §2.5

## 替代方案

1. **单表设计**：Job + Attempt 合并。未选择：重试历史查询困难
2. **Ray 为事实源**：未选择：Ray 故障导致数据丢失

## 参考

设计方案 §8.1 / ADR-002
