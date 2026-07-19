# LakeMind v0.2.0 设计方案

> **版本主题：Trustworthy Single-Node｜可信单节点版**  
> **核心目标：能安全、可靠地运行，并使 Agent 资产真正沉淀。**  
> **文档性质：总体设计与改造指导，不包含具体实现代码。**

---

## 0. 文档目的

本文用于指导 LakeMind 从 v0.1.0 的“全链路能跑通”原型，演进到 v0.2.0 的“可信单节点平台内核”。

本文重点回答以下问题：

1. v0.2.0 的版本边界和验收目标是什么；
2. LakeMind 的总体架构如何由现有结构收敛为四个逻辑平面；
3. LakeMind Control Center 如何统一承载 Monitor、Steward、ModelServing 配置和全局管理；
4. Knowledge、Skill、Memory 如何从若干存储操作，升级为可版本化、可审计、可恢复的 Agent 资产；
5. Job 与 Ray 应如何定位，既保留确定性任务执行能力，又建立可靠的安全边界；
6. ModelServing 的模型注册、部署、路由、密钥和运行配置如何纳入统一控制体系；
7. 架构、接口和资产模型在 v0.2.0 应稳定到什么程度；
8. Meeting Agent 如何成为 v0.2.0 的参考应用和验收基准；
9. v0.3.0、v0.4.0 及后续企业化版本如何沿当前架构自然演进。

本文的目标不是规定每个类、函数和表的实现方式，而是让开发团队清晰理解：

- 为什么要改；
- 改造后 LakeMind 应当是什么；
- 各模块的职责边界是什么；
- 哪些内容属于 v0.2.0 必须完成；
- 哪些内容必须明确留到后续版本。

---

# 1. 版本路线与总体判断

## 1.1 推荐版本路线

| 版本 | 版本主题 | 核心目标 | 主要成果 |
|---|---|---|---|
| v0.1.0 | Functional Prototype | 能跑通 | 多组件集成、三类 MCP、Ray Job、ModelServing、Meeting Agent 全链路 |
| **v0.2.0** | **Trustworthy Single-Node** | **能安全、可靠地沉淀和使用 Agent 资产** | Control Plane、Control Center、安全体系、资产内核、受控 Job Runtime、模型配置治理 |
| v0.3.0 | Scalable Runtime | 能在多节点环境中可靠执行和恢复 | 执行平面横向扩展、服务高可用、任务调度与恢复、多实例配置收敛 |
| v0.4.0 | Developer Platform | 能方便地开发、调试、发布和运营 LakeMind 资产及应用 | LakeMindStudio、Skill 开发工具、资产设计器、MCP 调试、发布流水线 |
| v0.5.0 / v1.0 | Enterprise Federation | 能融入企业级身份、目录、治理与审计体系 | 外部目录联邦、企业身份、复杂策略、跨系统治理、稳定兼容性承诺 |

该路线总体正确。需要特别强调：

- v0.2.0 不追求完整企业级安全，而是建立**受控网络和单节点部署条件下的可信运行能力**；
- v0.3.0 不应把所有组件同时“分布式化”，而应优先实现执行平面的横向扩展、无状态服务多副本和状态恢复；
- v0.4.0 再建设 Studio 是正确的，因为 Studio 必须建立在相对稳定的资产、Job、模型和 API 契约之上。

## 1.2 v0.2.0 的正式定位

建议将 v0.2.0 定义为：

> **LakeMind 的可信单节点版本：在受控部署环境中，Knowledge、Skill、Memory 可以被安全创建、版本化、检索、执行关联任务、审计、删除和故障恢复；平台配置、模型服务和运维操作由统一 Control Plane 管理。**

“可信单节点”包括三个层面的含义：

### 可信

- 调用者不能通过伪造请求头切换租户或身份；
- 不同租户和不同 Agent 的资产、Job、Secret 有明确隔离；
- Job 不能默认获得控制面全部环境变量和密钥；
- 重要操作可审计、可追溯；
- Token、Skill、模型 Deployment 可以真实撤销或禁用；
- 资产失败后不会被错误地展示为完整成功状态。

### 单节点

- 允许全部核心服务运行在一台主机的 Docker Compose 环境中；
- Ray 可以保留多个容器或 Worker，但不要求跨物理节点；
- PostgreSQL、SeaweedFS、Valkey 等暂不要求高可用集群；
- 逻辑边界必须为 v0.3.0 的多节点演进预留空间。

### 资产真正沉淀

资产沉淀不再等同于“文件写入 S3”或“向量写入 Lance”。一个完成沉淀的资产必须：

- 拥有稳定的资产 ID；
- 拥有明确的租户、所有者和访问范围；
- 拥有版本或修订语义；
- 能追踪原始来源和生成过程；
- 能识别各物理存储绑定是否完整；
- 能被重新构建索引；
- 能完整删除；
- 能知道由哪个 Skill、Job、模型和输入生成；
- 在部分失败时进入明确的降级或失败状态，而不是“表面成功”。

## 1.3 v0.2.0 的核心工程

v0.2.0 不应被理解为一次普通功能迭代，而应被视为四项基础工程：

1. **Control Plane Foundation**：安全、配置、模型注册、Operation、审计、实例状态和治理；
2. **Asset Runtime Foundation**：Knowledge、Skill、Memory 的统一资产模型、生命周期和一致性；
3. **Controlled Job Runtime**：以 Ray 为首选执行后端的受控、可审计、可恢复任务运行时；
4. **LakeMind Control Center**：统一的运维、配置、模型、资产、Job、安全和 Steward 管理入口。

---

# 2. 项目定位修正

## 2.1 需要解决的现有定位冲突

v0.1.0 的现有文档中同时存在两种表述：

- LakeMind 是认知资产存取平台，不是 Agent 执行平台，Skill 由 Agent 自行下载和执行；
- Ray Job 是一等能力，Meeting Agent 已通过 Skill Job 在 LakeMind 上执行 ASR、摘要和知识提取任务。

这两种表述需要在 v0.2.0 中统一，否则会持续影响 Skill、Job、权限和产品边界设计。

## 2.2 v0.2.0 的统一定位

建议统一为：

> **LakeMind 不是通用 Agent Runtime，不负责运行 Agent 的完整推理循环、业务决策和自主行为；但 LakeMind 提供受控 Job Runtime，用于执行 Agent 触发的、以 Skill 为定义的确定性或可复现任务。**

LakeMind 不负责：

- Agent 的长期推理循环；
- Agent 的自主规划；
- 多 Agent 协作编排；
- 业务工作流决策；
- 用户侧应用运行时；
- 任意不可信代码托管。

LakeMind 负责：

- Skill 资产的注册、版本、校验和发布；
- Job 的提交、权限、状态、重试、取消、审计和恢复；
- 输入资产、模型、Secret 和资源配额绑定；
- Ray 等执行后端的统一抽象；
- Job 输出 Artifact 的保存和资产化；
- 资产加工、索引构建、ASR、Embedding、摘要等受控任务。

该定位既保留 Ray 和 Job 的核心价值，也避免 LakeMind 演变成一个边界不清晰的通用 Agent 托管平台。

---

# 3. v0.2.0 设计原则

## 3.1 统一事实源

- PostgreSQL 是 LakeMind Control Plane、资产账本、Job 状态、配置版本和审计的事实源；
- SeaweedFS、Iceberg、Lance、图投影和 Valkey 根据职责保存数据或索引；
- 可重建索引不得成为资产存在性的唯一依据；
- Ray 状态不得成为 Job 状态的唯一事实源；
- ModelServing 不再独立拥有模型注册和全局路由的最终决定权。

## 3.2 协议入口与业务语义分离

- REST、MCP、Control Center 和未来 SDK 只是不同访问入口；
- 它们必须调用同一组 Application Service；
- MCP 不再自行编排 S3、Embedding、Lance、Graph 等底层操作；
- 管理页面和 Steward 不得绕过 Control Plane 直接修改数据库或引擎。

## 3.3 逻辑架构先定型，物理部署后演进

- v0.2.0 明确四个逻辑平面；
- 不强制把每个平面拆成独立微服务；
- 代码依赖、身份、网络和调用关系必须符合平面边界；
- v0.3.0 再依据负载和可靠性需求进行物理拆分。

## 3.4 最小权限和显式授权

- 租户、Agent、Scope 和角色由可信身份凭证解析，不能由请求方随意声明；
- Job 只获得声明并授权的资产、模型、Secret 和资源；
- Steward 不是超级管理员，不得拥有旁路权限；
- 管理和高风险操作必须经过 Operation Service 和审计。

## 3.5 最终一致性必须可观测

- 跨 PostgreSQL、S3、Lance、Iceberg、图等系统不追求分布式事务；
- 使用资产状态、Binding 状态、Outbox、幂等、补偿和 Reconciler 保证最终一致性；
- 失败必须显式暴露，不得通过吞掉异常或写入伪数据掩盖问题。

## 3.6 版本范围严格收敛

v0.2.0 重点建设：

- Knowledge；
- Skill；
- Memory；
- Job；
- ModelServing 管理；
- Control Center；
- 安全、配置、审计、Operation 和一致性。

