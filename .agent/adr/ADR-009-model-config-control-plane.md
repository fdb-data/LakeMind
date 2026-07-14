# ADR-009: ModelServing 配置归 Control Plane

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 的 LakeMindModelServing 独立管理配置（litellm config.yaml + 环境变量），与 LakeMindServer 配置分离。导致模型配置变更无审计、无版本、无回滚。

## 决策

ModelServing 的配置归 Control Plane 的 ConfigurationService + ModelManagementService 管理。ModelServing 只负责运行，不自行管理配置。

## 理由

- 配置变更需要审计和回滚（生产环境基本要求）
- ConfigurationService 提供 Revision + Desired/Active 模型
- ModelManagementService 管理模型定义、Deployment、Profile
- ModelServing 作为 Execution Plane 组件，不应持有配置管理逻辑

## 影响

- 新增 `/api/v1/models/*` API 端点
- ModelServing 从 Control Plane 拉取配置，不本地管理
- 配置变更通过 ConfigurationService.set() → activate() 流程
- 详见 `docs/architecture/v0.2.0/application-services.md` §2.6

## 替代方案

1. **ModelServing 自管理**：v0.1.0 方式。未选择：无审计、无回滚
2. **外部配置中心**：未选择：v0.2.0 不引入额外组件

## 参考

设计方案 §9.2 / ADR-002
