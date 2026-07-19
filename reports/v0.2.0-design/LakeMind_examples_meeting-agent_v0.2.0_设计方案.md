# LakeMind examples/meeting-agent v0.2.0 设计方案

> **定位**：LakeMind v0.2.0 Reference Application / Golden Example  
> **目标**：用一个真正可用、可演示、可验收的会议智能应用，验证 LakeMind 的身份、权限、对象存储、Skill、Job、Model、Artifact、Knowledge、Memory、血缘、恢复、审计和 Control Center 能力。  
> **设计原则**：应用体验优先、平台能力真实、权限边界可信、链路可恢复、不过度设计。  
> **适用版本**：LakeMind v0.2.0  
> **建议应用版本**：Meeting Agent v0.2.0

---

# 0. 执行摘要

当前 `examples/meeting-agent` 已经跑通：

```text
浏览器录音
→ 音频分片
→ Ray ASR Job
→ 周期性会议纪要
→ 知识萃取
→ 向量入库
→ 任务展廊与知识检索
```

它证明了 LakeMind v0.1 阶段的对象存储、Ray、ModelServing、Skill 包和向量存储可以协同工作。

但是当前版本仍然是一个单用户、单租户、无认证的技术 Demo，存在以下根本限制：

- 所有人共用一个固定 Tenant；
- Web 和 API 无认证；
- 所有人可看到全部会议任务；
- SSE 是全局广播，不区分用户和会议；
- 活动会议状态保存在进程内存，服务重启后无法恢复；
- 任务状态使用 Iceberg append-only 全表扫描，不适合作为多用户事务状态；
- 音频只有分片，没有正式的可播放 Recording Artifact；
- 纪要模板和知识萃取目标写死在 Skill 代码中；
- 知识在会议进行期间直接写入共享知识库，容易产生重复、错误和污染；
- 任务详情依靠“会议标题语义检索”查找知识，不能保证属于该会议；
- Agent 仍使用旧式内部 API Key、`X-Tenant-Id` 和部分 v0.1 API；
- Agent 和 Job 中存在直接绑定 ModelServing 地址、模型名和 Secret 的方式；
- 缺少失败重试、幂等、恢复、完整删除和用户级配额。

Meeting Agent v0.2.0 应从“流水线 Demo”升级为：

> **一个支持快速注册、个人任务隔离、会议处理模板、录音回放、知识审核发布和全过程可观察的 LakeMind 黄金样例。**

核心体验：

1. 用户快速注册并登录；
2. 用户只能看到自己的会议任务；
3. 创建任务时选择或编辑会议处理模板；
4. 实时录音、转写和纪要预览；
5. 停止后生成可回放的完整录音；
6. 生成最终转写、最终纪要和知识草稿；
7. 用户审核、修改并发布知识；
8. 所有处理过程由正式 Skill、Job、Model Profile 和 Artifact 完成；
9. 用户可重试失败阶段、下载结果或完整删除；
10. 管理员可在 Control Center 中看到 Job、Asset、Model、资源、Operation 和 Audit。

---

# 1. 产品定位

## 1.1 一句话定位

> **Meeting Agent 是一个将会议录音转化为可回放、可检索、可审核知识资产的个人会议智能工作台。**

## 1.2 它不是什么

Meeting Agent v0.2.0 不定位为：

- 企业级视频会议平台；
- Zoom、Teams 或腾讯会议替代品；
- 多人实时协同编辑平台；
- 大规模呼叫中心录音平台；
- 完整知识管理产品；
- 独立身份平台；
- 独立模型平台；
- 复杂工作流设计器。

它首先是一个：

- 可日常使用的示例应用；
- LakeMind 标准接入参考；
- v0.2.0 Golden Path；
- 安全、一致性和恢复能力的验收应用。

## 1.3 目标用户

### 普通用户

- 快速注册；
- 创建和录制会议；
- 上传已有录音；
- 设置会议处理模板；
- 查看自己的任务；
- 回放录音；
- 查看和编辑转写；
- 查看和编辑纪要；
- 审核和发布知识。

### 平台管理员

不在 Meeting Agent UI 中直接浏览所有用户会议内容。

管理员通过 Control Center：

- 查看应用服务健康；
- 查看 Job；
- 查看 Asset 和 Artifact；
- 查看模型使用；
- 查看失败和重试；
- 查看资源消耗；
- 查看 Audit；
- 执行获得授权的治理操作。

## 1.4 v0.2.0 成功标准

Meeting Agent v0.2.0 完成后，应能真实证明：

```text
Identity
+ Tenant Membership
+ Owner Isolation
+ Published Skill
+ Job Service
+ Model Profile
+ Secret 最小注入
+ Artifact
+ Knowledge
+ Memory
+ Lineage
+ Retry
+ Recovery
+ Delete
+ Audit
+ Control Center Observability
```

---

# 2. 设计准则

## 2.1 用户数据默认私有

- 每个会议任务有不可变的 `owner_principal_id`；
- 普通用户只能读取和修改自己的任务；
- 默认不提供会议分享；
- 不允许客户端提交或修改 Owner；
- 权限由服务端 SecurityContext 决定；
- 管理员跨用户查看内容必须通过专门权限和审计，不在示例前端提供。

## 2.2 单一示例 Tenant，不为每个用户创建 Tenant

建议：

```text
Tenant: meeting-agent-demo
Membership: 每个注册用户自动加入该 Tenant
Role: meeting_user
```

理由：

- 注册快速；
- 不制造大量 Tenant；
- 验证 Tenant 内 Principal 和 Owner 级隔离；
- 更符合 SaaS 应用的基本模式；
- Platform Admin 仍可通过 Control Center 管理该 Tenant。

每个用户的文件和认知资产仍按 Principal 隔离：

```text
meeting-agent-demo/
  users/{principal_id}/
    meetings/{task_id}/
```

## 2.3 LakeMind 是平台事实源，Meeting Agent 只保存应用状态

Meeting Agent 保存：

- 任务标题；
- 用户选择的模板；
- 录音分片清单；
- 页面进度；
- Stage 与 Job 的关联；
- 转写段落编辑记录；
- 知识审核状态。

LakeMind 保存和治理：

- Principal、Membership、Token；
- Published Skill；
- Job Run / Attempt；
- Artifact；
- Model Profile / Deployment；
- Secret；
- Knowledge；
- Memory；
- Audit；
- Operation；
- Asset Binding 和 Lineage。

