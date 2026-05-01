# ADR-LIN-008 — Phase 0 audit: existing async-worker framework

**Status:** Accepted (Phase 228 Foundations — audit document)
**Date:** 2026-04-30
**Related:** REQ-LIN-002 (signal handler runs inside `transaction.on_commit`), REQ-LIN-003 (backfill command), ADR-LIN-004 (notification dispatcher)

## Audit summary

Phase 228's needs for asynchronous execution are: (1) the lineage-sync `post_save` handler must not block the request thread; (2) the `backfill_lineage_edges` management command runs as a long-lived job; (3) the change-notification dispatcher (Phase 228 F3) drains a debounce buffer every minute. The audit confirms **two complementary async-worker frameworks already exist**:

1. **`django_rq`** — Redis-backed job queue used by `hub/apps/jobs/tasks_base.py` for off-request background work.
2. **`transaction.on_commit`** — Django's built-in commit hook used for "after-the-DB-write" handlers that need not be off-process.

**Phase 228 does NOT introduce a new worker framework.** It uses both above, each for the role they fit best.

## What exists

### `django_rq` queue framework

[`hub/apps/jobs/tasks_base.py:16`](../../../hub/apps/jobs/tasks_base.py) imports `from django_rq import job`. The codebase has multiple RQ-decorated tasks already:

- `hub/apps/contracts/tasks.py::renormalize_contracts_v310` — long-running contract re-normalization batches (hours).
- `hub/apps/notifications/tasks.py::send_email_async` — email dispatch (seconds).
- `hub/apps/webhooks/tasks.py::deliver_webhook` — webhook delivery (seconds).

Queues: `job_default`, `notifications`, `webhooks`, `email` — all configured via `RQ_QUEUES` in `hub/settings.py`.

Worker pods run `python manage.py rqworker <queue>` per the existing chart in `infrastructure/k8s/` (see ADR-LIN-009 capacity doc for IaC pattern).

### `transaction.on_commit`

Django's standard `django.db.transaction.on_commit` is used in:

- `hub/apps/contracts/services.py` — wraps event-publishing post-create.
- `hub/apps/audit/utils.py` — wraps audit-event creation post-write.
- `hub/apps/webhooks/service.py` — wraps webhook-delivery scheduling.

`on_commit` is in-process but post-commit, so the request thread is not blocked by the registered callback's execution. This is the correct primitive for the lineage-sync handler (REQ-LIN-002) because:

- The diff calculation is fast (<5 ms typical) so off-process queueing is overkill.
- The handler must run with the same DB connection / transaction state visibility, which is `on_commit`'s guarantee.
- Failures need to be loud (REQ-LIN-002 requires "fail loudly, do not silently swallow"), and `on_commit` callbacks raising surface to structured logs / Sentry without disrupting the request.

## What Phase 228 adds

| Addition | Worker primitive | Why |
|---|---|---|
| Lineage-sync `post_save` handler | `transaction.on_commit` | <5 ms diff, must see the just-committed contract row, must be in-process for transactional consistency. |
| `backfill_lineage_edges` management command | Standalone `BaseCommand` (no RQ) | Long-lived ops job invoked by an SRE; the operator wants to see stdout in real time, restart on crash, and check `select_for_update(skip_locked=True)` against a known DB connection. RQ would add indirection without value. |
| Change-notification dispatcher (Phase 228 F3) | `django_rq` job on the `notifications` queue, scheduled every minute via the existing `django-rq-scheduler` | Drains the Redis debounce buffer; needs to be off-process so a buffer-flush failure doesn't bring down a request thread; needs to be retryable via the existing RQ retry policy. |
| OpenLineage adapter (Phase 228 F4) | `django_rq` job on a new `openlineage` queue | Decouples slow OpenLineage receivers from the lineage-sync handler; retries on 5xx via the existing retry policy. |

## What Phase 228 does NOT add

- **No new worker framework.** RQ is sufficient.
- **No Celery migration.** The `notifications` and `webhooks` queues already use RQ; introducing Celery would split the operational surface.
- **No bespoke threading.** `on_commit` covers the in-process need.

## Risks identified during audit

- **Risk:** RQ workers can be killed mid-job; Phase 228's backfill command is exposed to this. **Mitigation:** the spec (REQ-LIN-003) requires `--resume-key` checkpointing in Redis so a kill resumes from the last batch. Pinned by `test_lineage_backfill.py::test_resume_after_kill`.
- **Risk:** `transaction.on_commit` callbacks run in registration order; if the lineage-sync handler races with a webhook handler, ordering matters. **Mitigation:** the handler is **idempotent** (REQ-LIN-002 invariant) so ordering is not load-bearing — running twice produces the same end state.

## Conclusion

The existing async-worker frameworks are sufficient for Phase 228. Phase 228 picks the right primitive per role: `on_commit` for the in-request signal handler, RQ for the off-request dispatcher and adapter, standalone `BaseCommand` for the operator-driven backfill.
