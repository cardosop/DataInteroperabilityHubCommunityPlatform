# STRIDE Threat Model — Pipeline Spine (W3)

One-pager for the oss-release-remediation W3 surface (scheduled
ingestion/export runs, the dlt dispatch spine, crash recovery, cancel).
Every mitigation cites its verifying test or gate (P4). Ledger:
`docs/audits/w111-threat-model-refresh-2026-10-15.md`.

## Scope / assets

- Scheduled ingestion/export run rows and their state machines, the
  dlt dispatch spine (entrypoints + processed-key cursors), the
  completion side effects (next_run_at, failure accounting, outbox,
  audit), the heartbeat/lease columns, the stuck-run detectors, and the
  out-of-band cancellation path.

## Trust boundaries

- Tenant → API (run creation, internal PATCH transitions, cancel).
- API/worker → dlt pipelines (dispatch entrypoints).
- Worker → PostgreSQL (run rows, cursor state).
- Cron/helm → detector commands.

## Spoofing

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Forged run transitions via the internal API | `GuardedStateMachine` matrices + `clean()/save()` guards; internal PATCH validates hops under `select_for_update` (400 `INVALID_TRANSITION`); DB CHECK-constraint domain guards | `hub/apps/scheduled_ingestion/tests/test_w31_run_state_machine.py` |
| Cancelled runs keep executing | Worker rejects CANCELLED (`RUN_CANCELLED`, zero side effects); the spine honors CANCELLED | `hub/apps/scheduled_ingestion/tests/test_w31_run_state_machine.py` |

## Tampering

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Run state corruption by double-completion | Both entrypoints route through `apply_run_completion_side_effects` exactly once | `hub/apps/scheduled_ingestion/tests/test_w32_uniform_completion.py` |
| Cursor tampering / premature advance | Cursors advance only when `files_failed == 0 AND files_processed > 0` (both source branches) | `hub/data_movement/tests/test_w34_cursor_on_success.py` |
| Unauthorized cancel | `POST /internal/runs/{id}/cancel/` guarded by the W3.1 permission matrices on both viewsets | `hub/apps/scheduled_ingestion/tests/test_w36_cancel_endpoint.py` |

## Repudiation

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Completion side effects untraceable | Completion emits the outbox + audit rows (Phase 273 contract extended to the catalog phase) | `hub/apps/scheduled_ingestion/tests/test_w32_uniform_completion.py` |
| Cancel intent disputed | `WorkflowCancellationRequest` rows persist the out-of-band intent (OneToOne, RLS-paired) | `hub/apps/orchestration/tests/test_w36_cancel_checkpoints.py` |

## Information disclosure

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Cross-tenant run reads | Run models tenant-scoped with the W1 arming + queryset coverage | `scripts/lint_queryset_coverage.py` |
| Worker-side file data leakage | Catalog core is shared with the worker path but tenant-bound by the authenticated worker context (W1.14) | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py` |

## Denial of service

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Stuck runs hold resources forever | `heartbeat_at` lease columns + shared `stuck_run_predicate`; detectors cover PENDING + NULL `started_at`; helm CronJobs every 15 min | `hub/apps/scheduled_ingestion/tests/test_w35_crash_recovery.py` |
| Duplicate dispatches on retry | Export `write_disposition="replace"`; ingestion filters discovery through dlt processed-keys | `hub/data_movement/tests/test_w33_idempotent_reruns.py` |
| Duplicate catalog rows on re-delivery | Idempotent by source key via File metadata_json provenance; cursor advances only when the catalog row landed | `hub/data_movement/tests/test_w38_ingestion_parity.py` |

## Elevation of privilege

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Run-state transition privilege escalation | Matrices per role on the internal viewsets (W3.1) | `hub/apps/scheduled_export/tests/test_w31_run_state_machine.py` |
| Cancel bypassing the state machine | The engine checkpoints the cancel signal before the first step and between every step — remaining steps never execute | `hub/apps/transformation/tests/test_w36_cancel_execution.py` |

## Open threats (not yet shipped — documented, not claimed)

- dlt round-trip verification against live Databricks destinations is
  environment-gated (sandbox availability), not a blocking CI lane.
- The per-tenant pipeline heartbeat tuning (interval vs stuck-window)
  is ops-configurable; the detector defaults are the shipped contract.