## 2.4 实时预览不等于最终结果

会议进行中：

- 实时转写是 Preview；
- 实时纪要是 Preview；
- 知识只能是 Draft Preview；
- 不直接发布到正式 Knowledge。

会议结束后：

- Finalize Audio；
- Finalize Transcript；
- Generate Final Minutes；
- Extract Knowledge Draft；
- 用户审核；
- Publish Knowledge。

## 2.5 所有结果可追溯

最终知识条目必须知道：

- 来自哪个会议；
- 来自哪个转写段落；
- 对应录音的时间范围；
- 使用哪个 Skill 版本；
- 使用哪个 Job Attempt；
- 使用哪个 Model Deployment；
- 使用哪个模板版本；
- 由谁审核和发布。

## 2.6 不使用内部万能身份

禁止：

- 全局内部 API Key 代表所有用户；
- 信任 `X-Tenant-Id`；
- Agent 直接持有平台管理员 Token；
- Job 获得全部环境变量；
- 浏览器获得 ModelServing Key；
- 浏览器获得 S3 Secret；
- 通过客户端请求体指定用户身份。

---

# 3. 用户核心旅程

## 3.1 首次注册

```text
打开 Meeting Agent
→ 输入用户名、密码、显示名称
→ 注册
→ 自动加入 meeting-agent-demo Tenant
→ 自动获得 meeting_user Role
→ 自动登录
→ 进入“我的会议”
```

Demo 模式可以不做邮件验证，但必须：

- 用户名唯一；
- 密码安全哈希；
- 注册限流；
- 禁止弱密码；
- 防止批量滥用；
- 注册服务权限被限制在固定 Tenant 和固定 Role。

## 3.2 创建实时会议任务

```text
点击“新建会议”
→ 输入标题和参会人
→ 选择会议处理模板
→ 调整转写设置和知识萃取要点
→ 创建任务
→ 授权麦克风
→ 开始录音
```

## 3.3 实时会议处理

```text
录音
→ 浏览器产生连续音频分片
→ 分片上传
→ ASR Job
→ 转写段落实时返回
→ 周期性生成纪要预览
→ 页面展示处理状态
```

## 3.4 停止和最终处理

```text
停止录音
→ 等待最后分片上传
→ Finalize Audio Job
→ Finalize Transcript Job
→ Final Minutes Job
→ Knowledge Extract Job
→ 生成知识草稿
→ 状态进入 REVIEW_REQUIRED
```

## 3.5 回放和审核

```text
进入任务详情
→ 播放完整录音
→ 当前播放位置高亮对应转写
→ 点击转写段落跳转到录音时间
→ 编辑转写
→ 查看并编辑纪要
→ 审核知识草稿
→ 发布知识
→ 任务 COMPLETED
```

## 3.6 上传已有录音

建议作为 v0.2.0 必备功能，而不是以后再做：

```text
新建任务
→ 选择“上传录音”
→ 上传 mp3 / wav / m4a / webm
→ 创建 Recording Artifact
→ 运行同一最终处理流水线
```

它可以：

- 降低演示对麦克风的依赖；
- 方便固定测试音频回归；
- 验证大文件Artifact和Job链路；
- 便于用户处理历史会议。

---

# 4. 信息架构与页面设计

## 4.1 页面结构

```text
/auth
  ├─ 登录
  └─ 注册

/app
  ├─ 我的会议
  ├─ 新建会议
  ├─ 会议详情
  ├─ 我的模板
  ├─ 我的会议知识
  └─ 个人设置
```

## 4.2 登录与注册页

注册字段：

- 用户名；
- 显示名称；
- 密码；
- 确认密码；
- 同意录音和数据处理提示。

可选字段：

- Email；
- 部门。

不建议第一版加入：

- 手机验证码；
- OAuth；
- 企业SSO；
- 邀请码体系；
- 复杂组织注册。

## 4.3 “我的会议”首页

页面顶部：

- 新建实时会议；
- 上传录音；
- 搜索；
- 状态过滤；
- 时间过滤；
- 模板过滤。

任务卡片或列表显示：

- 会议标题；
- 创建时间；
- 时长；
- 来源：实时录音 / 上传；
- 状态；
- 当前处理阶段；
- 模板；
- 转写段数；
- 知识草稿数；
- 错误提示；
- 快速操作。

快速操作：

- 查看；
- 继续录音；
- 重试；
- 删除。

列表只返回当前用户自己的任务。

## 4.4 新建会议页

建议采用三步轻量向导。

### 第一步：基本信息

- 会议标题；
- 参会人；
- 来源：
  - 实时录音；
  - 上传音频。

### 第二步：会议处理模板

选择：

- 通用会议；
- 项目评审；
- 需求访谈；
- 客户沟通；
- 事故复盘；
- 自定义模板。

### 第三步：快速调整

#### 转写设置

- 语言；
- 专业词汇 / Hotwords；
- 是否保留时间戳；
- 是否识别说话人；
- 标点和段落；
- 自定义转写说明。

#### 纪要设置

- 纪要结构；
- 是否生成行动项；
- 是否提取负责人；
- 是否提取截止日期；
- 自定义章节。

#### 知识萃取设置

- 决策；
- 行动项；
- 风险；
- 需求；
- 事实与数据；
- 待解决问题；
- 经验与教训；
- 概念和术语；
- 自定义关注要点。

默认关闭“自动发布”，只生成草稿。

## 4.5 录音工作台

顶部：

- 标题；
- 录音状态；
- 计时器；
- 暂停 / 继续；
- 停止；
- 网络和上传状态；
- 待处理分片数量。

主体三栏或Tabs：

### 实时转写

- 时间戳；
- 文本；
- 处理状态；
- 失败分片重试；
- 自动滚动；
- 当前说话区域。

### 纪要预览

- 明确标注“实时预览”；
- 更新时间；
- 不作为最终纪要；
- 可展开查看历史预览版本。

### 知识预览

- 明确标注“草稿预览”；
- 类型；
- 标题；
- 证据时间；
- 不直接进入正式知识库。

## 4.6 任务详情页

页面顶部固定展示：

- 标题；
- 状态；
- 当前阶段；
- 创建时间；
- 时长；
- 模板；
- 重试；
- 下载；
- 删除。

第一屏重点展示录音播放器。

Tabs：

1. **录音与转写**
2. **会议纪要**
3. **知识草稿**
4. **处理过程**
5. **配置快照**
6. **历史与审计**

