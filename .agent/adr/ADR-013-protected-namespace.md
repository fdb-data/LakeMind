# ADR-013: DataMCP Protected Namespace

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 的 DataMCP `s3_put` / `s3_delete` 可以操作任意 S3 路径，包括资产管理的 `ten_*/ast_*` 路径。可能导致 DataMCP 用户意外覆盖或删除资产文件，破坏资产一致性。

## 决策

DataMCP 的 S3 写操作（`s3_put` / `s3_delete`）实施 Protected Namespace 写保护：不得覆盖或删除 `ten_*/ast_*` 路径下的对象。

## 理由

- 资产文件由 AssetService 管理，通过 Binding 保证一致性
- DataMCP 是数据面工具，不应破坏资产面数据
- Protected Namespace 是轻量级校验，不增加架构复杂度
- ObjectStorageProvider 新增 `check_protected()` 方法

## 影响

- `s3_put` / `s3_delete` 增加路径前缀校验
- ObjectStorageProvider 新增 `check_protected(key)` 方法
- 详见 `docs/architecture/v0.2.0/provider-contracts.md` §2.1

## 替代方案

1. **完全禁止 DataMCP S3 写操作**：未选择：DataMCP 需要写临时数据
2. **独立 S3 bucket**：资产和数据分桶。未选择：增加配置复杂度

## 参考

设计方案 §6.2 / `docs/architecture/v0.2.0/mcp-service-mapping.md` §3.3
