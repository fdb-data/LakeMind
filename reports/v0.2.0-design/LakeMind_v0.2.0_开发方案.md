# LakeMind v0.2.0 开发方案与计划

> **版本：v0.2.0 — Trustworthy Single-Node｜可信单节点版**  
> **文档性质：开发方案、工作分解、里程碑与执行计划**  
> **依据：[LakeMind_v0.2.0_设计方案.md](./LakeMind_v0.2.0_设计方案.md)**  
> **日期：2026-07-13**

---

## 0. 文档说明

本文将设计方案转化为**可执行的开发方案**，包含：

1. 工作分解结构（WBS）——每个 WP 拆解为可分配的 Task；
2. 阶段计划与里程碑——6 阶段（A–F）的时间线与交付物；
3. 依赖关系与并行策略——哪些可以并行，哪些必须串行；
4. 数据库迁移计划——v0.1.0 → v0.2.0 的 schema 演进；
5. 风险登记与缓解措施；
6. 验收与验证策略——逐 WP 的 DoD（Definition of Done）；
7. ADR 清单与文档更新计划；
8. 团队配置与工作量估算。

**估算单位**：1 SP ≈ 1 人理想日。总估算不含管理开销。

---

# 1. 总体执行策略

## 1.1 核心原则

| 原则 | 说明 |
|------|------|
| 设计先行 | 阶段 A 冻结契约后才开始大规模编码 |
| 垂直切片 | 每个 WP 产出端到端可验证的切片，而非水平层 |
| 事实源驱动 | PostgreSQL 账本先行，引擎 Binding 后接 |
| 安全左移 | 安全测试与功能开发同步，不事后补 |
| 可恢复优先 | Outbox/Reconciler 与功能同步建设 |
| 文档同步 | 每个 WP 交付时同步更新对应文档 |

## 1.2 阶段总览

```
阶段 A 设计冻结        ████░░░░░░  2 周
阶段 B Control Plane   ████████░░  4 周
阶段 C Asset Runtime   ██████████  5 周
阶段 D Job + Model     ████████░░  4 周
阶段 E Control Center  ██████░░░░  3 周
阶段 F 硬化与发布      ████░░░░░░  2 周
                     ─────────────────────
                     总计约 20 周（5 个月）
```

并行窗口：

- 阶段 B 后期与阶段 C 前期可部分并行（Asset Core 依赖 B 的 Security Context，但 Knowledge/Skill 模型设计可先行）；
- 阶段 D 的 Job 与 ModelServing 两个子流可并行；
- 阶段 E 依赖 B/C/D 的 API 契约，但前端骨架可在 D 后期启动；
- 阶段 F 必须在所有功能 WP 完成后进行。

## 1.3 里程碑

| 里程碑 | 时间 | 标志 |
|--------|------|------|
| M0 — 设计冻结 | 第 2 周末 | 四平面文档 + API v1 规范 + ADR 1-15 签署 |
| M1 — Control Plane 可用 | 第 6 周末 | Security Context + Token + Config + Audit 端到端跑通 |
| M2 — Asset Runtime 可用 | 第 11 周末 | Knowledge/Skill/Memory CRUD + Binding + 状态机 + Reconciler |
| M3 — Job + Model 可用 | 第 15 周末 | Job 提交 → Ray 执行 → Artifact → 资产化全链路 |
| M4 — Control Center 可用 | 第 18 周末 | 10 页面 + 管理员认证 + Operation 审批 |
| M5 — v0.2.0 发布 | 第 20 周末 | Meeting Agent Golden Pass + 全验收标准通过 |

---

# 2. 工作分解结构（WBS）

## 2.1 WP1：架构与契约基础

> **目标**：冻结 v0.2.0 逻辑架构和外部契约，为后续所有 WP 提供"地基"。
> **阶段**：A | **估算**：24 SP | **依赖**：无

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| WP1-T01 | 编写四平面架构文档 | `docs/architecture/v0.2.0/four-planes.md`，含组件归属、Trust Boundary、禁止事项 | 3 | — |
| WP1-T02 | 定义 Application Service 边界 | 12 个 Service 的接口签名文档 + 依赖图 | 3 | T01 |
| WP1-T03 | 制定 API v1 规范 | OpenAPI 3.1 spec：`/api/v1/*` 全部资源端点、错误模型、分页、幂等 | 4 | T02 |
| WP1-T04 | 统一资源 ID 与 URI 规范 | ID 前缀表 + 逻辑 URI grammar + 物理 ID 不外泄规则 | 2 | T02 |
| WP1-T05 | 统一错误模型 | 错误码枚举 + 错误响应 schema + 可重试性标记 | 2 | T03 |
| WP1-T06 | Operation / 事件 / 幂等规范 | Operation 状态机 + 事件名清单 + Idempotency Key 规则 | 2 | T03 |
| WP1-T07 | MCP 与 REST 共享语义方案 | MCP tool → Application Service 映射表，消除 MCP 自编排 | 2 | T02 |
| WP1-T08 | 编写 ADR 1-15 | `.agent/adr/ADR-001` 至 `ADR-015` | 3 | T01-T07 |
| WP1-T09 | 消除文档定位冲突 | 更新 AGENTS.md / README / .agent/DESIGN.md，统一"受控 Job Runtime"表述 | 2 | T08 |
| WP1-T10 | 内部 Provider 契约定义 | 10 个 Provider 抽象接口（Python Protocol/ABC） | 1 | T02 |

**DoD**：
- 四平面文档经团队评审签署；
- API v1 OpenAPI spec 可渲染（Swagger/Redoc）；
- ADR 1-15 全部合并到主分支；
- 现有文档中"平台不执行 Skill"与"Ray Job 一等能力"的冲突表述已消除。

---

## 2.2 WP2：Control Plane 与安全

