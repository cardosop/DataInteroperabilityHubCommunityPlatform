# Migration Guide — Structureless-Contract Deprecation (Phase 227)

**Audience:** External SDK consumers, third-party integration authors,
CI/CD pipeline maintainers who programmatically create or update
Meshant data contracts.

**Effective:** Phase 227 Wave 1 deployed 2026-04-30. The structural
floor is **always-on**; there is no opt-out.

**TL;DR:** Contracts that normalise to an empty
`hub_contract_json.models[*].fields[]` AND empty
`hub_contract_json.schema.fields[]` are now rejected at the API edge
with HTTP 400 `STRUCTURELESS_CONTRACT`. Update your contract
templates and CI pipelines to ensure every payload carries
resolvable structure.

---

## What changed

Before Phase 227, the API would accept structureless contract bodies
silently — normalising to a row with `hub_contract_json = NULL` (the
"silent-nullify" path) or `hub_contract_json.models = []`.
Downstream lineage, search, and marketplace publish then surfaced
empty schemas to consumers, with no signal at upload time.

Phase 227 hardens the validation pipeline at five layers (see
[ARCHITECTURE.md](../ARCHITECTURE.md#structural-floor-invariant-phase-227-wave-1)
for the enforcement model). The user-visible change for SDK
consumers:

1. `POST /api/v1/contracts/` and `PATCH /api/v1/contracts/{id}/`
   now return **HTTP 400** with `error.code = "STRUCTURELESS_CONTRACT"`
   when the submitted/derived contract has no resolvable structure.
2. `PATCH /api/v1/assets/{id}/` with `status: ACTIVE` returns the
   same code if the active contract violates the floor.
3. Marketplace publish (`PATCH /api/v1/marketplace/listings/{id}/`
   with `status: PUBLISHED`) returns **HTTP 422** with the same code.

The error envelope's `error.details.subcode` distinguishes the
cause (see [error catalog](../mvpdocs/reference/error-codes.md#structureless-contract-codes-phase-227)
for the full taxonomy).

## Detection — am I affected?

Run the diagnosis command against staging or production:

```bash
python /app/hub/manage.py renormalize_contracts \
    --spec-version=3.1.0 \
    --filter=structureless \
    --dry-run --output=json \
    --tenant-id=<YOUR_TENANT_UUID> \
    > structureless-audit.jsonl
```

If `wc -l structureless-audit.jsonl` returns > 0 (excluding the `#`
comment lines), your tenant has structureless contracts that will
trip the gate when you next try to update them or activate the
backing asset. Pipe through `jq` to summarise:

```bash
# Per-classification counts:
jq -c 'select(.contract_id) | .classification' structureless-audit.jsonl \
    | sort | uniq -c
```

Possible classifications:

- `pure_odps_with_outputports` — ODPS bug fixed in Phase 227.L1.
  **No SDK action needed** — re-running normalisation populates the
  models. If you control the tenant, run `--apply` (see runbook).
- `odcs_no_schema_block` — ODCS contract genuinely lacks structure.
  **SDK action required**: update your contract template to include
  a `schema:` block with at least one field.
- `other` — operator triage. Open a ticket via your Meshant CSM.

## SDK migration — minimum-viable shapes

### Python SDK — ODCS

**Before** (silently accepted, now rejected):

```python
from datahub_interoperability import DataHubClient
client = DataHubClient(api_key="...")

# This used to land a structureless row. Now: raises ValidationError.
contract = client.contracts.create(
    original_raw="""
        kind: DataContract
        apiVersion: v3.0.2
        id: orders
        name: orders
        version: 1.0.0
        status: active
        info:
          description: Order events stream  # <-- info-only, no schema
    """,
    original_format="YAML",
    original_spec_type="ODCS",
)
```

**After** (passes the structural floor):

```python
contract = client.contracts.create(
    original_raw="""
        kind: DataContract
        apiVersion: v3.0.2
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
              - name: amount
                type: decimal
    """,
    original_format="YAML",
    original_spec_type="ODCS",
)
```

### Python SDK — ODPS

**Before** (empty `outputPorts[]` — now rejected):

```python
contract = client.contracts.create(
    original_raw="""
        schema: https://opendataproducts.org/schema/v3.0
        version: "3.0"
        product:
          details:
            en:
              productID: orders
              name: Orders
              productVersion: 1.0.0
          outputPorts: []  # <-- empty list, now rejected
    """,
    original_format="YAML",
    original_spec_type="ODPS",
)
```

**After** (at least one resolvable port):

```python
contract = client.contracts.create(
    original_raw="""
        schema: https://opendataproducts.org/schema/v3.0
        version: "3.0"
        product:
          details:
            en:
              productID: orders
              name: Orders
              productVersion: 1.0.0
          outputPorts:
            - name: orders
              contract:
                spec:
                  schema:
                    - name: orders
                      fields:
                        - {name: order_id, type: string}
    """,
    original_format="YAML",
    original_spec_type="ODPS",
)
```

### TypeScript / Node SDK — same shapes

The TypeScript SDK accepts the same `original_raw` payload — only
the calling syntax differs. Ensure your contract templates / fixture
files in `tests/fixtures/` are updated.

## Error-handling patterns

### Catch `STRUCTURELESS_CONTRACT` programmatically

```python
from datahub_interoperability import (
    DataHubClient,
    ValidationError,
)

try:
    contract = client.contracts.create(
        original_raw=raw,
        original_format="YAML",
        original_spec_type="ODCS",
    )
except ValidationError as e:
    if e.code == "STRUCTURELESS_CONTRACT":
        subcode = e.details.get("subcode")
        remediation_url = e.details.get("remediation_url")
        # Surface the deep-link to the user; or fail fast in CI.
        raise SystemExit(
            f"Contract is structureless ({subcode}). "
            f"Open the Schema editor: {remediation_url}"
        )
    raise
```

### CI pipeline guard (pre-flight)

Run the CLI validator before pushing — it catches structureless
contracts locally without a round-trip to the API:

```bash
meshant contract validate contract.yaml || exit 1
```

The CLI exits non-zero on structural-floor violations with the same
subcode taxonomy as the API.

## Backward-compatibility shims (none)

Per the 2026-04-30 ungate directive, **there is no deprecation
period and no per-tenant override**. Customers cannot opt out. The
floor is `always-on` from Phase 227 Wave 1 deployment forward.

If your integration relies on creating placeholder/header-only
contracts and adding structure later, you must:

1. Either: defer contract creation until you have the structure
   ready (recommended).
2. Or: upload a minimum-viable shape (one model, one field —
   typically a placeholder `id: string`) and use
   `PATCH /api/v1/contracts/{id}/` to add the real structure later.
   Each PATCH re-runs the floor check, so the patched body must
   itself satisfy the floor.

## Timeline

| Phase | Date | What |
| ----- | ---- | ---- |
| Wave 0 | T-14 | Tenant admins receive `asset.contract_structureless_pending` heads-up email. Diagnosis-only — no rejections. |
| Wave 1 | T-0 | Validation gate enabled. **API now rejects** structureless contracts with `STRUCTURELESS_CONTRACT`. Self-heal pass runs in parallel. |
| Wave 2 | T+7 | Schema editor open to all roles with modify permission. |
| Wave 3 | T+14 | Bulk self-heal of `pure_odps_with_outputports` cohort completes. |
| Wave 4 | T+30 | Final remediation reminder for residual cohort. |
| Wave 5 | T+44 | Assets backed by still-structureless contracts auto-revert to DRAFT (audit-traceable, reversible via the L6.4 reverse migration). |
| Wave 6 | T+44 onwards | Cleanup — observability metrics + CI gates remain on. |

## Support

- **Operator runbook**: [`docs/runbooks/structureless-contracts.md`](../runbooks/structureless-contracts.md)
- **Error catalog**: [`docs/mvpdocs/reference/error-codes.md`](../mvpdocs/reference/error-codes.md#structureless-contract-codes-phase-227)
- **Canonical shapes**: [`docs/CONTRACTS.md`](../CONTRACTS.md)
- **CSM contact**: open a ticket via your Meshant Customer Success Manager
- **Slack** (internal): `#data-governance` for general triage,
  `#sre-oncall` for production-severity escalations
