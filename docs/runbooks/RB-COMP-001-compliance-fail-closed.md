# RB-COMP-001 — Compliance Fail-Closed Investigation (283.2.6)

**Date:** 2026-05-15  
**Feature flag:** `compliance_fail_closed_enabled` (GA)  
**Audit event:** `TENANT_FEATURE_FLAG_CHANGED` (filter: `flag=compliance_fail_closed_enabled`)

## 1. Overview

When `compliance_fail_closed_enabled` is True, asset creation is REJECTED if the compliance gate check fails. This is the production-safe posture — non-compliant assets cannot enter the catalogue.

When the flag is flipped OFF (to False), the system falls back to legacy create-then-validate mode, allowing non-compliant assets to be created without a compliance scan.

## 2. Symptoms

### Asset creation blocked

- **Symptom:** User attempts to create an asset and receives a `COMPLIANCE_GATE_BLOCKED` error
- **Expected:** This is NORMAL behaviour when `compliance_fail_closed_enabled=True` — the compliance scan failed or hasn't completed
- **Response:** Check the compliance scan status for the asset. If the scan failed, investigate the scan failure root cause. Do NOT disable the flag unless it's a confirmed false positive.

### Unauthorised flag flip

- **Symptom:** `TENANT_FEATURE_FLAG_CHANGED` audit event with `flag=compliance_fail_closed_enabled`, `action=DISABLED` by an unexpected user
- **Expected:** Flag flips require two-person approval (feature flag approval workflow, Phase 235.4)
- **Response:** Immediate investigation per §3

## 3. Investigation Procedure

### 3.1 — Confirm flag state

```sql
SELECT tenant_id, is_enabled, updated_at, updated_by
FROM feature_flag_approval
WHERE flag_name = 'compliance_fail_closed_enabled'
ORDER BY updated_at DESC LIMIT 5;
```

### 3.2 — Check audit trail

```
GET /api/v1/audit/events/?action=TENANT_FEATURE_FLAG_CHANGED&flag=compliance_fail_closed_enabled&since=7d
```

Look for:
- Who flipped the flag (`actor_user_id`)
- Whether it was DISABLED or ENABLED
- Whether the two-person approval was satisfied (`approval_count`)
- Whether the DPO signoff was obtained (`dpo_signoff_at`)

### 3.3 — Check for compliance scan backlog

If the flag was flipped because "scans are too slow":

```bash
python manage.py shell -c "
from hub.apps.compliance.models import ComplianceRun
pending = ComplianceRun.objects.filter(status='PENDING').count()
print(f'Pending scans: {pending}')
"
```

If pending >100, investigate compliance-service health and Redis queue depth. Do NOT disable the flag — increase scanner workers instead.

### 3.4 — Verify compliance service health

```bash
curl -sf https://compliance-service.hub-production:8082/health
kubectl get pods -n hub-production -l app=compliance-service
kubectl logs -n hub-production -l app=compliance-service --tail=50
```

## 4. Remediation

### Flag was disabled without authorisation

1. Re-enable immediately: `PATCH /api/v1/admin/feature-flags/compliance_fail_closed_enabled/ {is_enabled: true}`
2. File an incident in `#meshant-incidents`
3. Audit all assets created during the disabled window for compliance

### Flag was disabled due to scan backlog

1. Increase `COMPLIANCE_SCANNER_WORKERS` to 16
2. Verify Redis queue draining (`rq info --url $REDIS_QUEUE_URL`)
3. Re-enable flag once backlog <10
4. Root-cause the backlog (compliance-service OOM? Fuseki unreachable?)

### Legitimate false positive

1. Document the false-positive case (which framework? which regulation? which asset type?)
2. Open an issue in the compliance eng backlog
3. The flag stays ENABLED — the false positive is fixed in the compliance rules, not by disabling the gate

## 5. Recovery Validation

After remediation:
- [ ] `TENANT_FEATURE_FLAG_CHANGED` audit event shows `flag=compliance_fail_closed_enabled`, `action=ENABLED`
- [ ] Asset creation works for compliant assets
- [ ] Asset creation is rejected for non-compliant assets (confirm fail-closed)
- [ ] Compliance scan queue is draining normally
- [ ] No SEV1 alerts active

## 6. Escalation

| Condition | Action |
|---|---|
| Flag disabled >1 hour without authorisation | Escalate to Platform Lead + Security |
| 2+ unauthorised flips in 30 days | Escalate to CTO — review access controls |
| Compliance scan backlog >500 | Escalate to compliance-eng on-call |
| False positive rate >5% | Escalate to compliance-eng for rule review |

## 7. Related Runbooks