> **目标**：建立可信身份、授权、配置、Secret、审计和管理操作的基础设施。
> **阶段**：B | **估算**：48 SP | **依赖**：WP1

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| **WP2-S1：数据库迁移基础** | | | | |
| WP2-T01 | 统一迁移机制 | Alembic 迁移框架接入，`migrations/` 目录，版本化 schema | 2 | WP1 |
| WP2-T02 | Control Plane 核心 schema | `principals` `tenants` `roles` `role_bindings` `tokens` `audit_log` `operations` `config_revisions` `config_values` `secrets` `instance_registry` `outbox` 表 | 4 | T01 |
| **WP2-S2：身份与授权** | | | | |
| WP2-T03 | Security Context 实现 | 请求 → Token 解析 → SecurityContext 对象（Principal/Tenant/Roles/Scopes） | 3 | T02 |
| WP2-T04 | 统一 Token 体系 | Token 签发（哈希存储）、撤销（实时生效）、绑定 Principal/Tenant/Scope/过期 | 3 | T03 |
| WP2-T05 | RBAC + 资源级授权 | AuthorizationService：角色 → 动作 → 资源规则；所有动作枚举（§8.4） | 4 | T03 |
| WP2-T06 | 租户隔离强制 | Server 端 SecurityContext → 物理路径解析；移除 MCP 层 Tenant Header 拼接 | 3 | T05 |
| WP2-T07 | Protected Namespace | S3 Key / Lance Path / Iceberg Namespace 生成规则 + DataMCP 写保护 | 2 | T06 |
| **WP2-S3：配置与实例** | | | | |
| WP2-T08 | Configuration Service | Schema 定义 + 作用域 + 默认值 + 校验 + Revision + 激活 + 回滚 | 4 | T02 |
| WP2-T09 | 配置优先级解析 | 系统默认 < 平台 < 租户 < Agent/Service < Job 覆盖；安全配置不可覆盖 | 2 | T08 |
| WP2-T10 | Instance Registry | 服务注册 + 心跳 + Capability + Active Revision 上报 | 2 | T02 |
| WP2-T11 | 配置生效模式 | HOT_RELOAD / COMPONENT_RELOAD / SERVICE_RESTART 标记 + Desired/Active 收敛检测 | 2 | T08 |
| **WP2-S4：Secret** | | | | |
| WP2-T12 | Secret Service | 加密存储（PG + 主密钥外部引用）、secret_ref 引用、版本、轮换、使用记录 | 3 | T02 |
| WP2-T13 | Secret 最小注入 | Job Secret 按 Skill Manifest + 调用者权限 + Job 目的注入；控制面全局密钥不注入 Ray | 2 | T12 |
| **WP2-S5：审计与 Operation** | | | | |
| WP2-T14 | Audit Service | 审计事件写入 + 查询 + 过滤；覆盖 §8.7 全部审计点 | 3 | T02 |
| WP2-T15 | Operation Service | Operation 状态机（PENDING→APPROVAL_REQUIRED→APPROVED→RUNNING→SUCCEEDED/FAILED/CANCELLED）+ 风险等级 + 审批 | 3 | T14 |
| WP2-T16 | Outbox 基础 | PG Outbox 表 + Worker 拉取 + 幂等执行 + 重试 | 3 | T02 |
| **WP2-S6：网络与集成** | | | | |
| WP2-T17 | 网络边界调整 | Docker Compose 网络隔离：内部端口不对外；Service Identity 替代共享 API Key | 2 | T10 |
| WP2-T18 | REST API 认证中间件 | 所有 `/api/v1/*` 端点接入 SecurityContext + Authorization | 2 | T05 |
| WP2-T19 | 跨租户隔离测试 | 自动化测试：Tenant A 无法访问 Tenant B 资产/Job/Secret | 2 | T06 |

**DoD**：
- Token 撤销在 REST + 3 MCP + Control Center 全部入口实时生效；
- 伪造 Tenant Header 无法改变 SecurityContext；
- Configuration Revision 变更产生记录且可回滚；
- Secret API 不返回明文；
- 审计日志覆盖所有高风险操作；
- 跨租户测试自动化通过。

---

## 2.3 WP3：Asset Runtime

> **目标**：让 Knowledge、Skill、Memory 真正成为可版本化、可审计、可恢复的平台资产。
> **阶段**：C | **估算**：52 SP | **依赖**：WP1, WP2

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| **WP3-S1：Asset Core** | | | | |
| WP3-T01 | Asset Core schema | `assets` 表：Asset ID / Tenant / Type / Name / Version / Status / Owner / Visibility / Source / Checksum / Metadata / 时间戳 | 3 | WP2 |
| WP3-T02 | Asset Binding schema | `asset_bindings` 表：Binding ID / Asset ID / Type / Provider / Physical URI / Status / Required / Last Error | 2 | T01 |
| WP3-T03 | 资产状态机 | DRAFT→CREATING→PROCESSING→READY / DEGRADED / FAILED / DEPRECATED→DELETING→DELETED；转换校验 + 事件发射 | 3 | T01 |
| WP3-T04 | AssetService 公共接口 | create / get / list / update / delete / get_bindings / reindex / get_lineage | 3 | T03 |
| WP3-T05 | 版本与 Revision | 内容版本 + Metadata Revision + Binding Version 三级版本语义 | 2 | T03 |
| WP3-T06 | 血缘记录 | `asset_lineage` 表：来源对象 / Skill 版本 / Job Run / 输入资产版本 / 模型 / 输出 Artifact / 配置 Revision | 2 | T01 |
| **WP3-S2：Knowledge** | | | | |
| WP3-T07 | Knowledge 模型与 schema | Knowledge 特有字段：解析器版本 / Embedding Space / 索引状态 / Chunk 配置 | 2 | T04 |
| WP3-T08 | Knowledge 摄入流程 | 上传 → 创建资产(CREATING) → Outbox → 写 S3 → 解析 → Chunk → Embedding → Binding → READY | 4 | T07 |
| WP3-T09 | Knowledge 检索 | 语义检索（Lance）+ 元数据过滤 + 来源追溯；不返回 DEGRADED/FAILED 的向量 | 3 | T08 |
| WP3-T10 | Embedding 失败处理 | 失败 → DEGRADED（非 READY）；不写零向量；保留原始内容；支持后台重试 | 2 | T08 |
| WP3-T11 | Knowledge 重建索引 | reindex Operation：清除旧 Binding → 重新 Chunk + Embed → 新 Binding | 2 | T09 |
| **WP3-S3：Skill** | | | | |
| WP3-T12 | Skill 模型与 schema | Manifest / 代码 Checksum / 输入输出 Schema / Entry Point / 依赖锁定 / 权限声明 / 模型 Profile / Secret 声明 / 资源需求 / 网络需求 / 可信级别 | 3 | T04 |
| WP3-T13 | Skill 生命周期 | DRAFT→VALIDATING→PUBLISHED→DEPRECATED / REVOKED；发布后不可变 | 2 | T12 |
| WP3-T14 | Skill 校验 | Manifest 校验 + 代码 Checksum + 依赖安全扫描 + Schema 校验 | 2 | T13 |
| WP3-T15 | Skill 检索 | 按名称 / 版本 / 可信级别 / 发布状态检索；读取权限与执行权限分离 | 2 | T13 |
| **WP3-S4：Memory** | | | | |
| WP3-T16 | Memory 模型与 schema | Memory Type / Subject / Scope / Source / Content / Importance / Retention / Expiration / Access Scope / Embedding Status / Consolidation Status / Revision | 3 | T04 |
| WP3-T17 | 临时态 vs 持久态分离 | Working/Session Memory（Valkey TTL）vs 持久 Memory（Lance + PG 账本） | 2 | T16 |
| WP3-T18 | Memory CRUD | add / search / get / list / update / delete / clear / history（mem0 风格 8 方法） | 3 | T17 |
| WP3-T19 | Memory 过期与归档 | TTL 过期清理 + 归档 Operation + 保留期限策略 | 2 | T18 |
| **WP3-S5：一致性与恢复** | | | | |
| WP3-T20 | Outbox Worker（资产） | 消费资产 Outbox 事件 → 写 S3/Lance/Graph → 更新 Binding 状态 → 幂等 | 3 | WP2-T16 |
| WP3-T21 | Reconciler | 定期扫描：Binding 状态偏差 / DELETING 超时 / DEGRADED 可重试 / 索引缺失 → 修复或标记 | 3 | T20 |
| WP3-T22 | 异步删除 | DELETING → 撤销引用 → 清除全部 Binding → 检查血缘 → DELETED；失败保持 DELETING + Reconciler 重试 | 3 | T21 |
| WP3-T23 | 故障注入测试 | S3 成功 + Embedding 失败 → DEGRADED；Lance 丢失 → 重建；删除失败 → 保持 DELETING | 2 | T22 |

