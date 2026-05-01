# OpenLineage integration

**Phase:** 228 F4 (228.F4.27)
**Capability flag:** `lineage.openlineage_export`
**Receiver:** Marquez (self-hosted on EKS, OP-1)
**Last updated:** 2026-04-30
**Deployed Marquez version:** 0.46.0 (track upgrades in `marquez-upgrade.md`)

## Overview

Phase 228 F4 wires Meshant's internal lineage into the OpenLineage
2.0.0 standard. Two directions:

- **Outbound** — every contract save fans out a translated
  ``RunEvent`` to Marquez via the in-house adapter.
- **Inbound** — external producers (Airflow, dbt, custom) POST
  RunEvents to Meshant via ``/api/v1/lineage/openlineage/events/``.
  Meshant ingests them into the relational ``LineageEdge`` index.

The translator bridges the two shapes via a custom
``meshant_contract_ref`` facet that round-trips loss-lessly when
Meshant emits → external receiver → Meshant.

## Quick start (external producers)

### 1. Get an ingest API key

Tenant admins create keys at `/admin/integrations/openlineage`:

1. Navigate to the OpenLineage admin page.
2. Click "Generate key" + provide a label (e.g. "marquez-prod").
3. **Copy the plaintext key NOW** — Meshant cannot recover it after
   the success banner closes.

The key has the shape `msh_ol_<48-char-base64url>`.

### 2. Generate the HMAC signing key

The HMAC signing key lives in AWS Secrets Manager under
`meshant/staging/openlineage/hmac_signing_key`. It rotates every
90 days. Customer-success provisions the key share-secret into the
producer's vault on subscription onboarding.

### 3. POST your event

```bash
EVENT='{
  "eventType": "COMPLETE",
  "eventTime": "2026-04-30T12:00:00Z",
  "producer": "https://airflow.example.com/",
  "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
  "run": {"runId": "550e8400-e29b-41d4-a716-446655440000"},
  "job": {"namespace": "etl", "name": "orders_etl"},
  "inputs": [{"namespace": "meshant.contracts", "name": "<source-contract-uuid>"}],
  "outputs": [{"namespace": "meshant.contracts", "name": "<target-contract-uuid>"}]
}'

SIGNATURE="sha256=$(echo -n "$EVENT" | openssl dgst -sha256 -hmac "$HMAC_KEY" | awk '{print $2}')"

curl -X POST https://meshant-internal.example.com/api/v1/lineage/openlineage/events/ \
  -H "Content-Type: application/json" \
  -H "X-Meshant-OpenLineage-Key: $INGEST_KEY" \
  -H "X-Meshant-Signature: $SIGNATURE" \
  -d "$EVENT"
```

Response: `202 Accepted` on success, `400` on schema-validation
failure, `401` on auth failure, `404` when the capability flag
is OFF for the deployment.

### Auth — why a custom header?

We use `X-Meshant-OpenLineage-Key` instead of `Authorization: Bearer
<key>` because the Hub's global JWT middleware claims any
`Authorization: Bearer ...` header and 401's anything that can't be
decoded as a JWT. Co-locating an opaque API key in `Authorization`
would never reach the OpenLineage view. The custom header is also
greppable in Hub access logs without conflicting with JWT-based
audits.

## Outbound integration (Meshant → Marquez)

Driven automatically by the contract-save signal handler. No
configuration required beyond the deployment-level settings:

| Setting | Default | Purpose |
|---|---|---|
| `OPENLINEAGE_URL` | `http://marquez.marquez.svc.cluster.local:5000/api/v1/lineage` | Marquez receiver URL. Deployment-level. |
| `OPENLINEAGE_PRODUCER_NAME` | `https://meshant.com/lineage/openlineage` | Surfaced on every event's `producer` field. |
| `OPENLINEAGE_HMAC_SIGNING_KEY` | (empty in dev) | HMAC signing key, populated from Secrets Manager. |

## Translator behaviour

The bidirectional mapping is documented inline in
[`hub/apps/integrations/openlineage/translator.py`](../../hub/apps/integrations/openlineage/translator.py).
Key points:

- **Edge-type → eventType**: `transformation`/`derivation`/
  `upload`/`export` → `COMPLETE`; `reference` → `OTHER`.
- **Custom facet**: `meshant_contract_ref` carries `contract_id`,
  `model`, `field`, `edge_type`, `transformation_ref`, `job_ref`.
  Inbound events without this facet fall back to the
  `namespace == "meshant.contracts"` + `name == <uuid>` convention.
- **Schema validation**: every inbound event validates against an
  embedded subset of the OpenLineage 2.0.0 schema. The full upstream
  schema is large + carries vendor-specific facets we don't emit;
  the embedded subset focuses on the structural keys our pipeline
  reads.

## Adapter (outbound)

Backoff schedule: `1s → 2s → 4s → 8s → 16s`, max 5 attempts. After
the 5th failed attempt the event is dead-lettered with the
encrypted payload + failure context. Replay via:

```bash
python manage.py replay_openlineage_dlq --dry-run    # plan
python manage.py replay_openlineage_dlq --max=500    # apply
```

DLQ runbook: [openlineage-dlq-replay.md](../runbooks/openlineage-dlq-replay.md).

## Operations

| Task | Command |
|---|---|
| List ingest keys for a tenant | `GET /api/v1/lineage/openlineage/keys/` (admin-only) |
| Rotate keys with 7-day grace | `python manage.py rotate_openlineage_keys --tenant=<uuid>` |
| Replay DLQ | `python manage.py replay_openlineage_dlq --max=500` |
| Check Marquez reachability | `curl ${OPENLINEAGE_URL%/api/v1/lineage}/api/v1/namespaces` |

Runbooks:

- [DLQ replay](../runbooks/openlineage-dlq-replay.md) — when DLQ pending climbs.
- [Marquez outage](../runbooks/marquez-outage.md) — when Marquez itself is down.
- [Quarterly upgrade](../runbooks/marquez-upgrade.md) — Marquez chart upgrade procedure.

## Related

- [REQ-LIN-F4 spec](../../openspec/changes/preprod01/specs/lineage-foundations/spec.md)
- [Translator source](../../hub/apps/integrations/openlineage/translator.py)
- [Adapter source](../../hub/apps/integrations/openlineage/adapter.py)
- [Models source](../../hub/apps/integrations/openlineage/models.py)
- [k6 load test](../../tests/load/openlineage_inbound.k6.js)
