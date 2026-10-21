# Workflow DR — runbook

**Phase**: 250.0.19 (250.1.C operational support)

## Scope

Disaster recovery for workflow-versioning incidents: workflow definition rollback, soak-window expiration with in-flight runs, multi-version conflicts.

## Symptoms

- `WORKFLOW_VERSION_MIGRATION_REQUIRED` HTTP 410 on workflow polling.
- Audit event volume of `WORKFLOW_VERSION_DEPRECATED_PATH_USED` spikes after a new version activation.
- Runbook task: rollback a workflow version due to incident.

## Diagnosis

1. Query active version + recent versions via `WorkflowVersionManager.get_versions_eligible_for_inflight_runs(workflow_name='asset_creation')`. Verify the active version + recently-deactivated versions within the 14-day soak.

2. Identify in-flight runs against an out-of-soak version:
   ```
   from datetime import timedelta
   from django.utils import timezone
   from hub.apps.orchestration.models import WorkflowInstance
   stale_runs = WorkflowInstance.objects.filter(
       workflow_name='asset_creation',
       status__in=['PENDING', 'RUNNING'],
       workflow_version='1.0.0',  # the deprecated version
       started_at__lt=timezone.now() - timedelta(days=14),
   )
   ```

## Remediation paths

### Path A: extend soak window (one-off)

If a long-running workflow is approaching the 14-day boundary AND can't be migrated:

```
python manage.py extend_workflow_version_soak --workflow=asset_creation --version=1.0.0 --days=30
```

Updates the workflow definition's `updated_at` to extend the soak. Bounded — max 90 days; emits `WORKFLOW_SOAK_EXTENDED` audit.

### Path B: migrate in-flight runs

Phase 250.0.12 ships per-step migration support. For each stale run:

```
python manage.py migrate_workflow_run --run-id=<uuid> --target-version=1.1.0 --dry-run
# verify; then:
python manage.py migrate_workflow_run --run-id=<uuid> --target-version=1.1.0
```

Migration is best-effort for steps already executed; remaining steps run on the target version. Emits `WORKFLOW_RUN_MIGRATED`.

### Path C: abort stale run

For stale runs with no migration path:

```
python manage.py abort_workflow_run --run-id=<uuid> --reason="version-unsupported"
```

Emits `WORKFLOW_RUN_ABORTED`. Rolls back any partial side-effects per the saga compensation map.

### Path D: workflow definition rollback (incident)

If a newly-activated version has a critical bug:

```
python manage.py activate_workflow_version --workflow=asset_creation --version=1.0.0
```

This re-activates the prior version; new runs use `1.0.0`; in-flight runs on `1.1.0` continue (it's still in soak).

## Verification

```
python manage.py audit_workflow_version_invariants --workflow=asset_creation
```

Asserts:
- Exactly one version is active.
- All `is_active=False` versions either are within 14-day soak OR have zero in-flight runs.
- No `WorkflowInstance` references a non-existent `WorkflowDefinition`.

## Escalation

- Data integrity violation (run migrated to incompatible version): Eng EM + DPO if PII involved.
- Bulk rollback (>50 workflows): SRE on-call → Eng Director.
