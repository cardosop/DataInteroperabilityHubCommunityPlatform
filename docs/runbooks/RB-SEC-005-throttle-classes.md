# RB-SEC-005 — Throttle Class Management

**Owner**: Security Engineering
**Severity**: High (DoS protection)

## Purpose

Every DRF ViewSet MUST have `throttle_classes` to prevent abuse. This runbook covers adding throttles, auditing coverage, and triaging violations.

## Quick Reference

```bash
# Check throttle coverage (CI gate)
python hub/manage.py check_throttle_coverage

# List all exemptions
cat scripts/exemptions/throttle_exemptions.yaml
```

## Standard Throttle Scopes (285.14.6.10)

| Scope | Rate | Use Case |
|-------|------|----------|
| `user_read` | 120/min | Authenticated read endpoints |
| `user_write` | 30/min | Authenticated write endpoints |
| `tenant_read` | 500/min | Per-tenant aggregate read |
| `tenant_write` | 100/min | Per-tenant aggregate write |
| `admin` | 60/min | Platform admin endpoints |
| `public_pricing` | 60/min | Public pricing page |
| `health` | 120/min | Health check endpoints |
| `graphql` | 30/min | GraphQL queries |

## Adding Throttle to a New ViewSet

```python
from hub.apps.core.throttles import TenantScopedThrottle

class MyViewSet(viewsets.ModelViewSet):
    throttle_classes = [TenantScopedThrottle]
```

## Triage: Missing Throttle

If `check_throttle_coverage` reports a violation:

1. Identify the ViewSet and its risk profile
2. If the endpoint needs throttle: add `TenantScopedThrottle` to `throttle_classes`
3. If exemption applies: add entry to `throttle_exemptions.yaml`
4. Re-run check to verify

## Monitoring (285.14.6.11)

Throttle hits are tracked via `throttle_hit_total` counter with tags:
- `app`: application name
- `view`: ViewSet class name
- `scope`: throttle scope
- `tenant_id`: tenant UUID

Grafana panel: "Throttle Hit Rate by App"
Alert: >100/min for single tenant across all scopes → page on-call.

## CI Enforcement

- `check_throttle_coverage` in `.github/workflows/ci.yml`
- Blocks PRs that add new ViewSets without `throttle_classes`
- Exemptions in `scripts/exemptions/throttle_exemptions.yaml`