## 4.7 录音与转写Tab

### 播放器

- 播放 / 暂停；
- 进度条；
- 当前时间 / 总时长；
- 0.75× / 1× / 1.25× / 1.5× / 2×；
- 前进 / 后退 10 秒；
- 下载录音；
- 音量；
- Loading 和 Range 状态。

### 转写联动

- 当前时间对应的Segment高亮；
- 点击Segment跳转到对应时间；
- Segment显示开始和结束时间；
- 可编辑文本；
- 可标记说话人；
- 编辑自动保存；
- 保留原始ASR文本和编辑版本；
- 可重新生成最终纪要和知识草稿。

## 4.8 会议纪要Tab

- Preview和Final明显区分；
- Markdown渲染；
- 编辑模式；
- 自动保存；
- 版本历史；
- 根据最新转写重新生成；
- 下载Markdown；
- 下载PDF不作为第一版强制要求。

## 4.9 知识草稿Tab

每条知识显示：

- 类型；
- 标题；
- 正文；
- Tags；
- 置信度；
- 证据转写；
- 录音时间范围；
- 来源会议；
- 状态。

操作：

- 编辑；
- 接受；
- 拒绝；
- 合并；
- 发布；
- 批量发布。

发布后：

- 创建或更新Knowledge Asset；
- 建立Chunk和Embedding Binding；
- 建立Source Lineage；
- 可从知识条目回到会议录音证据。

## 4.10 处理过程Tab

展示阶段：

```text
Audio Upload
ASR
Audio Finalize
Transcript Finalize
Minutes Generate
Knowledge Extract
Knowledge Publish
Memory Save
```

每个阶段显示：

- 当前状态；
- Job ID；
- Attempt；
- Skill版本；
- Model Profile；
- 开始和结束时间；
- 错误；
- Retry按钮；
- 输出Artifact。

## 4.11 我的模板页

分为：

- 内置模板；
- 我的模板；
- 已归档模板。

用户可以：

- 预览；
- 复制；
- 编辑自己的模板；
- 创建新版本；
- 归档。

内置模板不可直接修改，只能复制。

---

# 5. 用户与权限设计

## 5.1 身份模型

使用LakeMind正式身份服务。

用户注册后创建：

```text
Principal
  type = USER

PrincipalTenantMembership
  tenant = meeting-agent-demo
  role = meeting_user
  status = ACTIVE
```

## 5.2 注册服务身份

Meeting Agent后端使用一个受限Service Principal：

```text
meeting-agent-registration-service
```

它只允许：

- 在固定Tenant创建USER Principal；
- 创建固定`meeting_user` Membership；
- 不允许创建Platform Admin；
- 不允许创建其他Tenant；
- 不允许修改Role；
- 不允许查看用户会议内容；
- 不允许读取Secret。

## 5.3 应用权限

建议定义：

```text
meeting:task:create
meeting:task:read_own
meeting:task:update_own
meeting:task:delete_own
meeting:task:record
meeting:task:reprocess_own
meeting:template:manage_own
meeting:knowledge:review_own
meeting:knowledge:publish_own
meeting:audio:play_own
```

## 5.4 Owner隔离规则

每个MeetingTask：

```text
tenant_id
owner_principal_id
```

服务端查询规则：

```text
WHERE tenant_id = SecurityContext.tenant_id
  AND owner_principal_id = SecurityContext.principal_id
```

Platform Admin也不应自动通过普通Meeting Agent API查看内容。

管理员内容访问应使用显式能力，例如：

```text
meeting:task:read_all
```

并产生Audit。

## 5.5 Session安全

- HttpOnly Cookie；
- Secure；
- SameSite；
- CSRF保护写操作；
- 登录限流；
- 注册限流；
- Logout失效；
- Token撤销后Session失效；
- Tenant Membership撤销后失效。

---

# 6. 任务与模板数据模型

## 6.1 关键设计决定：不再用Iceberg全表扫描管理任务

Iceberg适合分析型数据和历史沉淀，不适合：

- 多用户任务列表；
- 高频状态更新；
- 乐观锁；
- 并发；
- 唯一约束；
- 精确分页；
- 事务状态机。

建议Meeting Agent使用独立应用Schema：

```text
PostgreSQL schema: meeting_agent
```

Meeting Agent只能访问该Schema，不允许直接访问LakeMind Control Plane业务表。

## 6.2 meeting_tasks

```sql
meeting_tasks (
  task_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  owner_principal_id UUID NOT NULL,

  title VARCHAR NOT NULL,
  participants JSONB NOT NULL DEFAULT '[]',
  source_type VARCHAR NOT NULL,      -- LIVE | UPLOAD

  status VARCHAR NOT NULL,
  current_stage VARCHAR,
  progress_percent INT DEFAULT 0,

  template_id UUID,
  template_version INT,
  template_snapshot JSONB NOT NULL,

  language VARCHAR,
  started_at TIMESTAMP,
  stopped_at TIMESTAMP,
  duration_ms BIGINT,

  recording_artifact_id UUID,
  transcript_artifact_id UUID,
  minutes_artifact_id UUID,
  knowledge_asset_id UUID,
  memory_asset_id UUID,

  error_code VARCHAR,
  error_message TEXT,

  version INT NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,

  UNIQUE(tenant_id, task_id)
)
```

## 6.3 meeting_audio_chunks

```sql
meeting_audio_chunks (
  chunk_id UUID PRIMARY KEY,
  task_id UUID NOT NULL,
  sequence_no INT NOT NULL,
  started_ms BIGINT,
  duration_ms BIGINT,
  mime_type VARCHAR,
  size_bytes BIGINT,
  checksum VARCHAR NOT NULL,
  object_uri TEXT NOT NULL,
  upload_status VARCHAR,
  asr_stage_run_id UUID,
  created_at TIMESTAMP,

  UNIQUE(task_id, sequence_no)
)
```

## 6.4 meeting_stage_runs

```sql
meeting_stage_runs (
  stage_run_id UUID PRIMARY KEY,
  task_id UUID NOT NULL,
  stage VARCHAR NOT NULL,
  run_no INT NOT NULL,
  status VARCHAR NOT NULL,

  job_id UUID,
  job_attempt_id UUID,
  skill_id UUID,
  skill_version VARCHAR,
  model_profile VARCHAR,
  resolved_deployment_id UUID,
  config_revision_id UUID,

  input_refs JSONB,
  output_refs JSONB,
  error_code VARCHAR,
  error_message TEXT,

  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  created_at TIMESTAMP,

  UNIQUE(task_id, stage, run_no)
)
```

