# ADR-005: 资产范围

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 允许动态注册资产类型（`register_asset_type` / `unregister_asset_type`），但实际只有 4 种默认类型（Knowledge / Skills / Memory / Ontology），且动态注册功能未产生实际价值，增加了类型校验复杂度。

## 决策

v0.2.0 固定 3 种核心资产类型：Knowledge / Skill / Memory。Ontology 标记为 Experimental。移除动态资产类型注册。

## 理由

- 3 种核心资产覆盖当前全部用例
- 固定类型简化 API、UI 和文档
- 移除动态注册减少攻击面和维护成本
- Ontology 保留但标记 Experimental，不作为核心验收

## 影响

- `register_asset_type` / `unregister_asset_type` / `list_asset_types` 标记 Experimental
- API `/api/v1/metadata/asset-types` 移除
- 资产类型枚举固定在 `AssetType` schema

## 替代方案

1. **保留动态注册**：未选择：无实际需求，增加复杂度
2. **插件化资产类型**：未选择：v0.2.0 不需要

## 参考

设计方案 §3.1 / WP1-T07 AdminMCP 映射
