# Staged Rollout Procedure — Meshant Platform

**Last updated:** 2026-05-15
**Target:** ≥3 production tenants, ≥7 days stability
**Owner:** Platform Engineering

## 1. Tenant Selection Criteria

Select 3 friendly tenants for initial rollout. Criteria:

| Criterion | Requirement |
|---|---|
| **Relationship** | Friendly/partner tenant with direct Slack/email access to engineering team |
| **Usage volume** | Low-to-moderate (not the highest-traffic tenant) |
| **Feature diversity** | Covers core workflows: asset creation, contract management, marketplace, compliance |
| **Plan tier** | At least 1 free-tier + 1 paid-tier tenant |
| **Geographic** | At least 1 non-US tenant (GDPR coverage) |

### Selected Tenants

| # | Tenant Name | Slug | Plan | Contact | Feature Flags Enabled |
|---|---|---|---|---|---|
| 1 | _____________ | ___ | ___ | _____________ | See §2 |
| 2 | _____________ | ___ | ___ | _____________ | See §2 |
| 3 | _____________ | ___ | ___ | _____________ | See §2 |

## 2. Feature Flag Configuration

For each rollout tenant, enable the following CANARY flags (from `feature_flag_registry.py`):

```bash
# Tenant 1: enable all CANARY flags
# NOTE: `datahub admin feature-flags` CLI module planned but not yet implemented (279.F Phase 5).
# Until then, use the Django admin or direct DB update:
#   python manage.py shell -c "from hub.apps.tenants.models import Tenant; ..."
datahub admin feature-flags update --tenant-id <t1> \
    --flag ai_natural_language_search_enabled=true \
    --flag ai_schema_matching_enabled=true \
    --flag data_quality_enabled=true \
    --flag data_quality_advanced_enabled=true \
    --flag datasets_enabled=true \
    --flag files_enabled=true \
    --flag lineage_openlineage_export_enabled=true \
    --flag lineage_change_notifications_enabled=true \
    --flag transformation_enabled=true

# Tenant 2: enable core CANARY flags only (conservative)
datahub admin feature-flags update --tenant-id <t2> \
    --flag data_quality_enabled=true \
    --flag datasets_enabled=true \
    --flag files_enabled=true \
    --flag transformation_enabled=true

# Tenant 3: enable marketplace + data CANARY flags
datahub admin feature-flags update --tenant-id <t3> \
    --flag data_quality_enabled=true \
    --flag datasets_enabled=true \
    --flag files_enabled=true \
    --flag marketplace_enabled=true \
    --flag social_communities_enabled=true
```

### Flag enablement audit

```bash
# Verify flags are set correctly
for tenant in <t1> <t2> <t3>; do
    datahub admin feature-flags get --tenant-id $tenant --format json
done
```

## 3. Plan Limits Configuration

Assign correct plan limits per tenant:

| Tenant | Plan | Asset Limit | Storage (GB) | API Calls/mo | Users |
|---|---|---|---|---|---|
| 1 | Paid (Pro) | 500 | 50 | 100,000 | 50 |
| 2 | Free | 10 | 1 | 1,000 | 5 |
| 3 | Paid (Pro) | 500 | 50 | 100,000 | 50 |

```bash
# Assign plans (if not already set)
# NOTE: `datahub billing plan assign` not yet implemented.
# Use `python manage.py shell` or Django admin to assign plans.
python manage.py assign_plan --tenant t1 --plan pro
python manage.py assign_plan --tenant t2 --plan free
python manage.py assign_plan --tenant t3 --plan pro
```

## 4. User Role Configuration

Ensure each tenant has the minimum role coverage:

| Role | Tenant 1 | Tenant 2 | Tenant 3 |
|---|---|---|---|
| TENANT_ADMIN | ✅ | ✅ | ✅ |
| DATA_ENGINEER | ✅ | ✅ | ✅ |
| DATA_CONSUMER | ✅ | ✅ | ✅ |
| COMPLIANCE_OFFICER | ✅ | — | ✅ |
| PLATFORM_ADMIN | — | — | — (platform-level only) |

```bash
# Verify roles
datahub users list --tenant-id <t1> --format table
datahub users roles <user-id>
```

## 5. Monitoring Dashboard

### Grafana Dashboard: `Rollout Health`