**DoD**：
- Knowledge/Skill/Memory 共享统一 Asset Core；
- 每个资产可查看 Binding 状态和血缘；
- Required Binding 全部完成才进入 READY；
- Embedding 失败不写伪零向量；
- 删除最终清理所有 Binding 或保持 DELETING 由 Reconciler 处理；
- 索引可重建；
- 故障注入测试自动化通过。

---

## 2.4 WP4：Job Runtime 与 Ray

> **目标**：建立受控、可审计、可恢复的任务运行时。
> **阶段**：D | **估算**：36 SP | **依赖**：WP1, WP2, WP3

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| **WP4-S1：Job 模型** | | | | |
| WP4-T01 | Job Run / Attempt schema | `job_runs` `job_attempts` 表：Skill 版本 / 输入 / 模型绑定 / Secret 引用 / 参数 / 状态 / 资源 / 时间戳 | 3 | WP3 |
| WP4-T02 | Job 状态机 | SUBMITTED→QUEUED→RUNNING→SUCCEEDED/FAILED/CANCELLING/CANCELLED/TIMED_OUT/LOST | 2 | T01 |
| WP4-T03 | Artifact 模型 | `job_artifacts` 表：Artifact ID / Job Run / Type / URI / Checksum / 可资产化标记 | 2 | T01 |
| **WP4-S2：JobService** | | | | |
| WP4-T04 | Job 提交 API | submit（Skill 版本 + 输入 + 参数 + 模型 Profile + 资源覆盖）→ 权限校验 → Skill 资格校验 → 资源配额 → 创建 Job Run | 3 | T02 |
| WP4-T05 | Skill 执行资格校验 | 只允许 PUBLISHED 且未 REVOKED 的可信 Skill；移除任意 eval/源码执行入口 | 2 | T04 |
| WP4-T06 | 资源配额 | Skill 默认 + 租户上限 + 平台上限 + Job 覆盖 → 最终资源；不可突破租户配额 | 2 | T04 |
| WP4-T07 | Secret 与模型绑定 | Skill 声明 → Control Plane 解析 → Secret 最小注入 + Model Profile → Deployment 解析 → 固定到 Job Run | 3 | T04 |
| **WP4-S3：Execution Backend** | | | | |
| WP4-T08 | ExecutionBackend 抽象 | Python Protocol：submit / cancel / get_status / get_logs / get_result | 2 | T02 |
| WP4-T09 | RayExecutionBackend | 实现 ExecutionBackend → Ray Job Submission；LakeMind Job ID ↔ Ray Job ID 映射 | 3 | T08 |
| WP4-T10 | Job 状态同步 | Ray 状态 → LakeMind Job Run/Attempt 状态同步（PG 为事实源）；Lost 检测 | 2 | T09 |
| **WP4-S4：恢复与结果** | | | | |
| WP4-T11 | 重试 / 取消 / 超时 | 重试产生新 Attempt；取消 → CANCELLING → CANCELLED；超时 → TIMED_OUT | 2 | T10 |
| WP4-T12 | Server 重启恢复 | 启动时扫描 RUNNING Job → 校准 Ray 状态 → 标记 LOST 或恢复 | 2 | T10 |
| WP4-T13 | 日志归档 | Job 日志 → S3 Artifact；Result URI 注册 | 2 | T03 |
| WP4-T14 | Artifact 资产化 | Artifact → 注册为 Knowledge 或 Memory 的 Operation | 2 | T13 |
| WP4-T15 | 可复现性记录 | Job Run 固定：Skill 版本 / 包 Checksum / 输入版本 / 参数 / 环境 / 模型 ID+Deployment+Revision / 配置 Revision / Secret 引用版本 | 2 | T07 |

**DoD**：
- Skill / Job Run / Attempt / Artifact 边界清晰；
- 只执行可信 PUBLISHED Skill 或内置 Job；
- 任意源码 eval 入口已移除；
- Job 不获得控制面全部环境变量；
- Secret 按最小范围注入；
- 重试 / 取消 / 超时 / Lost 全部支持；
- Server 重启后 Job 状态可恢复；
- Ray 状态异常被 Reconciler 发现；
- Artifact 可资产化。

---

## 2.5 WP5：ModelServing 管理

