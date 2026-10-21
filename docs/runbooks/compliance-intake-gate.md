# Runbook: Compliance intake gate & publish threshold (Phase 231)

## Scope

This runbook covers **tenant compliance intake auto-scan**, **activation gating**, **marketplace publish gating** (risk threshold vs latest succeeded run), **compliance.completed webhooks**, and **compliance-service circuit-breaker degradation**.

## Symptom index

| Symptom | Likely cause | First checks |
|--------|----------------|--------------|
| Assets stay `DRAFT`; activation returns 400 with intake blocker text | No succeeded run with `allowed_to_store=true` while `compliance_intake_gate_enabled` is on | Latest `ComplianceRun` rows for asset; worker/compliance-service logs; `compliance_intake_gate_events_total{event="ACTIVATION_GATE_BLOCK"}` |
| Marketplace publish HTTP 422 `COMPLIANCE_RUN_REQUIRED` | No succeeded run for listing asset | Same as above; listing → asset linkage |
| Publish 422 `COMPLIANCE_THRESHOLD_EXCEEDED` | Latest succeeded run `risk_level` ordinal above tenant `compliance_risk_threshold` | Tenant config / feature flags; audit rows `COMPLIANCE_THRESHOLD_EXCEEDED` on `LISTING` |
| Assets flip `compliance_status=WARN` after activation | Compliance-service circuit OPEN | `compliance_circuit_breaker_state`; audit `COMPLIANCE_SERVICE_UNAVAILABLE`; metric `event="SERVICE_UNAVAILABLE"` |
| Webhook subscribers miss events | Delivery failures; no terminal transition; idempotency stamp | `ComplianceRun.webhook_fired_at`; webhook service logs; `event="WEBHOOK_FIRED"` rate |

## Metrics & dashboards

- **Dashboard:** `monitoring/grafana/dashboards/compliance-intake-gate.json` (UID `compliance-intake-gate-231`).
- **Primary counter:** `compliance_intake_gate_events_total{event,tenant_id}` — vocabulary documented in `hub.apps.compliance.metrics_phase231`.
- **Audit panel:** rate of `audit_events_total` with `action=~"COMPLIANCE_.*"` (covers `resource_type` **ASSET**, **LISTING**, and **COMPLIANCE_RUN** — intake and publish-gate rows are not all on `COMPLIANCE_RUN`).
- **Poll timeouts:** `poll_timeout_total{service="compliance"}` (worker path).

## Alert tuning

Rules live in `monitoring/prometheus/alerts/compliance.yml`. Thresholds assume medium-scale multi-tenant traffic; adjust `for` / rate bounds if you operate at much lower or higher aggregate QPS.

## Execution checklist

1. **Confirm tenant flags:** `Tenant.compliance_intake_gate_enabled`, merged tenant config `compliance_risk_threshold`, `allowed_compliance_regimes`.
2. **Inspect latest run:** Ordering for activation matches `compliance_runs_order_by_activation_latest` (completed_at DESC NULLS LAST, then created_at).
3. **Scanner health:** compliance-service deployment, Redis/RQ queues for `COMPLIANCE_RUN` jobs, circuit breaker registry entry `compliance-service`.
4. **Force publish path:** Only platform admins may bypass; expect audit `COMPLIANCE_GATE_OVERRIDDEN` and metric `event="GATE_OVERRIDDEN"`.
5. **GDPR:** Erasure scrubs PII JSON on `ComplianceRun` rows attributed via `Job.created_by` — see `ErasureService.execute_erasure`.

## Escalation

- **P2** — sustained gate denials affecting multiple tenants after scanner recovery window.
- **P1** — circuit breaker OPEN across cells with rising activation failures.


## Maintenance

- **Owner**: Compliance Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11

## References

- `hub/apps/compliance/intake_scan.py` — intake enqueue + activation audit helper.
- `hub/apps/marketplace/compliance_gate.py` — publish threshold enforcement.
- `hub/apps/compliance/webhook_emission.py` — `compliance.completed` fan-out.