Ontology：

- 保留占位和实验接口；
- 标记为 Experimental；
- 不作为 v0.2.0 发行验收条件；
- Meeting Agent 主链路不得强依赖 Ontology；
- 不在 v0.2.0 建设完整本体设计器和复杂图治理。

其他新资产类型暂不引入。

---

# 4. 目标总体架构：四个逻辑平面

## 4.1 四平面定义

| 平面 | 核心职责 | 主要组件 | 明确禁止事项 |
|---|---|---|---|
| Access Plane 接入面 | 协议适配、请求校验、用户与管理员入口 | AssetMCP、DataMCP、AdminMCP、REST API、Control Center BFF | 不直接决定权限；不直接拼接受保护物理路径；不直接修改底层引擎 |
| Control Plane 控制面 | 身份、安全、资产、Job、模型注册、配置、Operation、审计和治理 | Application Services、PostgreSQL 元数据、Auth、Policy、Config、Model Registry、Job Service、Operation、Reconciler | 不直接执行不可信代码；不把底层引擎状态当唯一事实源 |
| Data & Index Plane 数据与索引面 | 保存原始数据、表、索引、缓存和关系投影 | SeaweedFS、Iceberg、Lance/LanceDB、Valkey、PostgreSQL 图/结构化数据 | 不自行判断业务权限；不自行改变资产生命周期状态 |
| Execution Plane 执行面 | 执行 Skill Job、模型推理、解析、Embedding、ASR 和索引任务 | Ray、ModelServing、本地或远程 Worker、DuckDB 任务 | 不成为资产或 Job 的事实源；不持有控制面全局密钥 |

## 4.2 组件归属

### Access Plane

- LakeMindAssetMCP；
- LakeMindDataMCP；
- LakeMindAdminMCP；
- LakeMindServer 对外 REST API；
- LakeMind Control Center 前端及其 BFF；
- 未来 LakeMindStudio 和 SDK。

### Control Plane

- Identity Service；
- Authorization / Policy Service；
- Asset Service；
- Knowledge Service；
- Skill Service；
- Memory Service；
- Job Service；
- Model Registry 与 Routing Policy；
- Configuration Service；
- Secret Service；
- Instance Registry；
- Operation Service；
- Audit Service；
- Outbox Worker；
- Reconciler；
- Steward Agent。

### Data & Index Plane

- PostgreSQL；
- SeaweedFS / S3；
- Iceberg；
- Lance / LanceDB；
- Valkey；
- PostgreSQL Graph 或其他关系投影。

### Execution Plane

- Ray Head 与 Worker；
- LakeMindModelServing；
- 本地模型 Runtime；
- 外部模型 Provider 调用适配；
- Skill Worker；
- 文档解析、ASR、Embedding、索引重建等任务。

## 4.3 四平面不是四套微服务

v0.2.0 的目标是逻辑和信任边界定型，不要求立即形成四套独立部署。

允许：

- 多个 Control Plane Service 仍运行在 LakeMindServer 主进程中；
- Monitor 前端/BFF 在现有 LakeMindMonitor 项目上演进；
- Ray 和 ModelServing 保持独立容器；
- PostgreSQL 继续复用同一实例。

必须做到：

- Access Plane 不直接调用具体存储 SDK；
- 业务路由先进入 Application Service；
- 所有权限判断由 Control Plane 完成；
- Execution Plane 只能通过受控契约访问资产、模型和 Secret；
- 资产托管的物理路径不能被普通 DataMCP 写操作绕过。

## 4.4 应建立的核心应用服务

v0.2.0 至少应形成以下清晰的服务边界：

- AssetService：资产公共生命周期、版本、Binding、血缘和状态；
- KnowledgeService：Knowledge 创建、摄入、解析、索引、检索和删除；
- SkillService：Skill 注册、校验、发布、版本、撤销和检索；
- MemoryService：Memory 写入、检索、更新、过期、归档和删除；
- JobService：Job 提交、状态、尝试、重试、取消、结果和恢复；
- ModelManagementService：模型定义、部署、Profile、路由和配置版本；
- ConfigurationService：平台、租户、Agent、服务和功能配置；
- AuthorizationService：身份、角色、动作和资源授权；
- SecretService：Secret 保存、引用、使用授权、版本和轮换；
- OperationService：统一执行管理和治理动作；
- AuditService：记录安全、管理、资产、Job 和模型操作；
- ReconciliationService：检查并修复资产、Job、配置和模型运行状态偏差。

---

# 5. LakeMind Control Center

## 5.1 产品定位

LakeMind Control Center 是 v0.2.0 的统一全局管理与运维入口。

它不是第五个架构平面，而是：

- 位于 Access Plane 的管理界面；
- 调用 Control Plane 的管理 API；
- 聚合 Data & Index Plane 和 Execution Plane 的状态；
- 为管理员提供统一配置、治理、审计和操作入口。

现有 LakeMindMonitor 应演进为 LakeMind Control Center。建议：

- 产品名称和页面定位在 v0.2.0 变更为 Control Center；
- 代码目录是否立即从 `LakeMindMonitor` 重命名可由团队根据迁移成本决定；{{意见：LakeMindMonitor和LakeMindSteward 都并入新目录： LakeMindControlCenter\ }}
- 目录重命名不是 v0.2.0 的核心验收项，职责和安全模型的改变才是核心。

## 5.2 Control Center 与 LakeMindStudio 的区别

| 项目 | LakeMind Control Center | LakeMindStudio |
|---|---|---|
| 版本 | v0.2.0 | v0.4.0 |
| 面向用户 | 管理员、运维人员、平台负责人 | 开发者、Agent 工程师、资产设计者 |
| 核心目的 | 运行、监控、配置、治理、审计 | 开发、调试、设计、发布 |
| 主要对象 | 服务、资产状态、Job、模型 Deployment、配置、安全、Operation | Skill 工程、Knowledge 模板、MCP 调试、Agent 应用、开发流水线 |
| 是否直接面向生产系统 | 是 | 通过稳定 API 和发布流程接入 |

Control Center 不承担以下 Studio 能力：

- Skill IDE；
- 资产可视化设计器；
- MCP 通用调试台；
- 本地 Agent 开发环境；
- 完整 CI/CD 脚手架；
- Prompt 和工作流开发工具。

## 5.3 v0.2.0 页面结构

建议 Control Center 包含以下页面：

### 1. Overview｜平台总览

- 核心服务健康；
- Control Plane 状态；
- Data & Index Plane 状态；
- Execution Plane 状态；
- 资产总量和状态分布；
- Job 状态和失败趋势；
- Outbox 积压；
- Reconciler 异常；
- 近期安全事件；
- 配置 Revision 收敛情况。

### 2. Assets｜资产管理

- Knowledge、Skill、Memory 分类查看；
- 资产状态、版本、所有者和租户；
- Binding 完整性；
- 资产来源和血缘；
- DEGRADED、FAILED、DELETING 资产；
- 触发重试、重建索引、删除等受控 Operation；
- Ontology 仅显示 Experimental 标记。

### 3. Jobs｜任务管理

- Job Run 和 Job Attempt；
- Skill、输入、模型和 Deployment 绑定；
- 状态、日志、结果和错误；
- 重试、取消、标记 Lost、重新同步；
- CPU、内存、并发和队列使用；
- Ray 后端状态，但不向管理员暴露绕过 LakeMind 的直接控制路径。

### 4. Model Serving｜模型服务

- 模型定义；
- 模型 Deployment；
- 模型 Profile / Alias；
- 路由和 Fallback；
- Embedding Space；
- Provider Secret 引用；
- 实例健康、延迟、错误率和当前配置 Revision；
- 测试 Deployment、启用、禁用、预热、Reload 等 Operation。

### 5. Services｜服务与实例

- LakeMindServer、MCP、ModelServing、Ray、Steward、存储组件实例；
- 服务版本；
- 启动时间；
- 心跳；
- 当前配置 Revision；
- Desired Revision 与 Active Revision 差异；
- 功能能力和健康状态。

### 6. Configuration｜全局配置

- 平台配置；
- 租户覆盖配置；
- Agent 或 Service 配置；
- 功能开关；
- 配置 Schema、Revision、变更历史和回滚；
- 显示配置生效方式：热更新、模型 Reload、服务重启。

复杂领域配置不应全部堆入该通用页面。模型、Job、安全等配置分别在专属页面管理；通用配置页负责平台级基础参数和统一 Revision 管理。

### 7. Security｜安全管理

- 用户、Agent、Service Account 和 Steward 身份；
- 租户；
- 角色和权限；
- Token 和撤销状态；
- Secret 元数据和轮换；
- Skill 发布者和可信级别；
- 安全策略；
- 访问拒绝和异常事件。

### 8. Operations｜操作与审批

- Operation 列表；
- 自动执行、等待审批、运行中、成功和失败状态；
- 高风险操作人工批准；
- 操作输入、原因、执行人、执行结果和审计；
- Steward 创建的治理建议和 Operation Request。

### 9. Audit｜审计

