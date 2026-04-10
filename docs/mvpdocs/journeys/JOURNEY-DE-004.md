# JOURNEY-DE-004: Set Up Compliance Scanning

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DE-004, UC-COMP-001

## Overview

A Data Engineer enables and configures compliance scanning for an
asset to detect PII, sensitive data categories, and regulatory risk.
This journey covers enabling compliance for an asset, configuring the
scan profile, running the initial scan, reviewing findings, and
setting up an ongoing scan schedule integrated into the data pipeline.

## Journey Steps

1. **Enable compliance for asset** — The DE navigates to the asset's
   "Compliance" tab (or uses the SDK) and enables compliance scanning.
   Enabling compliance attaches a default scan profile to the asset
   based on the tenant's configuration. The profile determines which
   detectors are active (PII, payment card, health data, etc.).

   ```python
   asset.compliance.enable()
   ```

2. **Configure scan profile** — The DE customizes the scan profile to
   match the dataset's regulatory context. Configuration options
   include:

   - **Detectors:** Enable/disable specific PII categories
     (`PII_DIRECT_EMAIL`, `PII_DIRECT_PHONE`, `PAYMENT_CARD`,
     `HEALTH_DATA`, `PII_QUASI_ZIPCODE`, etc.).
   - **Sampling:** Full scan or sample-based (e.g., 10,000 rows) for
     large datasets.
   - **Risk thresholds:** Maximum acceptable risk level
     (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) for the asset to pass
     the compliance gate.
   - **Column exclusions:** Columns known to contain permitted PII
     (e.g., an encrypted email field) can be excluded from detection.

3. **Run initial scan** — The DE triggers the first
   [compliance run](../concepts/compliance-runs.md) via CLI or SDK:

   ```bash
   meshant compliance scan --asset <asset-id>
   ```

   The platform scans column values using regex, NLP-based NER, and
   statistical pattern matching. The scan produces a report with
   per-column findings, detected PII categories, confidence scores,
   and an overall risk level assessment.

4. **Review PII findings** — The DE reviews the scan results. Each
   finding includes the column name, detected category, confidence
   (0.0-1.0), sample matches (redacted), and a recommended action
   (mask, encrypt, remove, or accept risk). The DE can mark findings
   as false positives, which suppresses them in future scans.

5. **Set up ongoing schedule** — The DE configures a recurring
   compliance scan schedule (e.g., on every data upload or weekly).
   The schedule can be defined via cron syntax or event-driven
   triggers. Results from each scan update the asset's compliance
   badge and are visible to [Data Consumers](../personas/data-consumer/)
   on the marketplace listing.

   ```python
   asset.compliance.schedule(cron="0 2 * * 0")  # weekly Sunday 2 AM
   ```

## Success Criteria

- Compliance scanning is enabled with an appropriate detector profile.
- The initial scan completes and produces a structured report.
- PII findings include actionable detail (column, category, confidence).
- False positive suppression is persisted across subsequent scans.
- The ongoing schedule executes on time and updates the compliance badge.
- All compliance runs produce [audit events](../concepts/audit-events.md).

## Related

- Concepts: [Compliance Runs](../concepts/compliance-runs.md), [Assets](../concepts/assets.md), [Governance](../concepts/governance.md), [Audit Events](../concepts/audit-events.md)
- How-To: [DE How-To Guides](../personas/data-engineer/how-to/), [CPO How-To Guides](../personas/compliance-privacy-officer/how-to/)
- Journeys: [JOURNEY-CPO-001](JOURNEY-CPO-001.md) (Run Compliance Scan), [JOURNEY-CPO-006](JOURNEY-CPO-006.md) (Configure Automated Compliance)
