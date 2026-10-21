# Asset Webhook Events Runbook

**Phase 250.1.G.1 / B2-6** — canonical reference for the `asset.*` webhook event surface, the trigger points in the workflow / service layer, the payload schemas, and the **ordering guarantees** preserved across the Phase 250.1.A re-sequence.

---

## Why this runbook exists

The Phase 250.1.A re-sequence moved the compliance + DQ gates BEFORE asset persistence. That fundamentally changes WHEN the `asset.created` event can fire — webhook subscribers that previously assumed "every workflow start eventually produces an asset.created" would now see the event only on PASS / WARN gate outcomes.

This document pins the new contract so:

* **Subscribers** can rely on a stable ordering and payload shape.
* **Hub developers** know which workflow steps fire which events, so future refactors don't silently break the wire surface.
* **Ops** has a single reference for the event types when triaging "subscriber X never received the expected event" incidents.

---

## Event catalogue

All asset events use the `asset.*` namespace; subscribers can filter on the prefix to receive every lifecycle event without listing each type.

| Event type | Trigger | Payload (additional to `asset_id`) | Cached on idempotency replay? |
|---|---|---|---|
| `asset.created` | First commit that persists the `Asset` row in DRAFT status. Fires from BOTH (a) `AssetCreationWorkflow._create_asset_record_task` (data-first flow) AND (b) `AssetService.create_asset` (simple `POST /assets/` API path). | `name`, `domain`, `status`, `contract_id` | Replay returns the same `asset.created` indirectly via the cached HTTP response — **no second event fires** |
| `asset.updated` | Any commit from `AssetService.update_asset` (the `PATCH /assets/{id}` API path). Carries `changes.fields` listing which fields were touched. | `changes`, `previous_status`, `new_status` | N/A (only fires on a real update) |
| `asset.activated` | First commit that flips `status` to `ACTIVE`. Fires from THREE paths: (a) `AssetCreationWorkflow._activate_asset_task` (data-first auto-activation), (b) `AssetService.update_asset` when the request transitions status to ACTIVE, (c) `AssetViewSet.activate` (explicit `POST /assets/{id}/activate/` endpoint). | `activation_reason`, `dq_status`, `compliance_status` | N/A (replay returns the cached 201; the original `asset.activated` already fired) |
| `asset.published` | **NOT YET WIRED.** Schema is defined in `event_types.py` and `publish_asset_published()` exists on `AssetEventPublisher`, but the marketplace-publish path does not yet call it. Tracked under follow-up Phase 250.3. | `marketplace_listing_id`, `pricing_model`, `license_type` | N/A |
| `asset.retired` | First commit that flips `status` to `RETIRED`. Fires from `AssetService.delete_asset` (the `DELETE /assets/{id}` API path — the soft-delete path that transitions to RETIRED). | `retirement_reason`, `retired_at` | N/A |

The full per-event JSON schema lives in [`hub/apps/core/events/event_types.py`](../../hub/apps/core/events/event_types.py) (the source of truth for both the publisher and the subscriber-side validator).

### Status by emission path (Phase 250.1.G review-pass)

The original Phase 250.1.G work wired events into the workflow path only. The review pass found that the simple API paths through `AssetService` were silently NOT firing webhook events — webhook subscribers had to poll to detect those assets. All three API-path emissions are now wired:

| Code path | Event fired | Implementation reference |
|---|---|---|
| `AssetCreationWorkflow._create_asset_record_task` (data-first flow) | `asset.created` | [asset_creation.py:1444](../../hub/apps/orchestration/workflows/asset_creation.py) (via `_enqueue_asset_event`) |
| `AssetCreationWorkflow._activate_asset_task` (data-first flow) | `asset.activated` | [asset_creation.py:2664](../../hub/apps/orchestration/workflows/asset_creation.py) (via `_enqueue_asset_event`) |
| `AssetService.create_asset` (simple `POST /assets/`) | `asset.created` | [services.py:330+](../../hub/apps/assets/services.py) (via `_enqueue_asset_event_on_commit`) |
| `AssetService.update_asset` (`PATCH /assets/{id}`) | `asset.updated` (+ `asset.activated` on status→ACTIVE) | [services.py:443+](../../hub/apps/assets/services.py) |
| `AssetService.delete_asset` (`DELETE /assets/{id}`) | `asset.retired` | [services.py:613+](../../hub/apps/assets/services.py) |
| `AssetViewSet.activate` (explicit `POST /assets/{id}/activate/`) | `asset.activated` | [views.py:1740+](../../hub/apps/assets/views.py) |