> **目标**：将模型服务纳入统一 Control Plane 管理。
> **阶段**：D（与 WP4 并行） | **估算**：28 SP | **依赖**：WP1, WP2

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| **WP5-S1：模型领域模型** | | | | |
| WP5-T01 | Model Definition schema | `model_definitions` 表：ID / 名称 / 类型 / 能力 / Provider Family / 上下文长度 / Embedding 维度 / 模态 | 2 | WP2 |
| WP5-T02 | Model Deployment schema | `model_deployments` 表：ID / Model ID / Provider / Endpoint / Secret Ref / 状态 / 优先级 / 超时 / 并发 / 健康 / Config Revision | 2 | T01 |
| WP5-T03 | Model Profile / Alias | `model_profiles` 表：逻辑名称（meeting-asr / knowledge-embedding 等）→ Route | 2 | T01 |
| WP5-T04 | Model Route | `model_routes` 表：Profile → Deployment 列表 + 优先级 + Fallback + 租户覆盖 | 2 | T03 |
| WP5-T05 | Embedding Space | `embedding_spaces` 表：模型 + Revision + 维度 + 归一化 + 距离度量 + 索引版本；不兼容模型不可 Fallback | 2 | T01 |
| **WP5-S2：配置与运行** | | | | |
| WP5-T06 | Control Plane 模型管理 API | CRUD for Model Definition / Deployment / Profile / Route / Embedding Space；全部产生 Revision | 3 | T04 |
| WP5-T07 | Secret Ref 替换 | Deployment 中 API Key → Secret Ref；不保存明文 | 1 | T02 |
| WP5-T08 | models.yaml 导入 | 首次部署 / 开发环境 Bootstrap 导入 → PG；之后 YAML 不覆盖动态配置 | 2 | T06 |
| WP5-T09 | ModelServing 配置加载 | ModelServing 启动 → 拉取 Desired Revision → 加载 → 上报 Active Revision | 2 | T06 |
| WP5-T10 | 配置生效模式 | HOT_RELOAD（路由/优先级） / MODEL_RELOAD（本地模型/Batch） / SERVICE_RESTART（设备/缓存） | 2 | T09 |
| **WP5-S3：Job 绑定与审计** | | | | |
| WP5-T11 | Job 模型绑定解析 | Skill 声明 Model Profile → Control Plane 解析 → Model ID + Deployment ID + Revision + Embedding Space → 固定到 Job Run | 2 | T04 |
| WP5-T12 | 模型管理 Operation | 切换默认模型 / 禁用 Deployment / Reload → Operation Service → 校验 → 审计 | 2 | T10 |
| WP5-T13 | 实例健康上报 | ModelServing 实例 → Instance Registry：健康 / 延迟 / 错误率 / 当前 Revision | 1 | T09 |

**DoD**：
- Model Definition / Deployment / Profile / Route / Embedding Space 概念分离且持久化；
- Provider 密钥使用 Secret Ref，不保存明文；
- ModelServing 加载 Desired Revision 并上报 Active Revision；
- Job 记录实际模型和 Deployment；
- 不兼容 Embedding 模型不能写入同一向量空间；
- 模型管理动作全部可审计。

---

## 2.6 WP6：LakeMind Control Center

> **目标**：将 LakeMindMonitor 演进为统一全局管理入口。
> **阶段**：E | **估算**：34 SP | **依赖**：WP2, WP3, WP4, WP5

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| **WP6-S1：基础设施** | | | | |
| WP6-T01 | 目录合并 | `LakeMindMonitor/` + `LakeMindSteward/` → `LakeMindControlCenter/`（前端 + BFF + Steward 后端） | 2 | WP2 |
| WP6-T02 | 管理员认证 | 管理员身份 + 会话 + 角色；移除共享静态 Token；BFF 使用独立 Service Identity | 3 | T01 |
| WP6-T03 | BFF 架构 | BFF → Control Plane API；不直连 PG/S3/Ray/ModelServing | 2 | T02 |
| WP6-T04 | 页面权限控制 | 根据管理员角色控制页面和操作可见性 | 1 | T02 |
| **WP6-S2：10 个页面** | | | | |
| WP6-T05 | Overview 页 | 服务健康 / 资产总量 / Job 趋势 / Outbox 积压 / Reconciler 异常 / 安全事件 / 配置收敛 | 2 | T03 |
| WP6-T06 | Assets 页 | Knowledge/Skill/Memory 分类 / 状态 / 版本 / Binding / 血缘 / DEGRADED+FAILED / 触发 Operation | 3 | T03 |
| WP6-T07 | Jobs 页 | Job Run + Attempt / Skill 绑定 / 状态 / 日志 / 结果 / 重试 / 取消 / 标记 Lost / 资源使用 | 3 | T03 |
| WP6-T08 | Model Serving 页 | Models / Deployments / Routing / Runtime 四子页（§11.5） | 3 | T03 |
| WP6-T09 | Services 页 | 实例列表 / 版本 / 心跳 / Desired vs Active Revision / 健康 | 2 | T03 |
| WP6-T10 | Configuration 页 | 平台 / 租户 / Agent 配置 / 功能开关 / Schema / Revision / 变更历史 / 回滚 | 2 | T03 |
| WP6-T11 | Security 页 | 用户 / Agent / Service Account / 租户 / 角色 / Token / Secret 元数据 / Skill 可信级别 / 策略 / 拒绝事件 | 2 | T03 |
| WP6-T12 | Operations 页 | Operation 列表 / 状态 / 审批 / 执行结果 / 审计 | 2 | T03 |
| WP6-T13 | Audit 页 | 审计事件查询 / 过滤 / 导出 | 1 | T03 |
| WP6-T14 | Steward 页 | Steward 对话 / 巡检结果 / 治理建议 / 待批准 Operation / 自动策略 | 2 | T03 |
| **WP6-S3：Operation 集成** | | | | |
| WP6-T15 | 写操作 → Operation Service | 所有页面写操作统一进入 Operation Service；高风险需二次确认/审批 | 2 | T12 |
| WP6-T16 | 审计集成 | 所有管理操作写入 Audit | 1 | T15 |

**DoD**：
- 10 个页面全部可用；
- 管理员有身份和角色，不使用共享静态 Token；
- 所有写操作通过 Operation Service；
- BFF 不直连底层引擎；
- 高风险操作有二次确认/审批；
- 管理操作全部有审计。

---

## 2.7 WP7：Steward 治理

> **目标**：将 Steward 从管理对话工具升级为受控治理 Agent。
> **阶段**：E（与 WP6 后期并行） | **估算**：16 SP | **依赖**：WP2, WP6

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| WP7-T01 | 独立 Service Identity | Steward Service Account + Token + 权限范围（非超级管理员） | 2 | WP2 |
| WP7-T02 | Level 1 观察 | 巡检：服务健康 / DEGRADED 资产 / Lost Job / Outbox 积压 / Binding 偏差 / 配置偏差 → 诊断报告 | 3 | T01 |
| WP7-T03 | Level 2 低风险自动治理 | 策略授权范围内：重试 Embedding / 重建索引 / 同步 Ray 状态 / 运行 Reconciler / 清理临时文件 / 执行已批准 Reload | 3 | T02 |
| WP7-T04 | Level 3 高风险审批 | 删除资产 / 撤销 Token / 修改安全策略 / 禁用模型 / 停止服务 → 创建待批准 Operation | 2 | T03 |
| WP7-T05 | 治理策略配置 | 自动操作级别 + 允许动作清单 + 风险阈值 → Configuration Service | 2 | T03 |
| WP7-T06 | 结果审计 | 所有 Steward 动作写入 Audit + 关联 Operation | 1 | T04 |
| WP7-T07 | Control Center 集成 | Steward 页面展示对话 / 巡检 / 建议 / 待批准 Operation | 2 | WP6 |
| WP7-T08 | 不绕过审批 | LLM 判断不绕过 Operation 审批；不以系统提示词代替权限控制 | 1 | T04 |

