# W11.7 — ASVS V11 Business-Logic Adversarial Matrix

**Change:** `openspec/changes/oss-release-remediation` — W11.7
**Date:** 2026-10-16
**Register rows closed:** 10 (TOCTOU / check-then-act) and 16 (race conditions &
lost updates)
**ASVS mapping:** V11.1 (business-logic flow enforcement), V1.5/V4.1 (state
guards on every mutation path), V11.x (anti-automation/idempotency).

Every cell carries ONE named test, run live against the real stack (real DRF,
real DB rows, real threads, real services). The `Stripe.Refund.create` boundary
is the suite's documented seam (`_StubStripeRefund` — third-party-boundary
pattern from `test_seller_refund_endpoint.py`; every business-logic guard,
lock and persist runs for real). Verified mechanically by
`scripts/tests/test_w117_business_logic_matrix_veracity.py`.

---

## Matrix 1 — State-machine transition matrices (full)

The shared primitive: `hub/apps/core/state_machine.py` `GuardedStateMachine`
(strict — identity is NOT a transition; terminal states derived from the
matrix; raw-string safe).

### Orders (`OrderStateMachine`, marketplace/models.py)

| From → To | Legal? | Named test |
|---|---|---|
| REQUESTED → APPROVED | ✓ | `hub/apps/marketplace/tests/test_w23_order_state_machine.py::OrderStateMachineMatrixTest::test_legal_hops_pass_the_guard` |
| REQUESTED → REJECTED | ✓ | (same) |
| REQUESTED → CANCELLED | ✓ | (same) |
| REQUESTED → FULFILLED (direct) | ✗ | `hub/apps/marketplace/tests/test_w23_order_state_machine.py::OrderStateMachineMatrixTest::test_requested_to_fulfilled_direct_write_blocked` |
| APPROVED → FULFILLED | ✓ | `hub/apps/marketplace/tests/test_w23_order_state_machine.py::OrderStateMachineMatrixTest::test_named_actions_drive_the_legal_hops` |
| APPROVED → CANCELLED | ✓ | (same) |
| every other pair | ✗ | `hub/apps/marketplace/tests/test_w23_order_state_machine.py::OrderStateMachineMatrixTest::test_every_illegal_hop_is_blocked` (exhaustive 20-pair loop) |
| PATCH/PUT `{"status": ...}` | ✗ 400 | `hub/apps/marketplace/tests/test_w23_order_state_machine.py::OrderStateMachineApiTest::test_patch_status_returns_400` / `OrderStateMachineApiTest::test_put_status_also_returns_400` |
| identity saves | no-op | `hub/apps/marketplace/tests/test_w23_order_state_machine.py::OrderStateMachineMatrixTest::test_identity_saves_are_noops_on_every_status` |

### Payments (`PaymentStateMachine`, marketplace/models.py)

| From → To | Legal? | Named test |
|---|---|---|
| PENDING → {PROCESSING, SUCCEEDED, FAILED, CANCELLED} | ✓ | `hub/apps/marketplace/tests/test_w31_payment_state_machine.py::PaymentStateMachineTest::test_legal_lifecycle_pending_processing_succeeded_refunded` |
| PROCESSING → {SUCCEEDED, FAILED, CANCELLED} | ✓ | (same) |
| SUCCEEDED → REFUNDED | ✓ | (same) |
| FAILED → SUCCEEDED (late webhook) | ✗ | `test_failed_payment_mark_succeeded_raises` + `test_succeeded_webhook_does_not_resurrect_failed_payment` |
| REFUNDED → SUCCEEDED | ✗ | `test_refunded_payment_mark_succeeded_raises` |
| direct ORM status write | ✗ | `test_direct_status_write_on_existing_row_rejected` |
| every other pair | ✗ | `hub/apps/marketplace/tests/test_w31_payment_state_machine.py::PaymentMatrixTest::test_matrix_covers_every_pair` |
| partial refund keeps SUCCEEDED | ✓ | `test_partial_refund_keeps_succeeded` |

### Runs — ingestion (`IngestionRunStateMachine`)

| From → To | Legal? | Named test |
|---|---|---|
| PENDING → {RUNNING, COMPLETED, FAILED, CANCELLED} | ✓ | `hub/apps/scheduled_ingestion/tests/test_w31_run_state_machine.py::IngestionRunMatrixTest::test_matrix_covers_every_pair` |
| RUNNING → {COMPLETED, FAILED, CANCELLED} | ✓ | (same) |
| FAILED → COMPLETED (internal PATCH) | ✗ 400 INVALID_TRANSITION | `hub/apps/scheduled_ingestion/tests/test_w31_run_state_machine.py::InternalRunStateMachineTest::test_patch_failed_to_completed_rejected` + `InternalRunStateMachineTest::test_patch_failed_to_completed_does_not_refire_side_effects` |
| CANCELLED → COMPLETED | ✗ | `hub/apps/scheduled_ingestion/tests/test_w31_run_state_machine.py::InternalRunStateMachineTest::test_patch_cancelled_to_completed_rejected` |
| direct ORM write | ✗ | `hub/apps/scheduled_ingestion/tests/test_w31_run_state_machine.py::InternalRunStateMachineTest::test_direct_status_write_on_existing_run_rejected` |
| process-file on CANCELLED | ✗ | `hub/apps/scheduled_ingestion/tests/test_w31_run_state_machine.py::InternalRunStateMachineTest::test_process_file_on_cancelled_run_rejected` |

