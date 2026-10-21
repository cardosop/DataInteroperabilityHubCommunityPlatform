# RB-INTEGRATIONS-001 — Marketplace Connector Failure

**Owner:** platform-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
Integrations subsystem manages marketplace connections (CKAN, Swagger, custom) and federated import pipelines. Failures include connector authentication errors, rate limiting by external APIs, and sync job stalls.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| `MarketplaceConnection` sync job stuck in PENDING | External API rate limiting; RQ worker down |
| Federated import returns 403 | `federated_import_enabled=False` or DPO signoff missing |
| Connector auth fails | API key expired or rotated in external system |
| `EXTERNAL_RESOURCE_REFERENCE_SSRF_BLOCKED` | URL points to private IP or internal network |
| Sync job produces stale data | External source schema changed; mapping outdated |

## 3. Investigation
1. Check sync job: `datahub jobs get {job_id}`
2. Verify connector config: `GET /api/v1/integrations/marketplace/connections/{id}/`
3. Test external API access from worker pod
4. Check SSRF guard logs for blocked URLs
5. Verify flag: `Tenant.federated_import_enabled`

## 4. Remediation
- **Rate limited:** Adjust sync schedule; implement exponential backoff
- **Auth failure:** Update API key in connector config
- **SSRF blocked:** Use public URL for external resource
- **Stale data:** Re-sync; update field mappings
- **Flag off:** Obtain DPO signoff; enable federated_import_enabled

## 5. Recovery
1. Fix connector configuration or external API access
2. Manually trigger sync: `POST /api/v1/integrations/marketplace/connections/{id}/sync/`
3. Verify data freshness
4. Re-enable automated sync schedule

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single connector sync delayed | Tenant admin |
| P2 | All connectors for a marketplace instance failing | platform-eng@meshant.com |
| P1 | Federated import cross-tenant data leak suspected | SEV1 — security + platform-eng |

## 7. Related
- `hub/apps/integrations/federated_import_views.py`
- `hub/apps/integrations/config/marketplace_instances.py`
- `docs/runbooks/RB-COMP-006-federated-import.md`
- `docs/runbooks/federated-degradation.md`
