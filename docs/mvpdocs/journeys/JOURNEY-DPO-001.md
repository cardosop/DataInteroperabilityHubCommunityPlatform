# JOURNEY-DPO-001: Onboard New Asset via Data-First Flow

**Persona:** [Data Product Owner](../personas/data-product-owner/)
**Use Cases:** UC-DPO-001, UC-DPO-002, UC-DPO-003

## Overview

A Data Product Owner uploads a raw data file (CSV or Parquet), lets the
platform infer the schema, reconciles it against an optional data
contract, runs data quality and compliance checks, reviews results, and
publishes the asset as a draft. This "data-first" flow is the fastest
path from raw file to governed data product.

## Journey Steps

1. **Upload CSV or Parquet** — From the tenant dashboard the DPO clicks
   "New Asset" and selects the Data-First flow. They drag-and-drop or
   browse for a local file (CSV up to 500 MB, Parquet up to 2 GB). The
   platform streams the upload and displays a progress indicator.

2. **Review inferred schema** — The platform analyzes the first 10,000
   rows to infer column names, data types, nullability, and basic
   statistics (distinct count, min/max, sample values). The DPO sees
   an editable schema table and can rename columns, override types, or
   add descriptions.

3. **Reconcile with contract (optional)** — If a
   [data contract](../concepts/contracts.md) already exists the DPO
   selects it from a dropdown. The platform highlights mismatches
   between the inferred schema and the contract (missing columns, type
   conflicts, extra fields). The DPO resolves each conflict inline.

4. **Run data quality checks** — The DPO clicks "Run DQ" to execute
   the default [DQ profile](../concepts/dq-runs.md) (or a contract-
   defined profile). Checks include completeness, uniqueness,
   format conformance, and statistical outlier detection. Results are
   displayed as a pass/fail summary with drill-down per column.

5. **Run compliance scan** — The DPO triggers a
   [compliance scan](../concepts/compliance-runs.md) to detect PII
   categories (email, phone, SSN, payment card) and assess overall
   risk level (LOW / MEDIUM / HIGH / CRITICAL). Findings are listed
   per column with recommended remediations.

6. **Review results** — The DPO reviews the combined DQ and compliance
   dashboard. Each check shows status, severity, and affected rows.
   The DPO can accept, suppress, or annotate individual findings.

7. **Publish as draft** — Once satisfied the DPO saves the asset in
   `draft` state. The [asset](../concepts/assets.md) is now visible
   within the tenant, carries its inferred (or reconciled) schema, and
   retains all DQ/compliance run history. It is ready for further
   enrichment or promotion to `active`.

## Success Criteria

- The asset exists in `draft` state with a complete schema.
- At least one DQ run and one compliance run are recorded.
- All schema conflicts (if a contract was attached) are resolved.
- An `asset.created` [audit event](../concepts/audit-events.md) is
  logged with the upload method `data_first`.
- The raw file is stored in the tenant's object storage with
  server-side encryption (AES-256).

## Related

- Concepts: [Assets](../concepts/assets.md), [Contracts](../concepts/contracts.md), [DQ Runs](../concepts/dq-runs.md), [Compliance Runs](../concepts/compliance-runs.md)
- How-To: [DPO How-To Guides](../personas/data-product-owner/how-to/)
- Journeys: [JOURNEY-DPO-002](JOURNEY-DPO-002.md) (Publish to Marketplace), [JOURNEY-DE-001](JOURNEY-DE-001.md) (Contract-First Onboarding)
