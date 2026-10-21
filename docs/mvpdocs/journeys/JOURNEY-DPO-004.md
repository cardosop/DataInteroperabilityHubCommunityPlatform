# JOURNEY-DPO-004: Monitor Asset Quality

**Persona:** [Data Product Owner](../personas/data-product-owner/)
**Use Cases:** UC-DPO-007, UC-DQ-001

## Overview

A Data Product Owner proactively monitors the ongoing data quality of
their assets by reviewing the DQ dashboard, analyzing trend charts,
investigating failures, re-running checks, and updating quality
profiles. This journey ensures that published data products maintain
consumer trust through continuous quality assurance.

## Journey Steps

1. **View DQ dashboard** — The DPO navigates to the "Data Quality"
   section from the asset detail page. The dashboard displays the
   current overall quality score (0-100), individual check results
   grouped by dimension (completeness, uniqueness, validity, accuracy,
   timeliness), and a history of recent
   [DQ runs](../concepts/dq-runs.md).

2. **Review trend charts** — The DPO selects a time range (7d, 30d,
   90d) to view quality score trends. Line charts show score evolution
   per dimension, highlighting regressions. A red threshold line
   indicates the minimum acceptable score configured in the tenant
   settings or [data contract](../concepts/contracts.md).

3. **Investigate failures** — The DPO clicks a failing check to drill
   down. The detail view shows the check rule definition, expected vs.
   actual values, affected row count, sample failing rows (up to 100),
   and the column(s) involved. For statistical checks a distribution
   histogram is displayed.

4. **Re-run checks** — After identifying the root cause (e.g.,
   upstream schema change, data refresh delay) the DPO can re-run
   individual checks or the full DQ profile. The new run is linked
   to the previous run for comparison. Results update the trend chart
   in real time.

5. **Update quality profile** — If a check is no longer relevant or a
   new check is needed the DPO edits the DQ profile. They can add
   custom rules (regex patterns, value ranges, cross-column
   validations), adjust severity levels (warning vs. critical), and
   modify thresholds. Changes take effect on the next scheduled or
   manual run.

6. **Set up alerts** — The DPO configures alert rules that fire when
   the quality score drops below a threshold or a specific check fails
   consecutively. Alerts are delivered via email and
   [webhooks](../concepts/webhooks.md) and include a deep link to the
   failing check.

## Success Criteria

- The DQ dashboard reflects the latest run results within 60 seconds
  of completion.
- Trend charts accurately display historical scores with no gaps.
- Drill-down provides actionable detail including sample failing rows.
- Re-run results are linked to previous runs for comparison.
- Alert notifications fire within 5 minutes of a threshold breach.
- Quality profile changes are versioned and auditable.

## Related

- Concepts: [DQ Runs](../concepts/dq-runs.md), [Contracts](../concepts/contracts.md), [Assets](../concepts/assets.md), [Webhooks](../concepts/webhooks.md)
- How-To: [DPO How-To Guides](../personas/data-product-owner/how-to/)
- Journeys: [JOURNEY-DPO-001](JOURNEY-DPO-001.md) (Onboard Asset), [JOURNEY-DE-003](JOURNEY-DE-003.md) (Configure DQ Checks)
