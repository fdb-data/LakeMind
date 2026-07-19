# ADR-011: Control Center Security Model

> Status: ACCEPTED  
> Date: 2026-07-16  
> Supersedes: implicit BFF-token-pass-through pattern in `bff/app.py`

## Context

Control Center v0.2.0 has four security defects:

1. BFF injects `X-Tenant-Id` header as trusted identity source — tenant spoofing
2. BFF falls back to `BFF_TOKEN` when user token expires — privilege confusion
3. Session stored in process-memory dict (`_sessions`) — no persistence, no TTL enforcement, lost on restart
4. No CSRF protection on unsafe methods
5. Token permissions cannot be revoked instantly (must wait for natural expiry)
6. No multi-tenant membership model — Principal.tenant_id is a single scalar

## Decision

### 1. Authentication Flow

```
User login → Server issues Token (opaque, hash-stored in v2_tokens)
  Token payload: {token_id, principal_id, tenant_id, scopes, security_version, expires_at}
  → BFF stores in Valkey Session (key=cc:session:{sid}, TTL=3600)
  → BFF sets HttpOnly + Secure + SameSite=Lax cookie

User request → BFF extracts session_id from cookie → Valkey lookup → user token
  → BFF calls Server with Authorization: Bearer <user_token>
  → Server parses SecurityContext from token
  → Server validates security_version == principal.current_security_version
  → All queries append WHERE tenant_id = ctx.tenant_id
```

### 2. Tenant Isolation

- Tenant ID comes **only** from Server-side SecurityContext (parsed from token)
- BFF **must not** inject `X-Tenant-Id` as a trusted header
- Platform Admin cross-tenant access via `target_tenant_id` query param + `tenant:cross` scope check
- Frontend **must not** do tenant filtering

### 3. Token Fallback

- User token expiry → Server returns 401 → BFF returns 401 → frontend redirects to Login
- `BFF_TOKEN` is **only** for BFF's own health checks and service registration
- **Never** use `BFF_TOKEN` as a fallback for user requests

### 4. Session (Valkey)

- Session ID: `secrets.token_urlsafe(32)` (256-bit entropy)
- Stored in Valkey: `cc:session:{sid}` with TTL=3600
- Session data: `{token, principal_id, tenant_id, roles, csrf_token, security_version, jti, created_at, last_access}`
- Sliding expiry: `last_access` updated on each request; idle timeout enforced
- Absolute expiry: `created_at + max_lifetime` cannot be exceeded
- Logout: delete Valkey key + increment `principal.security_version`
- Session Rotation on login (prevents Session Fixation)

### 5. CSRF Protection

- `csrf_token = secrets.token_urlsafe(32)` stored in Valkey Session
- All unsafe methods (POST/PUT/PATCH/DELETE) must have `X-CSRF-Token` header matching session
- `Origin` header also validated
- **Refresh recovery**: `GET /auth/csrf` returns current session's CSRF token via response header
- Frontend stores CSRF in memory (not localStorage), recovers on page refresh via `/auth/csrf`

### 6. Security Version (Instant Permission Revocation)

```
Token embeds security_version (snapshot of principal.security_version at issue time)
  → Each request: Server checks token.security_version == principal.security_version
  → Mismatch → 401 (force re-login)

Triggers for security_version++:
  - Role Binding change
  - Membership Revoke
  - Tenant Suspend (all Principals under that Tenant)
  - Explicit Token Revoke → Valkey revocation list (TTL = remaining token lifetime)
```

### 7. Principal–Tenant Membership

```
principal_tenant_memberships (new table)
  id UUID PK
  principal_id UUID FK → principals
  tenant_id UUID FK → tenants
  role_binding_id UUID FK → role_bindings
  membership_status VARCHAR(32)  -- ACTIVE / INVITED / REVOKED
  invited_by UUID FK → principals
  invited_at TIMESTAMP
  joined_at TIMESTAMP
  revoked_at TIMESTAMP
  UNIQUE(principal_id, tenant_id)
```

- One Principal can belong to multiple Tenants
- Principal selects Tenant at login (or defaults to first ACTIVE membership)
- Platform Admin membership spans all Tenants
- Revoke membership → `principal.security_version++` → all tokens for that Principal invalidated

### 8. Operation State Machine

```
PENDING → RUNNING → SUCCEEDED
PENDING → CANCELLED
APPROVAL_REQUIRED → APPROVED → RUNNING → SUCCEEDED
APPROVAL_REQUIRED → REJECTED
APPROVAL_REQUIRED → CANCELLED
RUNNING → FAILED
RUNNING → CANCELLED
```

Frontend button state:

| Status | Buttons |
|--------|---------|
| PENDING | Cancel + Details |
| APPROVAL_REQUIRED | Approve + Reject + Cancel + Details |
| EXECUTING/RUNNING | Details only (buttons disabled) |
| SUCCEEDED/COMPLETED | Details |
| FAILED | Retry + Details |
| REJECTED | Details |
| CANCELLED | Details |

### 9. Steward Call Contract

```
Steward → Control Plane Service API (HTTP only)
  ├─ ReconciliationService.get_outbox_backlog()
  ├─ ReconciliationService.get_binding_drift()
  ├─ ConfigurationService.get_config_drift()
  ├─ JobService.list_jobs(status="LOST")
  ├─ AssetService.list_assets(status="DEGRADED")
  └─ InstanceService.list_instances()

Prohibited: Steward direct PostgreSQL connection
```

## Consequences

- BFF requires Valkey dependency (`redis>=5.0`)
- Server `token_parser.py` must add `security_version` check
- `SecurityContext` gains `security_version` field
- New migration: `principal_tenant_memberships` table + `principals.security_version` column
- BFF `_sessions` dict removed, replaced with Valkey-backed session store
- BFF `_cp_get`/`_cp_post` use user token from session, not `BFF_TOKEN`
- BFF `/ws` echo endpoint deleted
