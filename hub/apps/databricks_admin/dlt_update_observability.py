"""Phase 10 (openspec add-databricks-dlt-pipelines task 10.6) — the DLT
update terminal-transition observability (design D6).

A terminal update (the 10.2 vocabulary's quartet COMPLETED / FAILED /
CANCELED / TIMED_OUT) finalizes through ONE chokepoint
(``finalize_terminal_update``), which:

- derives the events-derived DBU ESTIMATE — wall-clock duration (the
  update's events: first→last reported timestamp) x the cluster size
  factor (the pipeline spec's clusters, 1 + 0.5 x workers — the 4.4
  heuristic) x the settings-overridable DBH rate
  (``DATABRICKS_DLT_UPDATE_COST_ESTIMATE_DBH_RATE``, default 0.55) —
  and writes it onto the mirror row's ``dbu`` column together with the
  update's last reported event message as ``error_message`` (FAILED
  only — never invented),
- records ONE ``CostRecord`` through the provider-agnostic
  cost-recording seam (``warehouses.cost_recording.record_cost``, the
  7.5 inversion) with source ``dlt_update`` — stored, not billed (P7
  attribution + enforcement apply),
- emits the OpenLineage run event — COMPLETE / FAIL with the
  errorMessage facet — capability-gated ``lineage.openlineage_export``,
  fire-and-forget via the module-level dispatch seam (the 4.4
  convention), and
- fires the ``databricks.dlt.update.failed`` webhook on a terminal
  FAILED update (the 10.6 seam, best-effort).

Contracts:

- **Exactly-once**: the chokepoint runs ONLY while the row's ``dbu`` IS
  NULL (the 10.3 mirror never writes it) — the second finalize is a
  no-op, and the guard is re-checked inside ``select_for_update`` so
  two racing passes still land exactly one ledger row.
- **Never invented**: a terminal update whose events carry no usable
  timestamps finalizes with a ZERO-unit estimate (the row and the
  ledger still exist — the P7 billing sync later appends the billed
  truth); malformed events are skipped, never guessed.
- **Best-effort**: the lineage dispatch, the webhook fan-out, the
  metric, and the cost seam are all fail-soft — a broken lineage
  endpoint, an unreachable webhook, or a dropped ledger write never
  blocks the terminal transition (the Phase 273 discipline).
- **The caller owns the client**: ``finalize_pending_terminal_updates``
  takes the raw ``DatabricksApiClient`` as the required keyword (the
  10.3 mirror's contract — identity resolution is the caller's
  concern). The pass wraps itself in ``tenant_context`` (the CLAUDE.md
  worker contract — the writes touch tenant-scoped rows).

Scope: the pass is the machinery; wiring it onto a cron/JobType (the
1.5/7.3 pattern) is a follow-up the roadmap names (the same honest note
as the 10.3 mirror).
"""

from __future__ import annotations

import contextlib
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from hub.apps.databricks_admin.models import (
    DatabricksDltPipeline,
    DatabricksDltPipelineUpdate,
)
from hub.apps.tenants.request_tenant import tenant_context

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.models import DatabricksWorkspace

logger = logging.getLogger(__name__)

# The outbound OpenLineage dispatch (the contracts/lineage_sync seam):
# lazy-imported so the module imports without the integrations app, and
# a MODULE-LEVEL attribute so the sanctioned patch point in tests
# (monkeypatching ``dlt_update_observability.send_openlineage_event_async``)
# reaches every dispatch (the 4.4 convention).
send_openlineage_event_async: Any | None = None
with contextlib.suppress(ImportError):
    from hub.apps.integrations.openlineage.tasks import (
        send_openlineage_event_async,
    )

# The 10.6 webhook notifier — the same lazy-import sanctioned-patch-point
# shape as the lineage seam.
notify_dlt_update_failed: Any | None = None
with contextlib.suppress(ImportError):
    from hub.apps.databricks_admin.dlt_webhooks import (
        notify_dlt_update_failed,
    )

# The terminal update quartet (the 10.2 model's reported set) — the
# chokepoint finalizes ONLY these; every other reported state is still
# in flight and never touched here.
_TERMINAL_UPDATE_STATES = frozenset({"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"})

