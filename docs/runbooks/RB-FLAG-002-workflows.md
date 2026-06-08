# RB-FLAG-002 — Workflows Feature Flag

**Flag:** `workflows_enabled`
**Stage:** GA
**Owner:** catalog-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| "Workflows unavailable" in UI | Flag disabled for tenant | `GET /api/v1/admin/tenants/{id}/feature-flags/` → `workflows_enabled` |
| Workflow stuck in PENDING | Executor queue stalled; Prefect agent down | `workflow_execution_duration_seconds`; Prefect health; Redis queue depth |
| Workflow fails immediately | SDK/Prefect version mismatch; invalid DAG definition | `workflow_execution_errors_total`; job logs; workflow definition validation |
| All workflows timing out | Resource exhaustion; executor OOM | `workflow_execution_timeout_total`; node metrics; executor pod status |
| SDK workflow deploy fails | Client version skew; auth token expired | SDK version check; `datahub version` output; API key validity |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/workflows.json`
- **Primary:** `workflow_execution_duration_seconds{status, workflow_type}`
- **Error rate:** `workflow_execution_errors_total`
- **Queue:** `workflow_queue_depth{queue_name}`
- **Audit:** `WORKFLOW_EXECUTED`, `WORKFLOW_DEFINITION_CREATED`

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Check executor health: Prefect server + agent status; Redis connectivity
3. Inspect recent executions: `GET /api/v1/jobs/?job_type=WORKFLOW&limit=20`
4. Verify SDK compatibility: `datahub version` → SDK version matches server
5. Test minimal workflow: deploy a hello-world workflow; verify execution completes within 30s
6. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=workflows_enabled`

## Escalation

- **P3** — Individual workflow type degraded (<5% failure rate increase)
- **P2** — Executor queue backlog >100 jobs or >10min delay
- **P1** — All workflows failing across multiple tenants (executor down)

## Related

- `docs/runbooks/workflow-dr.md` — Disaster recovery procedures
- `docs/runbooks/workflow-stuck.md` — Stuck workflow remediation
- `docs/runbooks/warehouse-dr.md` — Warehouse connectivity DR (workflows depend on warehouse)

## Maintenance

- **Owner:** Catalog Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16
