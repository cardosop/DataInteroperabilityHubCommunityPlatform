# JOURNEY-DE-001: Programmatic Contract-First Onboarding

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DE-001, UC-DE-002, UC-CONTRACT-001

## Overview

A Data Engineer uses the Meshant CLI and Python SDK to onboard a data
asset programmatically, starting from a data contract. This
"contract-first" flow defines the expected schema before any data
arrives, enabling CI/CD integration and infrastructure-as-code
practices for data product management.

## Journey Steps

1. **Write contract YAML** — The DE authors an ODCS-compliant
   [data contract](../concepts/contracts.md) in YAML, typically stored
   in version control alongside pipeline code. The contract specifies
   dataset name, owner, column definitions with types and constraints,
   quality rules, and freshness SLAs.

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

## Related

- Concepts: [Contracts](../concepts/contracts.md), [Assets](../concepts/assets.md), [DQ Runs](../concepts/dq-runs.md), [Compliance Runs](../concepts/compliance-runs.md)
- How-To: [DE How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DPO-001](JOURNEY-DPO-001.md) (Data-First Onboarding), [JOURNEY-DE-003](JOURNEY-DE-003.md) (Configure DQ Checks)