**DoD**：
- Steward 使用独立 Service Identity，非超级管理员；
- 三级动作模型清晰且可配置；
- 高风险操作必须审批；
- Steward 不直连数据库和引擎；
- 所有动作有审计。

---

## 2.8 WP8：Meeting Agent Golden Path

> **目标**：以真实参考应用验证全部核心能力。
> **阶段**：F | **估算**：18 SP | **依赖**：WP3, WP4, WP5, WP6

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| WP8-T01 | Meeting Skill 发布 | ASR Skill + 摘要 Skill + 知识提取 Skill → 注册 + 校验 + PUBLISHED | 2 | WP3, WP4 |
| WP8-T02 | 标准链路实现 | 上传 → 资产 → ASR Job → 转写 Artifact → 摘要 Job → Knowledge → Chunk + Embedding → Memory → 检索 → 血缘展示 | 4 | T01 |
| WP8-T03 | 安全验收场景 | 6 个场景自动化测试（§14.3）：跨租户隔离 / 伪造 Header / 无权限 Skill / Secret 最小注入 / 撤销 Skill / Ray Dashboard 不暴露 | 3 | T02 |
| WP8-T04 | 一致性验收场景 | 7 个场景自动化测试（§14.4）：DEGRADED / Job 失败记录 / 幂等 / 索引重建 / 删除失败保持 DELETING / ModelServing 不可用 / 配置未同步 | 3 | T02 |
| WP8-T05 | 恢复验收场景 | 6 个场景自动化测试（§14.5）：Server 重启 / Ray Job 丢失 / Outbox 重启 / Reconciler 修复 / ModelServing 重启 / Steward 发现异常 | 3 | T02 |
| WP8-T06 | 完整删除验收 | Meeting 资产删除 → 全部 Binding 清理 → 血缘清理 → DELETED | 1 | T02 |
| WP8-T07 | Control Center 可观察 | Meeting 全过程在 Control Center Assets/Jobs/Audit 页面可观察 | 2 | T02 |

**DoD**：
- Meeting Agent 标准链路 14 步全部跑通；
- 安全 / 一致性 / 恢复验收场景全部自动化通过；
- 完整删除验证通过；
- Control Center 可观察全过程。

---

## 2.9 WP9：工程与发布

> **目标**：使 v0.2.0 可重复部署、迁移和验证。
> **阶段**：F（贯穿全周期，集中收尾） | **估算**：20 SP | **依赖**：所有 WP

| Task ID | 任务 | 交付物 | SP | 依赖 |
|---------|------|--------|----|------|
| WP9-T01 | 数据库迁移脚本 | v0.1.0 → v0.2.0 全量迁移脚本 + 回滚脚本 | 2 | WP2 |
| WP9-T02 | Bootstrap 初始化 | 首次部署向导：初始化管理员 / 主密钥 / 默认配置 / 模型导入 | 2 | WP2 |
| WP9-T03 | 默认密钥清理 | 移除或强制更改默认密码 / 默认 Token / 默认 API Key | 1 | WP2 |
| WP9-T04 | v0.1 数据导入工具 | v0.1.0 资产 / 配置 / 模型 → v0.2.0 格式导入 | 2 | T01 |
| WP9-T05 | 测试体系 | 单元 + 契约 + 集成 + 安全测试框架；`scripts/verify_v0.2.0.py` | 3 | All |
| WP9-T06 | 备份与恢复说明 | PG dump / S3 同步 / 配置导出 + 恢复步骤文档 | 1 | T01 |
| WP9-T07 | 发布文档 | 升级指南 / 安全部署指南 / Control Center 使用说明 / Skill 发布说明 / ModelServing 配置说明 / Meeting Agent Golden Path 文档 | 3 | All |
| WP9-T08 | Docker Compose 更新 | 单节点完整部署 compose + 网络隔离 + 健康检查 | 2 | All |
| WP9-T09 | 版本标记 | VERSION → 0.2.0 + CHANGELOG + Git tag | 1 | All |
| WP9-T10 | 文档体系更新 | AGENTS.md / .agent/DESIGN.md / .agent/SPEC.md / .agent/STATE.md / README / API Reference / MCP 工具说明 | 3 | All |

**DoD**：
- 全新单节点部署可在一台主机上完成；
- v0.1.0 数据可迁移到 v0.2.0；
- 默认密钥全部清理或强制更改；
- `scripts/verify_v0.2.0.py` 全部分层测试通过；
- 全部发布文档就绪。

---

# 3. 阶段计划与依赖

## 3.1 阶段 A：设计冻结（第 1-2 周）

| 周 | 任务 | 产出 |
|----|------|------|
| W1 | WP1-T01 ~ T06 | 四平面文档 + Service 边界 + API v1 spec + ID/URI + 错误模型 + Operation 规范 |
| W2 | WP1-T07 ~ T10 | MCP 共享语义 + ADR 1-15 + 文档冲突消除 + Provider 契约 |

**门禁**：M0 — 设计冻结评审通过后方可进入阶段 B。

## 3.2 阶段 B：Control Plane 骨架（第 3-6 周）

| 周 | 任务 | 产出 |
|----|------|------|
| W3 | WP2-T01 ~ T02 | 迁移框架 + Control Plane 核心 schema |
| W4 | WP2-T03 ~ T07 | Security Context + Token + RBAC + 租户隔离 + Protected Namespace |
| W5 | WP2-T08 ~ T13 | Config Service + Instance Registry + Secret Service |
| W6 | WP2-T14 ~ T19 | Audit + Operation + Outbox + 网络边界 + REST 认证 + 跨租户测试 |

**门禁**：M1 — Control Plane 端到端跑通（Token 签发 → 认证 → 授权 → 审计 → 配置 Revision）。

## 3.3 阶段 C：Asset Runtime（第 7-11 周）

| 周 | 任务 | 产出 |
|----|------|------|
| W7 | WP3-T01 ~ T06 | Asset Core + Binding + 状态机 + AssetService + 版本 + 血缘 |
| W8 | WP3-T07 ~ T11 | Knowledge 模型 + 摄入 + 检索 + Embedding 失败处理 + 重建索引 |
| W9 | WP3-T12 ~ T15 | Skill 模型 + 生命周期 + 校验 + 检索 |
| W10 | WP3-T16 ~ T19 | Memory 模型 + 临时/持久分离 + CRUD + 过期归档 |
| W11 | WP3-T20 ~ T23 | Outbox Worker + Reconciler + 异步删除 + 故障注入测试 |

**门禁**：M2 — Knowledge/Skill/Memory 全生命周期 + 一致性机制可用。

## 3.4 阶段 D：Job + ModelServing（第 12-15 周）

WP4 与 WP5 并行。

