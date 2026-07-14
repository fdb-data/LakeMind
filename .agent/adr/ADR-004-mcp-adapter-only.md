# ADR-004: MCP 协议适配层

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 的 MCP（尤其 AssetMCP）在 tool 内自编排底层操作：直接操作 S3、Lance、PG，甚至调用 LLM 做事实抽取。导致 MCP 与 REST API 逻辑重复，维护成本高，且 MCP 绕过了 REST API 的认证和审计。

## 决策

MCP 降为协议适配层，全部 68 个 tool 映射到 Application Service，与 REST API 共享同一组 Service。MCP 不直连任何底层引擎。

## 理由

- 消除逻辑重复：一处实现，两个入口（REST + MCP）
- 统一认证和审计：所有请求经过 Control Plane
- MCP 价值在于协议适配（Agent 友好的 tool/resource/prompt），不在于业务逻辑
- 共享基础包减少重复代码

## 影响

- 提取 `lakemind_mcp_common/` 共享包（auth / client / errors / pagination / operation）
- DataMCP 的 5 个 Ray 工具改为调用 JobService
- AdminMCP 写操作全部通过 OperationService
- 详见 `docs/architecture/v0.2.0/mcp-service-mapping.md`

## 替代方案

1. **MCP 独立实现**：保持现状。未选择：逻辑重复、安全风险
2. **MCP 调 REST API**：MCP 作为 HTTP Client 调 REST。部分采用：DataMCP 保留透传，但 AssetMCP/AdminMCP 直接调 Service

## 参考

设计方案 §4.5 / `docs/architecture/v0.2.0/mcp-service-mapping.md`
