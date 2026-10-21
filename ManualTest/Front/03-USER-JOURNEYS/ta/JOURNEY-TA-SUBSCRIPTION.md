# JOURNEY-TA-SUBSCRIPTION: Manage Subscription and Invoices

**Journey ID**: JOURNEY-TA-SUBSCRIPTION  
**Title**: Manage Subscription and Invoices  
**Persona**: Tenant Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: useronboardfix Phase 17 — Change Plan & Invoices

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)
- [ ] Billing feature enabled (Stripe or mock billing configured)

---

## What You Will Do

View current subscription plan, change plan (upgrade/downgrade), and access invoice history. Uses `/settings/subscription` page.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to subscription | Go to **Settings** → **Subscription** (or `/settings/subscription`). | Subscription page loads | ☐ |
| 2 | View current plan | Check plan heading and current plan name. | Plan displayed (e.g. FREE, PRO) | ☐ |
| 3 | View invoice history | Scroll to invoice history section. | Table or empty state ("No invoices") visible | ☐ |
| 4 | Change plan (if available) | If other plans exist: select new plan from dropdown, submit. | Plan change initiated or success message | ☐ |
| 5 | Download invoice (if any) | If invoices exist: click download link. | PDF or hosted URL opens | ☐ |

---

## Success Criteria

- Subscription page accessible
- Current plan visible
- Invoice history section visible (table or empty state)
- Plan change UI visible when other plans exist
- Invoice download works when invoices exist

---

## API Endpoints (Reference)

- `GET /api/v1/billing/subscription/current/` — Current subscription
- `POST /api/v1/billing/subscription/current/change-plan/` — Change plan
- `GET /api/v1/billing/plans/` — Available plans
- `GET /api/v1/billing/invoices/` — Invoice list
- `GET /api/v1/billing/invoices/{id}/` — Invoice detail
- `GET /api/v1/billing/invoices/{id}/download/` — Invoice PDF

See [docs/API_REFERENCE.md](../../../../docs/API_REFERENCE.md) and [docs/BILLING.md](../../../../docs/BILLING.md).

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-SUBSCRIPTION.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md — useronboardfix Gap Coverage](../../../../docs/TEST_TRACEABILITY.md#useronboardfix-gap-coverage-phases-7-17)
- **Runbook**: [Subscription plan change failures](../../../../docs/RUNBOOKS.md#subscription-plan-change-failures)