| 周 | WP4（Job） | WP5（Model） |
|----|-----------|---------------|
| W12 | T01-T03：Job/Attempt/Artifact schema | T01-T05：模型领域 5 表 |
| W13 | T04-T07：JobService + 资格 + 配额 + 绑定 | T06-T08：管理 API + Secret Ref + YAML 导入 |
| W14 | T08-T10：ExecutionBackend + Ray + 状态同步 | T09-T11：配置加载 + 生效模式 + Job 绑定 |
| W15 | T11-T15：恢复 + 日志 + Artifact 资产化 + 可复现 | T12-T13：模型 Operation + 健康上报 |

**门禁**：M3 — Job 提交 → Ray 执行 → Artifact → 资产化全链路 + 模型管理全链路。

## 3.5 阶段 E：Control Center + Steward（第 16-18 周）

| 周 | 任务 | 产出 |
|----|------|------|
| W16 | WP6-T01 ~ T04 | 目录合并 + 管理员认证 + BFF + 页面权限 |
| W17 | WP6-T05 ~ T14 | 10 个页面 |
| W18 | WP6-T15 ~ T16 + WP7 全部 | Operation 集成 + 审计 + Steward 三级治理 |

**门禁**：M4 — Control Center 10 页面可用 + Steward 受控治理。

## 3.6 阶段 F：硬化与发布（第 19-20 周）

| 周 | 任务 | 产出 |
|----|------|------|
| W19 | WP8-T01 ~ T05 | Meeting Skill + 标准链路 + 安全/一致性/恢复验收 |
| W20 | WP8-T06 ~ T07 + WP9 全部 | 完整删除 + Control Center 可观察 + 迁移/测试/文档/发布 |

**门禁**：M5 — v0.2.0 全部验收标准（§18）通过 + 发布。

---

# 4. 数据库迁移计划

## 4.1 新增表清单

按创建顺序排列，标注所属 WP 和阶段：

| 序号 | 表名 | WP | 阶段 | 说明 |
|------|------|----|------|------|
| 1 | `tenants` | WP2 | B | 租户（v0.1 有但需扩展） |
| 2 | `principals` | WP2 | B | User / Agent / ServiceAccount / Steward / SystemWorker |
| 3 | `roles` | WP2 | B | 角色定义 |
| 4 | `role_bindings` | WP2 | B | Principal × Role × Tenant |
| 5 | `tokens` | WP2 | B | Token 哈希 + 绑定 + 撤销 |
| 6 | `audit_log` | WP2 | B | 审计事件 |
| 7 | `operations` | WP2 | B | Operation 状态机 |
| 8 | `config_revisions` | WP2 | B | 配置版本 |
| 9 | `config_values` | WP2 | B | 配置值（按作用域） |
| 10 | `secrets` | WP2 | B | 加密 Secret + 版本 |
| 11 | `instance_registry` | WP2 | B | 服务实例 + 心跳 |
| 12 | `outbox` | WP2 | B | Outbox 事件 |
| 13 | `assets` | WP3 | C | 统一资产账本 |
| 14 | `asset_bindings` | WP3 | C | 物理 Binding |
| 15 | `asset_lineage` | WP3 | C | 血缘关系 |
| 16 | `knowledge_meta` | WP3 | C | Knowledge 特有元数据 |
| 17 | `skill_meta` | WP3 | C | Skill Manifest + 校验信息 |
| 18 | `memory_meta` | WP3 | C | Memory 特有元数据 |
| 19 | `job_runs` | WP4 | D | Job Run |
| 20 | `job_attempts` | WP4 | D | Job Attempt |
| 21 | `job_artifacts` | WP4 | D | Job 输出 Artifact |
| 22 | `model_definitions` | WP5 | D | 模型定义 |
| 23 | `model_deployments` | WP5 | D | 模型部署 |
| 24 | `model_profiles` | WP5 | D | 模型 Profile / Alias |
| 25 | `model_routes` | WP5 | D | 路由 + Fallback |
| 26 | `embedding_spaces` | WP5 | D | Embedding 空间 |
| 27 | `reconciler_state` | WP3 | C | Reconciler 扫描状态 |

## 4.2 迁移策略

```
v0.1.0 schema
    │
    ├── migration_001_control_plane.sql    (阶段 B：表 1-12)
    ├── migration_002_asset_runtime.sql    (阶段 C：表 13-19, 27)
    ├── migration_003_job_model.sql        (阶段 D：表 20-26)
    ├── migration_004_data_import.sql      (阶段 F：v0.1 数据导入)
    └── migration_005_cleanup.sql          (阶段 F：移除旧表/旧字段)
```

每个迁移包含：
- `up.sql`：前向迁移；
- `down.sql`：回滚迁移；
- `verify.sql`：迁移后数据完整性校验；
- `data_import.py`：v0.1 数据格式转换（如需）。

## 4.3 v0.1 → v0.2 数据映射

| v0.1 数据 | v0.2 目标 | 转换逻辑 |
|-----------|-----------|----------|
| S3 中的知识文件 | `assets` (type=knowledge) + `asset_bindings` (ORIGINAL_OBJECT) | 扫描 S3 → 创建资产记录 → Binding 指向已有 URI |
| Lance 向量表 | `asset_bindings` (VECTOR_INDEX) | 扫描 Lance → 关联到已有资产 → 标记 Binding |
| PG memory 表 | `assets` (type=memory) + `memory_meta` | 逐行迁移 → 创建资产 + Memory 元数据 |
| PG graph_nodes/edges | 保留，标记为 Experimental | 不迁移，保留占位 |
| models.yaml | `model_definitions` + `model_deployments` + `model_profiles` + `model_routes` | YAML 解析 → 导入 PG |
| .env / 静态 Token | `config_values` + `tokens` + `secrets` | 环境变量 → Bootstrap 或 Dynamic Config；静态 Token → 数据库 Token |

---

# 5. 依赖关系图

```
WP1 (架构与契约)
  │
  ├──→ WP2 (Control Plane)
  │      │
  │      ├──→ WP3 (Asset Runtime)
  │      │      │
  │      │      ├──→ WP4 (Job Runtime) ──→ WP8 (Meeting Agent)
  │      │      │
  │      │      └──→ WP5 (ModelServing) ──→ WP8
  │      │
  │      ├──→ WP5 (ModelServing)  [可与 WP3 并行]
  │      │
  │      └──→ WP6 (Control Center)
  │             │
  │             └──→ WP7 (Steward)
  │
  └──→ WP9 (工程与发布) [贯穿全周期]

并行窗口：
  - WP4 ∥ WP5  (阶段 D)
  - WP7 ∥ WP6 后期 (阶段 E)
  - WP9 贯穿，集中收尾于阶段 F
```

关键依赖约束（来自设计方案 §17）：

