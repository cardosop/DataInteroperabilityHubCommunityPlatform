# DQ Runs

A DQ (Data Quality) run is a single execution of quality checks against a data [asset](assets.md). Each run evaluates the asset's data against the rules defined in its bound [contract](contracts.md) and produces a detailed report: an overall quality score, per-rule pass/fail results, row-level findings, and suggested remediation actions. DQ runs are the primary mechanism for enforcing data quality standards in Meshant.

DQ runs can be triggered manually, on a schedule, or automatically when an asset enters the `validating` state. Every run is tracked as a [job](jobs.md), providing progress monitoring, cancellation, and retry capabilities.

## Lifecycle

| State | Description |
|---|---|
| `PENDING` | The DQ run has been queued but execution has not started. Waiting for available compute. |
| `RUNNING` | Quality checks are actively executing against the asset's data. Progress percentage is updated periodically. |
| `SUCCEEDED` | All checks completed. Results are available. The overall score and per-rule outcomes are stored. |
| `FAILED` | The run encountered an infrastructure error (not a data quality failure). The job can be retried. |
| `CANCELLED` | A user or system process cancelled the run before completion. Partial results may be available. |

A `SUCCEEDED` run does not mean the data passed all quality checks -- it means the run itself completed without infrastructure errors. The quality results within a successful run may show failing rules and low scores.

## Quality Scoring

Each DQ run produces a composite quality score from 0 to 100 based on weighted rule categories:

| Category | Description | Default Weight |
|---|---|---|
| Completeness | Missing values, null ratios, required field coverage | 25% |
| Accuracy | Value range checks, referential integrity, format validation | 25% |
| Consistency | Cross-field rules, duplicate detection, uniqueness constraints | 20% |
| Timeliness | Freshness checks, timestamp recency, update frequency | 15% |
| Validity | Schema conformance, data type checks, enum membership | 15% |

Weights are configurable per contract. The overall score is the weighted average of category scores. [Governance](governance.md) policies can enforce minimum score thresholds for publishing.

## Findings

Each DQ run produces a list of findings -- individual rule violations detected in the data. A finding contains:

| Field | Description |
|---|---|
| `rule_name` | The name of the quality rule that was violated. |
| `category` | Which quality category the rule belongs to (completeness, accuracy, etc.). |
| `severity` | `error` (hard failure) or `warning` (advisory). |
| `column` | The column where the violation was detected (if applicable). |
| `row_sample` | Up to 10 sample row identifiers where the violation occurred. |
| `message` | Human-readable description of the violation. |
| `expected` | The expected value or pattern from the rule definition. |
| `actual` | The actual value or statistic that triggered the violation. |

Findings are stored with the run and queryable via the findings API. They are retained for the same duration as the run record itself.

## Relationships

- **Assets** -- Every DQ run targets a specific [asset](assets.md). The asset's quality score badge reflects the most recent passing run.
- **Contracts** -- Rules executed in a DQ run are defined in the [contract](contracts.md) bound to the asset. The run records which contract version was used.
- **Jobs** -- Each DQ run is backed by a [job](jobs.md) that tracks execution state, duration, and resource consumption.
- **Datasets** -- The run operates on the physical data within the asset's [datasets](datasets.md).
- **Audit Events** -- DQ run creation, completion, and cancellation are recorded as [audit events](audit-events.md).
- **Webhooks** -- The `dq.completed` event fires when a run finishes, delivering the summary results to configured [webhook](webhooks.md) endpoints.
- **Orchestration** -- DQ runs can be chained with [compliance runs](compliance-runs.md) and publish steps through [orchestration](orchestration.md) workflows.

## MVP Scope

**Available at launch:**

- Manual DQ run triggering via API, CLI, and SDK.
- Automatic triggering on asset state transition to `validating`.
- Scheduled DQ runs (cron-based).
- Quality scoring across all five categories.
- Per-rule pass/fail results with row-level finding details.
- Historical run comparison (score trend over time).
- Webhook notification on completion.

**Post-MVP:**

- Anomaly detection using ML-based quality rules.
- Custom rule authoring in SQL or Python.
- Sampling strategies for large datasets (statistical sampling with confidence intervals).
- DQ run templates for common data patterns.
- Automated remediation suggestions with one-click fix.
- Real-time DQ monitoring for streaming assets.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Trigger DQ run | `POST /api/v1/dq-runs` | `meshant dq run <asset_id>` | `client.dq_runs.create(asset_id)` |
| Get DQ run | `GET /api/v1/dq-runs/{id}` | `meshant dq get <id>` | `client.dq_runs.get(id)` |
| List DQ runs | `GET /api/v1/dq-runs` | `meshant dq list` | `client.dq_runs.list()` |
| Get findings | `GET /api/v1/dq-runs/{id}/findings` | `meshant dq findings <id>` | `client.dq_runs.findings(id)` |
| Cancel DQ run | `POST /api/v1/dq-runs/{id}/cancel` | `meshant dq cancel <id>` | `client.dq_runs.cancel(id)` |
| Get score trend | `GET /api/v1/assets/{id}/dq-trend` | `meshant dq trend <asset_id>` | `client.dq_runs.trend(asset_id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for filtering, pagination, and rule configuration.
