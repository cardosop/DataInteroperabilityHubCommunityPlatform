# Warehouse Connectivity API Reference (Phase 275)

## Endpoints

### Records API
`GET /api/v1/datasets/{id}/rows/?limit=100&cursor=abc123`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Max rows per page |
| `cursor` | string | null | Opaque cursor for pagination |

**Content Negotiation:**
- `Accept: application/json` (default) — decimals as strings per RFC 7159
- `Accept: application/vnd.apache.arrow.stream` — Arrow IPC stream with native precision

**Rate Limit:** `warehouse-query-records` (60 req/min/tenant)

### Delta Sharing
`GET /api/v1/datasets/{id}/share/`

Serves the Delta Sharing 1.0 protocol with Hub auth.

**Rate Limit:** `warehouse-query-share` (30 req/min/tenant)

**Audit:** `WAREHOUSE_SHARE_ACCESSED` emitted per access.

## Warehouse Connections

### Webhook Events
| Event | Trigger |
|-------|---------|
| `warehouse.connection.created` | Connection created |
| `warehouse.connection.updated` | Connection config updated |
| `warehouse.connection.deleted` | Connection deleted |
| `warehouse.export.completed` | Scheduled export succeeded |
| `warehouse.export.failed` | Scheduled export failed |
| `warehouse.share.accessed` | Delta Sharing endpoint accessed |
| `warehouse.connection.test_failed` | Connection test failed |
| `warehouse.schema.drift_detected` | Schema drift detected |
