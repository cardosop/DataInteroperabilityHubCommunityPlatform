# Feature Availability

[Post-MVP] features referenced below for context.

Meshant uses a feature-gating system to control which capabilities are
available in the current release. Some features are gated behind the
**MVP mode** flag and will return errors or redirect to placeholder pages
when accessed.

## How Gating Works

Feature gating is enforced at three levels:

### Backend (API)

When `MVP_MODE=True`, the `MvpModeApiGateMiddleware` returns HTTP `404` for
any request to a gated API path. The following path prefixes are gated:

| Prefix | Feature |
|--------|---------|
| `/api/v1/mesh/` | Data Mesh domains |
| `/api/v1/virtualization/` | Data virtualization |
| `/api/v1/integrations/` | Marketplace integrations |
| `/api/v1/baas/` | Backend-as-a-Service |
| `/api/v1/ml/` | ML model registry |
| `/api/v1/ai/` | AI services |
| `/api/v1/transformation/` | ETL/ELT pipelines |
| `/api/v1/social/` | Ratings, reviews, communities |
| `/api/v1/scheduled-ingestions/` | Scheduled data ingestion |
| `/api/v1/scheduled-exports/` | Scheduled data export |

The OpenAPI schema at `/api/v1/openapi.json` is also filtered — gated
endpoints are stripped from the schema when `MVP_MODE=True`, so developers
reading the staging OpenAPI spec see only available endpoints.

### Frontend (UI)

The `MvpGatedRoute` component redirects users to a `/coming-soon` page
when they navigate to a gated route. The `CapabilityRoute` component
checks a capabilities API and redirects to `/unavailable` if the
capability is not present.

### CLI

The CLI includes `_mvp_gates.py` which prevents execution of gated
commands. Users see a clear error message indicating the feature is not
available in the current release.

## What Users See

| Layer | Gated Request | Response |
|-------|--------------|----------|
| API | `GET /api/v1/mesh/domains/` | `404 Not Found` |
| Frontend | Navigate to `/mesh` | Redirect to `/coming-soon` |
| CLI | `datahub mesh list` | Error: feature not available in MVP |

## Checking Feature Availability

```bash
# Check if a capability is enabled
curl -H "Authorization: Bearer $TOKEN" \
  https://meshant-internal.example.com/api/v1/capabilities/

# Check MVP mode setting
python hub/manage.py shell -c \
  "from django.conf import settings; print(settings.MVP_MODE)"
```

## Related

- [MVP Features](../product/mvp-features.md) -- full feature tier list
- [Configuration Reference](../operations/configuration-reference.md) -- `MVP_MODE` setting