## 6.5 meeting_transcript_segments

```sql
meeting_transcript_segments (
  segment_id UUID PRIMARY KEY,
  task_id UUID NOT NULL,
  chunk_sequence INT,
  start_ms BIGINT,
  end_ms BIGINT,
  speaker_label VARCHAR,

  original_text TEXT NOT NULL,
  edited_text TEXT,
  confidence DOUBLE PRECISION,

  revision INT DEFAULT 1,
  updated_by UUID,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

## 6.6 meeting_minutes_versions

```sql
meeting_minutes_versions (
  minutes_version_id UUID PRIMARY KEY,
  task_id UUID NOT NULL,
  version INT NOT NULL,
  content_markdown TEXT NOT NULL,
  source_transcript_revision INT,
  generated_by_job_id UUID,
  status VARCHAR,              -- PREVIEW | DRAFT | FINAL
  edited_by UUID,
  created_at TIMESTAMP,

  UNIQUE(task_id, version)
)
```

## 6.7 meeting_knowledge_items

```sql
meeting_knowledge_items (
  item_id UUID PRIMARY KEY,
  task_id UUID NOT NULL,
  item_type VARCHAR NOT NULL,
  title VARCHAR NOT NULL,
  body TEXT NOT NULL,
  tags JSONB,

  evidence_segment_ids JSONB,
  evidence_start_ms BIGINT,
  evidence_end_ms BIGINT,
  confidence DOUBLE PRECISION,

  review_status VARCHAR,       -- DRAFT | ACCEPTED | REJECTED | PUBLISHED
  published_asset_version_id UUID,
  reviewed_by UUID,
  reviewed_at TIMESTAMP,

  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

## 6.8 meeting_templates

```sql
meeting_templates (
  template_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  owner_principal_id UUID,     -- NULL表示内置模板
  name VARCHAR NOT NULL,
  description TEXT,
  status VARCHAR,              -- ACTIVE | ARCHIVED
  current_version INT,
  is_builtin BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

## 6.9 meeting_template_versions

```sql
meeting_template_versions (
  template_version_id UUID PRIMARY KEY,
  template_id UUID NOT NULL,
  version INT NOT NULL,
  config_json JSONB NOT NULL,
  created_by UUID,
  created_at TIMESTAMP,

  UNIQUE(template_id, version)
)
```

Published模板版本不可变。任务创建后保存`template_snapshot`，后续模板修改不影响已有任务。

---

# 7. 会议处理模板设计

## 7.1 模板结构

```yaml
name: 项目评审会议

transcription:
  language: zh
  timestamps: segment
  punctuation: true
  speaker_diarization: false
  hotwords:
    - LakeMind
    - Ray
    - LanceDB
  custom_instructions: 保留技术名词、版本号和数字

minutes:
  preset: project_review
  sections:
    - 会议摘要
    - 评审结论
    - 关键决策
    - 行动项
    - 风险与问题
    - 待确认事项
  extract_owner: true
  extract_due_date: true
  custom_instructions: 行动项必须包含负责人

knowledge:
  enabled_types:
    - decision
    - action_item
    - risk
    - requirement
    - lesson
  focus_points:
    - 技术选型
    - 关键约束
    - 责任人和截止日期
  require_evidence: true
  min_confidence: 0.60
  auto_publish: false
```

## 7.2 内置模板

建议v0.2.0提供5个：

### 通用会议

- 摘要；
- 决策；
- 行动项；
- 讨论要点；
- 待解决问题。

### 项目评审

- 目标；
- 当前进展；
- 评审结论；
- 问题；
- 风险；
- 行动项。

### 需求访谈

- 业务背景；
- 用户角色；
- 现状问题；
- 需求；
- 规则；
- 约束；
- 未确认问题。

### 客户沟通

- 客户背景；
- 核心诉求；
- 反馈；
- 承诺事项；
- 商机；
- 后续动作。

### 事故复盘

- 事故摘要；
- 时间线；
- 影响；
- 已知原因；
- 处置；
- 改进项；
- 待验证假设。

## 7.3 模板安全

用户可配置结构化字段，但不建议默认允许任意System Prompt。

处理原则：

- 字段Schema校验；
- 字符长度限制；
- 自定义说明作为用户要求拼接；
- 不允许覆盖平台安全System Prompt；
- 不允许请求输出Secret；
- 输出必须符合JSON Schema或Markdown结构；
- 模型输出进行Schema校验；
- 失败时重试或进入人工处理。

---

# 8. 录音、存储与回放设计

## 8.1 浏览器录音

建议使用一个持续的MediaRecorder：

```javascript
mediaRecorder.start(10000)
```

不要每10秒停止并重新创建Recorder。

每次`dataavailable`：

- 生成sequence；
- 记录本地时间；
- 计算或携带checksum；
- 上传分片；
- 保留有限待上传队列；
- 显示网络状态。

## 8.2 分片上传

接口：

```text
PUT /api/tasks/{task_id}/audio/chunks/{sequence}
```

请求包含：

- binary body；
- `Content-Type`；
- `X-Chunk-Checksum`；
- `X-Chunk-Started-Ms`；
- `X-Chunk-Duration-Ms`；
- Idempotency Key。

服务端：

1. 验证任务Owner；
2. 验证任务状态为RECORDING；
3. 验证sequence；
4. 验证大小和mime；
5. 保存到S3；
6. 创建Chunk记录；
7. 创建ASR Job；
8. 重复上传返回已有结果。

## 8.3 对象路径

路径必须由服务端生成：

```text
s3://lakemind-filesets/
  meeting-agent-demo/
    users/{principal_id}/
      meetings/{task_id}/
        audio/chunks/000001.webm
        audio/chunks/000002.webm
        audio/manifest.json
        audio/final/recording.m4a
        transcript/preview.json
        transcript/final.json
        minutes/preview-0001.md
        minutes/final.md
        knowledge/draft.json
        exports/
```

客户端不得提交任意S3 URI。

## 8.4 Recording Artifact

会议停止后创建正式Recording Artifact：

```text
type: meeting_recording
mime_type: audio/mp4 或 audio/webm
owner: principal_id
source: meeting task
retention: user policy
```

Artifact Metadata：

- task_id；
- duration_ms；
- chunk_count；
- checksum；
- codec；
- sample_rate；
- original_mime；
- created_by；
- source chunk manifest。

## 8.5 Audio Finalize Job

新增Skill Job：

```text
audio_finalize
```

职责：

- 下载所有分片；
- 校验sequence和checksum；
- 合并；
- 转为可Seek格式；
- 生成最终录音；
- 计算时长；
- 生成Artifact；
- 写结果JSON。

ffmpeg或PyAV应包含在Job Runtime内，不再依赖Meeting Agent宿主机安装ffmpeg。

## 8.6 回放接口

```text
GET /api/tasks/{task_id}/audio
```

建议实现方式：

- 服务端验证Owner；
- 返回短期签名URL；或
- 代理支持HTTP Range。

必须支持：

- Range；
- Content-Length；
- Content-Type；
- Accept-Ranges；
- 过期URL；
- 不允许猜测S3路径访问他人录音。

## 8.7 转写和回放同步

ASR Segment至少包含：

```json
{
  "start_ms": 10000,
  "end_ms": 17300,
  "speaker": "S1",
  "text": "本次项目评审主要讨论三个问题。",
  "confidence": 0.91
}
```

前端：

- 根据`audio.currentTime`高亮Segment；
- 点击Segment设置`audio.currentTime`；
- 编辑文本不改变时间范围；
- 知识证据可跳转到该时间范围。

---

# 9. 处理流水线

## 9.1 Skill设计

建议将当前`meeting-processing`升级为正式Published Skill：

```text
lake://skills/meeting-processing@0.2.0
```

包含Jobs：

1. `asr_chunk`
2. `audio_finalize`
3. `transcript_finalize`
4. `minutes_preview`
5. `minutes_generate`
6. `knowledge_extract`
7. `knowledge_publish`可由AssetService完成，不一定是Job

## 9.2 Model Profiles

Skill只声明Profile，不绑定具体模型：

```text
meeting-asr
meeting-minutes
meeting-knowledge-extract
meeting-embedding
```

JobService解析：

- Profile；
- Route；
- Deployment；
- Secret；
- Config Revision。

Job Attempt固定实际解析结果，保证可复现。

## 9.3 实时阶段

### ASR

每个分片：

```text
Chunk
→ ASR Job
→ Transcript Segment
→ task-scoped SSE
```

要求：

- 最大并发限制；
- 超时；
- 重试；
- 分片幂等；
- 结果按sequence排序；
- 晚到结果可补入；
- 单分片失败不终止整场会议。

### Minutes Preview

每若干成功Segment生成预览：

```text
最新转写Revision
→ minutes_preview Job
→ Preview Minutes
```

不触发正式知识发布。

## 9.4 最终阶段

停止后：

```text
Wait All Chunks
→ Audio Finalize
→ Transcript Finalize
→ Final Minutes
→ Knowledge Extract Draft
→ Memory Draft / Save
→ REVIEW_REQUIRED
```

## 9.5 Transcript Finalize

职责：

- 合并按sequence排列的Segment；
- 检查缺失分片；
- 修正重复边界文本；
- 标准化标点；
- 可选说话人整理；
- 生成最终Segment列表；
- 创建Transcript Artifact；
- 建立Recording → Transcript Lineage。

## 9.6 Final Minutes

输入：

- 最终Transcript Artifact；
- 模板快照；
- 标题和参会人。

输出：

- `minutes.md`；
- 结构化JSON；
- Minutes Artifact；
- Transcript → Minutes Lineage。

## 9.7 Knowledge Extract

输入：

- 最终Transcript；
- Final Minutes；
- 模板中的Extraction Policy。

输出必须是结构化JSON：

```json
{
  "items": [
    {
      "type": "decision",
      "title": "采用PostgreSQL作为Catalog",
      "body": "项目决定不再使用Gravitino...",
      "tags": ["architecture", "catalog"],
      "evidence": {
        "segment_ids": ["..."],
        "start_ms": 312000,
        "end_ms": 339000,
        "quote": "..."
      },
      "confidence": 0.88
    }
  ]
}
```

## 9.8 Knowledge Publish

用户接受条目后：

1. 创建或更新Meeting Knowledge Asset；
2. 保存源内容；
3. 切Chunk；
4. 生成Embedding；
5. 建立Binding；
6. 建立Lineage；
7. 状态从DRAFT进入PUBLISHED；
8. 可进行检索自检。

若Embedding失败：

```text
Knowledge = DEGRADED
```

不得显示READY。

## 9.9 Memory

建议只保存经过用户确认的会议记忆摘要：

- 会议标题；
- 时间；
-关键结论；
-用户接受的行动项；
-Meeting Task ID；
-来源Artifact。

Memory Scope：

```text
PERSONAL
owner_principal_id = 当前用户
```

---

# 10. 状态机

## 10.1 Meeting Task状态

```text
DRAFT
  → READY
  → RECORDING
  → FINALIZING
  → REVIEW_REQUIRED
  → COMPLETED
```

异常分支：

```text
READY / RECORDING / FINALIZING
  → FAILED

FAILED
  → RETRYING
  → FINALIZING / REVIEW_REQUIRED

DRAFT / READY / RECORDING
  → CANCELLED

任意非DELETED状态
  → DELETING
  → DELETED
```

## 10.2 Stage状态

```text
PENDING
→ QUEUED
→ RUNNING
→ SUCCEEDED
```

异常：

```text
QUEUED / RUNNING → FAILED
FAILED → RETRYING → QUEUED
PENDING → SKIPPED
```

## 10.3 Knowledge Item状态

```text
DRAFT
→ ACCEPTED
→ PUBLISHED
```

或：

```text
DRAFT → REJECTED
```

已PUBLISHED条目修改时创建新Asset Version，不直接覆盖历史版本。

## 10.4 Template状态

```text
DRAFT → ACTIVE → ARCHIVED
```

内置模板从ACTIVE开始，只读。

---

# 11. API设计

## 11.1 Auth

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

## 11.2 Tasks

```text
GET    /api/tasks
POST   /api/tasks
GET    /api/tasks/{task_id}
PATCH  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
```

查询参数：

- status；
- source_type；
- template_id；
- created_from；
- created_to；
- q；
- page；
- page_size。

所有查询自动按Owner过滤。

## 11.3 Recording

```text
POST /api/tasks/{task_id}/start
PUT  /api/tasks/{task_id}/audio/chunks/{sequence}
POST /api/tasks/{task_id}/pause
POST /api/tasks/{task_id}/resume
POST /api/tasks/{task_id}/stop
POST /api/tasks/{task_id}/audio/upload
GET  /api/tasks/{task_id}/audio
GET  /api/tasks/{task_id}/audio/manifest
```

## 11.4 Task Events

```text
GET /api/tasks/{task_id}/events
```

SSE只推送该任务：

- task.status_changed；
- chunk.uploaded；
- stage.status_changed；
- transcript.segment_ready；
- minutes.preview_ready；
- knowledge.draft_ready；
- operation.status_changed；
- error。

## 11.5 Transcript

```text
GET   /api/tasks/{task_id}/transcript
PATCH /api/tasks/{task_id}/transcript/segments/{segment_id}
POST  /api/tasks/{task_id}/transcript/finalize
```

## 11.6 Minutes

```text
GET   /api/tasks/{task_id}/minutes
PATCH /api/tasks/{task_id}/minutes
POST  /api/tasks/{task_id}/minutes/regenerate
GET   /api/tasks/{task_id}/minutes/versions
```

## 11.7 Knowledge

```text
GET   /api/tasks/{task_id}/knowledge
PATCH /api/tasks/{task_id}/knowledge/{item_id}
POST  /api/tasks/{task_id}/knowledge/{item_id}/accept
POST  /api/tasks/{task_id}/knowledge/{item_id}/reject
POST  /api/tasks/{task_id}/knowledge/publish
POST  /api/tasks/{task_id}/knowledge/reextract
```

## 11.8 Retry

```text
POST /api/tasks/{task_id}/stages/{stage}/retry
```

允许重试：

- ASR chunk；
- audio_finalize；
- transcript_finalize；
- minutes_generate；
- knowledge_extract；
- knowledge_publish。

## 11.9 Templates

```text
GET    /api/templates
POST   /api/templates
GET    /api/templates/{template_id}
POST   /api/templates/{template_id}/versions
POST   /api/templates/{template_id}/clone
POST   /api/templates/{template_id}/archive
```

---

# 12. v0.2.0 LakeMind能力映射

| Meeting Agent能力 | LakeMind能力 |
|---|---|
| 注册与登录 | Security Service / Principal / Token |
| 用户加入Demo Tenant | Tenant Membership |
| 只能看自己的任务 | SecurityContext + Owner Policy |
| 音频分片 | S3 Object |
| 最终录音 | Artifact |
| ASR / 纪要 / 萃取 | Published Skill + JobService + Ray |
| 模型调用 | Model Profile / Route / Deployment |
| Secret | Secret Ref最小注入 |
| 转写和纪要 | Artifact |
| 知识草稿和发布 | Knowledge Asset / Version |
| Embedding | Embedding Space + Binding |
| 会议记忆 | Memory Asset |
| 来源证据 | Lineage |
| 重试 | Job Attempt |
| 删除 | Operation + Reconciler |
| 状态实时更新 | Event / SSE |
| 管理与监控 | Control Center |
| 操作记录 | Audit |
| 异常发现 | Steward / Control Center Finding |

---

# 13. 与当前代码的关键改造映射

## 13.1 `agent.py`

当前：

- 单文件；
- 全局固定Tenant；
- `_active`内存状态；
- 全局SSEBroker；
- 直接编排全部流水线；
- 无用户身份。

改造：

```text
app/main.py
app/api/
app/services/
app/repositories/
app/models/
app/security/
app/orchestration/
```

`agent.py`不再承担全部职责。

## 13.2 `TaskManager`

当前：

- 启动时自动创建Tenant；
- Iceberg append-only；
- 全表scan；
- 无Owner。

改造：

- Tenant由部署时预置；
- 用户注册只创建Principal和Membership；
- 任务状态进入PostgreSQL `meeting_agent` Schema；
- Owner是必填字段；
- 使用索引和分页；
- 使用乐观锁。

## 13.3 `SSEBroker`

当前：

- 所有客户端订阅同一个Broker；
- 所有会议事件广播给所有浏览器。

改造：

- Task-scoped SSE；
- 连接时验证Owner；
- 事件包含task_id和sequence；
- 不允许跨用户广播；
- 断线可重新读取任务状态；
- SSE只作体验通道，数据库是事实源。

## 13.4 `LakeMindClient`

当前：

- 旧式Server API Key；
- `X-Tenant-Id`；
- 旧Compute Job API；
- 直接ModelServing Embedding；
- 自动创建Tenant；
- 使用共享Asset Token。

改造：

- 用户委托Token；
- Server SecurityContext；
- 正式v0.2 JobService；
- Published Skill版本；
- Model Profile；
- Artifact API；
- Knowledge和Memory正式API；
- 不直接指定Tenant Header；
- 不直接调用ModelServing；
- 不自动创建Tenant；
- Background Service Identity最小授权。

## 13.5 `summarize`与`extract`

当前：

- Prompt写死；
- 输出类型固定；
- Extract直接写入共享Knowledge；
- 无证据；
- 无Review。

改造：

- 接收Template Snapshot；
- 输出Schema校验；
- 提取证据Segment；
- 生成Draft；
- 用户Review后Publish；
- 保留Skill、Model、Job和Config版本。

## 13.6 前端

当前：

- Vanilla JS单页；
- 无Auth；
- 四个View；
- 无播放器；
- 无模板；
- 无用户隔离。

建议：

- React + TypeScript + Vite；
- 或保持轻量框架，但必须拆分模块；
- 复用LakeMind Design Token，不直接依赖Control Center内部组件；
- 支持Auth、Task Detail、播放器、模板和审核。

---

# 14. 一致性、幂等与恢复

## 14.1 不再以内存状态为事实源

允许内存保存：

- SSE连接；
- 短期上传缓存；
- UI加速缓存。

禁止内存保存为唯一事实源：

- 活动会议；
- chunk sequence；
- Stage状态；
- Job ID；
- 最终Artifact；
- 用户权限。

## 14.2 幂等键

### 创建任务

```text
Idempotency-Key = client-generated UUID
```

### 上传分片

```text
UNIQUE(task_id, sequence_no)
checksum必须一致
```

同sequence同checksum：

- 返回已上传结果。

同sequence不同checksum：

- 返回409。

### Stage运行

```text
UNIQUE(task_id, stage, input_revision, active_run)
```

## 14.3 服务重启恢复

Meeting Agent启动时执行Reconcile：

- 查找RECORDING但长时间无chunk的任务；
- 查找QUEUED/RUNNING Stage；
- 向JobService查询实际状态；
- 补齐已完成Job结果；
- 标记LOST或FAILED；
- 恢复FINALIZING；
- 不重复创建已存在Artifact；
- 不重复发布Knowledge。

## 14.4 浏览器断线

浏览器重新打开任务：

- 查询任务状态；
- 查询已上传chunk；
- 查询转写Segment；
- 连接task SSE；
- 可继续录音或停止；
- 不依赖旧浏览器内存。

## 14.5 Job失败

- 页面显示失败Stage；
- 显示错误；
- 不影响原始录音；
- 用户可重试；
- 重试创建新Attempt；
- 不覆盖旧Attempt；
- Control Center可观察。

## 14.6 ModelServing不可用

- Job进入FAILED；
- Task进入FAILED或PARTIAL；
- 页面显示模型服务错误；
- 允许恢复后重试；
- 不伪造空转写或空知识为成功。

---

# 15. 删除、保留与隐私

## 15.1 完整删除

用户删除任务：

```text
Task → DELETING
→ 删除/失效录音Artifact
→ 删除转写和纪要Artifact
→ 删除Knowledge Asset或来源版本
→ 删除Memory
→ 删除S3对象
→ 删除Chunk和应用记录
→ DELETED
```

如果部分失败：

```text
保持DELETING
→ Reconciler重试
```

## 15.2 默认保留策略

Demo建议：

- 原始音频：30天；
- 最终录音：30天；
- 未发布知识草稿：30天；
- 已发布Knowledge：用户主动删除前保留；
- Audit：按平台策略。

允许用户手工删除。

## 15.3 隐私提示

开始录音前显示：

- 请确认已获得参会者许可；
- 录音将上传并由AI处理；
- 结果可能存在错误；
- 用户应审核后再发布知识。

---

# 16. Control Center集成

管理员应能在Control Center观察：

## 16.1 Jobs

- meeting-processing Skill；
- Stage；
- 用户/Owner；
- Task ID；
- Attempt；
- 模型；
-资源；
-状态；
-日志；
-Artifact。

## 16.2 Assets

- Recording Artifact；
- Transcript Artifact；
- Minutes Artifact；
- Knowledge Asset；
- Memory；
- Binding；
- Lineage；
- DEGRADED状态。

## 16.3 Models

- meeting-asr Profile；
- meeting-minutes Profile；
- meeting-knowledge-extract Profile；
- meeting-embedding Profile；
-实际Deployment；
-错误率；
-延迟。

## 16.4 Audit

至少记录：

- Register；
- Login；
- Task Create；
- Recording Start；
- Recording Stop；
- Template Change；
- Stage Retry；
- Transcript Edit；
- Minutes Edit；
- Knowledge Accept / Reject / Publish；
- Task Delete。

## 16.5 Correlation

建议：

```text
correlation_id = meeting task_id
```

所有：

- API；
- Job；
- Artifact；
- Asset；
- Event；
- Audit；

均能通过Task ID或Correlation ID关联。

---

# 17. Skill包建议结构

```text
examples/meeting-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── tasks.py
│   │   │   ├── recording.py
│   │   │   ├── transcript.py
│   │   │   ├── minutes.py
│   │   │   ├── knowledge.py
│   │   │   └── templates.py
│   │   ├── services/
│   │   │   ├── registration_service.py
│   │   │   ├── task_service.py
│   │   │   ├── recording_service.py
│   │   │   ├── pipeline_service.py
│   │   │   ├── template_service.py
│   │   │   └── lake_client.py
│   │   ├── orchestration/
│   │   │   ├── reconciler.py
│   │   │   └── event_dispatcher.py
│   │   ├── repositories/
│   │   ├── models/
│   │   └── security/
│   └── migrations/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── api/
│   │   └── state/
│   └── vite.config.ts
│
├── skills/
│   └── meeting-processing/
│       ├── SKILL.md
│       ├── manifest.yaml
│       └── jobs/
│           ├── asr_chunk/
│           ├── audio_finalize/
│           ├── transcript_finalize/
│           ├── minutes_preview/
│           ├── minutes_generate/
│           └── knowledge_extract/
│
├── scripts/
│   ├── setup.py
│   ├── seed_templates.py
│   └── verify.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── e2e/
│
├── docker-compose.yml
├── .env.example
├── README.md
├── DESIGN.md
└── GOLDEN_PATH.md
```

---

# 18. 开发工作包

## WP1：身份、用户和任务隔离

内容：

- 注册；
- 登录；
- Session；
-固定Demo Tenant；
- meeting_user Role；
- Owner字段；
- 只看自己的任务；
- Task-scoped SSE；
- 安全测试。

验收：

- 用户A看不到用户B任务；
- 修改URL无效；
- 搜索不泄露；
- SSE不泄露；
- S3路径不可猜测访问。

## WP2：任务、模板与新UI

内容：

- React/TypeScript前端；
- 我的会议；
- 新建任务；
-内置模板；
-自定义模板；
- Template Snapshot；
- 任务详情；
- Stage进度。

验收：

- 内置模板可选；
- 用户模板可复制和版本化；
- 已有任务不受模板后续修改影响。

## WP3：录音与回放

内容：

- 连续MediaRecorder；
- 分片幂等上传；
- Manifest；
- audio_finalize Job；
- Recording Artifact；
- Range或签名URL；
- 播放器；
- 转写同步；
- 上传已有音频。

验收：

- 完整录音可播放；
- 点击转写跳转时间；
- 用户B无法播放用户A录音；
- 服务重启后仍可播放。

## WP4：v0.2正式流水线

内容：

- Published Skill；
- JobService；
- Model Profile；
- Artifact；
- Transcript Finalize；
- Final Minutes；
- Knowledge Draft；
- Memory；
- Lineage；
- Retry。

验收：

- 无旧式`X-Tenant-Id`；
- 无内部万能Key代表用户；
- Job固定Skill和Model版本；
- Control Center可观察。

## WP5：知识审核和发布

内容：

- 证据；
- Draft；
- Edit；
- Accept / Reject；
- Publish；
- Knowledge Asset；
- Binding；
-检索；
-来源回放。

验收：

- 未审核条目不进入正式Knowledge；
- 发布知识可以检索；
- 能回到对应录音时间；
- Embedding失败时DEGRADED。

## WP6：恢复、删除和验收

内容：

- Reconcile；
-重启恢复；
- Retry；
-完整删除；
- Audit；
- Golden Path；
-安全、一致性、恢复测试。

---

# 19. 开发优先级

## P0：必须完成

- 注册与登录；
- 用户任务隔离；
- Task所有权；
- 新建任务；
- 会议处理模板；
- 实时录音；
- 分片ASR；
- 最终录音和回放；
- 最终转写；
- 最终纪要；
- 知识草稿；
-知识审核和发布；
-失败重试；
-服务重启恢复；
-完整删除；
-Control Center可观察。

## P1：建议完成

- 上传已有音频；
- 暂停和继续；
- 转写编辑；
-纪要编辑；
-下载录音、转写和纪要；
-任务搜索和过滤；
-模板复制和版本；
-播放速度；
-转写点击跳转；
-站内处理通知。

## P2：后续考虑

- 多人分享；
- 协同编辑；
- 说话人自动识别；
- 多语言自动检测；
- Calendar集成；
- Zoom / Teams导入；
- 手机端；
- 实时翻译；
-视频；
-复杂会议分析；
-组织级知识审核。

---

# 20. Golden Path验收

## 20.1 标准链路

1. 用户注册；
2. 用户登录；
3. 创建会议任务；
4. 选择模板；
5. 开始录音；
6. 上传多个分片；
7. ASR Job完成；
8. 实时转写显示；
9. 停止录音；
10. 生成Recording Artifact；
11. 回放录音；
12. 生成Final Transcript；
13. 生成Final Minutes；
14. 生成Knowledge Draft；
15. 用户编辑和接受知识；
16. 发布Knowledge；
17. 生成Embedding Binding；
18. 生成Memory；
19. 进行Knowledge检索；
20. 从Knowledge跳回会议证据；
21. 在Control Center查看Job、Asset和Audit；
22. 删除会议并验证完整清理。

## 20.2 安全验收

- 用户A无法查看用户B任务；
- 用户A无法播放用户B录音；
- 用户A无法读取用户B转写、纪要和知识；
- 用户A无法订阅用户B SSE；
- 伪造Owner无效；
- 伪造Tenant Header无效；
- 无Skill权限不能提交Job；
- Job只获得声明的Secret；
- 撤销Skill后不能运行；
- 浏览器无法访问Ray Dashboard；
- 浏览器无ModelServing Secret。

## 20.3 一致性验收

- 分片重复上传不重复处理；
- 同sequence不同checksum返回冲突；
- S3成功、ASR提交失败可重试；
- ASR成功、回写失败可恢复；
- Audio Finalize失败不丢原始分片；
- Embedding失败Knowledge为DEGRADED；
- Publish重试不重复创建知识；
- 删除失败保持DELETING；
- Task详情知识不依赖标题语义搜索。

## 20.4 恢复验收

- Meeting Agent重启后任务仍存在；
- 录音中断后可继续或停止；
- JobService重启后状态可恢复；
- Ray Job丢失后Stage标记LOST/FAILED；
- ModelServing恢复后可重试；
- Reconciler不重复Artifact；
- SSE断线后重新读取状态；
- Control Center可看到异常和恢复。

## 20.5 回放验收

- 完整录音时长正确；
- 可Seek；
- Range请求工作；
- 播放速度有效；
- Segment与音频时间基本一致；
- 点击Segment可跳转；
- 未授权用户访问返回403或404；
- 删除后签名URL失效。

---

# 21. 非功能要求

## 21.1 性能

建议Demo验收规模：

- 20个注册用户；
- 每用户100个历史任务；
- 5个并发录音用户；
- 单场会议60分钟；
- 10秒音频分片；
- ASR并发受Quota控制。

目标：

- 任务列表P95 < 500ms；
- 任务详情P95 < 1s，不含大文件；
- 分片上传确认 < 1s；
- 转写显示延迟取决于ASR，但应明确展示；
- 音频首播 < 2s；
- Seek响应 < 1s；
- 页面无持续内存增长。

## 21.2 可用性

- Chrome / Edge优先；
- Firefox可用；
- 麦克风授权失败有明确提示；
- 网络中断有待上传状态；
- 页面刷新后任务可恢复；
- 所有Stage有进度和错误；
- 用户不需要理解Ray、S3或ModelServing才能使用。

## 21.3 可维护性

- 后端模块化；
- 前端组件化；
- 数据库Migration；
- OpenAPI；
- 类型生成；
- 单元测试；
- E2E测试；
- Setup和Verify脚本；
- 不将默认密码写在页面；
- 不将生产Secret写入`.env.example`。

---

# 22. 明确不做的过度设计

Meeting Agent v0.2.0暂不需要：

- 每用户一个Tenant；
- 独立微服务群；
- Kafka；
- 独立工作流引擎；
- Kubernetes Operator；
- 多区域；
- 复杂协同权限；
- 文档级CRDT；
- 完整数据湖建模；
- 全量Event Sourcing；
- 自建IAM；
- 自建向量数据库；
- 自建模型网关；
- 独立Observability平台。

建议架构保持：

```text
React Web
+ FastAPI Meeting App
+ PostgreSQL应用Schema
+ LakeMind v0.2 APIs
+ Published Meeting Skill
```

---

# 23. 最终建议

新版Meeting Agent最关键的不是增加更多“AI按钮”，而是建立一条可信闭环：

```text
用户身份可信
→ 任务只属于本人
→ 原始录音可保留和回放
→ 转写与纪要可审核
→ 知识有证据
→ 发布后成为正式资产
→ 全链路可重试和恢复
→ 管理员可在Control Center观察
```

当前版本中最应优先替换的四个设计是：

1. **用LakeMind正式身份和Owner隔离，替换固定Tenant、无认证和全局任务列表；**
2. **用PostgreSQL应用Schema和持久Stage，替换Iceberg全表扫描与进程内活动状态；**
3. **用Recording Artifact和Audio Finalize Job，补齐录音回放；**
4. **用Template Snapshot、Knowledge Draft和人工发布，替换写死Prompt和自动污染共享知识库。**

完成这些后，Meeting Agent才会成为真正有说服力的LakeMind v0.2.0 Example：

> 它不仅能“跑通AI流水线”，还能证明LakeMind可以支撑一个安全、多用户、可恢复、可治理、可追溯的Agent应用。