All emissions use `transaction.on_commit` deferral so subscribers only see events after the originating transaction commits — no ghost events from rolled-back operations.

---

## Phase 250.1.A trigger points (data-first workflow)

The data-first workflow now fires events in this order:

```
┌─────────────────────────────┐
│ Pre-persistence gates       │ NO events fire here.
│   compliance_check_inmemory │ A FAIL/UNKNOWN result terminates the
│   dq_check_inmemory         │ workflow with FailClosedRejection;
└─────────────────────────────┘ subscribers never see ghost events.
              │
              ▼ gates PASS / WARN
┌─────────────────────────────┐
│ create_asset_record         │ → registers `asset.created` via
│                             │   transaction.on_commit
└─────────────────────────────┘
              │
              ▼
┌─────────────────────────────┐
│ attach_contract             │ no event (synchronous attach;
│ create_dataset_from_file    │ event would duplicate semantically)
│ attach_dataset              │
│ validate_contract           │
│ link_odps                   │
└─────────────────────────────┘
              │
              ▼ if auto_activate
┌─────────────────────────────┐
│ activate_asset              │ → registers `asset.activated` via
│                             │   transaction.on_commit
└─────────────────────────────┘
              │
              ▼ workflow atomic commits
       ╔═════════════════╗
       ║ on_commit fires ║   asset.created  →  asset.activated
       ║   in order      ║   (in the order they were registered;
       ╚═════════════════╝    Django guarantees registration order)
```

### Why `transaction.on_commit`?

Both events are deferred via `transaction.on_commit` so they fire **only after the workflow's outer atomic commits**. This is the load-bearing webhook contract:

* **No ghost events**: a fail-closed rejection rolls back the engine's per-step savepoint AND the on_commit registration along with it. Subscribers never see an `asset.created` for an asset that doesn't exist in the database.
* **No early consumers**: a subscriber that GETs `/api/v1/assets/{asset_id}/` immediately on receipt of the event always sees the row (the commit has happened by definition).
* **Strict ordering**: Django's `on_commit` callbacks fire in registration order on the same transaction. Since `_create_asset_record_task` registers BEFORE `_activate_asset_task` runs, `asset.created` always precedes `asset.activated` for the same asset.

### Implementation reference

See `AssetCreationWorkflow._enqueue_asset_event` ([asset_creation.py:1494-1547](../../hub/apps/orchestration/workflows/asset_creation.py)). The two call sites are:

* `_create_asset_record_task` (line ~1444) — fires `asset.created` after `asset.save()` succeeds.
* `_activate_asset_task` (line ~2664) — fires `asset.activated` after `asset.status = ACTIVE; asset.save()`.

---

## Idempotency replay semantics

Phase 250.1.D added idempotency on `POST /assets/data-first/`. A replay returns the cached HTTP response **without** re-running the workflow — and therefore **without** re-firing `asset.created` / `asset.activated` events. This is the correct semantics for at-most-once webhook delivery: the original event is the canonical record; duplicates would force subscribers to dedupe themselves.

If a subscriber needs to detect "this client retried" after the fact, the HTTP response carries `Idempotent-Replay: true`. For event-driven subscribers, the absence of a second event for the same `asset_id` IS the dedup signal.

---

## Failure modes & subscriber expectations

