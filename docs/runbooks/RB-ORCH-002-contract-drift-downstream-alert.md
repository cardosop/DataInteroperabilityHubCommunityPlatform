# RB-ORCH-002 — Contract Drift Downstream Alert

**Owner:** data-platform@meshant.com | **Created:** 2026-05-19

## 1. Overview

When a data contract's schema changes, downstream pipelines that depend on the contract's output columns may break. The `ContractDriftDetector` hooks into the contract save path, diffs the old and new schemas, classifies changes as BREAKING (field removed, incompatible type change, NOT NULL added) or WARNING (field added, type widened, constraint removed), and alerts downstream pipeline owners via audit events and webhooks. This runbook covers diagnosis and recovery when contract drift affects pipeline execution.

## 2. Symptoms

| Symptom | Likely Cause |
|---------|-------------|
| `CONTRACT_DRIFT_DETECTED` audit events appearing | Contract schema was updated; drift detector found changes |
| `PIPELINE_INCIDENT_DOWNSTREAM_ALERT` audit events | Upstream pipeline failed; incident propagator alerted downstream |
| Webhook receiving drift alerts for a pipeline | Contract upstream of that pipeline changed schema |
| Pipeline execution fails with schema mismatch | BREAKING change in upstream contract (field removed or type changed) |
| `PIPELINE_DEPENDENCY_STALE_CLEANED` audit events | `clean_pipeline_deps` management command deactivated stale references |
| Downstream pipeline stuck in `SKIPPED_UPSTREAM_FAILED` | Upstream pipeline FAILED; failure propagation marked downstream |
| `pipeline_dependency_cycle_detected_total` incrementing | New dependency created a cycle; resolver rejected it |
| Multiple tenants reporting drift on same contract pattern | Widespread schema migration; batch alert may be needed |

## 3. Investigation

### 3.1 Check drift report for a contract
```bash
python manage.py shell -c "
from hub.apps.orchestration.drift_detector import ContractDriftDetector
from hub.apps.contracts.models import Contract

contract = Contract.objects.get(id='<contract_id>')
detector = ContractDriftDetector(str(contract.tenant_id))
schema = detector._extract_schema(contract)
report = detector.detect(contract, schema)
print(json.dumps(report, indent=2))
"
```

### 3.2 Check downstream alerts
```bash
python manage.py shell -c "
from hub.apps.audit.models import AuditEvent
for e in AuditEvent.objects.filter(
    action='CONTRACT_DRIFT_DETECTED',
    tenant_id='<tenant_id>',
).order_by('-timestamp')[:10]:
    print(e.timestamp, e.details_json)
"
```

### 3.3 Check incident propagation
```bash
python manage.py shell -c "
from hub.apps.audit.models import AuditEvent
for e in AuditEvent.objects.filter(
    action='PIPELINE_INCIDENT_DOWNSTREAM_ALERT',
    tenant_id='<tenant_id>',
).order_by('-timestamp')[:10]:
    print(e.timestamp, e.details_json)
"
```

### 3.4 Check for stale dependencies
```bash
python manage.py clean_pipeline_deps --dry-run
```

## 4. Remediation

- **BREAKING change (field removed, type changed):** Either revert the contract change, or update all downstream pipeline configurations to handle the new schema. If the change was intentional, communicate to downstream owners before re-running.
- **WARNING change (field added, type widened):** Downstream pipelines should continue to work. Verify by running the downstream pipeline in preview mode: `datahub orchestration dependencies preview --pipeline-type <type> --pipeline-id <id>`.
- **Stale dependency references:** Run `python manage.py clean_pipeline_deps` to deactivate deps pointing to deleted pipelines. Emits `PIPELINE_DEPENDENCY_STALE_CLEANED` audit events.
- **Downstream stuck in SKIPPED_UPSTREAM_FAILED:** After fixing the upstream failure, manually re-trigger via the trigger engine: `_on_pipeline_terminal(tenant_id, pipeline_type, pipeline_id, 'SUCCEEDED')`.

## 5. Recovery

1. Identify the drift or failure using §3 investigation steps.
2. Determine whether the contract change was intentional or accidental.
3. If intentional: notify downstream owners; update their pipeline configs.
4. If accidental: revert the contract; re-trigger downstream pipelines.
5. Run `clean_pipeline_deps` to clean up any stale references left by the incident.
6. Verify no cycles were introduced: `validate_no_cycles()` via the resolver.

## 6. Escalation

| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single contract drift warning, no downstream breakage | Tenant admin |
| P2 | BREAKING drift affecting multiple downstream pipelines | data-platform@meshant.com |
| P1 | Widespread drift across multiple tenants from shared contract template | SEV1 — data-platform on-call |

## 7. Related

- `docs/runbooks/RB-ORCH-001-dependency-chain-failure.md`
- `hub/apps/orchestration/drift_detector.py`
- `hub/apps/orchestration/incident_propagator.py`
- `hub/apps/orchestration/management/commands/clean_pipeline_deps.py`
- `hub/apps/orchestration/dependency_resolver.py`
- `hub/apps/contracts/lineage_sync.py`
