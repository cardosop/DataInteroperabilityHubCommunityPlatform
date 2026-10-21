# UC-BILL-002: Billing Upgrade

**Persona:** [Marketplace Platform Admin (MPA)](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :large_orange_circle: (NET-NEW -- Phase 217.1.4)
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_billing_upgrade`

## Description

A Marketplace Platform Admin upgrades the tenant's billing plan to a
higher tier, unlocking increased quotas (storage, seats, API rate
limits) and advanced features. The upgrade takes effect immediately,
with prorated charges applied for the remainder of the current billing
period.

## Preconditions

- The user holds the `TENANT_ADMIN` or `PLATFORM_ADMIN` role.
- The tenant has an active billing subscription on a lower-tier plan.
- The billing provider integration (Stripe, internal ledger) is
  operational.
- A valid payment method is on file for the tenant.

## Steps

1. MPA navigates to "Admin > Billing > Plan" or calls
   `GET /api/v1/billing/plans` to list available plans with their
   features and pricing.
2. The API returns an array of plans:
   - **Free:** 5 GB storage, 3 seats, 1,000 API calls/day.
   - **Professional:** 100 GB storage, 25 seats, 50,000 API calls/day,
     marketplace publishing, compliance scanning.
   - **Enterprise:** 1 TB storage, unlimited seats, unlimited API calls,
     SSO, advanced governance, priority support.
3. MPA selects the target plan and clicks "Upgrade" or calls
   `POST /api/v1/billing/subscriptions/upgrade` with
   `{ plan_id, payment_method_id }`.
4. The API calculates the prorated cost:
   - Remaining days in the current billing cycle.
   - Difference between the new plan's daily rate and the current
     plan's daily rate.
   - Total prorated charge = daily difference x remaining days.
5. The API returns a confirmation preview:
   `{ new_plan, prorated_charge, next_full_charge, effective_immediately }`.
6. MPA confirms the upgrade via
   `POST /api/v1/billing/subscriptions/upgrade/confirm`
   with `{ confirmation_token }`.
7. The billing provider charges the prorated amount to the payment
   method on file. The subscription record is updated to the new plan.
8. New quotas take effect immediately:
   - Storage limit is raised.
   - Seat limit is raised (existing invitations that were blocked by
     the old limit can now be accepted).
   - API rate limits are adjusted.
   - Gated features (SSO, advanced governance) become accessible.

## Expected Outcome

- The tenant's subscription is upgraded to the new plan with immediate
  effect.
- Prorated charges are applied to the current billing period; the next
  full charge reflects the new plan price.
- Quotas are increased and gated features are unlocked.
- An `AUDIT_BILLING_UPGRADE` event is recorded in the
  [audit log](../../concepts/audit-events.md) with old plan, new plan,
  and charge amount.
- Tenant members see updated quota indicators in the UI.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Payment method declined | `402 Payment Required` |
| Already on the highest plan | `422` with `ALREADY_MAX_PLAN` code |
| No payment method on file | `422` with `PAYMENT_METHOD_REQUIRED` code |
| Downgrade attempted via upgrade endpoint | `422` with `USE_DOWNGRADE_ENDPOINT` code |
| Billing provider timeout | `504 Gateway Timeout` -- retry safe |

## Related

- Concepts: [Billing](../../concepts/billing.md), [Tenants](../../concepts/tenants.md)
- Journeys: [JOURNEY-TA-007 -- Monitor Cost Tracking](../journeys/JOURNEY-TA-007.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
