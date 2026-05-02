# Runbook — SPARQL Federation (Phase 230.8 / REQ-SEM-FED-001)

> **Audience**: oncall + platform-security.
> **Phase**: 230.8 — SPARQL federation outbound calls.
> **Last updated**: 2026-05-01.

This runbook covers operational tasks for SPARQL federation:
allowlist management, troubleshooting denied queries, response-time
incidents, audit reconstruction, and the SSRF/egress kill switch.

---

## Quick reference

| Key | Value |
| --- | ----- |
| **Outbound timeout** | 30s hard cap (`FEDERATION_HARD_TIMEOUT_SECONDS`) |
| **Audit code** | `SEMANTIC_FEDERATED_QUERY` (one row per SERVICE URL per query) |
| **Allowlist mutation codes** | `SEMANTIC_FEDERATION_ALLOWLIST_ADD` / `_REMOVE` |
| **Validator rejection code** | `SPARQL_FEDERATION_NOT_ALLOWED` |
| **Timeout rejection code** | `FEDERATION_TIMEOUT` (HTTP 408) |
| **SSRF rejection code** | `SSRF_TARGET_BLOCKED` |
| **Opt-out filter** | `hub.apps.semantic.federation.filter_optout_triples` — applied at `rdf_export` |
| **Allowlist table** | `semantic_tenant_sparql_endpoint` |
| **Per-tenant kill switch** | Set `is_active=False` on every row, or delete them |
| **Cluster-wide kill switch** | `helm upgrade --set semanticService.federationEgressEnabled=false` |
| **CLI** | `meshant semantic federation {add\|list\|remove}` |
| **REST** | `/api/v1/tenants/<tenant_id>/sparql-endpoints/` (TENANT_ADMIN-only) |

---

## Symptoms → likely cause