1. Control Center 不先于 Control Plane 契约自由开发；
2. Job 不先于 Skill 版本和权限模型定型；
3. ModelServing 页面不先于 Model Definition/Deployment/Profile 定型；
4. Meeting Agent 最终迁移基于正式 Asset/Job/Model 契约。

---

# 6. 风险登记与缓解

| ID | 风险 | 影响 | 概率 | 缓解措施 |
|----|------|------|------|----------|
| R1 | 四平面边界在实现中发现不可行，需返工 | 高 | 中 | 阶段 A 充分评审 + ADR 留演进记录 + 允许 v0.2.0 内部边界微调 |
| R2 | v0.1 → v0.2 数据迁移丢失或损坏 | 高 | 中 | 迁移脚本含 verify.sql + 全量备份 + 干运行校验 + 回滚脚本 |
| R3 | Ray Job 状态同步不可靠，导致 LOST 误判 | 中 | 中 | PG 为事实源 + 定期心跳校准 + Reconciler 兜底 + 人工标记 LOST |
| R4 | 性能回退：Application Service 层增加延迟 | 中 | 高 | 批�关键路径 benchmark + 连接池 + 批量操作 + 异步非关键路径 |
| R5 | 安全模型过于复杂，阻碍功能开发 | 中 | 中 | RBAC 优先 + 资源级规则最小集 + 后续按需扩展 |
| R6 | Control Center 前端工作量超估 | 中 | 中 | 优先核心 5 页面（Overview/Assets/Jobs/Model/Security），其余可延后到补丁版 |
| R7 | ModelServing 配置迁移破坏现有模型可用 | 高 | 低 | 保留 models.yaml Bootstrap + 灰度切换 + 回滚到 YAML 模式 |
| R8 | Outbox Worker 成为瓶颈 | 中 | 低 | PG SKIP LOCKED 批量拉取 + 并行 Worker + 监控积压告警 |
| R9 | 文档更新滞后于代码 | 低 | 高 | 每个 WP DoD 包含文档更新 + 阶段门禁检查 |
| R10 | 范围蔓延：Ontology 或 Studio 需求被塞入 v0.2.0 | 高 | 中 | 严格遵循 §19 不做清单 + 变更需 ADR + 版本负责人裁决 |

---

# 7. 验收与验证策略

## 7.1 分层测试体系

| 层级 | 范围 | 工具 | 覆盖 |
|------|------|------|------|
| L0 — 单元测试 | Service / 状态机 / 工具函数 | pytest | 每个 Service 核心方法 |
| L1 — 契约测试 | API v1 / MCP tool 签名 | OpenAPI schema + pytest | 所有端点契约 |
| L2 — 集成测试 | Service × PG × S3 × Lance | pytest + Docker | 资产 CRUD + Binding + 状态流转 |
| L3 — 安全测试 | 认证 / 授权 / 租户隔离 / Secret | pytest + 故障注入 | §18.2 全部场景 |
| L4 — 一致性测试 | Outbox / Reconciler / 幂等 / 删除 | pytest + 故障注入 | §18.7 全部场景 |
| L5 — Job 测试 | 提交 / 执行 / 重试 / 取消 / 恢复 | pytest + Ray | §18.4 全部场景 |
| L6 — Model 测试 | 模型管理 / 路由 / Revision / 绑定 | pytest + ModelServing | §18.5 全部场景 |
| L7 — 端到端测试 | Meeting Agent Golden Path | pytest + 浏览器 | §14 全链路 |
| L8 — 恢复测试 | 重启 / 丢失 / Reconciler | pytest + Docker restart | §14.5 全部场景 |
| L9 — 迁移测试 | v0.1 → v0.2 数据迁移 | pytest + 采样比对 | 数据完整性 |

主验证脚本：`scripts/verify_v0.2.0.py`，输出 L0-L9 全部分层结果。

## 7.2 验收标准映射

设计方案 §18 的 8 类验收标准映射到 WP 和测试层级：

| 验收类别 | 设计方案节 | 负责 WP | 测试层级 |
|----------|-----------|---------|----------|
| 架构与契约 | §18.1 | WP1 | L1 |
| 安全 | §18.2 | WP2 | L3 |
| 资产 | §18.3 | WP3 | L2, L4 |
| Job 与 Ray | §18.4 | WP4 | L5 |
| ModelServing | §18.5 | WP5 | L6 |
| Control Center 与 Steward | §18.6 | WP6, WP7 | L2 |
| 一致性与恢复 | §18.7 | WP3, WP4 | L4, L8 |
| 文档与迁移 | §18.8 | WP9 | L9 |

---

# 8. ADR 清单

阶段 A 需完成以下 15 条 ADR，存放于 `.agent/adr/`：

| ADR | 标题 | 对应设计方案节 |
|-----|------|---------------|
| ADR-001 | LakeMind 定位：认知资产平台 + 受控 Job Runtime，非通用 Agent Runtime | §2.2 |
| ADR-002 | PostgreSQL 为 Control Plane 和资产账本事实源 | §3.1, §13.1 |
| ADR-003 | 四平面逻辑架构 | §4.1 |
| ADR-004 | MCP 是协议适配层，不承担一致性和安全事实 | §3.2, §12.3 |
| ADR-005 | Knowledge/Skill/Memory 为 v0.2.0 核心资产，Ontology 为 Experimental | §3.6, §9.1 |
| ADR-006 | Asset Binding 和最终一致性模型（Outbox + Reconciler） | §9.9 |
| ADR-007 | Skill / Job Run / Attempt / Artifact 分离 | §10.2 |
| ADR-008 | Ray 为首选 Execution Backend | §10.1, §10.4 |
| ADR-009 | ModelServing 配置归 Control Plane | §11.1 |
| ADR-010 | Control Center 取代只读 Monitor 定位 | §5.1 |
| ADR-011 | Steward 三级受控治理 | §6.3 |
| ADR-012 | Gravitino 和 Ranger 延后引入 | §13.2, §13.3 |
| ADR-013 | DataMCP 不得破坏受管理资产命名空间 | §8.5, §12.3 |
| ADR-014 | 配置使用 Revision 和 Desired/Active 模型 | §7.4 |
| ADR-015 | Secret 通过引用和最小权限使用 | §7.6 |

---

# 9. 文档更新计划

