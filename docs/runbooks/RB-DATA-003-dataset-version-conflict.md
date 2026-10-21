# RB-DATA-003 — Dataset Version Conflict

**Owner:** data-plane-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
Dataset versions track schema and data snapshots over time. Version conflicts occur when concurrent mutations create competing versions or when a rollback targets an archived version.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Version diff returns empty | Versions have identical schemas; diff engine error |
| Rollback rejected with 409 | Target version archived; resource locked |
| Version history missing entries | `versioning_enabled=False` during mutation |
| Snapshot job stuck in PENDING | `SEMANTIC_SNAPSHOT` queue backlog |

## 3. Investigation
1. Check version history: `GET /api/v1/versioning/versions/?resource_type=dataset&resource_id=<id>`
2. Compare versions manually: `GET /api/v1/versioning/compare/?resource_type=dataset&id_a=<v1>&id_b=<v2>`
3. CLI: `datahub versioning list datasets <id>` and `datahub versioning diff datasets <v1> <v2>`
4. Check `SEMANTIC_SNAPSHOT` job queue: `GET /api/v1/jobs/?type=SEMANTIC_SNAPSHOT`

## 4. Remediation
- **Archived version:** Cannot rollback to archived versions. Use time-travel query to inspect, then create new version from desired state.
- **Locked resource:** Wait for lock to release or contact admin to force-unlock.
- **Missing history:** Enable `versioning_enabled=True`; history only tracks forward from flag toggle.

## 5. Recovery
1. Identify desired state (version or timestamp)
2. Create new version from desired state
3. Verify new version schema matches expectations

## 6. Escalation
- **P3:** Version diff inconsistency
- **P2:** Rollback blocked for production asset
- **P1:** Version data loss — escalate to data-plane-eng@meshant.com

## 7. Related
- `docs/runbooks/dataset-version-compare-failure.md`
- `docs/runbooks/RB-FLAG-006-versioning.md`
- `cli/datahub_cli/commands/versioning.py`
