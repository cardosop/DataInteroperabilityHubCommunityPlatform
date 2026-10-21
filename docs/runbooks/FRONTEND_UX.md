# Frontend UX Troubleshooting Runbook

**When to use:** Toast notifications not showing; Breadcrumbs hidden when expected; ConfirmDialog not appearing or behaving oddly; UUID validation errors; Empty states not rendering; Notifications dropdown issues.

**Related docs:** [docs/design.md](../design.md) — Notifications decision; [openspec/changes/useronboardfix/design.md](../../openspec/changes/useronboardfix/design.md) — User onboarding UX design.

---

## Overview

The frontend uses shared UX components (Toast, Breadcrumbs, ConfirmDialog, EmptyState, UuidWithCopy) and feature flags to control optional behavior. Build-time environment variables configure these features.

**Architecture:**
- **Feature flags:** `frontend/src/shared/config/featureFlags.ts` — `FEATURE_TOAST_ENABLED`, `FEATURE_BREADCRUMBS_ENABLED`
- **Toast:** `ToastContext` wraps the app; `useToast()` provides `success`, `error`, `info`
- **Breadcrumbs:** Rendered on detail pages; returns `null` when disabled or `items.length === 0`
- **ConfirmDialog:** Modal for destructive/confirm actions (delete, revoke, etc.)
- **EmptyState:** Shown when lists are empty; optional action button
- **Notifications:** Header dropdown placeholder; backend integration not yet implemented

---

## Root Causes and Fixes

### 1. Toast notifications not showing

**Cause:** `FEATURE_TOAST_ENABLED` is false.

**Fix:** Set `VITE_FEATURE_TOAST_ENABLED=true` in `frontend/.env` or Docker build args. Default is `true` (enabled). Rebuild after changing env vars: `npm run build` or `docker compose build frontend`.

**Verify:** `import.meta.env.VITE_FEATURE_TOAST_ENABLED` (or `"true"` in built output). Call `useToast().success('test')` — toast should appear when enabled.

---

### 2. Breadcrumbs not visible

**Cause:** Either (a) `FEATURE_BREADCRUMBS_ENABLED` is false, or (b) `Breadcrumbs` is called with `items.length === 0`.

**Fix:**
- If feature disabled: Set `VITE_FEATURE_BREADCRUMBS_ENABLED=true` in `frontend/.env`; rebuild.
- If empty items: Ensure the page passes `items` with at least one item (e.g. `[{ label: 'Home', href: '/' }, { label: 'Detail', href: undefined }]`).

**Verify:** `import.meta.env.VITE_FEATURE_BREADCRUMBS_ENABLED`. Navigate to a detail page (e.g. Asset, Dataset) — breadcrumbs should appear if items are provided and feature is enabled.

---

### 3. ConfirmDialog not appearing or not closing

**Cause:** (a) `isOpen` is false when expected; (b) `onClose` or `onConfirm` not wired; (c) CSS z-index or overlay hiding the dialog.

**Fix:**
- Ensure `isOpen={!!deleteTarget}` (or equivalent) when user triggers delete/confirm.
- Pass `onClose` and `onConfirm` handlers; `onConfirm` should perform the action and clear state (e.g. `setDeleteTarget(null)`).
- Check `.confirm-dialog-overlay` and `.confirm-dialog` z-index in `ConfirmDialog.css`; ensure overlay is above page content.

**Verify:** Click delete/revoke on a resource — dialog should open; Cancel closes; Confirm performs action and closes.

---

### 4. UUID validation errors

**Cause:** User enters non-UUID in asset/dataset ID fields (e.g. Scheduled Export source scope). `isValidUUID()` rejects invalid values.

**Fix:** Ensure IDs are valid UUIDs (e.g. `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Use copy-from-detail (UuidWithCopy) or API response IDs. Do not enter arbitrary strings.

**Verify:** `frontend/src/shared/utils/validation.ts` — `isValidUUID(s)` returns true for valid UUIDs. Toast shows "Asset IDs must be valid UUIDs" or similar when invalid.

---

### 5. Empty states not rendering

**Cause:** (a) `EmptyState` not imported or used; (b) List has results so empty branch is not reached; (c) `title` or `message` missing.

**Fix:** Use `EmptyState` when `!data || data.results.length === 0`. Provide `title`, `message`, and optional `action` (e.g. "Create Pipeline"). Check that API returns empty `results` when expected.

**Verify:** Navigate to a list page with no data — EmptyState with icon, title, message, and optional action button should appear.

---

### 6. Notifications dropdown shows "No notifications yet" always

**Cause:** Expected behavior — notifications are a placeholder. Backend integration (access requests, DQ results, etc.) is not yet implemented.

**Fix:** None for placeholder. When backend supports notifications, integrate via API and replace placeholder content.

**Verify:** Header notifications button opens dropdown; shows "No notifications yet" and explanatory message. Escape key closes dropdown.

---

### 7. Feature flags not taking effect after env change

**Cause:** Vite env vars are baked in at build time. Changing `.env` after build does not update the app.

**Fix:** Rebuild: `cd frontend && npm run build`. For Docker: `docker compose build frontend` and restart. For dev: restart `npm run dev`.

**Verify:** `docker compose exec frontend env | grep VITE_` shows build-time vars if set in Dockerfile; for runtime, use build args in `docker compose build`.

---

### 8. Docker: overriding feature flags at build time

**Cause:** Need to disable Toast or Breadcrumbs in a Docker deployment.

**Fix:** Set env vars before build; they are passed as build args:
```bash
# In .env or export before docker compose build
VITE_FEATURE_TOAST_ENABLED=false
VITE_FEATURE_BREADCRUMBS_ENABLED=false

docker compose build frontend
docker compose up -d frontend
```

Or one-off: `VITE_FEATURE_TOAST_ENABLED=false docker compose build frontend`

---

## Diagnostic Commands

```bash
# Check feature flags in built frontend (from container)
docker compose exec frontend grep -r "VITE_FEATURE" /usr/share/nginx/html/assets/*.js 2>/dev/null || echo "Check .env at build time"

# Verify Toast/Breadcrumbs in dev
cd frontend && npm run dev
# In browser console: Check that useToast and Breadcrumbs work; inspect featureFlags if exposed

# Run UX-related unit tests
cd frontend && npm run test:run -- src/shared/config src/shared/components/UuidWithCopy src/shared/components/ConfirmDialog src/shared/components/Toast src/shared/components/Breadcrumbs src/shared/utils/validation
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_FEATURE_TOAST_ENABLED` | `true` | When `false`, Toast is disabled (addToast no-op, container not rendered). |
| `VITE_FEATURE_BREADCRUMBS_ENABLED` | `true` | When `false`, Breadcrumbs component returns `null`. |
| `VITE_APP_NAME` | `Meshant` | Brand name shown in UI. |

---

## References

- [docs/design.md](../design.md) — Notifications decision
- [openspec/changes/useronboardfix/design.md](../../openspec/changes/useronboardfix/design.md) — User onboarding UX
- `frontend/src/shared/config/featureFlags.ts` — Feature flag definitions
- `frontend/src/shared/components/Toast/ToastContext.tsx` — Toast provider
- `frontend/src/shared/components/Breadcrumbs.tsx` — Breadcrumbs component
- `frontend/src/shared/components/ConfirmDialog.tsx` — Confirm dialog
- `frontend/src/shared/components/EmptyState.tsx` — Empty state
- `frontend/src/shared/utils/validation.ts` — `isValidUUID`