- 身份认证；
- 授权结果；
- 资产变更；
- Job 提交和执行；
- Secret 使用；
- 模型路由和配置变化；
- Steward 动作；
- 管理员批准或拒绝。

### 10. Steward｜运维智能体

- Steward 对话；
- 巡检结果；
- 异常诊断；
- 治理建议；
- 待批准 Operation；
- 自动治理策略；
- 近期自动操作和结果。

该页面可以继续保留当前 Monitor 中的 Steward 对话体验，但后端必须改为受控治理流程。

## 5.4 Control Center 的安全要求

现有 Monitor 使用静态平台 Token 的方式不应继续作为正式管理机制。

v0.2.0 要求：

- Control Center 有明确管理员身份；
- 管理员操作使用用户身份和会话，而不是共享静态 Token；
- Control Center BFF 使用独立 Service Identity 与 Control Plane 通信；
- 页面权限根据管理员角色控制；
- 所有写操作进入 Operation Service；
- 前端和 BFF 不直接连接 PostgreSQL、S3、Ray 或 ModelServing 管理数据库；
- 高风险操作需要二次确认或审批状态；
- 管理操作必须写入 Audit。

---

# 6. Monitor 与 Steward 的目标设计

## 6.1 Monitor 的定位

Monitor 不应首先被设计成智能体。它应当是一套确定性的可观测与状态聚合能力。

Monitor 能力拆为两部分：

### Observability Backend

属于 Control Plane，负责：

- 服务心跳；
- 引擎健康；
- 资产状态统计；
- Job 运行状态；
- 配置 Revision；
- Outbox 和 Reconciler；
- 安全与审计事件；
- 容量、配额和资源使用；
- 告警和异常聚合。

### Control Center UI

属于 Access Plane，负责展示和发起受控管理操作。

v0.2.0 的 Monitor 不需要立即建设完整 Prometheus、Grafana 或 OpenTelemetry 平台，但必须形成统一的健康、状态、指标和审计数据接口。后续版本可以替换或接入专业可观测系统。

## 6.2 Steward 的定位

Steward 是位于 Control Plane 的受控治理与运维智能体，但它本身不能成为安全边界。

Steward 必须：

- 使用独立 Service Account；
- 通过 AdminMCP 或 Control Plane API 调用正式管理能力；
- 所有动作经过 Authorization；
- 所有改变系统状态的动作通过 Operation Service；
- 不直接连接数据库和底层引擎；
- 不拥有控制面主密钥；
- 不以“系统提示词”代替权限控制；
- 不因 LLM 判断而绕过审批。

## 6.3 Steward 三级动作模型

### Level 1：观察和建议

允许自动完成：

- 检查服务和引擎健康；
- 发现 DEGRADED 资产；
- 发现超时或 Lost Job；
- 检查 Outbox 积压；
- 检查索引、Binding 或配置偏差；
- 生成诊断报告和建议。

### Level 2：低风险自动治理

在策略授权范围内可以自动执行：

- 重试 Embedding；
- 重建可重建索引；
- 重新同步 Ray Job 状态；
- 运行 Reconciler；
- 清理明确无引用的临时文件；
- 重连失效的非关键服务；
- 执行已批准的配置 Reload。

### Level 3：高风险操作

必须创建待批准 Operation：

- 删除资产；
- 撤销 Token；
- 修改安全策略；
- 修改租户配额；
- 禁用生产模型 Deployment；
- 停止服务；
- 取消关键 Job；
- 删除或撤销 Skill；
- 执行数据迁移；
- 轮换平台级 Secret。

## 6.4 Operation Service

Monitor、Control Center、Steward 和 AdminMCP 的写操作最终都应统一进入 Operation Service。

Operation 至少应具有以下状态：

- PENDING；
- APPROVAL_REQUIRED；
- APPROVED；
- RUNNING；
- SUCCEEDED；
- FAILED；
- CANCELLED。

每个 Operation 应记录：

- 操作类型；
- 目标资源；
- 发起身份；
- 发起渠道；
- 原因；
- 风险等级；
- 是否需要审批；
- 审批人；
- 执行结果；
- 失败原因；
- 关联审计事件。

---

# 7. 全局配置与整体管控

## 7.1 Configuration Service

v0.1.0 中配置散落在 `.env`、多个 YAML、Docker Compose、代码默认值、MCP 静态 Token 和 PostgreSQL 表中。v0.2.0 必须建立统一 Configuration Service。

Configuration Service 负责：

- 配置 Schema；
- 配置作用域；
- 默认值；
- 校验；
- Revision；
- 激活；
- 变更历史；
- 回滚；
- 生效方式；
- 实例配置收敛状态。

## 7.2 配置分类

### 1. Bootstrap 配置

系统启动前必须获得的配置：

- PostgreSQL 初始连接；
- 平台加密主密钥或其引用；
- Control Plane 地址；
- 初始管理员；
- 服务监听地址；
- Service Identity 凭证；
- 本地缓存根目录；
- 基础日志级别。

Bootstrap 配置保留在安全的环境变量或部署文件中，不能完全依赖 PostgreSQL。

### 2. 平台动态配置

保存在 Control Plane：

- 默认 Job 超时和重试；
- 默认 Memory 保留策略；
- 资产大小限制；
- 默认模型 Profile；
- 索引策略；
- Steward 自动治理开关；
- 告警阈值；
- 全局功能开关；
- Operation 审批规则。

### 3. 租户配置

- 租户 Job 并发和资源上限；
- 可用模型范围；
- Memory 保留期限；
- 资产容量；
- 外部模型使用权限；
- Skill 发布和执行权限。

### 4. Agent 或 Service 配置

- Agent 可访问的资产范围；
- Service 所需配置 Revision；
- Steward 自动操作级别；
- ModelServing 实例运行参数；
- MCP 协议相关参数。

### 5. Secret

Secret 不作为普通配置值保存。普通配置只引用：

- 系统 Secret；
- 租户 Secret；
- Provider Secret；
- Job 运行 Secret。

## 7.3 配置优先级

推荐优先级：

**系统默认值 < 平台配置 < 租户配置 < Agent / Service 配置 < 被允许的 Job 覆盖项**

安全配置不能被下层覆盖。例如：

- Tenant ID 不允许 Job 覆盖；
- Secret 权限不允许 Job 覆盖；
- Skill 可信状态不允许 Job 覆盖；
- 网络出口权限不允许 Job 覆盖；
- CPU 和超时只允许在租户上限范围内覆盖。

## 7.4 配置 Revision 和生效模式

每次配置变化必须产生新的 Revision，并记录：

- 修改人；
- 修改原因；
- 修改前后值；
- 作用域；
- Schema 校验结果；
- 激活时间；
- 是否可回滚。

配置生效方式分为：

- HOT_RELOAD：无需重启即可生效；
- COMPONENT_RELOAD：需要重载模型、Skill 或组件；
- SERVICE_RESTART：需要重启服务。

每个服务实例上报：

- Desired Revision；
- Active Revision；
- 最近加载结果；
- 配置是否收敛。

## 7.5 Instance Registry

v0.2.0 即使是单节点部署，也应建立服务实例概念。

Instance Registry 记录：

- Instance ID；
- Service Type；
- 版本；
- Endpoint；
- 启动时间；
- Last Heartbeat；
- 当前健康状态；
- Capability；
- Active Configuration Revision。

这将为 v0.3.0 的多节点、多副本和滚动配置提供基础。

## 7.6 Secret Service

v0.2.0 可以使用 PostgreSQL 保存加密后的 Secret，但必须满足：

- 不保存明文 Secret；
- 主加密密钥不存入同一数据库；
- API 不返回 Secret 原文；
- 通过 `secret_ref` 引用；
- 支持 Secret 版本和轮换；
- 记录哪个 Service 或 Job 在什么时间使用；
- Job 只获得显式声明并授权的 Secret；
- 控制面全局密钥永不注入 Ray Job。

后续版本可以接入 Vault 或云 KMS，但不是 v0.2.0 的必要依赖。

---

# 8. 安全体系设计

## 8.1 安全目标

v0.2.0 的安全目标是：

> 在受控网络和单节点部署环境中，建立可信身份、资源授权、租户隔离、Secret 隔离、Job 隔离、管理审计和最小权限机制。

不承诺：

- 面向互联网的零信任企业平台；
- 完整 OIDC / SAML / LDAP 集成；
- 多区域安全联邦；
- 行列级数据脱敏；
- 强对抗环境中的任意不可信代码沙箱。

## 8.2 统一身份模型

建议支持以下 Principal 类型：

- User；
- Agent；
- Service Account；
- Steward；
- System Worker。

身份凭证解析后形成可信 Security Context，至少包含：

- Principal ID；
- Tenant ID；
- Principal Type；
- Roles；
- Scopes / Actions；
- Token ID；
- Request ID。

Tenant、Agent 和 Scope 不得继续由调用方通过普通请求头自由声明。

## 8.3 Token 体系

v0.2.0 应统一静态 Token 和数据库动态 Token：

