# Tenant Switch Failures Runbook

**When to use:** GET /auth/me/tenants/ or POST /auth/switch-tenant/ returns 403; X-Tenant-Id header rejected with 403; tenant switcher not visible in UI; user cannot switch tenant context.

**Related docs:** [TENANT_SWITCH_PLAN.md](../TENANT_SWITCH_PLAN.md) — production migration and rollback.

---

## Overview

Tenant switch allows users with multiple tenants (e.g. personal + org via invitation) to switch active tenant context. The system uses:

- **GET /auth/me/tenants/** — List tenants the user has membership in
- **POST /auth/switch-tenant/** — Switch active tenant; returns updated me summary
- **X-Tenant-Id header** — Scopes subsequent requests to switched tenant

---

## Root Causes and Fixes

### 1. 403 on GET /auth/me/tenants/ — "Tenant switch feature is disabled"

**Cause:** `FEATURE_TENANT_SWITCH_ENABLED` is false.

**Fix:** Set `FEATURE_TENANT_SWITCH_ENABLED=true` in environment (or remove to use default True). Restart API service.

**Verify:** `curl -H "Authorization: Bearer <token>" https://api.example.com/api/v1/auth/me/tenants/` returns 200 with tenant list.

---

### 2. 403 on POST /auth/switch-tenant/ — "Tenant switch feature is disabled"

**Cause:** Same as above — feature flag disabled.

**Fix:** Enable feature flag; restart API.

---

### 3. 403 on POST /auth/switch-tenant/ — "You do not have access to this tenant"

**Cause:** User has no UserTenantMembership for the target tenant. User can only switch to tenants they have been invited to.

**Fix:**
- Invite user to target tenant via tenant admin (POST /api/v1/users/invite/).
- Or run migration `0006_populate_user_tenant_memberships` if user had tenant_id before tenant switch was deployed (migration creates membership for primary tenant only; additional tenants require invite).

**Verify:** `UserTenantMembership.objects.filter(user_id=user.id, tenant_id=target_tenant_id).exists()` returns True.

---

### 4. 403 with X-Tenant-Id header on any request

**Cause:** Either (a) feature disabled, or (b) user has no membership in the tenant specified in X-Tenant-Id.

**Fix:**
- If feature disabled: enable `FEATURE_TENANT_SWITCH_ENABLED`.
- If invalid membership: ensure user was invited to that tenant; or stop sending X-Tenant-Id (use default tenant from JWT).

**Verify:** Remove X-Tenant-Id header — request should succeed with user's primary tenant. Add header with valid membership — request should succeed.

---

### 5. Tenant switcher not visible in UI

**Cause:** GET /auth/me/ returns `feature_tenant_switch_enabled: false` (backend setting), so frontend hides the switcher.

**Fix:** Set `FEATURE_TENANT_SWITCH_ENABLED=true`; restart API. User may need to refresh /auth/me/ (e.g. log out and log in, or refresh page).

---

### 6. Empty tenant list (GET /auth/me/tenants/ returns [])

**Cause:** User has no UserTenantMembership rows. Possible if:
- Migration 0006 not run (users with tenant_id before tenant switch have no memberships).
- User created before migration and migration skipped them (e.g. tenant_id was null).

**Fix:** Run migration `0006_populate_user_tenant_memberships`. For users with tenant_id, it creates membership. For users with multiple tenants (via invite), memberships are created by invite flow.

**Verify:** `UserTenantMembership.objects.filter(user_id=user.id).count()` >= 1.

---

### 7. 400 Bad Request — "tenant_id is required" or "tenant_id must be a valid UUID"

**Cause:** Request body missing tenant_id or tenant_id is not a valid UUID.

**Fix:** Ensure POST /auth/switch-tenant/ body is `{"tenant_id": "uuid-string"}` with valid UUID.

---

## Diagnostic Commands

```bash
# Check feature flag (from Django shell)
python manage.py shell -c "from django.conf import settings; print(getattr(settings, 'FEATURE_TENANT_SWITCH_ENABLED', True))"

# Check user memberships (replace USER_ID with actual UUID)
python manage.py shell -c "
from hub.apps.users.models import UserTenantMembership
from hub.apps.users.models import User
u = User.objects.get(id='USER_ID')
memberships = UserTenantMembership.objects.filter(user=u).select_related('tenant')
for m in memberships:
    print(m.tenant.id, m.tenant.name, m.tenant.slug)
"
```

---

## References

- [TENANT_SWITCH_PLAN.md](../TENANT_SWITCH_PLAN.md) — Migration and rollback
- [API_REFERENCE.md](../API_REFERENCE.md#tenant-switch) — API documentation
- Design D16: [openspec/changes/useronboardfix/design.md](../../openspec/changes/useronboardfix/design.md)
