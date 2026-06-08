# API Endpoint Deprecation Playbook

**Owner**: Developer Experience  
**Last reviewed**: 2026-05-13  
**Next review**: 2026-08-11  

## Scope

This playbook describes the end-to-end process for deprecating an API endpoint in Meshant. It covers registration, header emission, frontend banners, consumer communication, CHANGELOG updates, sunset enforcement, and cleanup. The governing policy is defined in [`docs/api/versioning-policy.md`](../api/versioning-policy.md).

## Prerequisites

- Access to the repository (`push` to `staging` branch).
- `kubectl` access to the staging cluster (`kubectl config current-context` → `meshant-staging`).
- A documented reason for deprecation (ADR or phase spec).
- A replacement endpoint path (or `null` if no replacement).

---

## Step 1 — Register the Deprecated Endpoint

Add a `DeprecatedEndpoint` entry in the `DEPRECATED_ENDPOINTS` registry.

**File**: `hub/apps/api/versioning.py`

```python
# In APIVersionManager.DEPRECATED_ENDPOINTS (class variable, line ~250):
DeprecatedEndpoint(
    path="/api/v1/<endpoint>/",
    method="GET",  # or "POST", "PUT", "DELETE", "*"
    deprecated_since="2026-05-13",          # ISO date (today)
    sunset_date="2026-08-11",               # 90 days out (180 for high-volume)
    replacement="/api/v2/<endpoint>/",       # or None
    migration_guide="docs/migration/<guide>.md",  # or ""
    removal_issue="https://github.com/.../issues/N",  # or ""
)
```

**Validation**: After deploy, `curl -I https://api.stagingmeshant-internal.example.com/api/v1/<endpoint>/` must return:

```
Deprecation: true
Sunset: Tue, 11 Aug 2026 00:00:00 GMT
Link: </api/v2/<endpoint>/>; rel="successor-version"
```

The headers are emitted automatically by `APIVersionMiddleware` for any path registered in `DEPRECATED_ENDPOINTS`. No view-level code changes are required.

---

## Step 2 — Add Frontend Deprecation Banner

Add an in-app banner so consumers see the notice before the endpoint stops working.

**File**: `frontend/src/shared/components/DeprecationBanner.tsx` (create if absent; pattern: `PlanLimitErrorBanner.tsx`)

```tsx
// Minimal banner pattern — conditionally renders when capability flag is on.
export function DeprecationBanner({ endpoint, sunsetDate, replacementUrl }: Props) {
  // Renders a dismissible warning bar.
}
```

**Integration points**:
- Mount the banner on the affected page component(s).
- Gate behind a capability flag: `deprecation.<endpoint-slug>` so it can be toggled without a deploy.
- Include the sunset date in the banner text (ISO → human-readable).

**Validation**: Load the affected page in staging. Dismiss the banner. Verify it reappears on next navigation (non-dismissed state stored in `localStorage` keyed to endpoint path).

---

## Step 3 — Notify Consumers

Notify internal and external consumers through all available channels.

### 3a. Internal Engineering Announcement

Follow the [`internal-eng-announcement-protocol.md`](internal-eng-announcement-protocol.md):

```bash
# Post in #eng-announcements (Slack):
#   [DEPRECATION] <endpoint> — <sunset date> — <replacement link>
#   Migration guide: <url>
#   Removal issue: <url>
```

### 3b. External Consumer Email

**File**: `hub/apps/notifications/templates/deprecation_notice.md` (create from email template pattern in `hub/apps/notifications/templates/`).

**Trigger**: Run the tenant-notification command after deploy to staging:

```bash
kubectl exec -n hub-staging deploy/hub-api -- \
  python manage.py notify_deprecated_endpoint \
    --endpoint /api/v1/<endpoint>/ \
    --method GET \
    --dry-run   # remove after verifying recipient list
```

The command queries tenants with active API keys that have called the endpoint in the last 90 days (from audit log), deduplicates by tenant admin email, and sends one email per tenant.

### 3c. SDK Deprecation Warning

If the deprecated endpoint has SDK coverage:

- **Python SDK** (`sdk/python/`): Add `warnings.warn(DeprecationWarning("..."))` in the affected method. Reference PR.
- **TypeScript SDK** (`sdk/typescript/`): Annotate the generated method with `@deprecated` JSDoc tag.
- **CLI** (`cli/`): Add `click.echo("Warning: ...", err=True)` for deprecated commands.

**Validation**: Run `sdk/python/tests/`, `sdk/typescript/tests/`, `cli/tests/` and verify deprecation warnings are emitted.

---

## Step 4 — Update CHANGELOG

Add a `### Deprecated` section to `CHANGELOG.md` for the current release:

```markdown
### Deprecated
- **<endpoint>** (`GET /api/v1/<endpoint>/`). Replaced by `<replacement>`.
  Sunset date: `<YYYY-MM-DD>`. See [migration guide](<url>).
```

Also add a `### Removed` entry pre-emptively for the release that will follow the sunset date, so the removal is tracked in the release plan.

---

## Step 5 — Monitor During Deprecation Window

### 5a. Usage Dashboard

```bash
# Query audit log for deprecation header hits (weekly):
kubectl exec -n hub-staging deploy/hub-api -- python manage.py audit_query \
  --action API_DEPRECATION_WARNING \
  --since "$(date -d '7 days ago' -Iseconds)" \
  --format csv > deprecation_usage_$(date -I).csv
```