- PostgreSQL 保存 Token 哈希，不保存明文；
- Token 首次签发时只显示一次；
- 撤销立即影响所有 MCP 和 REST 入口；
- Token 绑定 Principal、Tenant、Scope、过期时间和状态；
- MCP、Control Center、ModelServing 和内部服务使用同一身份体系或可映射的 Service Identity；
- 移除“后台显示已撤销但静态配置仍可访问”的双重事实源。

## 8.4 授权模型

v0.2.0 建议采用以 RBAC 为基础、资源级规则补充的模型。

需要区分的动作包括：

- asset:create / read / update / delete；
- knowledge:ingest / search / reindex；
- skill:register / publish / execute / revoke；
- memory:add / read / update / delete / clear；
- job:submit / read / cancel / retry；
- model:read / configure / use；
- secret:use / rotate；
- operation:request / approve；
- config:read / write / activate；
- audit:read。

Skill 的读取权限和执行权限必须分开。

## 8.5 租户与物理资源隔离

租户隔离应由 Server / Control Plane 强制执行，不能只依赖 MCP 拼接前缀。

要求：

- 对外 API 使用逻辑资产 ID 和逻辑 URI；
- Server 根据 Security Context 解析物理路径；
- S3 Key、Iceberg Namespace、Lance Database、Valkey Key 和图数据均由服务端生成或严格校验；
- DataMCP 不得直接覆盖受 AssetService 管理的物理路径；
- 受管理资产路径应标记为 Protected Namespace；
- 任何跨租户访问都必须经过显式授权，而不是依赖调用方传入 Tenant Header。

## 8.6 网络边界

v0.2.0 单节点部署也需要明确网络边界：

- 对外主要暴露 MCP、受保护 REST API 和 Control Center；
- PostgreSQL、SeaweedFS、Valkey、Ray Dashboard 和 Worker 端口仅在内部网络访问；
- Agent 不能直接访问 Ray Job Submission API；
- Agent 不能直接访问数据库和对象存储；
- ModelServing 管理端点不直接暴露给普通 Agent；
- 内部服务使用独立 Service Identity，而不是共享全局 API Key。

## 8.7 审计

必须审计：

- 登录和 Token 使用；
- 授权允许和拒绝；
- 资产创建、更新、删除和状态变化；
- Skill 发布、撤销和执行；
- Job 提交、取消、重试和结果；
- Secret 使用；
- 模型路由、Deployment 和配置变更；
- Steward 建议与自动操作；
- 管理员审批；
- 配置激活和回滚。

---

# 9. 资产模型与 Asset Runtime

## 9.1 v0.2.0 资产范围

正式资产：

- Knowledge；
- Skill；
- Memory。

实验资产：

- Ontology。

v0.2.0 不开放任意动态资产类型的生产级能力。现有“注册资产类型”能力可以：

- 标记为 Experimental；
- 限制为管理员使用；
- 不宣称动态类型会自动生成完整 API、生命周期、存储绑定和 UI；
- 不纳入 v0.2.0 核心验收。

## 9.2 统一 Asset Core

Knowledge、Skill、Memory 应共享稳定的公共资产核心。公共信息至少包括：

- Asset ID；
- Tenant ID；
- Asset Type；
- Name；
- Version 或 Revision；
- Schema Version；
- Status；
- Owner；
- Created By；
- Visibility；
- Classification；
- Source Type；
- Source URI；
- Checksum；
- Retention Policy；
- Metadata；
- Created At；
- Updated At；
- Deleted At。

资产 ID 是平台内部稳定标识，资产名称可以变化，物理路径不能作为资产 ID。

## 9.3 Asset Binding

Asset Binding 描述一个逻辑资产在不同引擎中的物理表示。

Binding 应至少包含：

- Binding ID；
- Asset ID；
- Binding Type；
- Provider；
- Physical URI；
- Binding Version；
- Checksum；
- Status；
- 是否为 Required Binding；
- Metadata；
- Last Error。

常见 Binding 类型：

- ORIGINAL_OBJECT；
- PARSED_CONTENT；
- CHUNK_DATA；
- VECTOR_INDEX；
- GRAPH_PROJECTION；
- TABLE_DATASET；
- SKILL_PACKAGE；
- JOB_ARTIFACT。

## 9.4 资产状态机

建议统一基础状态：

- DRAFT；
- CREATING；
- PROCESSING；
- READY；
- DEGRADED；
- FAILED；
- DEPRECATED；
- DELETING；
- DELETED。

不同资产使用适合自己的子集。

READY 的含义必须严格：

- 所有 Required Binding 完成；
- 必要校验通过；
- 资产可以按照声明能力被使用。

可选投影失败时可以进入 DEGRADED，而不是错误地显示 READY。

## 9.5 Knowledge 模型

Knowledge 应覆盖：

- 原始文档或多模态对象；
- 解析内容；
- Chunk；
- Embedding；
- 可选图投影；
- 来源、引用和血缘；
- 解析器版本；
- Embedding Space；
- 索引状态。

Knowledge 的事实基础是：

- PostgreSQL 资产账本；
- 原始内容或规范化内容。

Lance 向量和图投影属于可重建 Binding。

Embedding 失败时：

- 不写入零向量；
- 资产进入 INDEXING、DEGRADED 或 FAILED；
- 保留原始内容；
- 支持后台重试和重建。

## 9.6 Skill 模型

Skill 是可版本化、可发布、可授权和可执行的资产。

Skill 至少包含：

- Skill 名称；
- 不可变版本；
- Manifest；
- 代码或包的 Checksum；
- 发布者；
- 输入 Schema；
- 输出 Schema；
- Entry Point；
- 依赖锁定信息；
- 权限声明；
- 所需资产范围；
- 所需模型 Profile；
- 所需 Secret 引用声明；
- 默认资源需求；
- 网络需求；
- 可信级别；
- 发布状态。

发布后的 Skill 版本不得覆盖。代码、依赖或 Manifest 变化必须发布新版本。

建议 Skill 生命周期：

- DRAFT；
- VALIDATING；
- PUBLISHED；
- DEPRECATED；
- REVOKED。

只有 PUBLISHED 且未 REVOKED 的可信 Skill 可以被 Job 执行。

## 9.7 Memory 模型

Memory 必须区分临时状态和沉淀资产。

### 不进入长期资产账本的内容

- 短期工作缓存；
- 临时推理中间状态；
- 可随会话销毁的上下文；
- 未经筛选的全部聊天内容。

### 可以沉淀为长期 Memory 的内容

- 有明确 Subject；
- 有明确来源；
- 有明确 Scope；
- 有明确访问范围；
- 有明确保留期限；
- 可以撤回或删除；
- 可以追踪生成事件；
- 具有实际复用价值。

Memory 至少应表达：

- Memory Type；
- Subject；
- Scope；
- Source；
- Content；
- Importance；
- Retention；
- Expiration；
- Access Scope；
- Embedding Status；
- Consolidation Status；
- Revision History。

建议区分：

- Working Memory；
- Session Memory；
- Agent Private Memory；
- User Memory；
- Organizational Shared Memory。

## 9.8 版本语义

### Knowledge

- 内容变化创建新版本；
- 元数据小改可以只增加 Metadata Revision；
- 重建索引只改变 Binding Version，不改变内容版本。

### Skill

- 发布后严格不可变；
- 使用明确版本标识；
- Job 必须固定使用某一 Skill 版本。

### Memory

- 通常不使用 SemVer；
- Memory ID 稳定；
- 内容修改增加 Revision；
- 合并或提炼可以产生新 Memory，并保留来源关系。

## 9.9 资产一致性机制

跨 PostgreSQL、S3、Lance、Iceberg 和图投影不使用分布式事务。建议采用：

- PostgreSQL 资产账本；
- Outbox；
- 后台 Worker；
- 幂等执行；
- Saga / 补偿；
- Binding 状态；
- Reconciler；
- 错误记录；
- 异步删除。

典型资产创建流程：

1. 在 PostgreSQL 创建资产记录，状态为 CREATING；
2. 在同一事务中写入 Outbox；
3. Worker 写入原始对象；
4. 执行解析和规范化；
5. 构建 Required Binding；
6. 校验 Checksum 和 Binding 状态；
7. 全部必要步骤成功后进入 READY；
8. 部分可恢复失败进入 DEGRADED；
9. 不可恢复失败进入 FAILED。

## 9.10 删除语义

删除必须是异步生命周期，而不是单个存储删除操作。

要求：

- 资产先进入 DELETING；
- 阻止新的使用或明确只读策略；
- 清除或撤销所有 Binding；
- 检查引用和血缘；
- 记录清理失败；
- Reconciler 重试；
- 所有必要物理表示清理完成后进入 DELETED；
- 删除接口不得在实际只删除 S3 时宣称“向量和图已全部删除”。

## 9.11 血缘

v0.2.0 至少需要记录：

- Knowledge 的来源对象；
- Skill 版本；
- Job Run；
- 输入资产版本；
- 模型和 Deployment；
- 输出 Artifact；
- 由 Artifact 生成的 Knowledge 或 Memory；
- 配置 Revision。

