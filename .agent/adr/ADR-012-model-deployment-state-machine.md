# ADR-012: Model Deployment State Machine and Convergence

> Status: ACCEPTED  
> Date: 2026-07-16

## Context

v0.2.0 `create_deployment` synchronously calls ModelServing register, causing:
- Coupling between Control Plane and Data Plane
- No drift detection when ModelServing state diverges from desired
- No retry/reconciliation mechanism
- Only Desired/Active binary state, no distinction between "model file available", "deployment ready", and "runtime serving"

## Decision

### 1. Deployment State Machine

```
DRAFT → DISABLED → ENABLING → ACTIVE → DISABLING → DISABLED
                                     ↓
                               FAILED / DRIFTED
```

- `create_deployment` → DRAFT (no ModelServing call)
- `enable_deployment` → Operation (low risk) → Outbox event → Reconciler
- `disable_deployment` → Operation (low risk) → Outbox event → Reconciler

### 2. Three-Dimension Health State

| Dimension | Meaning | Reporter | Trigger |
|-----------|---------|----------|---------|
| Test | Model file availability (exists, loadable, inference works) | ModelServing | Deployment create/update |
| Readiness | Deployment readiness (resources, deps, config) | ModelServing | Enable operation |
| Active | Runtime state (serving, latency, error rate) | ModelServing | Continuous heartbeat |

```
Test:       UNKNOWN → TESTING → PASSED / FAILED
Readiness:  UNKNOWN → CHECKING → READY / NOT_READY
Active:     UNKNOWN → STARTING → SERVING / DEGRADED / STOPPED

Composite derivation:
  Test=FAILED                          → Deployment=FAILED
  Test=PASSED + Readiness=NOT_READY    → Deployment=ENABLING
  Test=PASSED + Readiness=READY + Active=STARTING  → Deployment=ENABLING
  Test=PASSED + Readiness=READY + Active=SERVING   → Deployment=ACTIVE
  Test=PASSED + Readiness=READY + Active=DEGRADED  → Deployment=DRIFTED
  Test=PASSED + Readiness=READY + Active=STOPPED   → Deployment=DRIFTED
```

### 3. Config Revision State Machine (Immutable, Append-Only)

```
DRAFT → VALIDATED → APPLYING → ACTIVE
                         ↓
                   FAILED → ROLLED_BACK
```

- Revision content is immutable after creation (INSERT only, no UPDATE)
- `active_revision_id` is a pointer; activation only updates the pointer

### 4. Config Rollout State Machine (Independent)

```
Rollout:
  INITIATED → VALIDATING → APPLYING → ROLLED_OUT
                              ↓
                        ROLLED_BACK
  INITIATED → CANCELLED (only in VALIDATING)
```

### 5. Convergence Flow

```
Control Plane writes Desired Revision
  → Outbox event
  → Reconciler pulls Desired
  → Calls ModelServing Apply
  → ModelServing reports Active Revision
  → Control Plane compares Desired == Active → CONVERGED
  → Otherwise → DRIFTED → alert + Steward Finding
```

Convergence status:
- `CONVERGED`: desired == active
- `CONVERGING`: apply submitted, awaiting report
- `DRIFTED`: desired != active beyond threshold
- `FAILED`: apply returned error

### 6. Concurrency Control (Optimistic Lock)

```
config_scopes table:
  active_revision_id UUID
  rollout_version BIGINT NOT NULL DEFAULT 0

Activation:
  POST /revisions/{id}/activate
    → Read scope.rollout_version = V
    → CAS: UPDATE config_scopes SET active_revision_id={id}, rollout_version=V+1
           WHERE scope_id={scope_id} AND rollout_version=V
    → 0 rows → 409 Conflict
    → 1 row → Rollout INITIATED → Reconciler push → ROLLED_OUT
```

### 7. Rollback

- Rollback = activate old Revision (new Rollout, target = old Revision ID)
- Rollback is a Rollout, goes through Operation (medium risk, requires approval)
- After rollback, `active_revision_id` points to old Revision

## Consequences

- `model_management_service.py`: `create_deployment` no longer calls ModelServing
- New `reconciler.py`: pulls Desired, calls ModelServing, compares Active
- New `model_health.py` in ModelServing: three-dimension checks
- `config_revisions` content fields become immutable (application-layer guard)
- `config_scopes` gains `rollout_version` column for optimistic lock
- `GET /deployments/{id}` returns `{desired_state, active_state, test_state, readiness_state, convergence_status}`
- `GET /deployments/{id}/health` returns three-dimension health details
