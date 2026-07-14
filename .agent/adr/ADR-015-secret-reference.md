# ADR-015: Secret 引用 + 最小权限

> 状态：accepted  
> 日期：2026-07-13  
> 决策者：架构师

## 背景

v0.1.0 的 Secret 存储（`tenant_secrets` 表）支持全量获取（`get_secret_values`），且 Ray Job 提交时可能注入全部 Secret。存在过度暴露风险。

## 决策

Secret 采用引用模型 + 最小权限。API 返回 `SecretRef`（引用），不返回明文。Job 提交时仅获声明使用的 Secret 引用，ExecutionBackend 通过 `resolve(ref, identity)` 获取明文。

## 理由

- 最小权限原则：Job 只获声明的 Secret，不是全部
- 引用模型：API 不暴露明文，减少泄漏面
- `resolve()` 需授权调用，记录使用日志
- Secret 轮换不改变引用，只改变版本

## 影响

- SecretService 接口：create / get_ref / resolve / rotate / list / log_usage
- API `/api/v1/security/secrets` 返回 SecretRef，不返回明文
- Job 提交时声明 `secret_refs`，ExecutionBackend 按需 resolve
- 详见 `docs/architecture/v0.2.0/application-services.md` §2.9

## 替代方案

1. **环境变量全量注入**：v0.1.0 方式。未选择：过度暴露
2. **Vault 集成**：未选择：v0.2.0 不引入额外组件

## 参考

设计方案 §9.3 / `docs/architecture/v0.2.0/provider-contracts.md` §2.9