| Scenario | What subscribers see |
|---|---|
| Compliance gate FAIL (fail-closed enabled) | **NO `asset.created` event.** The workflow raises `FailClosedRejection` before the asset row is persisted; the savepoint rollback discards the on_commit registration. Audit row `ASSET_FAIL_CLOSED_REJECTED` is the canonical record (see `hub/apps/audit/event_types.py`). |
| DQ gate FAIL (fail-closed enabled) | Same as above — no event fires. |
| Compliance breaker OPEN, tenant did NOT opt-in to degraded mode | 503 from the endpoint; no workflow starts; no events. |
| Downstream step failure after asset persisted (e.g., `link_odps` raises) | Saga compensation runs, status → ROLLED_BACK. Today the `asset.created` on_commit DOES fire because the asset row was persisted in an earlier completed step's savepoint. Subscribers receive `asset.created` followed by an audit-only `ASSET_WORKFLOW_ROLLED_BACK` (no `asset.deleted` event yet — tracked separately under 250.1.B.4 saga work). |
| Webhook publish fails (event bus down, schema validation error) | The publish exception is logged at WARNING (`asset_webhook_publish_failed`) but **does not fail the workflow**. The asset still gets created / activated; the subscriber misses ONE event for that asset. Reconciliation: subscribers that need full state can poll `/api/v1/assets/?updated_since=<ts>`. |

The "workflow succeeds, webhook fails silently" trade-off is intentional: blocking asset creation on webhook delivery would make every subscriber outage tenant-visible. Operators monitor `asset_webhook_publish_failed` logs + the EventBus dead-letter queue (`hub.apps.core.events.models.DeadLetterQueue`) for stuck events.

---

## Subscribing to asset events

### Server-side (in-process subscriber)

```python
from hub.apps.core.events.subscriber import event_subscriber

@event_subscriber("my_subscriber_name", "asset.*")
def handle_asset_event(event: Dict[str, Any]) -> None:
    asset_id = event["data"]["asset_id"]
    if event["event_type"] == "asset.created":
        # ... handle creation ...
    elif event["event_type"] == "asset.activated":
        # ... handle activation ...
```

See `hub/apps/core/events/subscribers.py` for the canonical pattern. The `event_subscriber` decorator registers the handler at process start; restart the API service to pick up new subscriptions.

### External webhook subscribers

External subscribers register via the `WebhookSubscription` model (see `hub/apps/webhooks/models.py`). The `asset.created`, `asset.updated`, `asset.activated`, `asset.published`, `asset.retired` event types map to the `WebhookEventType.ASSET_*` enum values. Subscribers should:

* Verify the HMAC signature on every request (the webhook delivery layer signs the payload — see [webhook delivery runbook](./webhook-delivery.md) when written).
* Treat events as at-most-once. The Phase 250.1.D idempotency layer prevents duplicate workflow execution but NOT duplicate webhook delivery on transient subscriber 5xx (the event bus retries up to 3 times per subscriber).
* Reconcile from the REST API on failure rather than building deep state from events alone.

---

## B2-6 audit closeout — what changed in Phase 250.1.G

The B2-6 audit flagged that the `AssetEventPublisher.publish_asset_*` methods existed on `AssetService` but **were never called**. The Phase 250.1.A workflow re-sequence (asset persistence moved AFTER pre-gates) is the canonical opportunity to wire them in correctly:

* `_create_asset_record_task` and `_activate_asset_task` now call `AssetCreationWorkflow._enqueue_asset_event` to register a `transaction.on_commit` callback that publishes the corresponding `asset.*` event. Test pin: [test_asset_webhook_event_ordering.py](../../hub/apps/orchestration/workflows/tests/test_asset_webhook_event_ordering.py).
* The B2-13 audit (direct `Asset.objects.create()` callers bypassing AssetService) remains open — those call sites currently DO fire events via the workflow path (because the workflow is still the canonical persistence boundary), but the `AssetService.create_asset` shortcut path used by `views.py` / `ml/services.py` / `ml/training_orchestrator.py` does not yet fire events. Tracked under 250.1.G follow-up.

---

## Implementation references

* Server-side publisher: [hub/apps/core/events/service_publishers.py:146-244](../../hub/apps/core/events/service_publishers.py)
* Event schemas: [hub/apps/core/events/event_types.py:115-176](../../hub/apps/core/events/event_types.py)
* Workflow wiring: [hub/apps/orchestration/workflows/asset_creation.py:1494-1547](../../hub/apps/orchestration/workflows/asset_creation.py) (`_enqueue_asset_event`)
* Ordering tests: [hub/apps/orchestration/workflows/tests/test_asset_webhook_event_ordering.py](../../hub/apps/orchestration/workflows/tests/test_asset_webhook_event_ordering.py)
* Persistence model: [hub/apps/core/events/models.py:12-43](../../hub/apps/core/events/models.py) (`Event` table)
