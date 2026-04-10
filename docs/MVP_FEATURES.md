# Meshant MVP Feature Set

This document enumerates the features included in the MVP deployment and the post-MVP namespaces that are gated behind `MVP_MODE=true`.

## MVP-Included Django Apps (~22)

These apps are fully available in MVP mode:

| App | Description |
| --- | --- |
| `auth` | Authentication, login, logout, token refresh, email verification |
| `users` | User management, profiles, roles, invitations |
| `tenants` | Multi-tenant isolation, tenant switching, KYC status |
| `assets` | Data asset CRUD, lifecycle (DRAFT/ACTIVE/RETIRED), publishing |
| `datasets` | Dataset versions, file associations, schema detection |
| `files` | S3 file upload/download, presigned URLs, chunked upload |
| `contracts` | Data contracts, ODPS/ODCS normalization, versioning |
| `compliance` | Compliance runs, PII detection, regulation mapping |
| `data_quality` | DQ runs, rule evaluation, quality scoring |
| `jobs` | Async job management, RQ task dispatch, polling |
| `audit` | Audit trail, event logging, 3-year retention |
| `billing` | Stripe integration, subscription plans, usage metering |
| `lineage` | Data lineage graph, provenance tracking |
| `marketplace` | Marketplace listings, search, publish/subscribe |
| `notifications` | In-app notifications, email alerts |
| `observability` | Prometheus metrics, OpenTelemetry tracing |
| `search` | Full-text search across assets and contracts |
| `webhooks` | Webhook delivery, retry, DLQ |
| `api` | API versioning, middleware, OpenAPI schema |
| `core` | Base models, services, resilience (circuit breakers) |
| `frontend` | React SPA, role-based routing, tenant switching |
| `admin` | Django admin panel (TENANT_ADMIN only) |

## Gated (Post-MVP) API Namespaces

These URL prefixes under `/api/v1/` are blocked by `MvpModeApiGateMiddleware` when `MVP_MODE=true` and return HTTP 404:

| Prefix | Feature Area |
| --- | --- |
| `mesh/` | Data Mesh topology, domains, policies |
| `virtualization/` | Data virtualization, federated queries |
| `integrations/` | Third-party integration connectors |
| `baas/` | Backend-as-a-Service, API key management |
| `ml/` | ML model training, experiment tracking |
| `ai/` | AI/LLM features |
| `transformation/` | Data transformation pipelines |
| `social/` | Social features, comments, likes |
| `scheduled-ingestions/` | Scheduled data ingestion jobs |
| `scheduled-exports/` | Scheduled data export jobs |

## How Gating Works

1. **Backend middleware** (`hub/apps/api/mvp_mode.py`): `MvpModeApiGateMiddleware` checks `MVP_MODE` env var and returns 404 for gated paths.
2. **OpenAPI postprocessor** (`openapi_mvp.postprocess_drop_mvp_gated_paths`): strips gated paths from the Swagger/ReDoc schema.
3. **CLI/SDK**: commands for gated features show a "not available in MVP" message instead of cryptic 404s.
4. **Test infrastructure**: `skip_if_mvp_mode` marker skips post-MVP tests; `pytest -m mvp` runs only MVP-mode tests.

## References

- Canonical prefix list: `hub/apps/api/mvp_mode.py :: MVP_GATED_RELATIVE_PREFIXES`
- Middleware: `hub/apps/api/middleware.py :: MvpModeApiGateMiddleware`
- Test markers: `cli/tests/pytest_mvp_skip.py`, `sdk/python/tests/pytest_mvp_skip.py`
- Phase spec: `openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md`
