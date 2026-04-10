# JOURNEY-DPO-005: Configure Data Contracts

**Persona:** [Data Product Owner](../personas/data-product-owner/)
**Use Cases:** UC-DPO-008, UC-CONTRACT-001

## Overview

A Data Product Owner creates and manages data contracts that codify
the expected schema, quality rules, and SLA targets for their data
assets. This journey covers authoring a YAML contract, validating it
via the CLI, uploading it to the platform, binding it to an asset,
and managing subsequent versions.

## Journey Steps

1. **Write YAML contract** — The DPO authors a data contract in
   [ODCS-compliant](../concepts/contracts.md) YAML format. The contract
   defines the dataset name, owner, schema (column names, types,
   constraints), quality rules (completeness thresholds, uniqueness
   keys, regex patterns), and SLA targets (freshness, availability).
   A template is available in the platform documentation.

2. **Validate via CLI** — The DPO runs `meshant contract validate
   contract.yaml` using the Meshant CLI. The validator checks ODCS
   structural compliance, detects duplicate column names, validates
   rule syntax, and reports warnings for deprecated fields. The DPO
   fixes any errors before proceeding.

3. **Upload to platform** — The DPO uploads the validated contract
   via the UI ("Contracts > New Contract") or the API/SDK. The
   platform stores the contract in `draft` state and assigns a
   version number (starting at `1.0.0`). The contract is visible only
   within the owning tenant.

4. **Attach to asset** — The DPO navigates to an existing
   [asset](../concepts/assets.md) and selects "Bind Contract." The
   platform performs a reconciliation check, comparing the asset's
   current schema against the contract's expected schema and
   highlighting any mismatches. Once resolved the contract moves to
   `active` state.

5. **Manage versions** — When the data evolves the DPO creates a new
   contract version. The platform supports semantic versioning:
   - **Patch** (1.0.x): rule threshold adjustments, description edits.
   - **Minor** (1.x.0): new optional columns, relaxed constraints.
   - **Major** (x.0.0): breaking changes (column removal, type change).

   Promoting a new version to `active` automatically moves the
   previous version to `superseded`. Historical
   [DQ runs](../concepts/dq-runs.md) retain their reference to the
   contract version they executed against.

6. **Review contract history** — The DPO views the version timeline
   showing all contract iterations, who changed what, and which DQ
   runs were executed per version. Diffs between versions are
   available for audit purposes.

## Success Criteria

- The contract passes CLI validation with zero errors.
- The contract is stored in the platform with correct ODCS structure.
- Binding to an asset succeeds after all schema conflicts are resolved.
- Version promotion correctly transitions states (`active` to
  `superseded` for the old version).
- All contract operations produce [audit events](../concepts/audit-events.md).

## Related

- Concepts: [Contracts](../concepts/contracts.md), [Assets](../concepts/assets.md), [DQ Runs](../concepts/dq-runs.md), [Versioning](../concepts/versioning.md)
- How-To: [DPO How-To Guides](../personas/data-product-owner/how-to/), [DE How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DE-001](JOURNEY-DE-001.md) (Contract-First Onboarding), [JOURNEY-DPO-001](JOURNEY-DPO-001.md) (Data-First Onboarding)
