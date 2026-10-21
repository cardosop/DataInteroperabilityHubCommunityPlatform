# Troubleshooting

Common operational issues and their resolutions.

## Frontend UX

### Toast notifications not showing

Feature flag `VITE_FEATURE_TOAST_ENABLED` is `false`. Set to `true` and
rebuild the frontend (`npm run build` or `docker compose build frontend`).
Env vars are baked at build time.

### Breadcrumbs hidden

Either `VITE_FEATURE_BREADCRUMBS_ENABLED=false` or the breadcrumb items
array is empty. Enable the flag and verify the page provides items.

### ConfirmDialog not appearing

Check that `isOpen` is `true` and `onClose`/`onConfirm` handlers are wired.
Verify z-index is not blocked by another overlay.

### Feature flags not taking effect

Frontend env vars (`VITE_*`) are embedded at build time, not runtime. After
changing a flag, rebuild:

```bash
VITE_FEATURE_TOAST_ENABLED=true npm run build
# or
docker compose build frontend
```

---

## Resource Pickers

### Picker dropdowns empty or not loading

1. Backend API must be running on the expected port.
2. `VITE_API_BASE_URL` must be correct.
3. User must be authenticated with a valid `X-Tenant-ID`.
4. Test data must exist for the selected resource type.

### Text input instead of dropdown

`VITE_FEATURE_RESOURCE_PICKERS_ENABLED=false`. Set to `true` and rebuild.
When `false`, pickers render manual UUID text inputs.

### A11y violations in pickers

Run accessibility tests: `npm run test:a11y`. Fix contrast and label issues
in `frontend/src/shared/components/pickers/`.

**Test script**: `./scripts/run_resource_picker_tests.sh`

---

## Tenant Switching

### 403 on GET /auth/me/tenants/ or POST /auth/switch-tenant/

`FEATURE_TENANT_SWITCH_ENABLED=false`. Set to `true` and restart the API.

### Tenant switcher not visible in UI

The `/auth/me` response includes `feature_tenant_switch_enabled: false`.
Enable the setting and refresh the page.

### Empty tenant list

User has no `UserTenantMembership` records. Run the population migration:

```bash
python hub/manage.py migrate users 0006_populate_user_tenant_memberships
```

### Diagnostic commands

```bash
# Check feature flag
python hub/manage.py shell -c \
  "from django.conf import settings; print(settings.FEATURE_TENANT_SWITCH_ENABLED)"

# Check user memberships
python hub/manage.py shell -c "
from hub.apps.users.models import User
from hub.apps.tenants.models import Tenant
u = User.objects.get(email='user@example.com')
for m in u.tenant_memberships.select_related('tenant'):
    print(m.tenant.id, m.tenant.name)
"
```

---

## Related

- [Health Checks](health-checks.md) -- endpoint monitoring
- [Monitoring](monitoring.md) -- dashboards and alerting
- [Operational Runbooks](index.md#operational-runbooks) -- service-specific runbooks