| 文档 | 更新内容 | 负责 WP | 阶段 |
|------|----------|---------|------|
| `AGENTS.md` | 项目定位统一 + 四平面 + v0.2.0 包结构 | WP1, WP9 | A, F |
| `.agent/DESIGN.md` | 四平面架构 + Application Service + 资产模型 + Job + Model | WP1, WP3, WP4, WP5 | A-F |
| `.agent/SPEC.md` | 代码约定 + Docker + 迁移 + 验证 | WP9 | F |
| `.agent/STATE.md` | v0.2.0 进度跟踪 | 全部 | 持续 |
| `.agent/adr/ADR-001~015` | 15 条架构决策记录 | WP1 | A |
| `docs/architecture/v0.2.0/` | 四平面 + Trust Boundary + 资产模型 + Job + Model 设计 | WP1 | A |
| `docs/api-reference/` | API v1 OpenAPI 渲染 | WP1 | A |
| `docs/mcp-tools/` | MCP 工具说明（更新为共享语义） | WP1 | A |
| `docs/security/` | 安全部署指南 + Token + Secret + 审计 | WP2, WP9 | B, F |
| `docs/control-center/` | Control Center 使用说明 | WP6, WP9 | E, F |
| `docs/skill-job/` | Skill 发布和 Job 执行说明 | WP3, WP4, WP9 | C, D, F |
| `docs/model-serving/` | ModelServing v0.2.0 配置说明 | WP5, WP9 | D, F |
| `docs/meeting-agent/` | Meeting Agent Golden Path 文档 | WP8, WP9 | F |
| `docs/migration/` | v0.1→v0.2 升级指南 + 数据迁移 | WP9 | F |
| `README.md` | 项目定位 + 快速开始 + 链接更新 | WP9 | F |
| `README_agent.md` | Agent 接入指南更新（受控 Job + 资产模型） | WP9 | F |
| `CHANGELOG.md` | v0.2.0 变更日志 | WP9 | F |

---

# 10. 团队配置与工作量

## 10.1 工作量汇总

| WP | 估算 SP | 阶段 | 周数 |
|----|---------|------|------|
| WP1 | 24 | A | 2 |
| WP2 | 48 | B | 4 |
| WP3 | 52 | C | 5 |
| WP4 | 36 | D | 4 |
| WP5 | 28 | D | 4 |
| WP6 | 34 | E | 3 |
| WP7 | 16 | E | 2 |
| WP8 | 18 | F | 2 |
| WP9 | 20 | F | 2 |
| **合计** | **276 SP** | | **20 周** |

## 10.2 建议团队配置

| 角色 | 人数 | 主要负责 WP |
|------|------|------------|
| 架构师 / Tech Lead | 1 | WP1 + 全阶段评审 + ADR |
| 后端工程师（Control Plane） | 1-2 | WP2, WP3 |
| 后端工程师（Job / Model） | 1-2 | WP4, WP5 |
| 前端工程师（Control Center） | 1 | WP6 |
| 后端工程师（Steward / Agent） | 1 | WP7, WP8 |
| DevOps / SRE | 1 | WP9 + Docker + 迁移 |
| 安全顾问 | 0.5 | WP2 安全评审 + L3 测试 |

**最小团队**：3 人（1 架构师 + 2 后端），前端和 DevOps 兼职，周期延长至 ~28 周。  
**推荐团队**：5-6 人，周期 ~20 周。

## 10.3 关键路径

```
WP1 → WP2 → WP3 → WP4 → WP8 → WP9(发布)
```

关键路径上的任何延迟都会直接影响 M5 发布日期。WP5、WP6、WP7 有浮动空间。

---

# 11. 执行检查清单

## 11.1 阶段门禁检查

每个阶段结束前必须通过以下检查：

| 阶段 | 门禁检查项 |
|------|-----------|
| A → B | 四平面文档签署 / API v1 spec 可渲染 / ADR 1-15 合并 / 文档冲突消除 |
| B → C | Token 端到端 / RBAC 路由 / Config Revision / Audit 写入 / 跨租户测试通过 |
| C → D | Asset CRUD / Binding 状态 / 状态机 / Reconciler / 故障注入通过 |
| D → E | Job 全链路 / Ray 执行 / Artifact 资产化 / 模型管理 / Job 模型绑定 |
| E → F | 10 页面可用 / 管理员认证 / Operation 审批 / Steward 三级治理 |
| F → 发布 | Meeting Golden Path / L0-L9 全通过 / 迁移验证 / 文档就绪 / 默认密钥清理 |

## 11.2 发布前最终检查

- [ ] §18.1-18.8 全部验收标准通过
- [ ] §19 全部"不做事项"确认未混入
- [ ] `scripts/verify_v0.2.0.py` L0-L9 全 PASS
- [ ] 全新单节点部署验证（从零开始）
- [ ] v0.1.0 → v0.2.0 升级路径验证
- [ ] 默认密码 / 默认 Token / 默认 API Key 全部移除或强制更改
- [ ] VERSION = 0.2.0
- [ ] CHANGELOG.md 更新
- [ ] Git tag `v0.2.0` 创建
- [ ] 全部发布文档就绪

---

# 12. 附录

## A. 资源 ID 前缀速查

| 资源 | 前缀 | 示例 |
|------|------|------|
| Asset | `ast_` | `ast_8x7k2m` |
| Job Run | `job_` | `job_3p9n1q` |
| Job Attempt | `atm_` | `atm_5r2v8w` |
| Operation | `op_` | `op_1a6b3c` |
| Principal | `prn_` | `prn_7d4e9f` |
| Tenant | `ten_` | `ten_2g5h1j` |
| Model | `mdl_` | `mdl_6k3l8m` |
| Deployment | `dpl_` | `dpl_9n2p4q` |

## B. 逻辑 URI 速查

```
lake://knowledge/{name}@{version}
lake://skills/{name}@{version}
lake://memory/{memory_id}
lake://jobs/{job_id}
model://{profile}          # meeting-asr / knowledge-embedding / lake-chat-default
secret://{scope}/{name}
```

## C. 事件名速查

```
asset.created / asset.processing / asset.ready / asset.degraded / asset.deleted
job.submitted / job.running / job.succeeded / job.failed / job.lost
operation.approval_required / operation.succeeded
config.activated
model.deployment_unhealthy
```

## D. 资产状态机速查

```
DRAFT → CREATING → PROCESSING → READY
                              → DEGRADED (可选 Binding 失败)
                              → FAILED (不可恢复)
READY → DEPRECATED → DELETING → DELETED
任何状态 → DELETING → DELETED (异步删除)
```

## E. Job 状态机速查

```
SUBMITTED → QUEUED → RUNNING → SUCCEEDED
                          → FAILED (→ 重试 = 新 Attempt)
                          → TIMED_OUT
                          → CANCELLING → CANCELLED
                          → LOST (Reconciler 发现)
```

---

> **本开发方案是 v0.2.0 的执行蓝图，与 [设计方案](./LakeMind_v0.2.0_设计方案.md) 配合使用。设计方案定义"做什么"和"为什么"，本方案定义"怎么做"、"谁做"、"何时做"。**
