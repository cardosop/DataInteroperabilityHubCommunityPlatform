# RB-DEVELOPER-001 — Developer Portal / Plugin Failure

**Owner:** platform-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
Developer portal provides SDK docs, API key management, and plugin surface for third-party integrations. Failures include plugin registration errors, SDK generation issues, and API key provisioning delays.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Plugin registration fails | Invalid manifest or duplicate plugin ID |
| SDK docs not generating | OpenAPI schema fetch failed |
| API key provisioning delayed | Key generation service throttled |
| `developer_enabled=False` → 403 | Flag off for tenant |

## 3. Investigation
1. Check plugin registration: `GET /api/v1/developer/plugins/{id}/`
2. Verify OpenAPI schema: `GET /api/openapi.json`
3. Check API key status: `GET /api/v1/baas/api-keys/{id}/`
4. Verify flag: `Tenant.developer_enabled`

## 4. Remediation
- **Plugin failure:** Validate manifest against schema; re-register
- **SDK docs:** Regenerate from OpenAPI spec
- **API key:** Revoke and re-issue key

## 5. Recovery
1. Fix root cause
2. Re-register plugin or re-issue key
3. Verify functionality restored

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single plugin registration failure | Tenant developer |
| P2 | SDK docs not generating | platform-eng@meshant.com |
| P1 | API key service outage | SEV1 — platform-eng on-call |

## 7. Related
- `hub/apps/developer/views.py`
- `hub/apps/baas/views.py`
- `docs/api/API_STANDARDS.md`
