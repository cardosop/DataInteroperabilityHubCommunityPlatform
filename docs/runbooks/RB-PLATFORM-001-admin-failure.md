# RB-PLATFORM-001 — Platform Admin Operations Failure

**Owner:** platform-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
Platform admin endpoints include tenant lifecycle management, feature flag CRUD, impersonation, and global configuration. Failures can block tenant provisioning, flag changes, or admin investigations.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Tenant creation fails | Plan limit exhausted; billing not configured |
| Feature flag toggle returns 403 | Caller lacks PLATFORM_ADMIN role |
| Impersonation session expired | Session TTL elapsed; token refresh failed |
| Admin dashboard empty | Metrics pipeline stalled |

## 3. Investigation
1. Verify caller role: `GET /api/v1/users/me/`
2. Check tenant plan limits in admin
3. Review impersonation session: `GET /api/v1/admin/impersonation/sessions/`
4. Check metrics pipeline: Prometheus/Grafana health

## 4. Remediation
- **Tenant creation blocked:** Increase plan limit or verify billing
- **Flag toggle denied:** Verify PLATFORM_ADMIN role assignment
- **Impersonation:** Re-initiate session with new TTL
- **Dashboard:** Restart metrics collection pipeline

## 5. Recovery
1. Identify permission or configuration issue
2. Apply fix via admin or direct DB update
3. Verify admin functionality restored

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single admin operation failure | platform-eng@meshant.com |
| P2 | Tenant provisioning blocked | platform-eng + billing |
| P1 | Admin API fully unavailable | SEV1 — platform-eng on-call |

## 7. Related
- `hub/apps/tenants/views.py`
- `hub/apps/auth/permissions.py`
- `docs/runbooks/admin-feature-flag-flip.md`
- `docs/runbooks/admin-impersonation.md`
