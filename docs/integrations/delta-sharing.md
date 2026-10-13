# Delta Sharing Integration

The Hub serves the Delta Sharing 1.0 protocol natively under
`/api/v1/databricks/delta-sharing` — bearer-token auth, per-recipient
throttling, opt-out enforcement, and audit injection (the `meshant`
share per tenant).

The earlier Phase 275.D.3 stub (`GET /api/v1/datasets/{id}/share/`) and
the fabricated `DeltaShareView` routes (`/api/v1/warehouses/share/...`)
were REMOVED — the native surface replaces them (design D6: removed,
not migrated).

## Auth

- Bearer tokens ONLY (no sessions). Tokens are provisioned via the
  recipient registry (`DeltaShareToken.issue()` — the API-key store
  pattern: the plaintext is shown exactly once, only its SHA-256 hash
  is stored).
- An invalid/missing token answers `401` and audits
  `WAREHOUSE_SHARE_AUTH_FAILED`.
- A token's scope is the (share, schema, table) triple with NULL
  wildcards; anything outside the scope answers `404` (never a leak).

## Endpoints

| Method | Path | Mode |
|---|---|---|
| GET | `/delta-sharing/profile` | client profile |
| GET | `/delta-sharing/shares` | share list |
| GET | `/delta-sharing/shares/{share}` | share detail |
| GET | `/delta-sharing/shares/{share}/schemas` | schema list |
| GET | `/delta-sharing/shares/{share}/schemas/{schema}/tables` | table list |
| GET | `/delta-sharing/shares/{share}/schemas/{schema}/tables/{table}` | table detail |
| GET | `.../tables/{table}/metadata` | ndjson `protocol` + `metaData` lines |
| GET | `.../tables/{table}/version` | Parquet mode — presigned-URL `file` actions from the snapshot |
| POST | `.../tables/{table}/query` | JSON mode — `SELECT * ... LIMIT n` through the production warehouse connector (the connection's M2M identity), ndjson with the `query` count/rows line |

## Rate Limit

`delta_share_recipients`: 30 req/min per recipient token (tenant-scoped
cache keys — one exhausted token never throttles the recipient's other
tokens or another tenant).

## Opt-Out

`Asset.semantic_federate_optout=True` (REQ-SEM-FED-002) assets are
hidden from every listing and their direct table-data fetch answers
`404` (fail-closed, never a leak).

## Audit

- `WAREHOUSE_SHARE_ACCESSED` per consumer request (IP + user-agent),
  best-effort — an audit-DB outage never blocks a response.
- Snapshot outcomes audit `DATABRICKS_SHARE_SNAPSHOT_COMPLETED` /
  `DATABRICKS_SHARE_SNAPSHOT_FAILED`.

## Snapshots

The snapshot job (`JobType.DATABRICKS_DELTA_SHARE_SNAPSHOT`)
materializes Parquet table versions with a TTL; expired snapshots
refresh, and re-materializing the same source version is idempotent.
