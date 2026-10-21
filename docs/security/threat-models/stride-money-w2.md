# STRIDE Threat Model — Money Path (W2)

One-pager for the oss-release-remediation W2 surface (billing,
marketplace orders, entitlements, metering, plan limits). Every
mitigation cites its verifying test or gate (P4). Ledger:
`docs/audits/w111-threat-model-refresh-2026-10-15.md`.

## Scope / assets

- Charge/refund amounts and their serialization (cents helpers), Stripe
  price provisioning + webhook signature/idempotency, the order state
  machine, the governance approve path, usage metering, entitlement
  grants/revocations, and the plan-limit quota counters.

## Trust boundaries

- Tenant → API (orders, upgrades, metering writes).
- API ↔ Stripe (webhook signature verification; idempotency claims).
- API/worker → PostgreSQL (money rows, partial-unique constraints).
- Worker → Redis (quota counters — acceleration, not truth).

## Spoofing

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Forged Stripe webhooks | Webhook signature verification with dual secrets (`whsec_`) + the secret-FILE source `STRIPE_WEBHOOK_SECRET_FILE`; unsigned/mis-signed → 400 | `hub/apps/billing/tests/test_webhook_secret_file.py` |
| Replayed Stripe events | Atomic `processed` claim (one winner); `stripe events resend` E2E proves no re-handling (one row, `attempts=1`) | `frontend/e2e/features/billing-stripe-webhook.spec.ts` |
| Order-status forgery | Serializer rejects writes to status/listing/approved_by; `Order.clean()` routes every status write through the state machine | `hub/apps/marketplace/tests/test_w23_order_state_machine.py` |

## Tampering

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Float/truncation corruption of money | `DecimalField(max_digits=15, decimal_places=2)` + canonical `amount_to_cents` (ROUND_HALF_UP) on every conversion; float price-data migration rehearsed (U.7) | `hub/apps/marketplace/tests/test_w21_decimal_end_to_end.py` |
| Half-cent rounding theft | ROUND_HALF_UP everywhere incl. refunds (a half-cent refund cannot exceed its charge); property-tested | `hub/apps/marketplace/tests/test_w29_cents_properties.py` |
| Unauthorized governance approval | `governance.approval.advance` chain on the live path; segregation-of-duties ledger; dangling-approver re-route; reject row lock | `hub/apps/governance/tests/test_w24_governance_hardening.py` |
| Direct `status=APPROVED` writes outside the service | Deleted; marketplace approve delegates to `GovernanceService` | `hub/apps/governance/tests/test_w24_governance_hardening.py` |

## Repudiation

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Revocations leave no audit trail | ONE `emit_entitlement_revoked_audit` on every revocation path (view, cancel, refund, Stripe webhook, saga compensation) | `hub/apps/marketplace/tests/test_w26_entitlements.py` |
| Duplicate usage billing is unprovable | `UsageRecord.idempotency_key` + partial uniques (legacy period+metric grain AND per-(tenant,key) event grain); replays return the existing row | `hub/apps/billing/tests/test_w25_metering.py` |

## Information disclosure

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Cross-tenant order/entitlement reads | All marketplace surfaces remain tenant-scoped via the W1 arming + queryset coverage | `scripts/lint_queryset_coverage.py` |
| Plan-limit bypass via background ingestion | `check_limit` runs in BOTH background ingestion paths BEFORE any row exists | `hub/apps/files/tests/test_w27_plan_limits.py` |

## Denial of service

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Duplicate purchases / double charge | `/purchase` takes `select_for_update` on the listing + live-ACTIVE re-buy short-circuit (no second payment) | `hub/apps/marketplace/tests/test_w26_entitlements.py` |
| Quota counter drift (fail-open to 0) | `LIMIT_COUNTER_ERROR` audits always; `LIMIT_CHECK_STRICT` mode; job Redis counters DB-reconciled + fail-closed | `hub/apps/jobs/tests/test_w28_job_counter_reconciliation.py` |
| Upload completion fails open on S3 errors | Completion fails CLOSED (502/409); orphan S3 objects cleaned | `hub/apps/files/tests/test_w27_plan_limits.py` |

## Elevation of privilege

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Order cap bypass via direct ORM writes | Orders route through the monthly `max_access_requests_per_month` cap (403, zero rows written) | `hub/apps/marketplace/tests/test_w28_order_ar_cap.py` |
| Dataset-cap bypass via versioning | `create_version_from_dataset` routes through `max_datasets` | `hub/apps/datasets/tests/test_w28_versioning_max_datasets.py` |
| Entitlement access check mutating state | Access-check mutation moved off the read path | `hub/apps/marketplace/tests/test_w26_entitlements.py` |

## Open threats (not yet shipped — documented, not claimed)

- Live-Stripe real-account drift outside the test-mode E2E is covered
  by W16 `E2E_STRIPE_ENABLED` (environment-gated), not a blocking CI
  lane.
- The full refund path's ledger double-write is rehearsed but the
  production Stripe account switch is ops-scheduled.
