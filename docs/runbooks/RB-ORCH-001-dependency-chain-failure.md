# RB-ORCH-001 — Dependency Chain Failure

**Owner:** data-platform@meshant.com | **Created:** 2026-05-19

## 1. Overview

The pipeline dependency graph auto-derives dependencies from lineage edges and enforces execution ordering. A dependency chain failure means a downstream pipeline was blocked, skipped, or deferred because one or more upstream dependencies did not complete successfully. This runbook covers diagnosis and recovery for stuck dependency chains, propagation failures, and manual override procedures.

## 2. Symptoms

| Symptom | Likely Cause |
|---------|-------------|
| Pipeline stuck in `PENDING_DEPENDENCY` > timeout | Upstream dependency never completed; upstream pipeline crashed or was cancelled |
| Pipeline skipped with `SKIPPED_UPSTREAM_FAILED` | Upstream pipeline FAILED; failure propagation marked downstream |
| `CIRCULAR_DEPENDENCY` on preview/dependency endpoint | Self-referential or mutually-dependent pipeline pair |
| `DEPLOY_PREVIEW_BLOCKED` on deploy preview | Unsatisfied dependencies or cycle detected in target deployment chain |
| `WEBHOOK_URL_INVALID` on dependency creation | Alert webhook URL targets private IP or meshant.com domain |
| Trigger engine events not firing | `pipeline_dependency_enabled` flag is off; trigger engine not registered |
| `PipelineRunDependency` rows missing | `DependencyAwareExecutor` or trigger engine not invoked for completed runs |
| Downstream trigger batch job stuck in PENDING | `DEPENDENCY_TRIGGER_BATCH` RQ worker not running |

## 3. Investigation

### 3.1 Check dependency graph
```bash
datahub orchestration dependencies list --pipeline-type <type> --pipeline-id <id>
```

### 3.2 Check for cycles
```bash
datahub orchestration dependencies preview --pipeline-type <type> --pipeline-id <id>
```
If `cycle_free: false`, inspect the graph for self-referential edges.

### 3.3 Check pipeline status
```bash
datahub dq get <run_id>
datahub compliance get <run_id>
```

### 3.4 Check trigger engine registration
```bash
python manage.py shell -c "
from hub.apps.orchestration.trigger_engine import register_signals
register_signals()
print('Signals re-registered')
"
```

### 3.5 Check batch job queue
```bash
datahub jobs list --type DEPENDENCY_TRIGGER_BATCH
```

### 3.6 Verify feature flag
```python
from hub.apps.tenants.models import Tenant
t = Tenant.objects.get(slug='<slug>')
print(t.pipeline_dependency_enabled)
```

## 4. Remediation

- **Stuck in PENDING_DEPENDENCY:** If the upstream completed but the trigger didn't fire, manually re-run:
  ```bash
  python manage.py shell -c "
  from hub.apps.orchestration.trigger_engine import _on_pipeline_terminal
  _on_pipeline_terminal('<tenant_id>', '<pipeline_type>', '<pipeline_id>', 'SUCCEEDED')
  "
  ```
- **Cycle detected:** Remove the cyclic edge via the dependency list endpoint or admin. Re-derive from lineage using `derive_dependencies_from_lineage --tenant-id <id>`.
- **Flag off:** Enable `pipeline_dependency_enabled` for the tenant in admin or via API.
- **Batch job stuck:** Restart the RQ worker processing the `job_default` queue. Check `kubectl get pods -l app.kubernetes.io/component=worker`.

## 5. Recovery

1. Identify the root cause using §3.
2. Fix the underlying issue (flag, signal, cycle, upstream failure).
3. Manually trigger the stuck downstream via the Python shell command in §4.
4. Verify the dependency chain resolves by checking the preview endpoint.
5. For bulk recovery, re-run `derive_dependencies_from_lineage`.

## 6. Escalation

| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single pipeline stuck in PENDING_DEPENDENCY | Tenant admin |
| P2 | Multiple pipelines stuck across tenants | data-platform@meshant.com |
| P1 | Cycle detected in production graph blocking all pipelines | SEV1 — data-platform on-call |

## 7. Related

- `docs/runbooks/RB-DQ-002-warehouse-dq-failure.md`
- `docs/runbooks/RB-COMP-010-warehouse-compliance-failure.md`
- `hub/apps/orchestration/dependency_resolver.py`
- `hub/apps/orchestration/dependency_executor.py`
- `hub/apps/orchestration/trigger_engine.py`
- `hub/apps/orchestration/management/commands/derive_dependencies_from_lineage.py`
