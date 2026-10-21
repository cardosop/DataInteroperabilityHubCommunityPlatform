# Data Contracts — Single Source of Truth

This document is the canonical reference for **data contract shapes**
accepted by the Meshant API. It enumerates the minimum-viable ODCS
and ODPS payloads per supported spec version, the **structural floor
invariant** every contract must satisfy, and curl examples for the
create / update / introspect endpoints.

For the persona-flavoured walk-through (CLI + SDK), see
[JOURNEY-DE-001](mvpdocs/journeys/JOURNEY-DE-001.md). For the
architectural rationale and the five-layer enforcement model, see
[ARCHITECTURE.md](ARCHITECTURE.md#structural-floor-invariant-phase-227-wave-1).

> **Steady state (post Phase 227 W6 cutover, 2026-04-30):** the
> structural floor enforces unconditionally on every write surface;
> there is no opt-in / opt-out flag; every API write that violates
> the floor returns HTTP 400 with `error.code = "STRUCTURELESS_CONTRACT"`.
> The "Migration / Self-heal" section below describes the **operator
> tooling that remains available** for support escalations and
> ad-hoc diagnosis — it is no longer rollout-specific guidance.

## Structural Floor Invariant

Every contract that lands in the database carries **resolvable
structure** — at least one of:

- `models[*].fields[*]` — at least one model with at least one field, OR
- `schema.fields[*]` — top-level schema with at least one field.

Empty model lists, empty `outputPorts[]`, and
`models=[{"fields":[]}]` all violate the floor and produce HTTP 400
with `error.code = "STRUCTURELESS_CONTRACT"`. The error
`details.subcode` distinguishes the cause:

| Subcode | When |
| ------- | ---- |
| `STRUCTURELESS_ODPS_NO_PORTS` | ODPS contract has empty / unresolvable `outputPorts[]`. |
| `STRUCTURELESS_ODCS_NO_SCHEMA` | ODCS contract has no `schema.fields[]` AND no `models[*].fields[]`. |
| `STRUCTURELESS_CYCLIC_PORTS` | ODPS `outputPorts[*].contractId` chain forms a cycle (A → B → A). |
| `STRUCTURELESS_GENERIC` | Non-ODPS/ODCS spec_type or unrecognised shape — ops investigation. |

Per the 2026-04-30 ungate directive, the floor is **always-on** —
no feature flag, no per-tenant override, no deprecation period.

## ODCS — Open Data Contract Standard

Supported versions: **v2.2.2, v3.0.0, v3.0.0-preview, v3.0.1, v3.0.2,
v3.1.0**. The normalizer descends into nested `properties[]` (≥ v3.x)
and `fields[]` (≤ v3.0.x) keywords up to `CONTRACTS_MAX_NESTING_DEPTH`
(default 20).

### ODCS v3.0.2 — minimum viable shape

```yaml
kind: DataContract
apiVersion: v3.0.2
id: customer-transactions       # required
name: customer-transactions
version: 1.0.0
status: active
schema:
  - name: transactions           # at least one model
    fields:                      # with at least one field
      - name: transaction_id
        type: string
        primaryKey: true
      - name: amount
        type: decimal
        nullable: false
```

### ODCS v3.1.0 — adds `relationships[]` and `properties[]`

```yaml
kind: DataContract
apiVersion: v3.1.0
id: orders
name: orders
version: 1.0.0
status: active
schema:
  - name: orders
    fields:
      - name: order_id
        type: string
        primaryKey: true
      - name: customer
        type: object
        properties:              # nested object
          - name: id
            type: string
          - name: address
            type: object
            properties:          # ≤ 20 levels (CONTRACTS_MAX_NESTING_DEPTH)
              - {name: street, type: string}
              - {name: city, type: string}
      - name: items
        type: array
        items:                   # array element schema
          type: object
          properties:
            - {name: sku, type: string}
            - {name: qty, type: integer}
    relationships:
      - id: orders_customer_fk
        type: foreign_key
        source: [customer.id]
        target_contract: customers
        target_properties: [id]
```

### ODCS — minimum viable curl

```bash
curl -X POST https://meshant-internal.example.com/api/v1/contracts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\nversion: 1.0.0\nstatus: active\nschema:\n  - name: m\n    fields:\n      - {name: id, type: string}",
    "original_format": "YAML",
    "original_spec_type": "ODCS"
  }'
```

## ODPS — Open Data Product Standard

Supported versions: **v1.x, v2.x, v3.x, v4.0, v4.1, v4.2, Bitol
v1.0.0**. Each `outputPorts[*]` is normalized into one
`hub_contract_json.models[]` entry. Schema sources are tried in this
priority order:

1. `port.contractId` — references an existing ODCS Contract row.
2. `port.contract.spec.schema` — inline ODCS embedded in the port.
3. `port.dataSchema.fields[]` — direct field list on the port.
4. `port.schema` — alternative direct field list.
5. `port.contractURL` — external URL (resolved via
   [`RefResolver`](ARCHITECTURE.md) with SSRF defence).

`port.contractId` cycles (A → B → A) emit a
`STRUCTURELESS_CYCLIC_PORTS` warning and short-circuit without
recursing.

### ODPS v3.x / v4.x — minimum viable shape

```yaml
schema: https://opendataproducts.org/schema/v3.0
version: "3.0"
product:
  details:
    en:
      productID: customer-transactions
      name: Customer Transactions
      productVersion: 1.0.0
  outputPorts:                   # at least one outputPort
    - name: transactions
      contract:
        spec:
          schema:                # inline ODCS shape
            - name: transactions
              fields:
                - {name: transaction_id, type: string}
                - {name: amount, type: decimal}
```

### ODPS Bitol v1.0.0 — port-as-metadata + canonical models

```yaml
schema: https://bitol.io/schema/v1.0.0
version: "1.0.0"
product:
  details:
    en:
      productID: orders
      name: Orders
      productVersion: 1.0.0
  outputPorts:
    - name: orders
      tags: [pii, finance]       # metadata preserved under
                                 # extensions.x_odps.output_ports[*]
      customProperties:
        retention_days: "365"
      contractId: 41a4...        # references ODCS contract row;
                                 # OR inline schema as in v3/v4
  inputPorts:                    # become lineage.contracts[]
    - name: upstream-events
      namespace: kafka
```

### ODPS — minimum viable curl

```bash
curl -X POST https://meshant-internal.example.com/api/v1/contracts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "schema: https://opendataproducts.org/schema/v3.0\nversion: \"3.0\"\nproduct:\n  details:\n    en:\n      productID: p\n      name: P\n      productVersion: 1.0.0\n  outputPorts:\n    - name: o\n      contract:\n        spec:\n          schema:\n            - name: m\n              fields:\n                - {name: id, type: string}",
    "original_format": "YAML",
    "original_spec_type": "ODPS"
  }'
```

## Endpoints

### Create — `POST /api/v1/contracts/`

Body: `{original_raw, original_format, original_spec_type}`. Returns
201 with the persisted Contract on success; 400 with the typed error
envelope on rejection. Body cap is **2 MB** (`PAYLOAD_TOO_LARGE` →
413). The structural floor fires after normalisation.

### Update — `PATCH /api/v1/contracts/{id}/`

Same body shape as create. Supports RFC 7232 `If-Match` headers for
optimistic concurrency — see
[ARCHITECTURE.md](ARCHITECTURE.md#etag--if-match-optimistic-concurrency-phase-227-l43).
On 412 `PRECONDITION_FAILED`, the response body and `ETag` header
carry the server's current value so clients can reconcile in one
round-trip.

### Get — `GET /api/v1/contracts/{id}/`

Returns the contract row. Response carries an `ETag` header (RFC
7232 weak validator) — capture it for chained PATCHes.

### JSON Schema — `GET /api/v1/contracts/schema/json-schema/?spec=<odcs|odps>`

Returns the canonical Pydantic-derived JSON Schema describing valid
HubContract payloads. Content-Type is **`application/schema+json`**
(IANA-registered). The frontend Schema editor uses this to drive
client-side validation.

### Structureless triage — `GET /api/v1/contracts/?filter=structureless`

TENANT_ADMIN-only. Lists contracts in the calling user's tenant whose
normalised payload violates the floor. Drives the
`/admin/contract-health` triage page; remains available post-rollout
for support escalations and ad-hoc diagnosis.

## Migration / Self-heal (operator tooling)

The Phase 227 rollout is complete. The following commands remain
available for **support escalations** (e.g. a tenant restored a
backup containing legacy structureless rows) and **ad-hoc diagnosis**
(e.g. a regression in a new normaliser path). They are no longer
part of a scheduled rollout.

```bash
# Diagnosis (read-only, JSONL output for grep/jq):
python manage.py renormalize_contracts \
  --spec-version=3.1.0 \
  --filter=structureless \
  --dry-run --output=json \
  > audit-reports/structureless-$(date +%F).jsonl

# Self-heal pass (resumable, idempotent):
python manage.py renormalize_contracts \
  --spec-version=3.1.0 \
  --filter=structureless --apply \
  --checkpoint-table=structureless-self-heal-$(date +%F)

# Backlog gauge for the daily cron:
python manage.py renormalize_contracts \
  --spec-version=3.1.0 \
  --filter=structureless --dry-run --output=count
```

See the
[ops runbook](runbooks/structureless-contracts.md) for the full
playbook including the asset-revert step and rollback path.

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md#structural-floor-invariant-phase-227-wave-1) — five-layer enforcement model
- [Error catalog](mvpdocs/reference/error-codes.md#structureless-contract-codes-phase-227) — full code taxonomy
- [JOURNEY-DE-001](mvpdocs/journeys/JOURNEY-DE-001.md) — programmatic contract-first onboarding
- [UC-AM-001](mvpdocs/use-cases/UC-AM-001.md) — asset onboarding (activation gate)
- [Migration guide](migration-guides/structureless-contracts-deprecation.md) — for SDK consumers
- [Ops runbook](runbooks/structureless-contracts.md) — tenant rejection triage
