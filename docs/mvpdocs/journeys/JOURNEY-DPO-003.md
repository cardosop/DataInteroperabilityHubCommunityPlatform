# JOURNEY-DPO-003: Manage Asset Lifecycle

**Persona:** [Data Product Owner](../personas/data-product-owner/)
**Use Cases:** UC-DPO-005, UC-DPO-006

## Overview

A Data Product Owner manages an existing asset through its full
lifecycle: reviewing its current state on the asset dashboard, updating
metadata, triggering re-validation, archiving obsolete versions, and
restoring previously archived assets when needed. This journey ensures
assets remain accurate, governed, and trustworthy over time.

## Journey Steps

1. **View asset dashboard** — The DPO navigates to the asset list
   and opens a specific [asset](../concepts/assets.md). The dashboard
   shows current state (`draft`, `active`, `published`, `archived`),
   latest quality score, compliance status, version history, and
   recent [audit events](../concepts/audit-events.md).

2. **Update metadata** — The DPO edits asset metadata: name,
   description, domain tags, owner assignment, and custom key-value
   labels. Changes are versioned; the previous metadata snapshot is
   retained in the version history. An `asset.metadata_updated` audit
   event is recorded.

3. **Trigger re-validation** — The DPO clicks "Re-validate" to
   launch a new [DQ run](../concepts/dq-runs.md) and
   [compliance scan](../concepts/compliance-runs.md) against the
   current data and contract. This is useful after upstream data
   refreshes or contract amendments. Results appear in the quality
   trend chart alongside historical runs.

4. **Review version history** — The DPO opens the "Versions" tab to
   see every schema and metadata change. Each version is timestamped
   and linked to the user who made the change. The DPO can diff any
   two versions side-by-side to understand what changed and why.

5. **Archive old versions** — When an asset is no longer actively
   consumed the DPO transitions it to `archived`. Archived assets are
   excluded from marketplace search and API queries by default but
   remain accessible for [lineage](../concepts/lineage.md) tracing
   and regulatory audit. An `asset.archived` webhook fires to notify
   downstream consumers.

6. **Restore if needed** — If an archived asset is needed again the
   DPO clicks "Restore," which transitions the asset back to `active`.
   A new DQ run is automatically triggered to confirm the data is
   still valid. The restoration is logged as an `asset.restored`
   audit event.

## Success Criteria

- Metadata updates are versioned with full diff history.
- Re-validation produces a new DQ and compliance run linked to the
  asset.
- Archival removes the asset from active search but preserves all
  data and audit trail.
- Restoration triggers automatic re-validation.
- All state transitions produce corresponding audit events and
  webhooks.

## Related

- Concepts: [Assets](../concepts/assets.md), [Versioning](../concepts/versioning.md), [Lineage](../concepts/lineage.md), [Audit Events](../concepts/audit-events.md)
- How-To: [DPO How-To Guides](../personas/data-product-owner/how-to/)
- Journeys: [JOURNEY-DPO-001](JOURNEY-DPO-001.md) (Onboard), [JOURNEY-DPO-004](JOURNEY-DPO-004.md) (Monitor Quality)