不要求建设复杂可视化血缘图，但底层关系必须可以查询。

---

# 10. Job Runtime 与 Ray

## 10.1 核心定位

Ray 不应被排除出 LakeMind。正确定位是：

> **Job 是 LakeMind 的平台能力；Ray 是 v0.2.0 的首选 Execution Backend。**

LakeMind 拥有：

- Job API；
- Job 状态机；
- 权限；
- Skill 解析；
- 输入输出绑定；
- Secret 授权；
- 模型绑定；
- 资源配额；
- 重试、取消和超时；
- 审计和血缘；
- 结果保存和恢复。

Ray 负责：

- 调度任务到计算资源；
- 执行 Task、Actor 或 Job；
- 管理执行资源；
- 为 v0.3.0 提供多节点计算基础。

## 10.2 Skill、Job、Attempt 和 Artifact

必须明确区分：

### Skill

持久、版本化的能力定义。

### Job Run

某个 Agent 或系统使用某个 Skill 版本，对确定输入发起的一次逻辑运行。

### Job Attempt

Job Run 的一次具体执行尝试。重试会产生新的 Attempt，但仍属于同一个 Job Run。

### Artifact

Job 输出的文件、文本、结构化结果、日志或模型结果。Artifact 可以进一步注册为 Knowledge 或 Memory。

关系为：

**Skill → Job Run → Job Attempt → Artifact → Knowledge / Memory**

## 10.3 Job 状态

建议 Job Run 状态包括：

- SUBMITTED；
- QUEUED；
- RUNNING；
- SUCCEEDED；
- FAILED；
- CANCELLING；
- CANCELLED；
- TIMED_OUT；
- LOST。

Ray 的状态作为 Execution Backend 状态被同步到 LakeMind，但 PostgreSQL 中的 Job Run 和 Attempt 是事实源。

## 10.4 Execution Backend 抽象

v0.2.0 应定义 ExecutionBackend 抽象，首个正式实现为 RayExecutionBackend。

未来可以扩展：

- LocalExecutionBackend；
- KubernetesJobBackend；
- ExternalWorkflowBackend。

该抽象不是为了削弱 Ray，而是避免 Job API、资产模型和权限语义被 Ray 的内部字段绑定。

## 10.5 v0.2.0 Job 安全边界

必须完成：

- 删除通用 `eval` 或任意函数源码执行入口；
- 普通 Agent 不能上传任意代码后立即执行；
- 只允许执行内置 Job 或已 PUBLISHED 的可信 Skill；
- Job 不能获得 LakeMindServer 全部环境变量；
- Secret 依据 Skill Manifest、调用者权限和 Job 目的按最小范围注入；
- Ray Dashboard 和 Submission API 不直接暴露给 Agent；
- Job 使用独立执行身份；
- Job 只能访问被授权的输入资产和输出位置；
- Job 资源和网络权限受策略约束；
- Job 的取消、查询、重试必须验证租户和资源权限。

## 10.6 资源和配额

资源决策应综合：

- Skill 默认资源；
- 租户上限；
- 平台上限；
- Job 请求覆盖；
- 当前资源可用性。

Job 不能通过请求任意突破租户配额。

v0.2.0 至少应管理：

- CPU；
- 内存；
- 并发数；
- 超时；
- 重试次数；
- 队列长度；
- 可选 GPU 声明；
- 网络访问级别。

## 10.7 可复现性

“确定性任务”建议在正式文档中表述为“受控、可审计、可重试、可复现任务”。

Job 需要固定记录：

- Skill 版本；
- 包 Checksum；
- 输入资产版本；
- 参数；
- 运行环境或依赖版本；
- 随机种子（适用时）；
- 模型 ID、Deployment 和 Revision；
- 配置 Revision；
- 输出 Schema；
- Secret 引用版本（不记录明文）。

## 10.8 Job 恢复与结果

LakeMind 必须自行承担：

- Job 重试；
- Attempt 记录；
- 超时；
- 取消；
- Lost 检测；
- Server 重启后的状态恢复；
- Ray Job 丢失后的状态校准；
- 日志和结果归档；
- Result URI；
- 幂等；
- 输出 Artifact 注册。

不能只依赖 Ray 集群当前状态判断 Job 是否存在。

## 10.9 v0.3.0 的 Ray 演进

v0.2.0：

- 单一受控 Ray 集群；
- 可以多 Worker，但默认单物理节点；
- Job 状态和安全归 LakeMind 管理。

v0.3.0：

- 多物理节点 Worker；
- 多执行队列；
- 多 Ray 集群或资源池路由；
- Worker 身份和短期凭据；
- 执行故障转移；
- 更强资源隔离；
- 执行平面横向扩展。

---

# 11. ModelServing 设计

## 11.1 总体结论

ModelServing 的配置所有权属于 Control Plane，运行执行属于 Execution Plane，并在 Control Center 中提供独立的“模型服务”管理页面。

不是：

- 把全部模型配置塞进通用全局键值配置；
- 让 ModelServing 独立维护另一套管理系统；
- 让每个 Skill 直接保存 Provider API Key 和 Endpoint。

目标关系：

- Control Plane：模型注册、路由、权限、Secret、配置 Revision；
- ModelServing：加载模型、调用 Provider、执行推理、上报状态；
- Control Center：模型管理专属页面；
- Job：绑定具体模型、Deployment 和 Revision。

## 11.2 模型领域对象

v0.2.0 至少区分：

### Model Definition

描述逻辑模型：

- 模型 ID；
- 名称；
- 类型；
- 能力；
- Provider Family；
- 上下文长度；
- Embedding 维度；
- 支持模态；
- 元数据。

### Model Deployment

描述模型具体运行位置：

- Deployment ID；
- Model ID；
- Deployment Type；
- Provider；
- Endpoint；
- Secret Ref；
- Instance；
- 状态；
- 优先级；
- 超时；
- 最大并发；
- 健康状态；
- 配置 Revision。

### Model Profile / Alias

为 Skill 和 Agent 提供稳定逻辑名称，例如：

- meeting-asr；
- meeting-summary；
- knowledge-embedding；
- lake-chat-default。

Skill 应依赖 Profile，而不是直接依赖供应商 Endpoint。

### Model Route

定义 Profile 到一个或多个 Deployment 的路由、优先级和 Fallback。

### Embedding Space

描述一组兼容的向量空间：

- Embedding 模型和 Revision；
- 维度；
- 归一化策略；
- 距离度量；
- 索引版本。

Embedding 不允许在不兼容模型之间无条件 Fallback。

## 11.3 ModelServing 配置分类

### Bootstrap 配置

- Control Plane 地址；
- Service Identity；
- 服务监听地址；
- Instance ID；
- 模型缓存路径；
- 日志级别；
- 必要的启动连接。

### Control Plane 动态配置

- 模型定义；
- Deployment；
- Profile；
- Route；
- Fallback；
- 超时；
- 并发；
- 租户访问；
- Provider 使用策略；
- 配置 Revision。

### Runtime 配置

- CPU / GPU；
- Worker 数；
- Batch Size；
- 模型预热；
- 缓存；
- 模型加载和卸载策略；
- 请求队列。

### Secret

- Provider API Key；
- 外部模型认证；
- 私有 Endpoint 凭据。

Deployment 只保存 Secret Ref，不保存明文 API Key。

## 11.4 `models.yaml` 的目标角色

v0.2.0 中 `models.yaml` 可以保留为：

- 开发环境 Bootstrap；
- 首次部署初始化清单；
- 离线部署配置快照。

初始化导入后：

- PostgreSQL / Control Plane 成为模型注册和路由的事实源；
- ModelServing 不再以 YAML 持续覆盖动态配置；
- 模型管理修改通过 Control Center 和 Operation Service 完成；
- ModelServing 加载 Desired Revision，并上报 Active Revision。

## 11.5 ModelServing 管理页面

页面至少提供：

### Models

- 模型定义；
- 类型和能力；
- 模型状态；
- 被哪些 Profile 使用。

### Deployments

- Provider；
- Endpoint；
- Secret Ref；
- 优先级；
- 健康；
- 并发；
- 启用和禁用；
- 连接测试。

### Routing

- 默认模型；
- Profile；
- 主 Deployment；
- Fallback；
- Tenant 覆盖；
- 敏感数据模型限制；
- Embedding Space 兼容检查。

### Runtime

- 当前实例；
- 当前加载模型；
- 请求量；
- 成功率；
- 延迟；
- 错误；
- 资源；
- Desired / Active Revision；
- Reload 或预热状态。

## 11.6 模型配置生效

模型配置变更必须产生 Revision，并根据变更类型执行：

- HOT_RELOAD：路由、优先级、外部 Endpoint、超时；
- MODEL_RELOAD：本地模型、Batch、模型参数；
- SERVICE_RESTART：设备、缓存根目录、底层 Runtime 等。

切换默认模型等高影响动作应通过 Operation Service：

- 校验目标 Deployment；
- 检查健康；
- 检查 Embedding 兼容性；
- 创建 Revision；
- 下发配置；
- 验证生效；
- 激活；
- 审计。

