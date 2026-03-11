# JOURNEY-TA-TENANT-SETTINGS: View Usage and Configure Tenant

**Journey ID**: JOURNEY-TA-TENANT-SETTINGS  
**Title**: View Usage and Configure Tenant  
**Persona**: Tenant Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: useronboardfix Phase 8 — Tenant Usage & Config

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)

---

## What You Will Do

View tenant usage (storage, API calls, limits) and configure tenant settings (default DQ profile, versioning, workflows) at `/settings/tenant`.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to tenant settings | Go to **Settings** → **Tenant** (or `/settings/tenant`). | Tenant settings page loads | ☐ |
| 2 | View usage tab | Ensure **Usage** tab is active. View metrics (storage, API calls, limits). | Usage section visible with metric labels | ☐ |
| 3 | Switch to config tab | Click **Configuration** tab. | Config section visible | ☐ |
| 4 | Edit default DQ profile | Change default data quality profile (e.g. intake_basic_soda). Click **Save**. | Success message (updated/success) | ☐ |
| 5 | Toggle versioning | Toggle **Versioning enabled** checkbox. Save. | Change persisted | ☐ |
| 6 | Toggle workflows | Toggle **Workflows enabled** checkbox. Save. | Change persisted | ☐ |

---

## Success Criteria

- Usage tab shows metrics
- Config tab allows edits
- Default DQ profile change persists
- Versioning and workflows toggles work
- Success message after save

---

## API Endpoints (Reference)

- `GET /api/v1/tenants/me/usage/` — Tenant usage
- `GET /api/v1/tenants/me/config/` — Tenant config
- `PATCH /api/v1/tenants/me/config/` — Update config

See [docs/API_REFERENCE.md](../../../../docs/API_REFERENCE.md).

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-TENANT-SETTINGS.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md — useronboardfix Gap Coverage](../../../../docs/TEST_TRACEABILITY.md#useronboardfix-gap-coverage-phases-7-17)