| Symptom | Likely cause | Section |
| ------- | ------------ | ------- |
| User reports "SPARQL query rejected with `SPARQL_FEDERATION_NOT_ALLOWED`" | Endpoint not on allowlist, or `is_active=False`, or wrong tenant | [§ Allowlist troubleshooting](#allowlist-troubleshooting) |
| Allowlist add returns `SSRF_TARGET_BLOCKED` | URL is loopback / link-local / RFC1918 / IMDS | [§ SSRF rejections](#ssrf-rejections) |
| `response_time_ms` in audit rows climbs to ~30000 | Partner endpoint is slow; clamp is firing | [§ Slow partner](#slow-partner) |
| Spike in `result=FAILURE` audit rows for a single partner | Partner outage, TLS expiry, or DNS failure | [§ Partner outage](#partner-outage) |
| Auditor asks "what was tenant X's allowlist on date Y?" | Reconstruct from audit log | [§ Allowlist reconstruction](#allowlist-reconstruction) |
| Tenant reports an opted-out resource is leaking via the export endpoint | Verify the per-resource `semantic_federate_optout` flag is True; check `filter_optout_triples` is wired | [§ Opt-out enforcement](#opt-out-enforcement) |
| Compliance asks "kill all federation for tenant X" | Per-tenant kill | [§ Kill switches](#kill-switches) |
| Compliance asks "kill all federation cluster-wide" | Operator kill | [§ Kill switches](#kill-switches) |

---

## Allowlist troubleshooting

The validator rejects a SERVICE clause when:

1. **No tenant context** — caller didn't thread `tenant_id` through. Check the calling code path; non-tenant-scoped paths (system admin, batch jobs) default-reject.
2. **Endpoint not registered** — no `TenantSparqlEndpoint` row matches the URL after `normalise_endpoint`.
3. **Endpoint registered but `is_active=False`** — inactive rows do NOT count.
4. **URL mismatch after normalisation** — trailing slash, port, scheme casing.

### Diagnostic SQL

```sql
-- All allowlist rows for tenant <tenant_id>
SELECT id, name, endpoint_url, is_active, created_at
FROM semantic_tenant_sparql_endpoint
WHERE tenant_id = '<tenant_id>'
ORDER BY created_at DESC;

-- Recent denied federated queries (last hour)
SELECT timestamp, actor_user_id, details_json
FROM audit_events
WHERE action = 'SEMANTIC_FEDERATED_QUERY'
  AND result = 'FAILURE'
  AND details_json->>'outcome' = 'DENIED'
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 50;
```

### Normalisation reminder

`hub.apps.semantic.federation.normalise_endpoint` strips trailing slashes, lowercases scheme + host, drops default ports. So:

- `https://Partner.Example.com:443/sparql` ⇄ `https://partner.example.com/sparql/` ✓ match
- `https://partner.example.com/sparql/v1` ⇄ `https://partner.example.com/sparql/v1/` ✓ match
- `https://partner.example.com/sparql` ⇄ `http://partner.example.com/sparql` ✗ scheme differs

### Add via CLI

```bash
meshant semantic federation add \
  --tenant-id <tenant_uuid> \
  --name "partner-acme" \
  --endpoint-url "https://sparql.acme.example.com/query"
```

Or via REST (TENANT_ADMIN token):

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "partner-acme", "endpoint_url": "https://sparql.acme.example.com/query"}' \
  https://meshant-internal.example.com/api/v1/tenants/<tenant_uuid>/sparql-endpoints/
```

---

## SSRF rejections

`code=SSRF_TARGET_BLOCKED` on allowlist creation means the URL targets:

- Loopback (`127.0.0.0/8`, `::1`)
- Link-local + cloud IMDS (`169.254.0.0/16`)
- RFC1918 (`10/8`, `172.16/12`, `192.168/16`)
- Carrier-grade NAT (`100.64/10`)

### On-prem operators with private endpoints

If a deployment legitimately needs to reach a private SPARQL endpoint (intranet, on-prem partner over VPN), set in Django settings:

```python
SEMANTIC_FEDERATION_ALLOW_PRIVATE = True
```

AND in Helm:

```yaml
semanticService:
  federationEgressEnabled: true
  federationEgressAllowPrivate: true
```

**Both layers must agree.** Setting only the Django flag bypasses the application guard but leaves the NetworkPolicy CIDR exclusion in place, so packets are dropped at the cluster boundary. Setting only the Helm flag passes packets but the application still rejects URL creation.

> **Change-management gate** — flipping `SEMANTIC_FEDERATION_ALLOW_PRIVATE` is a meaningful security change. Require: (a) PLATFORM_ADMIN approval, (b) Slack-channel notification, (c) audit-event `OPERATIONAL_CONFIG_CHANGED` (manually emitted via the existing platform settings change path).

---

## Slow partner

Federation calls are clamped at 30s (`FEDERATION_HARD_TIMEOUT_SECONDS`). When a partner is slow:

1. **Audit rows show the clamp** — `response_time_ms ≈ 30000` and `details_json.outcome=TIMEOUT` (the granular outcome maps to `result=FAILURE` on the AuditEvent row).
2. **User-facing error** — HTTP **408 Request Timeout** with `code=FEDERATION_TIMEOUT` and `service_urls` echoing the partner endpoint(s). This is the spec-mandated mapping (REQ-SEM-FED-001 "Federation timeout fires" scenario). Non-federated query timeouts still map to 503 + `SERVICE_UNAVAILABLE`.

### Triage

```sql
-- Top slow partners in the last hour
SELECT details_json->>'target_url' AS target,
       COUNT(*) AS calls,
       AVG((details_json->>'response_time_ms')::int) AS avg_ms,
       MAX((details_json->>'response_time_ms')::int) AS max_ms
FROM audit_events
WHERE action = 'SEMANTIC_FEDERATED_QUERY'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY target
ORDER BY avg_ms DESC
LIMIT 10;
```

If a partner is consistently slow, contact the partner owner (allowlist `name` field is intentionally human-readable for this) and consider deactivating the row (`PATCH .../sparql-endpoints/<id>/ {"is_active": false}`) until the partner recovers.

---

## Partner outage

A partner endpoint returning errors / TLS-expired / DNS-fail manifests as:

- `SEMANTIC_FEDERATED_QUERY` audit rows with `result=FAILURE`, `outcome=ERROR`.
- HTTP 503 returned to the user with `code=SERVICE_UNAVAILABLE`.

### Steps

1. Confirm the partner is genuinely down: `curl -v https://<partner-url>` from a worker pod, check for TLS / DNS / 5xx.
2. Notify the partner contact (off-platform — partner admin email).
3. Optionally toggle `is_active=False` on the row to fail the query closer to the user (clearer error, lower latency).
4. Re-enable when the partner confirms recovery.

---

## Opt-out enforcement

REQ-SEM-FED-002: `Asset`, `Contract`, `Dataset` each carry a `semantic_federate_optout` BooleanField. When `True`, the resource's triples MUST NOT cross the federation boundary.

### Where it's enforced

`hub.apps.semantic.federation.filter_optout_triples(body, content_type, tenant_id)` parses the serialised RDF body, drops every triple whose **subject** IRI matches an opted-out resource, and reserialises in the same content type. Wired into `views.py::rdf_export` — the closest external-facing bulk RDF surface today.

Subject-position only: object-position references to an opted-out resource (e.g. `<other_asset> <hub:derivedFrom> <opted_out_asset>`) are preserved. Removing the inbound edges as well would prune unrelated resources and surprise operators; the SHA-256-style "this resource is hidden" guarantee only applies to triples where the resource is the asserted subject.

### Verifying the filter

```sql
-- Resources currently opted out of federation
SELECT 'asset' AS rtype, id, name FROM assets WHERE tenant_id = '<tenant_id>' AND semantic_federate_optout = true
UNION ALL
SELECT 'contract' AS rtype, id::text, version::text FROM contracts WHERE tenant_id = '<tenant_id>' AND semantic_federate_optout = true
UNION ALL
SELECT 'dataset' AS rtype, id::text, format FROM datasets WHERE tenant_id = '<tenant_id>' AND semantic_federate_optout = true;
```

To verify the filter is active end-to-end: opt out an asset, run `meshant semantic export --format n-triples`, grep for the asset's canonical IRI. A leaking subject means the filter helper raised an exception on parse or the wire content type didn't match the format-table; check the `semantic_export_optout_filter_failed` log line.

### Toggling opt-out

The flag is owned by the resource's TENANT_ADMIN; flip via the resource's REST PATCH endpoint (e.g. `PATCH /api/v1/assets/<id>/ {"semantic_federate_optout": true}`). No dedicated CLI yet — track as a follow-on if operator demand surfaces.

---

## Allowlist reconstruction

To answer "what was tenant X's allowlist on date Y?":

```sql
-- Adds up to and including date Y
SELECT timestamp, resource_id, details_json
FROM audit_events
WHERE action = 'SEMANTIC_FEDERATION_ALLOWLIST_ADD'
  AND tenant_id = '<tenant_id>'
  AND timestamp <= '<date_Y>'
ORDER BY timestamp;

-- Removes up to and including date Y
SELECT timestamp, resource_id, details_json
FROM audit_events
WHERE action = 'SEMANTIC_FEDERATION_ALLOWLIST_REMOVE'
  AND tenant_id = '<tenant_id>'
  AND timestamp <= '<date_Y>'
ORDER BY timestamp;
```

Replay: start with empty set → apply ADDs in order → remove the IDs that appear in REMOVEs (still keyed by `resource_id`). The result is the active allowlist at date Y.

> **Caveat** — PATCH-driven flag flips (`is_active=False`) do not currently emit an audit row distinct from REMOVE. **Follow-on**: emit `SEMANTIC_FEDERATION_ALLOWLIST_DEACTIVATED` for clearer reconstruction. Tracked separately from 230.8.

---

## Kill switches

### Per-tenant kill

Two equivalent options:

**A. Deactivate all rows** (preserves audit trail, easy to roll back):

```sql
UPDATE semantic_tenant_sparql_endpoint
SET is_active = false, updated_at = NOW()
WHERE tenant_id = '<tenant_id>';
```

**B. Delete all rows** (cleaner state, audit trail still in `_REMOVE` rows):

Loop the CLI:

```bash
for id in $(meshant semantic federation list --tenant-id <tenant_id> --format json | jq -r '.[].id'); do
  meshant semantic federation remove --tenant-id <tenant_id> --id "$id"
done
```

After either, the next federated query from that tenant returns `SPARQL_FEDERATION_NOT_ALLOWED`. Existing in-flight queries are unaffected (allowlist is read at validation time, not query time).

### Cluster-wide kill

The `allow-semantic-federation-egress` NetworkPolicy gates outbound HTTPS. Disable it:

```bash
helm upgrade --reuse-values \
  --set semanticService.federationEgressEnabled=false \
  meshant <chart>
```

After the policy is removed, the default-deny egress policy applies → all federation outbound calls are dropped at the network layer (TCP RST). The validator still allows queries through (so the user gets a clearer 503 rather than a 400) — flip both layers if you want a clean 400 deny:

```python
# Django settings — emergency disable
SEMANTIC_FEDERATION_HARD_DISABLE = True  # (NOT YET IMPLEMENTED — see follow-on below)
```

> **Follow-on** — wire a `SEMANTIC_FEDERATION_HARD_DISABLE` Django flag that short-circuits `validate_sparql_query` to reject SERVICE before any allowlist lookup. Currently the cluster-wide kill leaves the validator path running but the egress dropping; for a cleaner UX add the application kill switch in 230.8.x.

---

## Audit-row schema (reference)

`SEMANTIC_FEDERATED_QUERY` audit event (`details_json`):

```json
{
  "target_url": "https://partner.example.com/sparql",
  "query_sha256": "<64 hex chars>",
  "response_time_ms": 1234,
  "outcome": "SUCCESS"
}
```

Where `outcome ∈ {SUCCESS, DENIED, ERROR, TIMEOUT}`. The `result` column maps to `{SUCCESS → SUCCESS, DENIED|ERROR|TIMEOUT → FAILURE}`.

`SEMANTIC_FEDERATION_ALLOWLIST_ADD` (`details_json`):

```json
{
  "name": "partner-acme",
  "endpoint_url": "https://sparql.acme.example.com/query",
  "is_active": true
}
```

`SEMANTIC_FEDERATION_ALLOWLIST_REMOVE` (`details_json`):

```json
{
  "name": "partner-acme",
  "endpoint_url": "https://sparql.acme.example.com/query"
}
```

---

## Related docs

- Threat model: `docs/security/threat-models/federation-cross-tenant.md`
- Spec: `openspec/changes/preprod01/proposal.md` (Phase 230.8)
- Validator code: `hub/apps/semantic/business_rules.py::validate_sparql_query`
- Federation helpers: `hub/apps/semantic/federation.py`
- CRUD viewset: `hub/apps/semantic/views.py::TenantSparqlEndpointViewSet`
- CLI: `cli/datahub_cli/commands/semantic.py::federation`
- Helm policy: `helm/templates/networkpolicy/allow-semantic-federation-egress.yaml`