# The cost-estimate heuristic base rate (USD per DBH). P7 replaces the
# estimate with real attribution; until then this documented constant
# feeds the stored estimate (the 4.4 ``_DEFAULT_DBH_RATE`` convention).
_DEFAULT_DBH_RATE = 0.55


def estimate_dlt_update_cost(*, duration_seconds: float, workers: int, dbh_rate: float) -> dict:
    """The duration-x-size-x-rate ESTIMATE (design D6 — stored, not
    billed; P7 replaces it with real attribution).

    The size factor is the 4.4 heuristic (1 + 0.5 x workers); workers
    are clamped to zero (a malformed spec never invents compute).
    """
    try:
        workers = max(0, int(workers))
    except (TypeError, ValueError):
        workers = 0
    duration_seconds = max(0.0, float(duration_seconds))
    size_factor = 1.0 + 0.5 * workers
    rate = float(dbh_rate)
    cost = (duration_seconds / 3600.0) * rate * size_factor
    return {
        "duration_seconds": duration_seconds,
        "size_factor": size_factor,
        "dbh_rate": rate,
        "estimated_cost": round(cost, 6),
        "formula": "duration_hours x dbh_rate x (1 + 0.5 x workers)",
    }


def _event_timestamp_ms(event: Any) -> float | None:
    """One event's reported timestamp in milliseconds — a malformed
    shape yields None (skipped, never guessed)."""
    if not isinstance(event, dict):
        return None
    value = event.get("timestamp")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _event_update_id(event: Any) -> str | None:
    """One event's reported update identity from its details — absent
    or malformed details yield None (skipped, never guessed)."""
    if not isinstance(event, dict):
        return None
    details = event.get("details")
    if not isinstance(details, dict):
        return None
    value = details.get("update_id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    result = str(value).strip()
    return result or None


def derive_update_metrics(
    *,
    update_id: str,
    state: str,
    events: list,
    workers: int,
    dbh_rate: float | None = None,
) -> dict:
    """Derive the update's cost estimate + failure message from the
    pipeline's events (the API's own reported text — never invented).

    Duration spans the update's matching events (first→last timestamp);
    zero events or unusable timestamps yield a ZERO-unit estimate (the
    row still finalizes — the billing sync appends the truth later).
    The error message (FAILED only) is the update's LAST matching event
    message in timestamp order.
    """
    rate = float(
        dbh_rate
        if dbh_rate is not None
        else getattr(settings, "DATABRICKS_DLT_UPDATE_COST_ESTIMATE_DBH_RATE", _DEFAULT_DBH_RATE)
    )

    timestamps: list[float] = []
    messages: list[tuple[float, str]] = []
    for event in events:
        if _event_update_id(event) != update_id:
            continue
        timestamp = _event_timestamp_ms(event)
        message = event.get("message") if isinstance(event, dict) else None
        if timestamp is not None:
            timestamps.append(timestamp)
        if isinstance(message, str) and message.strip():
            messages.append((timestamp if timestamp is not None else float("-inf"), message))

    duration_seconds = (max(timestamps) - min(timestamps)) / 1000.0 if timestamps else 0.0

    error_message: str | None = None
    if state == "FAILED" and messages:
        error_message = max(messages, key=lambda pair: pair[0])[1]

    estimate = estimate_dlt_update_cost(
        duration_seconds=duration_seconds, workers=workers, dbh_rate=rate
    )
    return {
        **estimate,
        "error_message": error_message,
        "matched_events": len(timestamps),
    }


def _pipeline_workers(pipeline: DatabricksDltPipeline) -> int:
    """The pipeline spec's total worker count (the size factor input) —
    a malformed spec contributes zero (never invented)."""
    settings_spec = pipeline.settings or {}
    clusters = settings_spec.get("clusters") if isinstance(settings_spec, dict) else None
    if not isinstance(clusters, list):
        return 0
    total = 0
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        try:
            total += max(0, int(cluster.get("num_workers") or 0))
        except (TypeError, ValueError):
            continue
    return total


def finalize_terminal_update(
    *,
    workspace: DatabricksWorkspace,
    pipeline: DatabricksDltPipeline,
    update_row: DatabricksDltPipelineUpdate,
    events: list,
) -> dict:
    """The terminal-transition chokepoint (design D6).

    Finalizes a terminal update exactly once: writes the events-derived
    ``dbu`` + ``error_message`` onto the mirror row, records ONE ledger
    row through the cost-recording seam, emits the OpenLineage run
    event (capability-gated), records the metric, and fires the
    failure webhook on FAILED. Every emission is best-effort — none of
    them can block the transition. A non-terminal row and an
    already-billed row are no-ops.
    """
    state = update_row.state
    if state not in _TERMINAL_UPDATE_STATES:
        return {"finalized": False, "reason": "non_terminal"}

    workers = _pipeline_workers(pipeline)
    metrics = derive_update_metrics(
        update_id=update_row.update_id, state=state, events=events, workers=workers
    )
    units = round(metrics["estimated_cost"], 6)

    # The exactly-once guard, re-checked under a row lock — two racing
    # passes still land exactly one ledger row.
    with transaction.atomic():
        locked = (
            DatabricksDltPipelineUpdate.objects.select_for_update().filter(pk=update_row.pk).first()
        )
        if locked is None or locked.dbu is not None:
            return {"finalized": False, "reason": "already_billed"}
        locked.dbu = Decimal(str(units))
        if state == "FAILED" and metrics["error_message"]:
            locked.error_message = metrics["error_message"]
        locked.synced_at = timezone.now()
        locked.save(update_fields=["dbu", "error_message", "synced_at"])
        update_row.refresh_from_db()

    _record_cost(workspace, pipeline, update_row, metrics)
    _emit_lineage(workspace, pipeline, update_row)
    # 10.8 — the terminal audit (SUCCEEDED for COMPLETED, FAILED for
    # every other terminal state), best-effort by the helper's contract.
    from hub.apps.databricks_admin.dlt_lifecycle import emit_dlt_update_terminal

    emit_dlt_update_terminal(workspace, pipeline, update_row)
    try:
        from hub.apps.databricks_admin.metrics import record_dlt_update_outcome

        record_dlt_update_outcome(
            state, tenant_id=str(workspace.tenant_id), workspace_id=str(workspace.id)
        )
    except Exception:
        logger.warning(
            "databricks_dlt_update_metric_failed",
            extra={"update_id": update_row.update_id},
        )
    if state == "FAILED":
        _notify_failure(workspace, pipeline, update_row)

    return {"finalized": True, "units": units}


def _record_cost(workspace, pipeline, update_row, metrics: dict) -> None:
    """ONE ledger row per terminal update through the provider-agnostic
    seam (the 7.5 inversion). The facade never raises by contract; the
    mirror row's ``dbu`` is the stored truth regardless (a dropped
    ledger write never breaks the transition)."""
    try:
        from hub.apps.warehouses.cost_recording import CostRecord, record_cost

        record_cost(
            CostRecord(
                tenant_id=str(workspace.tenant_id),
                units=metrics["estimated_cost"],
                unit_label="USD_ESTIMATE",
                source="dlt_update",
                workspace_id=str(workspace.id),
                meta={
                    "pipeline_id": pipeline.pipeline_id,
                    "update_id": update_row.update_id,
                    "duration_seconds": metrics["duration_seconds"],
                    "size_factor": metrics["size_factor"],
                    "dbh_rate": metrics["dbh_rate"],
                },
            )
        )
    except Exception:
        logger.warning(
            "databricks_dlt_update_cost_record_failed",
            extra={"update_id": update_row.update_id},
            exc_info=True,
        )


def _emit_lineage(workspace, pipeline, update_row) -> None:
    """The terminal OpenLineage run event — COMPLETE on success, FAIL
    with the errorMessage facet on failure. Capability-gated
    (``lineage.openlineage_export``) and fail-soft (the
    contracts/lineage_sync convention); the dispatch is
    fire-and-forget (the 4.4 pattern)."""
    try:
        from hub.apps.api.capabilities import is_capability_enabled
    except Exception:
        return
    if not is_capability_enabled("lineage.openlineage_export"):
        return

    if send_openlineage_event_async is None:
        return

    from hub.apps.integrations.openlineage.translator import OPENLINEAGE_SCHEMA_URL

    # A terminal that did not COMPLETE is a FAIL event — CANCELED and
    # TIMED_OUT included (the 4.4 convention: never a fabricated
    # COMPLETE for an update that did not finish successfully).
    failed = update_row.state != "COMPLETED"
    producer = getattr(
        settings,
        "OPENLINEAGE_PRODUCER_NAME",
        "https://meshant.com/dlt/openlineage",
    )
    run_facets: dict[str, Any] = {}
    if failed:
        message = update_row.error_message or "the Databricks DLT update failed"
        run_facets["errorMessage"] = {
            "message": message,
            "programmingLanguage": None,
            "stackTrace": None,
        }
    event = {
        "eventType": "FAIL" if failed else "COMPLETE",
        "eventTime": timezone.now().isoformat(),
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
        "run": {
            "runId": f"databricks:{pipeline.pipeline_id}:{update_row.update_id}",
            "facets": run_facets,
        },
        "job": {
            "namespace": "meshant.databricks",
            "name": pipeline.name or pipeline.pipeline_id,
        },
        "inputs": [],
        "outputs": [],
    }
    try:
        dispatch_fn = getattr(send_openlineage_event_async, "delay", send_openlineage_event_async)
        dispatch_fn(
            event=event,
            target_url=getattr(settings, "OPENLINEAGE_URL", None),
            tenant_id=str(workspace.tenant_id),
        )
    except Exception as exc:
        logger.warning(
            "databricks_dlt_update_lineage_dispatch_failed",
            extra={"update_id": update_row.update_id, "error": str(exc)},
        )


def _notify_failure(workspace, pipeline, update_row) -> None:
    """10.6 — the ``databricks.dlt.update.failed`` webhook on a terminal
    FAILED update. Best-effort: the helper itself never raises by
    contract, and the call is guarded regardless."""
    if notify_dlt_update_failed is None:
        return
    try:
        notify_dlt_update_failed(
            tenant_id=str(workspace.tenant_id),
            workspace_id=str(workspace.id),
            pipeline_id=pipeline.pipeline_id,
            update_id=update_row.update_id,
            state=update_row.state,
            error_message=update_row.error_message,
        )
    except Exception:
        logger.warning(
            "databricks_dlt_update_webhook_failed",
            extra={"update_id": update_row.update_id},
        )


def _list_all_events(client: DatabricksApiClient, pipeline_id: str) -> list:
    """Every page of the pipeline's events (the page_token chain with
    the 1.12 repeating-token guard — a real workspace bug surface must
    fail classified, never hang)."""
    from hub.apps.databricks_admin.pipelines_mirror import _list_pages

    return _list_pages(client, "pipelines.events.list", "events", {"pipeline_id": pipeline_id})


def finalize_pending_terminal_updates(
    *, workspace: DatabricksWorkspace, client: DatabricksApiClient
) -> dict:
    """The observability pass over the mirrored fleet: for every
    pipeline of the workspace, list ALL its events (page chain), then
    finalize every terminal update row whose ``dbu`` is still NULL.

    Runs inside ``tenant_context`` (the CLAUDE.md worker contract); a
    transient events-list failure for one pipeline aborts that pipeline
    with the classified error (never a half-billed row — the finalize
    happens only after the events land).
    """
    counters = {"pipelines": 0, "finalized": 0, "already_billed": 0}
    with tenant_context(str(workspace.tenant_id)):
        pipelines = DatabricksDltPipeline.objects.filter(workspace=workspace).order_by(
            "pipeline_id"
        )
        for pipeline in pipelines:
            events = _list_all_events(client, pipeline.pipeline_id)
            counters["pipelines"] += 1
            terminal_rows = DatabricksDltPipelineUpdate.objects.filter(
                pipeline=pipeline, state__in=_TERMINAL_UPDATE_STATES
            ).order_by("update_id")
            for update_row in terminal_rows:
                if update_row.dbu is not None:
                    counters["already_billed"] += 1
                    continue
                result = finalize_terminal_update(
                    workspace=workspace,
                    pipeline=pipeline,
                    update_row=update_row,
                    events=events,
                )
                if result.get("finalized"):
                    counters["finalized"] += 1
                elif result.get("reason") == "already_billed":
                    counters["already_billed"] += 1
    return counters