## 11.7 Job 与模型绑定

Job 提交时，Control Plane 将 Skill 声明的 Model Profile 解析为具体：

- Model ID；
- Deployment ID；
- Model Revision；
- Routing Revision；
- Embedding Space。

这些信息必须固定在 Job Run 中。后续默认模型切换不能改变历史 Job 的实际模型记录。

## 11.8 v0.2.0 ModelServing 必须完成

- 模型定义、Deployment、Profile、Route 概念分离；
- PostgreSQL / Control Plane 成为动态配置事实源；
- API Key 改为 Secret Ref；
- 支持 Chat、Embedding、ASR 三类能力；
- 支持默认路由和受控 Fallback；
- 建立 Embedding Space；
- ModelServing 实例上报健康和 Revision；
- Job 记录实际模型绑定；
- Control Center 提供专属管理页面；
- 所有模型管理变化可审计。

## 11.9 后续版本再考虑

- 自动成本优化；
- A/B 测试；
- 智能路由；
- 多 GPU 调度；
- 模型自动扩缩容；
- 模型评测平台；
- Prompt 管理；
- 跨区域模型副本；
- 复杂费用结算。

---

# 12. 接口与契约设计

## 12.1 v0.2.0 稳定目标

架构、接口和资产模型不要求成为永久不变的 v1.0 契约，但必须达到：

- 核心概念稳定；
- 后续可以扩展而无需推翻；
- v0.3.0 多节点化不改变核心资源语义；
- v0.4.0 Studio 可以基于这些接口开发。

原则：

- 架构：逻辑定型，物理部署可演进；
- 外部接口：核心 Beta 稳定；
- 内部 Provider：允许演进；
- 资产模型：公共内核稳定，类型细节可扩展。

## 12.2 REST API

建议统一为版本化资源 API：

- `/api/v1/assets`；
- `/api/v1/knowledge`；
- `/api/v1/skills`；
- `/api/v1/memories`；
- `/api/v1/jobs`；
- `/api/v1/operations`；
- `/api/v1/models`；
- `/api/v1/configuration`；
- `/api/v1/security`；
- `/api/v1/audit`；
- `/api/v1/instances`；
- `/api/v1/health`。

需要统一：

- 认证和授权；
- Request ID；
- Correlation ID；
- 错误模型；
- 分页；
- 过滤和排序；
- 幂等键；
- 异步 Operation；
- 删除语义；
- 时间格式；
- 版本兼容规则。

## 12.3 MCP

MCP 必须与 REST 共享 Application Service 和业务语义。

### AssetMCP

- 面向业务 Agent；
- 提供 Knowledge、Skill、Memory 的语义能力；
- 不直接操作物理 S3、Lance 或图；
- 不自行实现跨存储一致性。

### DataMCP

- 面向 Steward 和受信任高级 Agent；
- 提供受控数据访问；
- 原始数据操作不得破坏 AssetService 托管的 Protected Namespace；
- 破坏性操作需要更严格权限；
- 不应成为绕过资产生命周期的入口。

### AdminMCP

- 面向 Steward、管理员工具和自动化；
- 管理能力最终调用 Configuration、Operation、Security、Model、Job 和 Asset Service；
- 不直接操作数据库。

## 12.4 资源 ID 与逻辑 URI

建议统一资源 ID 前缀：

- Asset：`ast_`；
- Job：`job_`；
- Attempt：`atm_`；
- Operation：`op_`；
- Principal：`prn_`；
- Tenant：`ten_`；
- Model：`mdl_`；
- Deployment：`dpl_`。

逻辑 URI 示例：

- `lake://knowledge/{name}@{version}`；
- `lake://skills/{name}@{version}`；
- `lake://memory/{memory_id}`；
- `lake://jobs/{job_id}`；
- `model://{profile}`；
- `secret://{scope}/{name}`。

物理 S3 Key、Lance Path 和数据库主键不应作为外部契约。

## 12.5 异步 Operation

以下动作应优先采用异步 Operation：

- Knowledge 摄入和索引；
- Asset 删除；
- Skill 发布和校验；
- Job 提交；
- 模型 Reload；
- 配置激活；
- 索引重建；
- Secret 轮换；
- 数据迁移。

API 应返回 Operation ID 和资源 ID，调用者通过状态查询后续结果。

## 12.6 幂等

至少以下操作需要支持 Idempotency Key：

- 创建资产；
- 摄入 Knowledge；
- 添加持久 Memory；
- 发布 Skill；
- 提交 Job；
- 删除资产；
- 创建管理 Operation。

Agent 网络重试不能导致重复资产或重复 Job。

## 12.7 错误模型

错误响应必须包含：

- 稳定错误码；
- 可读信息；
- Request ID；
- 资源状态；
- 可重试性；
- 必要细节。

重点错误类别：

- AUTHENTICATION_FAILED；
- PERMISSION_DENIED；
- TENANT_SCOPE_VIOLATION；
- ASSET_NOT_READY；
- ASSET_DEGRADED；
- SKILL_NOT_PUBLISHED；
- JOB_RESOURCE_DENIED；
- MODEL_DEPLOYMENT_UNAVAILABLE；
- EMBEDDING_SPACE_MISMATCH；
- CONFIG_REVISION_CONFLICT；
- OPERATION_APPROVAL_REQUIRED。

## 12.8 内部 Provider 契约

v0.2.0 应定义但不承诺永久兼容的内部抽象：

- ObjectStorageProvider；
- TableStorageProvider；
- VectorIndexProvider；
- GraphProjectionProvider；
- CacheProvider；
- ExecutionBackend；
- ModelProvider；
- AuthorizationProvider；
- SecretProvider；
- ConfigurationProvider。

这些抽象用于后续替换引擎或接入外部系统，不应把 Ray、Lance、SeaweedFS 等专有字段泄漏到外部 API。

## 12.9 内部事件

v0.2.0 可以先使用 PostgreSQL Outbox，无需立即引入消息队列，但事件名称和基本语义应稳定：

- asset.created；
- asset.processing；
- asset.ready；
- asset.degraded；
- asset.deleted；
- job.submitted；
- job.running；
- job.succeeded；
- job.failed；
- job.lost；
- operation.approval_required；
- operation.succeeded；
- config.activated；
- model.deployment_unhealthy。

v0.3.0 可以在不改变业务事件语义的情况下接入事件总线。

---

# 13. PostgreSQL、Gravitino 与 Ranger 的边界

## 13.1 v0.2.0 继续使用 PostgreSQL

PostgreSQL 在 v0.2.0 承担：

- 身份和 Token；
- 权限和角色；
- 资产账本；
- Asset Binding；
- Job Run 和 Attempt；
- Operation；
- 配置 Revision；
- 模型注册和路由；
- Secret 密文及元数据；
- 审计；
- Outbox；
- Reconciler 状态；
- Iceberg Catalog；
- 简单图关系。

PostgreSQL 是事实源，但安全能力由 Control Plane 执行，而不是“把数据放入 PostgreSQL 就自然安全”。

## 13.2 Gravitino 的引入时点

LakeMind 不应从 PostgreSQL “迁移到 Gravitino”。两者职责不同。

v0.2.0：

- 不引入 Gravitino；
- 稳定 LakeMind 自身资产语义和控制面；
- 为外部 Catalog Provider 保留抽象。

v0.3.0：

- 当出现多个 Iceberg Catalog、外部 Fileset、Spark/Trino/Flink 访问或跨来源发现需求时，可以进行实验性 Adapter；
- Gravitino 作为外部元数据联邦，不替代 LakeMind 资产账本。

v0.5.0 / 企业版：

- 在确有跨系统目录联邦需求时正式接入；
- LakeMind 管理“资产对 Agent 的语义、生命周期和使用关系”；
- Gravitino 管理“数据基础设施对象是什么、在哪里、如何被外部引擎发现”。

## 13.3 Ranger 的引入时点

v0.2.0：

- 不引入 Ranger；
- 实现 PostgreSQL 驱动的 AuthorizationProvider；
- 稳定 Knowledge、Skill、Memory、Job、Model 和 Secret 的权限粒度。

后续满足以下条件时再评估 Ranger：

- 企业已有 Ranger 体系；
- LakeMind 接入多个外部数据平台；
- 需要统一管理 S3、Kafka、Trino、Iceberg 等权限；
- 需要行级、字段级、标签驱动策略；
- 需要 LDAP / AD 组织治理；
- LakeMind 自身权限模型已经稳定。

Ranger 不替代 LakeMind 身份、资产生命周期、Job、Token 和 Secret 管理。

---

# 14. Meeting Agent：Reference Application 与 Golden Path

## 14.1 定位

Meeting Agent 在 v0.2.0 不再只是示例，而应成为：

- LakeMind Reference Application；
- 端到端 Golden Path；
- 安全、资产、Job、ModelServing、一致性和恢复的验收系统。

## 14.2 标准链路

Meeting Agent 应覆盖：

