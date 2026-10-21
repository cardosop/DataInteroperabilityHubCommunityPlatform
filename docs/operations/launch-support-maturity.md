# Launch & Support Maturity — Meshant Platform

**Last updated:** 2026-05-15

## A.8.1 — Self-Service Tenant Onboarding Portal

**Status:** ⏭️ Backend API exists, portal UI not built.

### Existing Infrastructure
- `hub/apps/tenants/views.py:100`: `service.create_tenant()` — automated provisioning endpoint
- `hub/apps/users/management/commands/ensure_user_tenant_memberships.py` — membership setup
- `docs/operations/operational-expansion.md` §3: manual tenant onboarding runbook

### Portal Feature Requirements
```
Self-Service Portal (https://meshant.com/signup):
1. Signup form: company name, admin email, plan tier
2. Stripe Checkout for paid plans
3. Automated provisioning:
   - Create tenant via POST /api/v1/admin/tenants/
   - Create admin user with TENANT_ADMIN role
   - Send invitation email with password setup link
   - Assign feature flags based on plan tier
4. Welcome page with getting-started guide links
```

### Implementation Path
1. Create `frontend/src/features/onboarding/SignupPage.tsx`
2. Wire Stripe Checkout for payment collection
3. POST to admin tenant creation endpoint
4. Redirect to login after email verification
5. Replace manual Linear ticket workflow with automated pipeline

## A.8.2 — Customer-Facing SLA

**Status:** ✅ Documented 2026-05-15.

### Service Level Agreement

| Metric | Customer SLA | Internal SLO | Margin |
|---|---|---|---|
| **Uptime** | 99.5% (3.65h downtime/month) | 99.9% (43.8 min/month) | 5× tighter |
| **API p95 latency** | <1,000ms | <500ms | 2× tighter |
| **API error rate** | <5% | <1% | 5× tighter |
| **Support response SEV1** | 2 hours | 1 hour | 2× tighter |
| **Support response SEV2** | 8 hours | 4 hours | 2× tighter |
| **Support response SEV3** | 48 hours | 24 hours | 2× tighter |

### Financial Penalties
| Uptime Tier | Penalty (% of monthly fee) |
|---|---|
| ≥99.5% | None (SLA met) |
| 99.0–99.49% | 10% credit |
| 98.0–98.99% | 25% credit |
| <98.0% | 50% credit + termination right |

### Measurement
- Uptime: `(total_minutes - downtime_minutes) / total_minutes × 100`
- Measured monthly via Prometheus `up` metric + independent external probe (StatusCake or Pingdom)
- Downtime excludes: scheduled maintenance (announced 48h in advance), force majeure, customer-caused outages

### Uptime Guarantee
- Pro tier and above: 99.5% uptime SLA
- Free tier: best-effort, no financial SLA
- Enterprise tier: custom SLA up to 99.95% (contact sales)

## A.8.3 — Dedicated Support Rotation

**Status:** ✅ RUNBOOK EXISTS (verified 2026-05-15). `docs/operations/on-call-runbook.md`.

### Coverage Model
- **Business hours:** Mon-Fri 09:00-18:00 UTC (8×5)
- **Off-hours:** PagerDuty escalation for SEV1 only
- **Minimum staff:** 3 trained engineers (primary + secondary + escalation)

### Rotation Schedule
| Role | Primary | Secondary | Off-Hours Escalation |
|---|---|---|---|
| Week 1 | Engineer A | Engineer B | Engineering Lead |
| Week 2 | Engineer B | Engineer C | Engineering Lead |
| Week 3 | Engineer C | Engineer A | Engineering Lead |

### Handoff
- Monday 09:00 UTC, 30-min sync via `#platform-oncall` Slack
- PagerDuty override available for schedule swaps (24h notice)

### Escalation Path
```
Customer ticket (Zendesk/support@meshant.com)
  → Support Engineer (first responder, SEV1: 2h customer SLA, 1h internal SLO)
    → Engineering Lead (unresolved >4h or SEV1 unacked >30min)
      → CTO (SEV1 unresolved >2h, security incident)
        → CEO (legal/regulatory notification required)
```

### Support Channels
| Channel | Purpose | Response |
|---|---|---|
| `support@meshant.com` | Customer tickets (Zendesk) | SEV1: 2h / SEV2: 8h / SEV3: 48h |
| `#platform-support` Slack | Internal engineering | Best-effort (no SLA) |
| PagerDuty | Automated alerts → incident | P0: 15 min / P1: 30 min |
| `meshant-internal.example.com` | Public status page | Updated within 15 min of incident |