- `RB-AUTH-001-rls-kill-switch.md` — similar sensitive-flag investigation pattern
- `RB-GOV-001-compliance-blocked-approval-investigation.md` — compliance blocking governance
- `compliance-intake-gate.md` — intake gate configuration

## 8. Cohort-Based Rollout Plan (284.F.2)

`compliance_fail_closed_enabled` is a **sensitive GA flag** (two-person rule,
Phase 235.1) that gates asset creation behind a mandatory compliance scan. A
blanket flip for all active tenants risks a production incident — pre-existing
false positives in compliance rules WILL block legitimate asset creation. The
rollout proceeds in **three cohorts over 30 days** with a progressive
de-risking strategy.

### 8.1 — Active Tenant Identification

Before any cohort flips, enumerate tenants with *active* asset creation
(more than zero assets created in the prior 90 days):

```sql
SELECT t.id, t.name, t.slug,
       COUNT(a.id) AS assets_90d,
       MAX(a.created_at) AS last_asset_created
FROM tenants_tenant t
JOIN assets_asset a ON a.tenant_id = t.id
WHERE a.created_at >= NOW() - INTERVAL '90 days'
  AND t.status = 'ACTIVE'
GROUP BY t.id, t.name, t.slug
ORDER BY assets_90d DESC;
```

Tenants with `assets_90d = 0` are **dormant** — the flag can be flipped
immediately with near-zero risk.

### 8.2 — Pre-Fix False Positives

For each tenant in the rollout cohorts below, audit the existing compliance
scan history BEFORE flipping the flag:

```sql
SELECT cr.id, cr.tenant_id, cr.status, cr.allowed_to_store,
       cr.framework, cr.regulation_key, cr.created_at
FROM compliance_compliancerun cr
WHERE cr.tenant_id = '<tenant-uuid>'
  AND cr.created_at >= NOW() - INTERVAL '30 days'
  AND cr.allowed_to_store = FALSE
ORDER BY cr.created_at DESC;
```

Any `allowed_to_store=FALSE` result where the asset appears *legitimately
compliant on manual review* is a false positive. Fix the compliance rule
BEFORE flipping the fail-closed flag for that tenant.

### 8.3 — Cohort Schedule

| Cohort | Day | Tenant Count | Criteria |
|---|---|---|---|
| **Cohort 1** | Day 1–7 | 3 friendly tenants (2 dormant + 1 low-volume) | Assets_90d ≤ 5, existing DPO contact, agreed via Slack |
| **Cohort 2** | Day 8–21 | 40% of remaining active tenants | Assets_90d ≤ 50, no critical compliance incident in prior 90d |
| **Cohort 3** | Day 22–30 | Remaining 60% | All tenants including high-volume; high-touch monitoring in first 48h |

**Cohort 1** selects friendly tenants with DPO buy-in. The low-volume tenant
serves as the canary — any false positive surfaces within 24h of normal usage.
Dormant tenants exercise the code path without production risk.

**Cohort 2** widens to medium-volume tenants. By this point, Cohort 1 has
soaked for at least 7 days. Any rule fixes from Cohort 1 false positives are
deployed before Cohort 2 begins.

**Cohort 3** completes the rollout. High-volume tenants get elevated
monitoring: every `COMPLIANCE_GATE_BLOCKED` audit event triggers a Slack
notification to `#compliance-eng` for the first 48 hours.

### 8.4 — Rollback Criteria per Cohort

During each cohort's active window, roll back the flag for that cohort if:

- **False positive rate >3%**: More than 3% of compliance gate blocks are
  confirmed false positives on manual review.
- **Asset creation blocked >1h**: A legitimate asset creation is blocked for
  more than 1 hour due to compliance scan queue backlog.
- **Compliance service degraded >5min**: The compliance service returns 503
  or times out for more than 5 consecutive minutes.

Rollback procedure:
```bash
# PLATFORM_ADMIN two-person rule — first admin opens flip request:
curl -X PUT https://api.stagingmeshant-internal.example.com/api/v1/admin/tenants/{id}/feature-flags/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"compliance_fail_closed_enabled": false, "reason": "Cohort rollback: <reason>"}'
# Second PLATFORM_ADMIN approves at:
# POST /api/v1/admin/feature-flag-approvals/{id}/approve/
```

### 8.5 — Post-Rollout Monitoring (Day 30+)

After all cohorts are complete (Day 30):

- [ ] `compliance_fail_closed_enabled = True` for all active tenants
- [ ] False positive rate ≤1% across all tenants
- [ ] `COMPLIANCE_GATE_BLOCKED` audit volume is baseline-established
- [ ] Compliance scan queue latency p95 ≤30s
- [ ] Zero unauthorised flag flips in audit trail
- [ ] Monthly false-positive review cadence established with compliance-eng team
