# Asset Creation — operational runbook

**Phase**: 250.0.19
**Status**: Authoritative; reviewed quarterly + on-incident.
**On-call escalation**: `#asset-creation-eng` Slack → SRE primary on-call → Eng EM → Eng Director.

## Scope

Operational guide for the canonical asset-creation flow ([hub/apps/orchestration/workflows/asset_creation.py](../../hub/apps/orchestration/workflows/asset_creation.py)) including its dependencies (compliance-service, dq-service, semantic-service, search-service, OpenLineage emission). Use this runbook for symptom triage; cross-link to the more specific runbooks when diagnosis narrows.

## Architecture (post-Phase-250.1.A)

```
POST /api/v1/assets/data-first/
  → 1. validate request (DRF serializer, KYC gate)
  → 2. enqueue WorkflowRun (state=PENDING)
  → 3. return WorkflowRun.id (HTTP 202 Accepted)
  → [async on worker]
    → schema-infer → ODCS-generate → ODCS-validate → ODCS-normalise →
    → contract-create → ComplianceService.scan_inmemory →
    → DQService.scan_inmemory → asset-create (only on PASS/WARN) →
    → contract-attach → dataset-create → dataset-attach →
    → contract-validate → odps-link → activate → search-index →
    → publish_asset_created webhook → publish_asset_activated webhook
GET /api/v1/workflows/runs/{id}/
  → tenant polls until state ∈ {COMPLETED, FAILED}
```

## Symptom triage matrix

| Symptom | Likely cause | Runbook |
|---|---|---|
| Customer reports: "I uploaded a file but no asset appears" | Workflow stuck or fail-closed | [asset-fail-closed-rollback.md](asset-fail-closed-rollback.md), [workflow-stuck.md](workflow-stuck.md) |
| Bulk DRAFT assets visible in tenant queries | Orphan-DRAFT cleanup needed | [orphan-draft-cleanup.md](orphan-draft-cleanup.md) |
| Hub api pods restarting; logs show ImproperlyConfigured | Cross-service version mismatch | See _Cross-service version mismatch_ below |
| Asset shows banner: "not yet discoverable in semantic search" | Semantic graceful degrade fired | [semantic-degraded.md](semantic-degraded.md) |
| Federated assets returning 404 unexpectedly | Federated import flag flipped OFF, source-tenant deletion | [federated-degradation.md](federated-degradation.md) |
| User sees HTTP 412 Precondition Failed on PATCH | Optimistic-locking version mismatch | [version-conflict.md](version-conflict.md) |
| Workflow runs stuck in `PENDING` for >5 min | RQ queue backed up; worker pod issue | [workflow-stuck.md](workflow-stuck.md) |
| Workflow runs failing on a deprecated version | Workflow version past 14-day soak | [workflow-dr.md](workflow-dr.md) |

## Cross-service version mismatch

**Symptom**: Hub api pod fails to start. Pod logs show `ImproperlyConfigured: dq-service: reported version 'X.Y.Z' is less than Hub-required minimum 'A.B.C'`.

**Diagnosis**:
1. `kubectl get pods -n hub-staging -l app=hub-api` — confirm pod is `CrashLoopBackOff`.
2. `kubectl logs <pod> -n hub-staging | grep cross_service_version_check` — confirm which service is mismatched.
3. `kubectl get deployment <service> -n <ns> -o jsonpath='{.spec.template.spec.containers[0].image}'` — get the actual deployed image tag.

**Remediation**:
1. **Roll forward**: deploy the correct microservice version. `helm upgrade ... --set <service>.image.tag=<required-version>`.
2. **OR roll back Hub**: `helm rollback hub <previous-revision>` if microservice-upgrade isn't immediately available.
3. **NEVER bypass the check** by setting `CROSS_SERVICE_VERSION_CHECK_ENABLED=False` in production. The check exists because Phase 250.1.A endpoints fail SILENTLY against older microservices — bypassing creates worse failures than refusing to start.

**Verification**: pod transitions to `Ready`; `kubectl logs <pod> | grep cross_service_version_check_ok` shows OK lines for both services.

**Escalation**: SRE on-call if both Hub roll-forward AND microservice roll-forward fail.

## Healthy-flow telemetry (Grafana dashboard `asset-creation`)

Verify these panels are green during normal operations:

- **Workflow duration p95**: < 30 s. Spike → investigate compliance / DQ latency.
- **Workflow success rate**: > 99 %. Drop → check fail-closed rejections (which are healthy! NOT failures); cross-reference `ASSET_FAIL_CLOSED_REJECTED` audit volume.
- **Orphan-DRAFT count**: 0 (or close). Sustained >100 → run [orphan-draft-cleanup.md](orphan-draft-cleanup.md).
- **Semantic-status distribution**: most assets in PASS. Sustained FAIL >5 % → investigate semantic-service health.
- **Webhook delivery success rate**: > 99 %. Drop → check downstream webhook reliability.
- **Workflow WARN audit volume** (`ASSET_WORKFLOW_WARN_LOGGED`): should stay near zero. Sustained increase means asset-creation is succeeding with non-fatal validation warnings; inspect `details_json.result_summary.warnings` to identify recurring warning steps and root causes.

## Deploy / rollback procedure

Per Phase 250 RACI matrix, deploy requires:
1. Sign-off from EM (Eng).
2. Pre-deploy soak in staging for 24h with `compliance_fail_closed_enabled=True`.
3. Pre-merge announcement per 250.0.18 protocol if behaviour-changing.

Rollback procedure:
1. `helm rollback hub <previous-revision>`.
2. If flag-flip in flight, run `python manage.py revert_compliance_fail_closed_flag --tenant=<tenant_id>`.
3. Monitor `ASSET_WORKFLOW_ROLLED_BACK` audit-event volume for 30 minutes; should return to 0.

## Capacity guidance

Per [docs/capacity/asset-creation.md](../capacity/asset-creation.md) (Phase 250.0.24 deliverable):
- Per-tenant workflow concurrency: 50 (default; per-tenant override allowed).
- RQ queue depth alert at >500 jobs queued.
- Asset-creation API throughput target: 100 RPS sustained, 500 RPS burst (auto-scaled).

## Related runbooks

- [asset-fail-closed-rollback.md](asset-fail-closed-rollback.md) — deeper on fail-closed rejection paths
- [orphan-draft-cleanup.md](orphan-draft-cleanup.md) — DRAFT-asset cleanup
- [workflow-dr.md](workflow-dr.md) — workflow-version DR scenarios
- [workflow-stuck.md](workflow-stuck.md) — stuck workflow runs
- [version-conflict.md](version-conflict.md) — optimistic-locking conflicts
- [semantic-degraded.md](semantic-degraded.md) — semantic graceful-degrade
- [federated-degradation.md](federated-degradation.md) — federated import issues