### Runs — export (`ExportRunStateMachine`) — mirror pins in
`hub/apps/scheduled_export/tests/test_w31_run_state_machine.py`.

### AccessRequests (governance, multi-step — `governance/state_machine.py`)

| From → To | Legal? | Named test |
|---|---|---|
| PENDING → PENDING_NEXT_APPROVER | ✓ | `hub/apps/governance/tests/test_approval_state_machine.py` + `hub/apps/governance/tests/test_phase_272_multi_step_integration.py` |
| PENDING → APPROVED (final/single step) | ✓ | (same) |
| PENDING → REJECTED | ✓ | (same) |
| PENDING → REVOKED (order-cancel withdrawal) | ✓ W11.7 | `hub/apps/governance/tests/test_w117_ar_transition_matrix.py::ARMatrixCoverageTest::test_matrix_covers_the_real_surface_hops` |
| PENDING → EXPIRED (SLA sweep) | ✓ W11.7 | (same) |
| PENDING_NEXT_APPROVER → APPROVED | ✓ | `test_business_rules_table_matches_the_machine` (the pre-fix local table wrongly rejected it) |
| APPROVED → REVOKED | ✓ | `hub/apps/governance/tests/test_phase_272_multi_step_integration.py::TestApprovalDelegation::test_revoke_with_reason_succeeds` |
| APPROVED → EXPIRED | ✓ | (matrix pin) |
| APPROVED → REJECTED | ✗ | (matrix pin — the pre-fix full-refund path VIOLATED this; see Matrix 2) |
| REJECTED → APPROVED | ✗ | `test_business_rules_table_matches_the_machine` |
| PATCH/PUT `{"status": "APPROVED"}` | ✗ ignored (read-only) | `test_patch_status_approved_is_ignored` (+ workflow/approvers/rejection_reason pins — the pre-fix serializer WROTE it through) |

---

## Matrix 2 — Money path: double-charge / double-refund / replay

| # | Adversarial cell | Named test | Expected |
|---|---|---|---|
| 2.1 | Duplicate purchase → existing SUCCEEDED row returned, no second Stripe call | `hub/apps/marketplace/tests/test_payment_idempotency.py::PaymentIdempotencyTests::test_duplicate_payment_returns_existing_succeeded_row` | one row, one wire call |
| 2.2 | Same order, different price → different idempotency key (no false dedup) | (same file, `PaymentIdempotencyTests::test_price_change_produces_different_idempotency_key`) | keys differ |
| 2.3 | Idempotency key embeds canonical cents | `hub/apps/marketplace/tests/test_w21_decimal_end_to_end.py::AmountToCentsConversionTests::test_idempotency_key_embeds_canonical_cents` | 19.99 → 1999 |
| 2.4 | Concurrent duplicate orders | `hub/apps/marketplace/tests/test_race_condition_locking.py::DuplicateOrderRaceConditionTest::test_concurrent_duplicate_orders_one_wins` | one 201, one 409, one row |
| 2.5 | Concurrent double approve | `hub/apps/marketplace/tests/test_race_condition_locking.py::DoubleApproveRaceConditionTest::test_concurrent_double_approve_one_wins` | one 200, one 400 |
| 2.6 | Webhook double-processing claim (billing + marketplace receivers) | `hub/apps/billing/tests/test_webhook_idempotency.py::TestConcurrentClaim::test_concurrent_claim_single_winner` + `hub/apps/marketplace/tests/test_stripe_webhooks.py::TestConcurrentMarketplaceClaim::test_concurrent_claim_single_winner` | exactly one handler run |
| 2.7 | Double refund after REFUNDED | `hub/apps/marketplace/tests/test_refunds.py::MarketplaceRefundApiTests::test_double_refund_rejected_after_refunded_status` | refused |
| 2.8 | Refund retry after completion is idempotent (dedup cache) | `hub/apps/marketplace/tests/test_seller_refund_endpoint.py::TestRefundIdempotency::test_full_refund_retry_after_completion_is_idempotent` | no-op 200, no second wire call |
| 2.9 | **Concurrent DIFFERENT-amount refunds (the W11.7 race)** | `hub/apps/marketplace/tests/test_w117_refund_race.py::ConcurrentRefundRaceTest::test_concurrent_different_amount_refunds_single_winner` | exactly ONE wire refund, loser refused by the balance guard, refund_amount == winner — the pre-fix unlocked read over-refunded (drill-proven: removing the row lock flips the pin RED) |
| 2.10 | Concurrent IDENTICAL refunds collapse | (same file, `test_identical_amount_concurrent_retry_is_idempotent`) | ≤1 wire call, total ≤ amount |
| 2.11 | Full refund → AR REVOKED (legal hop) | `hub/apps/marketplace/tests/test_seller_refund_endpoint.py::TestRefundFullRefundCascade::test_full_refund_cascade` | REVOKED + revocation_reason="refunded" (pre-fix: REJECTED — illegal hop, pinned as such) |

