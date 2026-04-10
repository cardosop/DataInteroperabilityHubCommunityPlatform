# JOURNEY-DE-003: Configure Data Quality Checks

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DE-003, UC-DQ-001

## Overview

A Data Engineer defines, configures, and automates data quality checks
for an asset. This journey covers creating a DQ profile with custom
rules, setting pass/fail thresholds, configuring a run schedule,
executing the first check, and integrating DQ results into data
pipeline orchestration.

## Journey Steps

1. **Define DQ profile** — The DE creates a DQ profile either inline
   in the [data contract](../concepts/contracts.md) YAML or as a
   standalone configuration. The profile lists checks by dimension:

   - **Completeness:** Percentage of non-null values per column
     (e.g., `email` must be >= 99% non-null).
   - **Uniqueness:** Columns or column combinations that must be
     unique (e.g., `transaction_id`).
   - **Validity:** Regex patterns, enum membership, or range checks
     (e.g., `status IN ('active','closed')`).
   - **Accuracy:** Cross-reference checks against a reference dataset
     or lookup table.
   - **Timeliness:** Maximum age of the newest record (e.g., data
     must not be older than 24 hours).

2. **Set thresholds** — For each check the DE sets a pass/fail
   threshold and severity. For example, a completeness check on
   `email` may be set to `threshold: 99.0, severity: critical` while
   a format check on `phone` may use `threshold: 95.0, severity:
   warning`. Critical failures block asset publication; warnings are
   advisory.

3. **Configure schedule** — The DE sets up a recurring schedule for
   DQ runs using cron syntax (e.g., `0 6 * * *` for daily at 06:00
   UTC). Schedules can also be event-driven, triggering on data
   upload completion via [webhooks](../concepts/webhooks.md). The
   schedule is stored as part of the asset configuration.

4. **Run first check** — The DE triggers the initial
   [DQ run](../concepts/dq-runs.md) via the CLI (`meshant dq run
   --asset <id>`) or SDK (`asset.run_dq()`). The platform executes
   all checks in the profile against the current data snapshot and
   returns a structured result with per-check status, observed value,
   threshold, and affected row count.

5. **Integrate results into pipeline** — The DE uses the DQ run
   result in their orchestration tool (Airflow, Dagster, Prefect) as
   a quality gate. A typical pattern:

   ```python
   result = asset.run_dq().wait()
   if result.status != "passed":
       raise QualityGateError(result.summary)
   # proceed with downstream processing
   ```

   Failed gates halt the pipeline and send alerts. The DE can also
   push DQ metrics to observability platforms via the
   [webhooks](../concepts/webhooks.md) integration.

## Success Criteria

- The DQ profile contains at least one check per quality dimension
  relevant to the dataset.
- Thresholds and severities are explicitly configured for each check.
- The scheduled run executes on time and produces results.
- The first run returns a structured result with per-check detail.
- Pipeline integration correctly gates on DQ status.
- All DQ runs are recorded as [audit events](../concepts/audit-events.md).

## Related

- Concepts: [DQ Runs](../concepts/dq-runs.md), [Contracts](../concepts/contracts.md), [Webhooks](../concepts/webhooks.md), [Assets](../concepts/assets.md)
- How-To: [DE How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DPO-004](JOURNEY-DPO-004.md) (Monitor Quality), [JOURNEY-DE-001](JOURNEY-DE-001.md) (Contract-First Onboarding)
