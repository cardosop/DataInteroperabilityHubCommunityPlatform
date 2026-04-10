# Orchestration

Orchestration in Meshant coordinates multi-step workflows that chain platform operations into automated pipelines. A typical orchestration workflow runs a [DQ check](dq-runs.md), followed by a [compliance scan](compliance-runs.md), and then publishes the [asset](assets.md) to the [Marketplace](marketplace-listings.md) -- all as a single, trackable unit of work. Orchestration eliminates the need for external workflow tools when the operations are entirely within the Meshant platform.

Each orchestration workflow is represented as a directed acyclic graph (DAG) of steps, where each step is a [job](jobs.md). Steps can declare dependencies on other steps, conditional branching based on prior step results, and failure handling policies. The orchestration engine manages execution order, parallelism, and error recovery.

## Lifecycle

| State | Description |
|---|---|
| `draft` | The workflow definition is being authored. Steps and dependencies are being configured. |
| `active` | The workflow is ready to be triggered. It can be run manually, on schedule, or by event. |
| `disabled` | The workflow is temporarily disabled. It will not execute even if triggered. |
| `archived` | The workflow is no longer in use. Historical execution records are preserved. |

Individual workflow **executions** follow the standard [job](jobs.md) lifecycle: PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED.

## Workflow Definition

A workflow consists of:

| Component | Description |
|---|---|
| Steps | Individual operations: DQ run, compliance scan, state transition, export, notification. Each step maps to a job type. |
| Dependencies | Directed edges between steps. A step runs only after all its dependencies have succeeded. |
| Conditions | Optional guards on steps. For example: "only run the publish step if the DQ score is above 85." |
| Failure policy | What happens when a step fails: `stop` (halt the entire workflow), `skip` (mark the step as skipped and continue), or `retry` (retry the step per its retry policy). |
| Timeout | Maximum duration for the entire workflow. Defaults to the sum of individual step timeouts. |

Example workflow:

```
upload_dataset
    |
    v
run_dq_check  (condition: dataset.status == "available")
    |
    v
run_compliance_scan  (parallel with: notify_data_steward)
    |
    v
publish_to_marketplace  (condition: dq.score >= 85 AND compliance.risk_level != "critical")
```

## Step Types

| Step Type | Description |
|---|---|
| `dq_run` | Trigger a [DQ run](dq-runs.md) against a specified asset. |
| `compliance_scan` | Trigger a [compliance run](compliance-runs.md) against a specified asset. |
| `state_transition` | Transition an [asset](assets.md) to a new lifecycle state. |
| `marketplace_publish` | Publish an asset as a [marketplace listing](marketplace-listings.md). |
| `export` | Export data to an external destination (S3, GCS, webhook URL). |
| `notification` | Send a notification via [webhook](webhooks.md), email, or Slack. |
| `wait` | Pause execution for a specified duration or until a condition is met. |
| `approval` | Pause execution and wait for a human approval from a designated [user](users-and-roles.md). |

## Relationships

- **Jobs** -- Each workflow execution is a parent [job](jobs.md). Each step within the workflow is a child job. The parent job tracks overall progress and aggregates step results.
- **DQ Runs** -- DQ run steps create [DQ runs](dq-runs.md) and wait for their completion before evaluating conditions.
- **Compliance Runs** -- Compliance scan steps create [compliance runs](compliance-runs.md) and feed their results into downstream conditions.
- **Assets** -- Workflows operate on [assets](assets.md), coordinating the validation and publication pipeline.
- **Marketplace Listings** -- Publish steps create or update [marketplace listings](marketplace-listings.md).
- **Webhooks** -- Notification steps can deliver messages to [webhook](webhooks.md) endpoints. Workflow completion events are also available as webhook events.
- **Audit Events** -- Workflow creation, execution, step completions, and failures are all recorded as [audit events](audit-events.md).
- **Lineage** -- Workflows that include transformation steps create [lineage](lineage.md) edges connecting input and output assets.

## MVP Scope

**Available at launch:**

- Workflow definition via API and CLI (YAML-based definition format).
- Sequential and parallel step execution.
- Step dependencies and ordering.
- Conditional step execution based on prior step results.
- Failure policies: stop, skip, retry.
- Manual and scheduled workflow triggering.
- Workflow execution monitoring with per-step status.
- Step types: dq_run, compliance_scan, state_transition, notification.
- Workflow listing, filtering by status and trigger type.

**Post-MVP:**

- Visual workflow editor in the web UI (drag-and-drop DAG builder).
- Event-driven triggering (start workflow when an asset is created or updated).
- Approval steps with role-based routing and timeout escalation.
- Workflow templates for common patterns (validate-and-publish, ingest-and-scan).
- Cross-asset workflows (operate on a batch of assets matching a filter).
- Workflow versioning with rollback.
- SLA monitoring and alerting for workflow execution duration.
- Export and marketplace_publish step types.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Create workflow | `POST /api/v1/orchestration/workflows` | `meshant orchestration create` | `client.orchestration.create()` |
| Get workflow | `GET /api/v1/orchestration/workflows/{id}` | `meshant orchestration get <id>` | `client.orchestration.get(id)` |
| List workflows | `GET /api/v1/orchestration/workflows` | `meshant orchestration list` | `client.orchestration.list()` |
| Trigger workflow | `POST /api/v1/orchestration/workflows/{id}/trigger` | `meshant orchestration trigger <id>` | `client.orchestration.trigger(id)` |
| Get execution | `GET /api/v1/orchestration/executions/{id}` | `meshant orchestration execution <id>` | `client.orchestration.execution(id)` |
| Cancel execution | `POST /api/v1/orchestration/executions/{id}/cancel` | `meshant orchestration cancel <id>` | `client.orchestration.cancel(id)` |
| List executions | `GET /api/v1/orchestration/executions` | `meshant orchestration executions` | `client.orchestration.executions()` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for workflow definition YAML schema and step configuration options.
