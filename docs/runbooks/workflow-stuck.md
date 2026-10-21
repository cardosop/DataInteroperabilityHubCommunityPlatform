# Workflow stuck — runbook

**Phase**: 250.0.19

## Scope

Workflow runs stuck in `PENDING` or `RUNNING` for > 5 minutes (well above the p95 SLO of 30 s).

## Symptoms

- `WorkflowInstance.status='PENDING'` or `'RUNNING'` for > 5 min on the same `id`.
- Customer ticket: "I uploaded my file but polling still says 'pending'".
- Grafana panel "Workflow duration" shows tail spike.

## Diagnosis

1. **Check the run state**:
   ```
   from hub.apps.orchestration.models import WorkflowInstance
   wi = WorkflowInstance.objects.get(id='<run_id>')
   print(wi.status, wi.workflow_name, wi.workflow_version, wi.started_at, wi.state_data)
   ```

2. **Check the worker pool**:
   ```
   kubectl get pods -n hub-staging -l app=hub-worker
   kubectl logs -l app=hub-worker -n hub-staging --tail=100
   ```
   Healthy → workers actively executing jobs. Stuck → no recent log lines OR `OOMKilled` events.

3. **Check the RQ queue**:
   ```
   from django_rq import get_queue
   q = get_queue('default')
   print(q.count, [j.id for j in q.jobs[:10]])
   ```

4. **Check the upstream microservice**:
   - If stuck on `compliance-check` step → `kubectl logs deployment/compliance-service -n hub-staging`
   - If stuck on `dq-check` step → `kubectl logs deployment/dq-service -n hub-staging`

## Remediation

### Case A: worker pool exhausted (RQ queue depth >500)

Scale up workers:
```
kubectl scale deployment/hub-worker -n hub-staging --replicas=10
```

If queue depth doesn't drop within 5 min, investigate worker pod resource limits or upstream microservice latency.

### Case B: stuck on compliance-check or dq-check

Microservice issue. Use [data-quality.md](data-quality.md) or compliance-service runbook (if exists). If microservice is healthy but step times out, increase the workflow step timeout:
```
kubectl set env deployment/hub-worker -n hub-staging WORKFLOW_STEP_TIMEOUT_SECONDS=120
```

### Case C: poison-pill workflow run

A specific run with bad input is timing out repeatedly:
```
python manage.py abort_workflow_run --run-id=<run_id> --reason="poison-pill-suspected"
```

Investigate the run's `state_data` field for clues; file Eng ticket if a recurring pattern.

### Case D: deadlock

Two runs holding tenant locks (per Phase 250.A.18 connection-pool semantics):
```
SELECT pid, query, state FROM pg_stat_activity WHERE wait_event_type='Lock';
```

Identify the lock-holder; if it's a stale workflow, abort via Case C.

## Verification

After remediation, verify recovery:
1. `WorkflowInstance.objects.filter(status='RUNNING', started_at__lt=now-5min).count()` = 0 (or stable low value).
2. Grafana "Workflow duration p95" returns to < 30 s within 10 minutes.
3. No new `WORKFLOW_RUN_TIMED_OUT` audit events for 30 minutes.

## Escalation

- Sustained worker pool saturation: SRE on-call.
- Data-loss suspected (asset persisted but workflow stuck): Eng EM + Compliance Lead.