1. 用户或 Agent 上传会议音频；
2. 创建原始输入对象和资产记录；
3. 提交 ASR Job；
4. Job 解析 `meeting-asr` 模型 Profile；
5. 生成转写 Artifact；
6. 提交摘要和知识提取 Job；
7. 生成 Knowledge；
8. 建立 Chunk 和 Embedding Binding；
9. 提取并沉淀符合条件的 Memory；
10. 进行 Knowledge 和 Memory 检索；
11. 展示来源、模型、Skill、Job 和配置血缘；
12. 支持失败重试；
13. 支持完整删除；
14. 在 Control Center 中观察全过程。

## 14.3 安全验收场景

- Tenant A 无法读取 Tenant B 的会议和结果；
- Agent 无法伪造 Tenant Header；
- 无 Skill 执行权限的 Agent 无法提交 Meeting Skill Job；
- ASR Job 只能获得声明的模型和 Secret；
- 被撤销的 Skill 不能运行；
- Agent 不能直接访问 Ray Dashboard；
- Control Center 管理操作全部有审计。

## 14.4 一致性验收场景

- S3 成功、Embedding 失败：资产进入 DEGRADED，而非 READY；
- Ray 提交失败：Job Run 仍存在并记录失败；
- 请求重试：不会产生重复资产或重复 Job；
- Lance 索引丢失：可以从资产内容重建；
- 删除失败：资产保持 DELETING，并由 Reconciler 继续处理；
- ModelServing 不可用：Job 有明确失败和重试语义；
- 配置 Revision 未同步：Control Center 可以发现。

## 14.5 恢复验收场景

- LakeMindServer 重启后 Job 和资产状态可恢复；
- Ray 中 Job 丢失后标记 LOST 或 FAILED；
- Outbox Worker 重启后不重复执行已完成步骤；
- Reconciler 可以修复不完整 Binding；
- ModelServing 重启后重新加载 Desired Revision；
- Steward 可以发现异常并创建治理 Operation。

---

# 15. v0.1.0 到 v0.2.0 的改造映射

## 15.1 LakeMindServer

从：

- 统一 REST API；
- Router 直接调用插件；
- 全局 API Key；
- 信任租户请求头；
- 多引擎薄封装。

改造为：

- Control Plane 核心承载；
- Application Service 层；
- Security Context；
- Asset Runtime；
- Job Service；
- Model Management；
- Configuration、Secret、Operation、Audit；
- Outbox 和 Reconciler；
- 统一数据库迁移管理。

## 15.2 三类 MCP

从：

- 各自实现部分业务编排；
- 各自持有重复 Client 和静态 Token 配置；
- MCP 层拼接租户路径；
- Admin 动态 Token 与实际认证脱节。

改造为：

- MCP 作为纯协议适配层；
- 统一认证和 Security Context；
- 调用同一 Application Service；
- 提取共享 MCP 基础包；
- 租户资源范围由 Server 强制；
- AdminMCP 调用 Operation 和 Control Plane 管理 API。

## 15.3 LakeMindMonitor

从：

- 只读 Dashboard；
- 静态 Token；
- 代理三个 MCP；
- 无用户系统；
- Steward Chat。

改造为：

- LakeMind Control Center；
- 管理员身份和角色；
- 统一 Overview；
- Assets、Jobs、Model Serving、Services、Configuration、Security、Operations、Audit、Steward 页面；
- 所有写操作通过 Operation Service；
- 展示 Desired / Active Revision；
- 展示资产和 Job 的真实状态，而非仅引擎健康。

## 15.4 LakeMindSteward

从：

- MCP 管理对话；
- 巡检和原始数据聚合；
- 可能使用宽泛管理能力。

改造为：

- 受控治理 Agent；
- 独立 Service Identity；
- 三级风险动作；
- 低风险自动治理；
- 高风险 Operation 审批；
- 不直接操作数据库和引擎；
- 所有动作审计。

## 15.5 LakeMindModelServing

从：

- `models.yaml`、环境变量、PostgreSQL Registry 多重配置源；
- API Key 可能直接存储；
- 自身管理模型注册；
- 缺少统一 Model Profile、Deployment 和 Revision。

改造为：

- Control Plane 统一模型管理；
- 模型、Deployment、Profile、Route、Embedding Space 分离；
- Secret Ref；
- 配置 Revision；
- Desired / Active 状态；
- Control Center 独立模型服务页面；
- Job 固定模型绑定。

## 15.6 Ray / Job

从：

- DataMCP Job 工具；
- Ray 状态与 LakeMind Job 混合；
- 通用函数或源码执行路径；
- Server 环境变量可能整体传递；
- Job 权限和租户校验不足。

改造为：

- JobService 一等 Control Plane 能力；
- RayExecutionBackend；
- Skill、Job Run、Attempt、Artifact 分离；
- 只执行可信 PUBLISHED Skill 或内置 Job；
- Secret 最小注入；
- 资源配额；
- Job 状态恢复；
- 完整租户和权限检查；
- Control Center Job 页面。

## 15.7 文档体系

必须同步更新：

- README 项目定位；
- AGENTS.md；
- `.agent/DESIGN.md`；
- `.agent/SPEC.md`；
- `.agent/STATE.md`；
- ModelServing DESIGN；
- MCP 工具说明；
- API Reference；
- Meeting Agent 文档；
- 安全与部署指南。

特别需要消除“平台完全不执行 Skill”与“Ray Job 是平台一等能力”的冲突描述。

---

# 16. 开发工作包

## WP1：架构与契约基础

目标：形成 v0.2.0 的稳定逻辑架构和外部契约。

交付物：

- 四平面架构文档；
- Trust Boundary 文档；
- Application Service 边界；
- API v1 规范；
- MCP 与 REST 共享语义方案；
- 统一资源 ID 和 URI；
- 统一错误模型；
- Operation、事件和幂等规范；
- ADR 清单。

## WP2：Control Plane 与安全

目标：建立可信身份、授权、配置、Secret、审计和管理操作。

交付物：

- Security Context；
- 统一 Token 体系；
- Principal、Tenant、Role、Policy；
- Token 哈希和撤销；
- Configuration Service；
- Instance Registry；
- Secret Service；
- Audit Service；
- Operation Service；
- 网络边界调整；
- 跨租户测试。

## WP3：Asset Runtime

目标：让 Knowledge、Skill、Memory 真正成为平台资产。

交付物：

- Asset Core；
- Asset Binding；
- 状态机；
- 版本和 Revision；
- Knowledge、Skill、Memory 类型模型；
- Outbox；
- Reconciler；
- 异步删除；
- 血缘；
- Protected Namespace；
- 故障注入测试。

## WP4：Job Runtime 与 Ray

目标：建立受控、可审计、可恢复的任务运行时。

交付物：

- JobService；
- Job Run 和 Attempt；
- RayExecutionBackend；
- Skill 执行资格校验；
- 资源和配额；
- Secret 与模型绑定；
- 结果 Artifact；
- 重试、取消、超时和 Lost；
- 日志归档；
- 移除任意代码和全环境注入路径。

## WP5：ModelServing 管理

目标：将模型服务纳入统一 Control Plane。

交付物：

- Model Definition；
- Deployment；
- Profile；
- Route；
- Embedding Space；
- Secret Ref；
- 配置 Revision；
- 实例状态；
- Job 模型绑定；
- 模型管理 Operation。

## WP6：LakeMind Control Center

目标：形成统一全局管理入口。

交付物：

- Overview；
- Assets；
- Jobs；
- Model Serving；
- Services；
- Configuration；
- Security；
- Operations；
- Audit；
- Steward；
- 管理员认证和权限；
- 管理操作审批。

## WP7：Steward 治理

目标：将 Steward 从管理对话工具升级为受控治理 Agent。

交付物：

- 独立 Service Identity；
- 观察、低风险自动治理、高风险审批三级模型；
- Operation Request；
- 治理策略配置；
- 结果审计；
- 与 Control Center 集成。

## WP8：Meeting Agent Golden Path

目标：以真实参考应用验证全部核心能力。

交付物：

- 安全链路；
- Skill、Job、Model、Artifact、Knowledge、Memory 全血缘；
- 故障恢复；
- 删除；
- 重试和幂等；
- Control Center 可观察；
- 自动化验收测试。

## WP9：工程与发布

目标：使 v0.2.0 可重复部署、迁移和验证。

交付物：

- 数据库迁移机制；
- Bootstrap 初始化；
- 默认密钥和密码清理；
- 配置迁移；
- v0.1 数据导入；
- 单元、契约、集成和安全测试；
- 备份与恢复说明；
- 发布文档；
- 升级和回滚指南。

---

# 17. 建议实施顺序

## 阶段 A：设计冻结

- 确认项目定位；
- 冻结四平面边界；
- 冻结 Asset、Skill、Job、Artifact、Model、Operation 核心术语；
- 确认 API v1 和状态机；
- 完成 ADR；
- 更新现有冲突文档。

## 阶段 B：Control Plane 骨架

- 数据库迁移；
- Security Context；
- Identity、Authorization、Audit；
- Configuration、Instance Registry、Secret；
- Operation 和 Outbox 基础。

## 阶段 C：Asset Runtime

