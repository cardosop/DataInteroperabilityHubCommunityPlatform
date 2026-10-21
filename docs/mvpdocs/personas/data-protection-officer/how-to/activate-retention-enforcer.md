# Activate Retention Enforcer

**Audience**: Data Protection Officer (DPO)  
**Feature Flag**: `compliance_retention_enforcer_enabled` (GA, opt-in)  
**311.5 (G6)**: Sprint 1 — Retention enforcer activation guide

## Overview

The Retention Enforcer automates tombstone and hard-delete sweeps for data past its retention window. It respects legal holds, DSAR restrictions, and per-regulation minimum retention periods.

## Prerequisites

- DPO or TENANT_ADMIN role
- `compliance_retention_enforcer_enabled` feature flag enabled

## Activation Steps

1. **Enable the flag**: Go to Settings → Feature Flags → enable `compliance_retention_enforcer_enabled`
2. **Configure retention policies**: Set per-resource-type retention periods in Governance → Retention Policies
3. **Review legal holds**: Any resource with `legal_hold=True` is excluded from auto-sweep
4. **Test with dry-run**: `python hub/manage.py tenant_hard_delete_sweep --dry-run` to preview affected resources
5. **Activate**: The sweep runs daily via cron; first sweep processes resources past their retention window

## Jurisdiction-Aware Defaults

For GDPR/LGPD jurisdiction tenants:
- Default retention: 30 days (after purpose fulfilled) for non-financial data
- Maximum retention: 10 years for financial records
- Right to erasure overrides apply to non-financial data

To auto-enable for GDPR tenants, set `compliance_retention_enforcer_enabled` default to `True` in the feature flag registry for tenants with `default_compliance_regimes` containing `GDPR` or `LGPD`.

## Verification

```bash
# Check sweep status
python hub/manage.py tenant_hard_delete_sweep --dry-run

# View audit events
GET /api/v1/audit/audit-events/?resource_type=RETENTION
```

## Rollback

Set `compliance_retention_enforcer_enabled` to `False` to disable auto-sweeps. Existing policies and legal holds remain intact.