Track:
- Requests/week to the deprecated endpoint (should be declining).
- Requests/week to the replacement (should be increasing).
- Unique tenant count using the deprecated endpoint.

### 5b. Alert on Zero Migration

If a tenant calls the deprecated endpoint ≥3 times in a 7-day window during the last 30 days of the window, open an outreach ticket to their tenant admin.

### 5c. Extension Requests

If a tenant requests more time, evaluate:
- Is the replacement endpoint feature-complete for their use case? → Help them migrate.
- Is the replacement missing a feature? → File a feature request and extend the window by 30 days for that tenant only (via per-tenant feature flag `deprecation_extend_<endpoint-slug>`).

---

## Step 6 — Hard Removal (Sunset Date)

### 6a. Pre-Removal Checklist

- [ ] No tenant has called the deprecated endpoint in the last 14 days (verify via audit log).
- [ ] All SDK deprecation warnings have been live for ≥60 days.
- [ ] Replacement endpoint has been stable (no 5xx spikes) for ≥30 days.
- [ ] CHANGELOG `### Removed` entry is drafted.
- [ ] Removal PR is open and reviewed.

### 6b. Execute Removal

**File**: `hub/apps/<app>/views.py`

Remove the deprecated view/ViewSet. Keep a stub that returns `410 Gone` with the `Link` header pointing to the replacement:

```python
@api_view(["GET", "POST", "PUT", "DELETE"])
def <endpoint>_gone(request, *args, **kwargs):
    response = Response(
        {"error": "This endpoint has been removed.", "replacement": "<url>"},
        status=status.HTTP_410_GONE,
    )
    response["Link"] = '</api/v2/<endpoint>/>; rel="successor-version"'
    return response
```

The `APIVersionMiddleware` will automatically add `Deprecation: true` and `Sunset` headers to the 410.

**File**: `hub/apps/<app>/urls.py`

Keep the URL entry but point it at the `_gone` stub (do NOT remove the URL pattern — that causes 404, which is indistinguishable from a typo).

### 6c. Post-Removal Validation

```bash
curl -I https://api.stagingmeshant-internal.example.com/api/v1/<endpoint>/
# Expected: HTTP/1.1 410 Gone
# Deprecation: true
# Sunset: <past date>
# Link: </api/v2/<endpoint>/>; rel="successor-version"
```

### 6d. Archive

After 30 days of stable 410 responses, remove the URL entry and the stub view. Mark the `DEPRECATED_ENDPOINTS` entry with `resolved=True` (keep it for historical record).

---

## Reference Example — Phase 273.1.8 (Search Deprecation)

The `GET /api/v1/search/` endpoint (legacy `SearchViewSet`) was deprecated in favor of `GET /api/search/` (UnifiedSearchView).

| Milestone | Date | Detail |
|---|---|---|
| Announced | 2026-03-19 | Registered in `DEPRECATED_ENDPOINTS` |
| Replacement live | 2026-03-19 | `GET /api/search/` deployed |
| Deprecation headers active | 2026-03-19 | `Deprecation`, `Sunset`, `Link` headers via `APIVersionMiddleware` |
| Sunset date | 2026-04-18 | 30-day window (search is critical-path; shortened to force migration) |
| Removal | 2026-04-18 | `SearchViewSet` removed from router; stub retained |
| Stub removal | Deferred | `grep -n "SearchViewSet" hub/apps/search/views.py` → zero results when done |

**Key files touched**:
- `hub/apps/search/views.py` — removed `SearchViewSet` registration
- `hub/apps/search/urls.py` — removed router entry
- `hub/apps/api/versioning.py` — added `DeprecatedEndpoint` entry
- `CHANGELOG.md` — `### Deprecated` and `### Removed` entries
- `frontend/src/shared/components/DeprecationBanner.tsx` — in-app notice
- `sdk/python/` — `DeprecationWarning` in search methods
- `sdk/typescript/` — `@deprecated` JSDoc annotations

---

## Step Runbook Summary

| Step | Action | File(s) | Validation |
|---|---|---|---|
| 1 | Register endpoint | `hub/apps/api/versioning.py` | `curl -I` → `Deprecation: true` |
| 2 | FE banner | `frontend/src/shared/components/DeprecationBanner.tsx` | Banner visible on page, dismissible |
| 3a | Internal announcement | Slack `#eng-announcements` | Message sent |
| 3b | Consumer email | `manage.py notify_deprecated_endpoint` | Dry-run recipient list correct |
| 3c | SDK warnings | `sdk/python/`, `sdk/typescript/`, `cli/` | Warnings emitted in tests |
| 4 | CHANGELOG | `CHANGELOG.md` | `### Deprecated` entry present |
| 5 | Monitor | Audit log queries | Usage declining |
| 6 | Hard removal | Views/URLs | `410 Gone` with `Link` header |

---

## Related Documents

- [`docs/api/versioning-policy.md`](../api/versioning-policy.md) — API versioning rules and deprecation window policy
- [`docs/runbooks/internal-eng-announcement-protocol.md`](internal-eng-announcement-protocol.md) — How to announce changes internally
- [`CHANGELOG.md`](../../CHANGELOG.md) — Release changelog
- [`hub/apps/api/versioning.py`](../../hub/apps/api/versioning.py) — `APIVersionManager` and `DeprecatedEndpoint` dataclass

## Maintenance

This document is reviewed quarterly alongside the versioning policy. When a new deprecation is executed, update the "Reference Example" section with the most recent deprecation so the playbook stays current.
