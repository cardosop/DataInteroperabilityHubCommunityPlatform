# Tenant Switch — Production Migration and Rollback

Plan for deploying and operating the tenant switch feature (Phase 29.65). Design: [openspec/changes/useronboardfix/design.md](../openspec/changes/useronboardfix/design.md) D16.

## Overview

Tenant switch allows users with multiple tenants (e.g. personal + org via invitation) to switch active tenant context without re-login. The system uses:

- **UserTenantMembership** model: many-to-many user↔tenant
- **X-Tenant-Id** header: stateless override of active tenant
- **GET /auth/me/tenants/**: list tenants the user has membership in
- **POST /auth/switch-tenant/**: validate membership and return updated me summary

## Prerequisites

- PostgreSQL (existing)
- Migrations `0005_add_user_tenant_membership` and `0006_populate_user_tenant_memberships` applied
- No schema changes required beyond these migrations

## Production Migration

### Step 1: Apply migrations

```bash
# From API service container or host with DB access
python hub/manage.py migrate users
```

Verify:

```bash
python hub/manage.py showmigrations users
# 0005_add_user_tenant_membership [X]
# 0006_populate_user_tenant_memberships [X]
```

### Step 2: Deploy backend and frontend

1. Deploy backend with tenant switch views and middleware (already in codebase).
2. Deploy frontend with tenant switcher in Header (already in codebase).
3. Ensure `FEATURE_TENANT_SWITCH_ENABLED` is **True** (default) or unset.

### Step 3: Verify

1. Log in as a user with multiple tenants (invited to at least one org).
2. Confirm tenant switcher appears in header.
3. Switch tenant and verify assets/listings are scoped to the new tenant.
4. Check audit log for `TENANT_SWITCH` events.

## Rollback

### Option A: Feature flag (recommended)

Disable tenant switch without code rollback:

```bash
# In .env or environment
FEATURE_TENANT_SWITCH_ENABLED=false
```

Effects:

- **GET /auth/me/tenants/** returns 403
- **POST /auth/switch-tenant/** returns 403
- **X-Tenant-Id** header is rejected (403) by middleware
- Frontend hides tenant switcher; shows static tenant name instead

Restart API service after changing the env var.

### Option B: Code rollback

If you must revert to a version without tenant switch:

1. Deploy previous backend version (before tenant switch).
2. Deploy previous frontend version.
3. **Data:** UserTenantMembership table and data remain. No automatic cleanup. This is safe; the old code simply ignores the table.

### Option C: Full data rollback (not recommended)

Removing UserTenantMembership data is **not recommended** because:

- Invitation flow may have added memberships; removing them breaks re-invite semantics.
- Migration is idempotent; re-running is safe.
- No performance impact from leaving the table populated.

If you must remove the table:

```sql
-- Only if absolutely necessary; run during maintenance window
DROP TABLE IF EXISTS users_usertenantmembership CASCADE;
```

Then revert migrations (requires custom reverse migration).

## Feature Flag

| Setting | Default | Effect |
|---------|---------|--------|
| `FEATURE_TENANT_SWITCH_ENABLED` | `True` | When `False`: disables GET /auth/me/tenants/, POST /auth/switch-tenant/, and X-Tenant-Id header |

**Environment variable:** `FEATURE_TENANT_SWITCH_ENABLED=true|false`

**Backend:** `hub/settings.py` — `env.bool("FEATURE_TENANT_SWITCH_ENABLED", default=True)`

**Frontend:** GET /auth/me/ returns `feature_tenant_switch_enabled`; Header hides switcher when false.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 403 on GET /auth/me/tenants/ | Feature disabled or user not authenticated | Set `FEATURE_TENANT_SWITCH_ENABLED=true`; ensure valid JWT/session |
| 403 on POST /auth/switch-tenant/ | Feature disabled or user has no membership in target tenant | Enable feature; verify UserTenantMembership exists for (user, tenant) |
| 403 with X-Tenant-Id header | Feature disabled or invalid membership | Enable feature; ensure user was invited to target tenant |
| Tenant switcher not visible | `feature_tenant_switch_enabled=false` in /auth/me/ | Set `FEATURE_TENANT_SWITCH_ENABLED=true` |
| Empty tenant list | User has no UserTenantMembership rows | Run migration 0006; or invite user to a tenant |

## Runbook

See [docs/runbooks/TENANT_SWITCH.md](runbooks/TENANT_SWITCH.md) for operational procedures and troubleshooting. Index: [RUNBOOKS.md](RUNBOOKS.md).

## References

- Design D16: [openspec/changes/useronboardfix/design.md](../openspec/changes/useronboardfix/design.md)
- Tasks: [openspec/changes/useronboardfix/tasks.md](../openspec/changes/useronboardfix/tasks.md) §29.65
