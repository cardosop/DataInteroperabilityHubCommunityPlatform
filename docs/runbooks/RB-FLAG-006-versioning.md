# RB-FLAG-006 — Versioning Feature Flag

**Flag:** `versioning_enabled`
**Stage:** GA
**Owner:** catalog-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)

## Scope

When enabled, datasets, contracts, and assets track versioned snapshots on every mutation. The version history is queryable via REST API, SDK (`VersioningAPI`), and CLI (`datahub versioning`). Disabling hides version history and prevents new snapshot creation.

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Version history returns 403 | `versioning_enabled=False` | Flag state; `GET /api/v1/admin/tenants/{id}/feature-flags/` |
| New mutations not creating versions | Flag disabled; async snapshot job backlog | Flag state; `version_snapshot_queue_depth`; job health |
| Version diff returns empty | Versions have no schema changes; diff engine error | Compare version schemas manually; `version_compare_errors_total` |
| Rollback fails | Target version archived; resource locked | Version status (`archived` cannot be rolled back); resource lock state |
| CLI `versioning list` returns error | SDK version mismatch; auth token expired | `datahub version`; `datahub login`; API key validity |
| Time-travel query timeout | Large dataset; complex schema evolution chain | `version_time_travel_duration_seconds`; paginate or narrow timestamp |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/versioning.json`
- **Primary:** `version_operations_total{operation}` (list, get, diff, rollback, time-travel)
- **Snapshot:** `version_snapshot_duration_seconds`, `version_snapshot_queue_depth`
- **Errors:** `version_operation_errors_total{operation, error_code}`
- **Audit:** `VERSION_CREATED`, `VERSION_COMPARED`, `VERSION_ROLLBACK_EXECUTED`

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Test version list: `datahub versioning list datasets <uuid>`
3. Test version diff: compare two versions and verify diff output
4. Test rollback (on test resource): `datahub versioning rollback datasets <uuid> <version_id> --reason "Test" --confirm`
5. Check snapshot job queue: no backlog >10; p95 latency <30s
6. Verify SDK: `VersioningAPI.get_version_history()` returns paginated results
7. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=versioning_enabled`

## Escalation

- **P3** — Version diff returns incomplete results for specific resource
- **P2** — Snapshot job backlog >50 or p95 latency >120s
- **P1** — Rollback causes data loss (immediate rollback of rollback + SEV1)

## Related

- `docs/runbooks/dataset-version-compare-failure.md` — Version comparison failure procedures
- `docs/api/versioning-policy.md` — API versioning policy (RFC 8594)
- `cli/datahub_cli/commands/versioning.py` — CLI versioning commands
- `sdk/python/datahub_interoperability/versioning.py` — SDK VersioningAPI

## Maintenance

- **Owner:** Catalog Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16