- Asset Core；
- Binding；
- Knowledge；
- Skill；
- Memory；
- Reconciler；
- 删除和恢复。

## 阶段 D：Job 与 ModelServing

- Job Run / Attempt；
- RayExecutionBackend；
- Skill 执行约束；
- 模型领域模型；
- ModelServing Revision；
- Secret 和模型绑定。

## 阶段 E：Control Center 与 Steward

- Monitor 演进；
- 管理页面；
- Operation 审批；
- Steward 三级治理；
- 管理员权限。

## 阶段 F：Meeting Agent 与硬化

- Golden Path 迁移；
- 安全测试；
- 故障注入；
- 恢复测试；
- 文档和发布检查。

开发可以在阶段间部分并行，但必须保持以下依赖：

- Control Center 不应先于 Control Plane 契约自由开发；
- Job 不应先于 Skill 版本和权限模型定型；
- ModelServing 页面不应先于 Model Definition、Deployment 和 Profile 模型定型；
- Meeting Agent 最终迁移必须基于正式 Asset、Job 和 Model 契约。

---

# 18. v0.2.0 发行验收标准

## 18.1 架构与契约

- 四平面职责和 Trust Boundary 有正式文档；
- REST、MCP 和 Control Center 调用同一 Application Service；
- 外部 API 使用 `/api/v1`；
- 资源 ID、URI、错误、幂等和 Operation 契约统一；
- Provider 接口不向外暴露底层引擎细节；
- 当前文档中的项目定位冲突已消除。

## 18.2 安全

- Tenant A 无法访问 Tenant B 的 Asset、Job 和 Secret；
- 伪造 Tenant / Agent Header 无法改变身份；
- Token 撤销在所有入口真实生效；
- Token 不以明文保存；
- Control Center 不使用共享静态管理员 Token；
- Ray Dashboard 不向 Agent 暴露；
- Job 不获得控制面全部环境变量；
- 所有高风险操作有授权和审计；
- 默认密码和默认生产密钥被移除或强制初始化更改。

## 18.3 资产

- Knowledge、Skill、Memory 拥有统一 Asset Core；
- 每个资产可以查看 Binding 状态；
- Skill 发布版本不可覆盖；
- Memory 的临时态和持久态明确区分；
- Required Binding 完成后才进入 READY；
- Embedding 失败不会写入伪零向量并假装成功；
- 删除可以最终清理所有必要 Binding；
- 索引可重建；
- 资产有来源和基本血缘。

## 18.4 Job 与 Ray

- Job 是 LakeMind 一等资源；
- Skill、Job Run、Attempt、Artifact 边界清晰；
- 只允许执行可信 PUBLISHED Skill 或内置 Job；
- 任意源码 `eval` 入口已移除；
- Job 有租户和资源权限校验；
- Job 支持重试、取消、超时和 Lost；
- LakeMindServer 重启后 Job 状态可恢复；
- Ray 状态异常可以被 Reconciler 发现；
- 输出 Artifact 可以资产化。

## 18.5 ModelServing

- 模型、Deployment、Profile、Route 和 Embedding Space 已建立；
- Provider 密钥使用 Secret Ref；
- ModelServing 加载 Desired Revision 并上报 Active Revision；
- Control Center 有独立模型服务页面；
- Job 记录实际模型和 Deployment；
- 不兼容 Embedding 模型不能自动写入同一向量空间；
- 模型管理动作可审计。

## 18.6 Control Center 与 Steward

- Control Center 成为统一管理入口；
- Overview、Assets、Jobs、Model Serving、Services、Configuration、Security、Operations、Audit 和 Steward 页面可用；
- 管理员有身份和角色；
- 所有写操作通过 Operation Service；
- Steward 具备三级治理；
- 高风险 Steward 操作必须审批；
- Steward 不直接访问数据库和引擎。

## 18.7 一致性与恢复

- Outbox 支持故障后继续处理；
- 重复请求不产生重复资产和 Job；
- Reconciler 可以发现和修复不完整 Binding；
- 删除失败保持 DELETING 并可重试；
- ModelServing 配置不收敛可被发现；
- Meeting Agent 能完成故障注入和恢复验收。

## 18.8 文档与迁移

- 有 v0.1.0 到 v0.2.0 升级说明；
- 有数据和配置迁移说明；
- 有备份和恢复说明；
- 有安全部署说明；
- 有 Control Center 使用说明；
- 有 Skill 发布和 Job 执行说明；
- 有 ModelServing 配置说明；
- 有 Meeting Agent Golden Path 文档。

---

# 19. v0.2.0 明确不做的事项

为保证版本收敛，以下事项不属于 v0.2.0：

- 完整 LakeMindStudio；
- 通用 Agent 托管平台；
- 多 Agent 工作流编排；
- 任意第三方不可信代码执行；
- Kubernetes Operator；
- 多区域部署；
- 全组件高可用；
- 复杂灰度发布；
- 自动模型成本优化；
- 完整本体设计器；
- 动态任意资产类型编译器；
- Apache Gravitino 正式接入；
- Apache Ranger 正式接入；
- 完整 OIDC / LDAP / SAML 企业身份集成；
- 复杂行列级数据脱敏；
- 大规模事件总线；
- 跨组织资产市场。

这些能力必须建立在 v0.2.0 稳定的控制面和资产契约之上。

---

# 20. 后续版本路线

## 20.1 v0.3.0：Scalable Runtime

重点：

- 无状态服务多副本；
- Execution Plane 多节点；
- Ray 多物理节点和资源池；
- Job 队列、调度和故障转移；
- Worker 短期身份；
- 配置多实例收敛；
- 更完整的可观测性；
- PostgreSQL、对象存储和缓存的生产部署方案；
- 外部 Catalog Provider 抽象；
- 在出现真实需求时进行 Gravitino 实验性 Adapter。

v0.3.0 不要求所有组件都变成分布式系统，而是优先解决执行吞吐、服务副本和故障恢复。

## 20.2 v0.4.0：Developer Platform

重点：

- LakeMindStudio；
- Skill 脚手架；
- Skill 本地验证；
- Manifest 编辑和校验；
- Knowledge 资产设计；
- MCP 调试；
- Job 调试；
- Model Profile 选择；
- 发布和版本管理；
- 开发环境与生产 Control Center 分离。

## 20.3 v0.5.0 / v1.0：Enterprise Federation

根据实际企业需求评估：

- OIDC、LDAP、AD；
- Gravitino 元数据联邦；
- Ranger 或其他外部策略系统；
- 多组织和跨域治理；
- 行列级策略和数据脱敏；
- 外部审计系统；
- 多区域和灾难恢复；
- 稳定长期兼容性承诺；
- 企业级 SLA。

---

# 21. 建议新增的架构决策记录

建议至少建立以下 ADR：

1. LakeMind 是认知资产平台，同时提供受控 Job Runtime，但不是通用 Agent Runtime；
2. PostgreSQL 是 Control Plane 和资产账本事实源；
3. 四平面逻辑架构；
4. MCP 是协议适配层，不承担资产一致性和安全事实；
5. Knowledge、Skill、Memory 是 v0.2.0 核心资产，Ontology 为 Experimental；
6. Asset Binding 和最终一致性模型；
7. Skill、Job Run、Attempt、Artifact 分离；
8. Ray 是首选 Execution Backend；
9. ModelServing 配置归 Control Plane；
10. Control Center 取代只读 Monitor 定位；
11. Steward 采用三级受控治理；
12. Gravitino 和 Ranger 延后引入；
13. DataMCP 不得破坏受管理资产命名空间；
14. 配置使用 Revision 和 Desired / Active 模型；
15. Secret 通过引用和最小权限使用。

---

# 22. 最终设计结论

LakeMind v0.2.0 的核心不是继续增加引擎、页面或资产类型，而是完成一次平台内核收敛：

- 以 PostgreSQL 为 Control Plane 和资产账本事实源；
- 以四平面明确系统职责和信任边界；
- 以 LakeMind Control Center 统一 Monitor、Steward、ModelServing 配置和全局管理；
- 以 Knowledge、Skill、Memory 建立稳定的 Agent 资产模型；
- 以 Asset Binding、Outbox、Reconciler 和状态机保障资产一致性；
- 以 JobService 和 RayExecutionBackend 承载受控、可审计、可恢复的任务；
- 以 Model Definition、Deployment、Profile、Route 和 Embedding Space 管理模型服务；
- 以统一身份、授权、Secret、Operation 和 Audit 建立可信运行环境；
- 以 Meeting Agent 证明整条链路能够安全运行、真实沉淀、故障恢复和完整删除。

v0.2.0 完成后，LakeMind 应达到以下状态：

> **它不再只是一个把多种引擎包在统一 API 后面的集成样机，而是形成了边界清晰、资产可信、配置统一、任务受控、模型可管、运维可审计的单节点平台内核。**

该内核将成为：

- v0.3.0 多节点扩展的基础；
- v0.4.0 LakeMindStudio 的稳定后端；
- 后续 Gravitino、Ranger 和企业治理体系的接入基础；
- 企业级多智能体矩阵的认知资产底座和受控计算执行入口的核心实现。
