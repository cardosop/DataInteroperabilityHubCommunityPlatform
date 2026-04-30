# JOURNEY-DE-001: Programmatic Contract-First Onboarding

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DE-001, UC-DE-002, UC-CONTRACT-001

## Overview

A Data Engineer uses the Meshant CLI and Python SDK to onboard a data
asset programmatically, starting from a data contract. This
"contract-first" flow defines the expected schema before any data
arrives, enabling CI/CD integration and infrastructure-as-code
practices for data product management.

## Required contract shapes (Phase 227 Wave 1)

Both ODCS and ODPS contracts MUST satisfy the **structural floor
invariant** before they can be activated or published: at least one
`models[*].fields[*]` entry OR a top-level `schema.fields[*]` entry,
populated with at least one resolvable field after normalisation.
Empty model lists, empty `outputPorts[]`, and `models=[{"fields":[]}]`
all violate the floor and produce HTTP 400 with
`error.code = "STRUCTURELESS_CONTRACT"`.

### ODCS — minimum viable shape

```yaml
kind: DataContract
apiVersion: v3.0.2
id: customer-transactions          # required
name: customer-transactions
version: 1.0.0
status: active
schema:
  - name: transactions              # at least one model
    fields:                         # with at least one field
      - name: transaction_id
        type: string
        primaryKey: true
      - name: amount
        type: decimal
```

### ODPS — minimum viable shape (v3.x / v4.x / Bitol v1.0.0)

```yaml
schema: https://opendataproducts.org/schema/v3.0
version: "3.0"
product:
  details:
    en:
      productID: customer-transactions
      name: Customer Transactions
      productVersion: 1.0.0
  outputPorts:                      # at least one outputPort
    - name: transactions
      contract:
        spec:
          schema:                   # with resolvable schema OR contractId
            - name: transactions
              fields:
                - {name: transaction_id, type: string}
                - {name: amount, type: decimal}
```

Either `port.contractId` (referencing an existing structural ODCS
contract) or an inline `port.contract.spec.schema.fields[]` /
`port.dataSchema.fields[]` is sufficient. See the
[CONTRACTS.md SSOT](../../CONTRACTS.md) for full per-version shapes.

## Journey Steps

1. **Write contract YAML** — The DE authors an ODCS-compliant
   [data contract](../concepts/contracts.md) in YAML, typically stored
   in version control alongside pipeline code. The contract specifies
   dataset name, owner, column definitions with types and constraints,
   quality rules, and freshness SLAs. The structural-floor invariant
   above is enforced at create-time by the API; CI pipelines can
   pre-flight via `meshant contract validate <file>` before pushing.

   ```yaml
   # Example snippet
   kind: DataContract
   apiVersion: odcs/v1
   info:
     name: customer-transactions
     owner: data-platform-team
   schema:
     columns:
       - name: transaction_id
         type: string
         unique: true
       - name: amount
         type: decimal
         not_null: true
   ```

2. **Validate with CLI** — The DE runs `meshant contract validate
   contract.yaml` in a CI pipeline or locally. The validator checks
   ODCS structure, rule syntax, and cross-references. Exit code 0
   means the contract is valid; non-zero prints actionable error
   messages. This step is typically a CI gate that blocks merges on
   invalid contracts.

3. **Create asset via SDK** — The DE uses the Python SDK to create
   an asset programmatically:

   ```python
   from meshant import DataHubClient
   client = DataHubClient(api_key="...")
   asset = client.assets.create(
       name="customer-transactions",
       contract_path="contract.yaml",
       domain="finance",
   )
   ```

   The SDK uploads the contract, creates the asset in `draft` state,
   and returns the asset ID. The contract is bound automatically.

4. **Attach data** — The DE uploads the data file (CSV, Parquet, or
   via streaming API) and attaches it to the asset:

   ```python
   asset.upload_data("transactions_2026_q1.parquet")
   ```

   The platform validates the uploaded data against the contract
   schema and reports mismatches immediately.

5. **Trigger DQ programmatically** — The DE triggers data quality
   and compliance checks via the SDK:

   ```python
   dq_run = asset.run_dq()
   compliance_run = asset.run_compliance()
   dq_run.wait()  # blocks until complete
   ```

   Results are returned as structured objects for integration into
   pipeline orchestration (pass/fail gates, alerting).

## Success Criteria

- The contract passes CLI validation with exit code 0.
- The asset is created programmatically with the contract bound.
- Data upload succeeds and schema reconciliation passes.
- DQ and compliance runs complete and return structured results.
- The entire flow can execute unattended in a CI/CD pipeline.
- All operations produce [audit events](../concepts/audit-events.md).

## Error envelopes (Phase 227 Wave 1)

| HTTP | `error.code` | When |
| ---- | ------------ | ---- |
| 400 | `STRUCTURELESS_CONTRACT` | The submitted contract has no resolvable models or schema fields. `error.details.subcode` ∈ `{STRUCTURELESS_ODPS_NO_PORTS, STRUCTURELESS_ODCS_NO_SCHEMA, STRUCTURELESS_GENERIC, STRUCTURELESS_CYCLIC_PORTS}`. CI pipelines should treat this as a hard failure and link to `error.details.remediation_url` in the PR comment. |
| 400 | `VALIDATION_ERROR` | Pydantic-level rejection (missing `info.name`, malformed JSON, etc.) |
| 400 | `SCHEMA_TOO_DEEP` | ODCS nested-properties walker hit the configured `CONTRACTS_MAX_NESTING_DEPTH` (default 20). |
| 400 | `INVALID_YAML` | YAML body contains an unsafe construct (`!!python/object/...`). |
| 412 | `PRECONDITION_FAILED` | `If-Match` ETag mismatch on PATCH — pipeline must re-fetch and merge. |
| 413 | `PAYLOAD_TOO_LARGE` | `original_raw` exceeds the 2 MB cap. |

See the [error catalog](../reference/error-codes.md#structureless-contract-codes-phase-227) for the full code taxonomy and remediation copy.

## Related

- Concepts: [Contracts](../concepts/contracts.md), [Assets](../concepts/assets.md), [DQ Runs](../concepts/dq-runs.md), [Compliance Runs](../concepts/compliance-runs.md)
- How-To: [DE How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DPO-001](JOURNEY-DPO-001.md) (Data-First Onboarding), [JOURNEY-DE-003](JOURNEY-DE-003.md) (Configure DQ Checks)
