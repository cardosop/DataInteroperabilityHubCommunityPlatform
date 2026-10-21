# JOURNEY-CPO-001: Run Compliance Scan for Asset

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-001, UC-COMP-002

## Overview

A Compliance Officer selects an asset, chooses a scan profile, executes
a compliance scan, and reviews the results including risk level, PII
categories, and per-column findings. The journey ends with exporting a
compliance report for regulatory documentation or stakeholder review.

## Journey Steps

1. **Select asset** — The CPO navigates to the "Compliance" section of
   the platform dashboard. A filterable list shows all
   [assets](../concepts/assets.md) in the tenant with their current
   compliance status (not scanned, passed, warning, failed). The CPO
   selects the target asset.

2. **Choose scan profile** — The platform offers pre-configured scan
   profiles (e.g., "GDPR Full," "PCI-DSS," "HIPAA," "Custom"). Each
   profile defines which detectors are active and their sensitivity
   levels. The CPO selects the appropriate profile or creates a custom
   one by enabling/disabling specific PII detectors.

3. **Execute scan** — The CPO clicks "Run Scan." The platform launches
   a [compliance run](../concepts/compliance-runs.md) that analyzes all
   columns in the asset using regex pattern matching, NLP-based named
   entity recognition, and statistical analysis. A progress indicator
   shows scan completion percentage.

4. **Review risk level** — On completion the CPO sees the overall risk
   assessment: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`. The risk level
   is computed from the highest-severity finding, weighted by
   confidence and data volume. A color-coded banner provides an
   at-a-glance summary.

5. **Review PII categories** — The CPO drills into per-column findings.
   Each finding shows the detected PII category (e.g.,
   `PII_DIRECT_EMAIL`, `PII_DIRECT_PHONE`, `PAYMENT_CARD`,
   `PII_QUASI_ZIPCODE`), confidence score (0.0-1.0), number of
   affected rows, and sample matches (automatically redacted). The CPO
   can accept, suppress (false positive), or escalate each finding.

6. **Export report** — The CPO exports the compliance report in PDF or
   JSON format. The PDF report includes an executive summary, risk
   level, finding details, remediation recommendations, and an audit
   trail section showing who ran the scan and when. The report is
   suitable for regulatory submissions and internal compliance reviews.

## Success Criteria

- The compliance scan completes within the expected time frame (under
  10 minutes for datasets up to 1 million rows).
- The risk level accurately reflects the severity of findings.
- All PII categories relevant to the scan profile are detected.
- The exported report contains all required fields for regulatory
  documentation.
- An `compliance.scan_completed` [audit event](../concepts/audit-events.md)
  is recorded with the scan ID, profile used, and result summary.

## Related

- Concepts: [Compliance Runs](../concepts/compliance-runs.md), [Assets](../concepts/assets.md), [Governance](../concepts/governance.md), [Audit Events](../concepts/audit-events.md)
- How-To: [CPO How-To Guides](../personas/compliance-privacy-officer/how-to/)
- Journeys: [JOURNEY-CPO-006](JOURNEY-CPO-006.md) (Automated Compliance), [JOURNEY-DE-004](JOURNEY-DE-004.md) (Set Up Compliance Scanning)
