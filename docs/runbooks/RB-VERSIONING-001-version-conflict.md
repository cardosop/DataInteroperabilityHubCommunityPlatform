# RB-VERSIONING-001 — Version Conflict

**Owner:** data-platform@meshant.com | **Created:** 2026-05-20

## 1. Overview
The versioning subsystem tracks asset, contract, and dataset versions with SCD Type 2 semantics. Version conflicts occur when concurrent updates race or when rollback targets a version that no longer exists.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| `ASSET_VERSION_MISMATCH` | `If-Match` header version doesn't match current |
| Version rollback fails | Target version deleted or superseded |
| Version history gap | Hard-delete removed intermediate versions |
| `versioning_enabled=False` → feature unavailable | Flag off for tenant |

## 3. Investigation
1. Check current version: `GET /api/v1/{resource}/{id}/`
2. List version history: `datahub versioning list {type} {id}`
3. Diff versions: `datahub versioning diff {type} {id} {v1} {v2}`

## 4. Remediation
- **Version mismatch:** Re-fetch current version; reconcile changes
- **Rollback blocked:** Use explicit version ID from history
- **History gap:** Restore from audit log or backup

## 5. Recovery
1. Identify conflicting version
2. Re-fetch latest state
3. Re-apply changes with correct `If-Match` header
4. Verify version counter incremented

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single resource version conflict | Tenant admin |
| P2 | Version history corruption | data-platform@meshant.com |
| P1 | Mass version loss across tenants | SEV1 |

## 7. Related
- `hub/apps/versioning/views.py`
- `CLAUDE.md` — Versioning CLI Convention (283.6.2)
- `docs/runbooks/version-conflict.md`