**NOTE:** This dashboard does not exist yet. Create it from the metrics below before rollout.
Template: `monitoring/grafana/dashboards/` — copy an existing dashboard JSON and modify.

Monitor these metrics continuously for 7 days:

| Metric | SLO | Alert |
|---|---|---|
| **p95 API latency** | <500ms | P1 if >2s for 5 min |
| **Error rate (5xx)** | <1% | P1 if >5% for 5 min |
| **4xx rate** | <5% | P2 if >10% for 15 min |
| **Availability** | >99.9% | P0 if <99% for 1 min |
| **DB connection pool** | <80% utilization | P1 if >90% |
| **Redis memory** | <80% | P1 if >90% |
| **Worker queue depth** | <100 pending | P2 if >500 for 10 min |
| **Webhook delivery rate** | >99% | P2 if <95% for 30 min |

### Daily Checklist (Days 1-7)

- [ ] **Day 1**: Confirm all 3 tenants can log in. Run smoke tests (create asset, upload file, run DQ check).
- [ ] **Day 2**: Verify marketplace workflows (listings, orders, entitlements) for Tenant 3.
- [ ] **Day 3**: Verify compliance workflows (compliance scan, DSAR submit) for Tenants 1+3.
- [ ] **Day 4**: Verify data quality workflows (DQ run, scorecard, alerts) for Tenants 1+3.
- [ ] **Day 5**: Verify scheduled ingestion/export for Tenant 1.
- [ ] **Day 6**: Stress test: 10 concurrent asset creates + 5 concurrent DQ runs (Tenant 1).
- [ ] **Day 7**: Final review: all metrics within SLO. Sign-off.

## 6. Success Criteria (280.A.8.2)

All criteria must be met for ALL 3 tenants for the full 7-day period:

| Criterion | Target | Measurement |
|---|---|---|
| **Zero SEV1 incidents** | 0 | PagerDuty incident count = 0 for rollout tenants |
| **p95 latency within SLO** | <500ms | Grafana: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| **Error rate** | <1% | Grafana: `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])` |
| **Core workflows functional** | All passing | Daily smoke tests: asset create→upload→DQ→activate, marketplace browse→checkout→entitlement, compliance scan→report, DSAR submit→status |

### Core Workflow Smoke Tests

```bash
# 1. Asset lifecycle (run for each tenant)
datahub assets create --name "Rollout Test $(date +%s)" --key "rollout-$(date +%s)" --tenant-id <tid>
datahub assets list --tenant-id <tid>
datahub assets activate <asset_id> --tenant-id <tid>

# 2. Contract creation
datahub contracts create --file cli/test-contract.odps.json

# 3. DQ run
datahub dq run --asset-id <asset_id> --tenant-id <tid>

# 4. Compliance scan
datahub compliance run --asset-id <asset_id> --regulation GDPR --tenant-id <tid>

# 5. Marketplace (Tenant 3 only)
datahub marketplace listings list --tenant-id <t3>
```

## 7. Rollback Plan

If any SEV1 incident occurs or error rate exceeds 5% for >10 min:

```bash
# 1. Disable CANARY flags for affected tenant
datahub admin feature-flags update --tenant-id <tid> \
    --flag ai_natural_language_search_enabled=false \
    --flag ai_schema_matching_enabled=false \
    --flag transformation_enabled=false

# 2. If issue persists, disable ALL CANARY flags
for flag in $(datahub admin feature-flags get --tenant-id <tid> --format json | jq -r '.flags | to_entries[] | select(.value.stage=="CANARY") | .key'); do
    datahub admin feature-flags update --tenant-id <tid> --flag "$flag=false"
done

# 3. Notify tenants via Slack/email
# 4. Post incident report in #incident-p0
# 5. Root cause analysis within 24h
```

## 8. Sign-Off

Rollout is complete when ALL success criteria are met:

- [ ] 7 days elapsed since Day 1
- [ ] Zero SEV1 incidents (PagerDuty count = 0)
- [ ] p95 latency <500ms for all 7 days
- [ ] Error rate <1% for all 7 days
- [ ] All core workflows pass daily smoke tests (7/7 days)
- [ ] All 3 tenant contacts confirm normal operation

**Engineering Lead:** _____________ **Date:** _________