## Matrix 3 — Metering idempotency drill

| # | Cell | Named test | Expected |
|---|---|---|---|
| 3.1 | Keyed replay is a no-op | `hub/apps/billing/tests/test_w25_metering.py::RecordUsageIdempotencyTest::test_idempotency_key_replay_is_a_no_op` | same record, no increment |
| 3.2 | Keys isolated per tenant | `hub/apps/billing/tests/test_w25_metering.py::RecordUsageIdempotencyTest::test_idempotency_key_isolated_per_tenant` | cross-tenant replay counts separately |
| 3.3 | Concurrent same-key claims one row | `hub/apps/billing/tests/test_w25_metering.py::ConcurrentClaimTest::test_concurrent_same_key_claims_one_row` | exactly one row |
| 3.4 | Concurrent sync → single Stripe record | `hub/apps/billing/tests/test_w25_metering.py::SyncUsageToStripeConcurrencyTest::test_concurrent_sync_produces_single_stripe_record` | one wire create |
| 3.5 | Synced record skips the wire | `hub/apps/billing/tests/test_w25_metering.py::SyncUsageToStripeConcurrencyTest::test_synced_record_skips_the_wire` | no re-meter |
| 3.6 | BaaS mirror dedup | `hub/apps/baas/tests/test_w25_usage_dedup.py` (3 pins) | counts once |

## Root fixes shipped by this suite (TDD, drill-proven)

1. **AR serializer wrote status straight through** — `AccessRequestSerializer`
   now read-only on `status`, `requires_approval`, `approval_workflow`,
   `current_approval_step`, `approvers`, `rejection_reason`, `expires_at`
   (pre-fix: PATCH `{"status": "APPROVED"}` = chain-free unaudited approval).
   Drill: re-writable status flips the pin RED.
2. **Full-refund hop APPROVED→REJECTED** (forbidden by the machine) →
   APPROVED→REVOKED with `revocation_reason="refunded"`; the legacy pin
   rewritten to the enforced contract.
3. **Governance matrix extended** with the real-surface hops (PENDING→REVOKED,
   PENDING→EXPIRED); the business-rules transition validator now IMPORTS the
   machine's table instead of a divergent local copy.
4. **`process_refund` unlocked read-modify-write** → the payment row is
   `select_for_update`-locked across guard → Stripe wire → persist (the tail
   extracted into `_refund_locked`). Drill: removing the lock flips the race
   pin RED (two wire refunds).
5. **Prefect-sync bulk FAILED update bypassed the run matrices** → the legal
   pre-state (`PENDING`/`RUNNING`) is enforced in the bulk filter for both run
   models.
6. Stale doc fixed: `core/tests/test_state_machine.py` docstring claimed
   "identity transitions are always legal" against its own strict pins.

## OPEN-THREATS (recorded, not claimed fixed)

* **`jobs.Job.status` is unguarded** — no matrix, no clean/save guard, no DB
  check; ~30 direct writes across apps (incl. terminal→RUNNING in
  ml/training_orchestrator, terminal→PENDING retry). Adopting
  `GuardedStateMachine` for Job is a W3-scale change (30 call sites + a U.7
  migration for the CHECK) — recorded here, not performed.
* **`BillingService.process_refund`** (billing/services.py) is a raw
  `stripe.Refund.create` pass-through — no local idempotency key or balance
  guard; Stripe is the sole arbiter on that surface.
* **No DB CHECK `refund_amount_cents <= amount_cents`** — the row lock closes
  the race at the app layer; a DB CHECK is the belt-and-braces follow-up.
* **Parent config statuses** (`ScheduledIngestion.status`,
  `ScheduledExport.status`) free-set — configuration lifecycle, out of the
  run-matrix scope.
* `_refund_records` dedup cache lives in `gateway_response` (replaced wholesale
  by `mark_succeeded`) — terminal-state guards currently prevent the overwrite;
  a defensive invariant is worth a follow-up.
