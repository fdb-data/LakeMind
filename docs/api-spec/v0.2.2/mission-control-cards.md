# Mission Control 卡片定义

> Phase 1A Core WP-C-Core-T4  
> 日期：2026-07-16

每个卡片定义：事实源 / 计算公式 / 刷新频率 / 新鲜度 / 下钻目标 / 不可用时显示

---

## 屏 1：需要处理

### Card: Pending Approvals
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/operations?status=APPROVAL_REQUIRED` |
| 计算 | `count(items)` |
| 刷新 | 10s |
| 新鲜度 | `max(items[].updated_at)` |
| 下钻 | `/operations?status=APPROVAL_REQUIRED` |
| 不可用 | 显示 `--` + `数据不可用` tooltip |
| 权限 | `operation:approve` |

### Card: Failed Jobs (24h)
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/jobs?status=FAILED&from=now-24h` |
| 计算 | `count(items)` |
| 刷新 | 30s |
| 新鲜度 | `max(items[].updated_at)` |
| 下钻 | `/jobs?status=FAILED` |
| 不可用 | 显示 `--` |
| 权限 | `job:view` |

### Card: Degraded Assets
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/assets?health=DEGRADED` |
| 计算 | `count(items)` |
| 刷新 | 60s |
| 新鲜度 | `max(items[].updated_at)` |
| 下钻 | `/assets?health=DEGRADED` |
| 不可用 | 显示 `--` |
| 权限 | `asset:view` |

### Card: Unhealthy Deployments
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/models/deployments?health=UNHEALTHY` |
| 计算 | `count(items)` |
| 刷新 | 30s |
| 新鲜度 | `max(items[].updated_at)` |
| 下钻 | `/models?health=UNHEALTHY` |
| 不可用 | 显示 `--` |
| 权限 | `model:view` |

### Card: Config Drifts
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/configuration/drifts` |
| 计算 | `count(items)` |
| 刷新 | 60s |
| 新鲜度 | `max(items[].detected_at)` |
| 下钻 | `/configuration?drift=true` |
| 不可用 | 显示 `--` |
| 权限 | `config:view` |

### Card: Outbox Backlog
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/system/reconcile/drifts` |
| 计算 | `sum(outbox_unpublished_count)` |
| 刷新 | 30s |
| 新鲜度 | `now()` (系统实时) |
| 下钻 | `/system/reconcile` |
| 不可用 | 显示 `--` |
| 权限 | `platform:admin` |

---

## 屏 2：平台健康

### Card: Data Plane Health
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/observability/metrics?name=service.health&labels={"service":"server-api,postgres,seaweedfs,valkey"}` |
| 计算 | 关键组件全 `healthy` → `HEALTHY`；任一 `down` → `DOWN`；否则 `DEGRADED` |
| 刷新 | 30s |
| 新鲜度 | `max(observed_at)` |
| 下钻 | `/services?plane=data` |
| 不可用 | 显示 `UNKNOWN` + 红色 |
| 权限 | `obs:view` |

### Card: Runtime Plane Health
| 属性 | 值 |
|------|-----|
| 事实源 | 同上，`labels={"service":"asset-mcp,data-mcp,admin-mcp"}` |
| 计算 | 同上 |
| 刷新 | 30s |
| 下钻 | `/services?plane=runtime` |
| 权限 | `obs:view` |

### Card: Model Plane Health
| 属性 | 值 |
|------|-----|
| 事实源 | 同上，`labels={"service":"model-serving"}` |
| 计算 | 同上 |
| 刷新 | 30s |
| 下钻 | `/services?plane=model` |
| 权限 | `obs:view` |

### Card: Management Plane Health
| 属性 | 值 |
|------|-----|
| 事实源 | 同上，`labels={"service":"control-center"}` |
| 计算 | 同上 |
| 刷新 | 30s |
| 下钻 | `/services?plane=management` |
| 权限 | `obs:view` |

---

## 屏 3：资源与使用

### Card: CPU Usage
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/observability/metrics?name=cpu.usage&labels={"service":"server-api"}` |
| 计算 | `avg(value)` over last 5min |
| 刷新 | 30s |
| 新鲜度 | `max(observed_at)` |
| 下钻 | `/observability/metrics?name=cpu.usage` |
| 不可用 | 显示 `--` |
| 权限 | `obs:view` |
| 显示 | 百分比 + 趋势线 |

### Card: Memory Usage
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/observability/metrics?name=memory.usage` |
| 计算 | `avg(value)` over last 5min |
| 刷新 | 30s |
| 下钻 | `/observability/metrics?name=memory.usage` |
| 权限 | `obs:view` |

### Card: Storage Usage
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/observability/metrics?name=storage.usage` |
| 计算 | `latest(value)` |
| 刷新 | 60s |
| 下钻 | `/observability/metrics?name=storage.usage` |
| 权限 | `obs:view` |

### Card: Job Queue Depth
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/observability/metrics?name=job.queue_depth` |
| 计算 | `latest(value)` |
| 刷新 | 10s |
| 下钻 | `/jobs?status=PENDING` |
| 权限 | `job:view` |

---

## 屏 4：资产和认知运行

### Card: Knowledge Health
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/assets?type=knowledge&fields=health` |
| 计算 | `count(HEALTHY) / count(total)` |
| 刷新 | 60s |
| 下钻 | `/assets?type=knowledge` |
| 权限 | `asset:view` |

### Card: Skill Health
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/assets?type=skill&fields=health` |
| 计算 | `count(HEALTHY) / count(total)` |
| 刷新 | 60s |
| 下钻 | `/assets?type=skill` |
| 权限 | `asset:view` |

### Card: Memory Health
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/assets?type=memory&fields=health` |
| 计算 | `count(HEALTHY) / count(total)` |
| 刷新 | 60s |
| 下钻 | `/assets?type=memory` |
| 权限 | `asset:view` |

### Card: Recent Changes
| 属性 | 值 |
|------|-----|
| 事实源 | `GET /api/v1/audit?page_size=5` |
| 计算 | 直接展示 |
| 刷新 | 30s |
| 下钻 | `/audit` |
| 权限 | `audit:view` |

---

## 健康计算规则

```
Plane Health:
  关键组件全 healthy → HEALTHY (绿)
  任一关键组件 down → DOWN (红)
  部分组件 degraded → DEGRADED (黄)
  数据不可用 → UNKNOWN (灰)
```

## Partial Failure 处理

```
BFF View Model 聚合：
  必需数据失败 → 503 (整个 View Model 不可用)
  可选数据失败 → 200 + partial: true + _meta.partial_failure: ["card_name"]
  空数组 → 200 + count: 0 (不伪装错误)
```
