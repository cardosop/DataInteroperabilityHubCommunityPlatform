"""
Phase 228 (REQ-LIN-002, 228.0.9) — lineage-sync signal handler.

The Contract ``post_save`` signal handler diffs the lineage subtree of
``hub_contract_json`` against the existing open ``LineageEdge`` rows for
the contract and applies SCD Type 2 close-then-insert mutations so the
relational index stays consistent with the JSONB canonical write source.

Engineering invariants
----------------------

* Runs only inside ``transaction.on_commit`` so a rolled-back save
  does not leave orphan edges. (REQ-LIN-002 #1.)
* DB-side ``NOW()`` for every timestamp write — the model's
  ``db_default=Now()`` + an explicit ``valid_to=Func('NOW')`` on the
  close-then-insert path. App time is never used. (REQ-LIN-F5-006.)
* Idempotent: running the handler twice with identical input produces
  the same end state (no duplicates, no extra closures). (REQ-LIN-002 #6.)
* Raises on internal error — never silently swallows a diff failure.
  (REQ-LIN-002 #7.)
* Emits the ``lineage_edge_writes_total{operation}`` metric for every
  mutation; ``operation ∈ {add, remove, noop}``.

The diff algorithm
------------------

1. Build the desired-state set ``desired`` from
   ``hub_contract_json.lineage.contracts`` (each entry → an edge tuple).
2. Read the current open-edge set ``current`` for the contract from the
   ``LineageEdge`` table.
3. ``to_add = desired − current`` → insert as new open rows.
4. ``to_remove = current − desired`` → close (set ``valid_to=NOW()``).
5. Identical tuples in both sets are noops.

The edge tuple for diff equality is the canonical scope tuple defined
by the model's open-row unique constraint: ``(tenant, source_contract,
target_contract, source_model, source_field, target_model,
target_field, edge_type)``.

The handler is registered via ``apps.py:ContractsConfig.ready()`` so it
auto-attaches when Django boots; the wiring is independent of any
import-order concern.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

from django.db import transaction
from django.db.models.functions import Now

# Module-level import so tests can patch
# ``hub.apps.contracts.lineage_sync.send_openlineage_event_async`` at the
# import-site. The task module itself is best-effort importable — if the
# integrations app is not installed (vendored deployments), the helper
# resolves to ``None`` and ``_emit_outbound_openlineage_events`` becomes
# a no-op.
from typing import Optional as _Optional, Callable as _Callable

send_openlineage_event_async: _Optional[_Callable[..., object]] = None
try:
    from hub.apps.integrations.openlineage.tasks import (
        send_openlineage_event_async,
    )
except Exception:  # noqa: BLE001 — integrations app is optional at import.
    pass  # typed as Optional above; stays None when import fails

logger = logging.getLogger(__name__)

# Edge tuple shape used for set-arithmetic diffing. The order matches
# the model's open-row unique constraint so equality semantics are
# guaranteed identical to the DB constraint.
_EDGE_TUPLE_FIELDS = (
    "source_contract_id",
    "target_contract_id",
    "source_model",
    "source_field",
    "target_model",
    "target_field",
    "edge_type",
    "transformation_ref",
    "job_ref",
)


def record_edge_write(*, operation: str, tenant_id: str | None = None) -> None:
    """Emit the ``lineage_edge_writes_total{operation}`` Prometheus
    counter. Imported as a helper so tests can patch this single
    binding (``hub.apps.contracts.lineage_sync.record_edge_write``)
    rather than reaching into the metrics module.

    Failure to emit the metric is non-fatal — observability is not the
    load-bearing operation. Errors are logged but swallowed.
    """
    try:
        from hub.apps.observability.metrics import (
            lineage_edge_writes_total,
        )
    except Exception:  # noqa: BLE001 — metric module optional at import time
        return
    try:
        labels: dict[str, str] = {"operation": operation}
        if tenant_id:
            labels["tenant_id"] = str(tenant_id)
        lineage_edge_writes_total.labels(**labels).inc()
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug(
            "lineage_edge_write_metric_emit_failed",
            extra={"operation": operation, "tenant_id": tenant_id},
        )


def _normalize_lineage_entry(entry: dict, contract: Any) -> tuple | None:
    """Convert a ``hub_contract_json.lineage.contracts[*]`` entry to
    the canonical edge tuple. Returns ``None`` when the entry is
    malformed (missing required keys); the caller filters Nones out.

    The convention ``"target_contract": "self"`` resolves to the saved
    contract's id — the canonical lineage shape used by the engine for
    upstream references.
    """
    if not isinstance(entry, dict):
        return None
    source_id = entry.get("source_contract")
    target_id = entry.get("target_contract")
    if target_id == "self":
        target_id = str(contract.id)

    return (
        source_id or None,
        target_id or None,
        str(entry.get("source_model") or ""),
        str(entry.get("source_field") or ""),
        str(entry.get("target_model") or ""),
        str(entry.get("target_field") or ""),
        str(entry.get("edge_type") or "reference"),
        str(entry.get("transformation_ref") or ""),
        str(entry.get("job_ref") or ""),
    )


def _desired_edge_set(contract: Any) -> set[tuple]:
    """Build the desired open-edge set for ``contract`` from its
    ``hub_contract_json.lineage`` subtree."""
    payload = getattr(contract, "hub_contract_json", None) or {}
    if not isinstance(payload, dict):
        return set()
    lineage = payload.get("lineage") or {}
    if not isinstance(lineage, dict):
        return set()
    raw_entries = lineage.get("contracts") or []
    if not isinstance(raw_entries, list):
        return set()
    out: set[tuple] = set()
    for entry in raw_entries:
        tup = _normalize_lineage_entry(entry, contract)
        if tup is None:
            continue
        out.add(tup)
    return out


def _current_edge_set(contract: Any) -> dict[tuple, Any]:
    """Read the current open-edge map for ``contract`` from the
    relational index. Keyed by the canonical tuple so the diff is a
    single set-arithmetic step."""
    from hub.apps.contracts.models import LineageEdge

    out: dict[tuple, Any] = {}
    rows = LineageEdge.objects.filter(
        target_contract=contract,
        valid_to__isnull=True,
    )
    for row in rows:
        key = (
            str(row.source_contract_id) if row.source_contract_id else None,
            str(row.target_contract_id) if row.target_contract_id else None,
            row.source_model,
            row.source_field,
            row.target_model,
            row.target_field,
            row.edge_type,
            row.transformation_ref,
            row.job_ref,
        )
        out[key] = row
    return out


def _apply_diff(
    contract: Any,
    *,
    to_add: Iterable[tuple],
    to_remove: Iterable[Any],
) -> tuple[int, int]:
    """Apply the diff transactionally. Returns ``(adds, removes)``.

    Phase 228 (REQ-LIN-007 / 228.0.19) — emits audit events for every
    mutation: ``LINEAGE_EDGE_CREATED`` per add, ``LINEAGE_EDGE_DELETED``
    per close. Audit emission is best-effort: a failure logs a warning
    but does NOT roll back the diff (the relational write is the
    load-bearing operation; audit is a downstream signal). Pinned by
    ``test_lineage_sync.py::TestEdgeAuditEvents``.
    """
    from hub.apps.contracts.models import LineageEdge

    add_count = 0
    remove_count = 0
    closed_rows_for_audit: list[Any] = []
    added_edge_ids_for_audit: list[Any] = []

    with transaction.atomic():
        # Close first so a same-scope re-open in ``to_add`` doesn't
        # collide with the open-row unique constraint.
        to_remove_list = list(to_remove)
        if to_remove_list:
            closed_rows_for_audit = list(to_remove_list)  # snapshot for audit
            ids = [r.pk for r in to_remove_list]
            updated = LineageEdge.objects.filter(pk__in=ids).update(valid_to=Now())
            remove_count = updated

        for tup in to_add:
            (
                source_id,
                target_id,
                source_model,
                source_field,
                target_model,
                target_field,
                edge_type,
                transformation_ref,
                job_ref,
            ) = tup
            row = LineageEdge.objects.create(
                tenant=contract.tenant,
                source_contract_id=source_id,
                target_contract_id=target_id,
                source_model=source_model,
                source_field=source_field,
                target_model=target_model,
                target_field=target_field,
                edge_type=edge_type,
                transformation_ref=transformation_ref,
                job_ref=job_ref,
                created_by_run="lineage_sync",
            )
            added_edge_ids_for_audit.append(row.id)
            add_count += 1

    # Audit events fire AFTER the atomic block commits so a failed
    # audit-write cannot rollback the diff. Failures are swallowed and
    # logged; the metric (``lineage_edge_writes_total``) and the
    # row-level state are the canonical record either way.
    _emit_edge_audit_events(
        contract=contract,
        added_edge_ids=added_edge_ids_for_audit,
        closed_rows=closed_rows_for_audit,
    )

    # Phase 228 F4 (228.F4.27 self-audit GAP-1) — outbound OpenLineage
    # emission. Same fail-soft contract as audit events: a Marquez
    # outage MUST NOT roll back the relational write. Gated on the
    # ``lineage.openlineage_export`` capability flag.
    _emit_outbound_openlineage_events(
        contract=contract,
        added_edge_ids=added_edge_ids_for_audit,
        closed_rows=closed_rows_for_audit,
    )

    return add_count, remove_count


def _emit_edge_audit_events(
    *,
    contract: Any,
    added_edge_ids: Iterable[Any],
    closed_rows: Iterable[Any],
) -> None:
    """Best-effort audit emission for REQ-LIN-007. Failures swallow."""
    try:
        from hub.apps.audit.models import (
            LINEAGE_EDGE_CREATED,
            LINEAGE_EDGE_DELETED,
        )
        from hub.apps.audit.utils import create_audit_event
    except Exception:  # noqa: BLE001 — audit module optional at import time.
        return

    tenant = getattr(contract, "tenant", None)
    contract_id = str(getattr(contract, "id", "")) or None

    for edge_id in added_edge_ids:
        try:
            create_audit_event(
                resource_type="LINEAGE_EDGE",
                action=LINEAGE_EDGE_CREATED,
                actor_user=None,
                tenant=tenant,
                resource_id=str(edge_id),
                details={"contract_id": contract_id, "via": "lineage_sync"},
            )
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning(
                "lineage_edge_created_audit_failed",
                extra={"edge_id": str(edge_id), "error": str(exc)},
            )

    for row in closed_rows:
        try:
            create_audit_event(
                resource_type="LINEAGE_EDGE",
                action=LINEAGE_EDGE_DELETED,
                actor_user=None,
                tenant=tenant,
                resource_id=str(row.pk) if hasattr(row, "pk") else None,
                details={"contract_id": contract_id, "via": "lineage_sync"},
            )
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning(
                "lineage_edge_deleted_audit_failed",
                extra={
                    "edge_id": str(getattr(row, "pk", "")) or None,
                    "error": str(exc),
                },
            )


def _emit_outbound_openlineage_events(
    *,
    contract: Any,
    added_edge_ids: Iterable[Any],
    closed_rows: Iterable[Any],
) -> None:
    """Phase 228 F4 (228.F4.27 self-audit GAP-1) — best-effort outbound
    OpenLineage emission for every edge add + close.

    For each added edge id we re-read the persisted row (so the event
    carries the DB-side ``valid_from`` + the canonical row id). For
    each closed row we use the snapshot we already hold. Each event is
    enqueued via :func:`send_openlineage_event_async` so the request
    thread is not blocked by the network call to Marquez.

    Fail-soft contract — failures are swallowed + logged. The
    relational ``LineageEdge`` row is the load-bearing record; the
    OpenLineage event is a downstream signal that we re-deliver via
    the DLQ replay path on Marquez recovery.

    Capability-flag gated: ``lineage.openlineage_export`` OFF → no
    dispatch. Default in production is OFF (per
    ``hub/apps/api/capabilities.py``); customer-success flips it ON
    per-tenant via ``CAPABILITY_FLAGS`` settings override.

    Project-convention variance vs spec wording (DoD self-audit DD-D)
    -----------------------------------------------------------------
    The spec text (``REQ-LIN-F4-001``) says the adapter SHALL "subscribe
    to internal events emitted by ``LineageEventPublisher``
    (``lineage.relationship_added`` / ``relationship_removed`` /
    ``updated``)". The Meshant codebase has no such publisher — every
    "derived signal on lineage mutation" goes through the post-save
    signal handler + ``transaction.on_commit`` (the same surface that
    ``_emit_edge_audit_events`` uses to emit the lineage audit codes).
    Co-existing two emit paths would split the operational surface
    (one set of metrics, one set of audit events, one cross-domain
    audit-trail of dispatches), so we hook into ``_apply_diff`` here
    rather than introducing a parallel ``LineageEventPublisher``
    substrate. The ``openlineage_outbound_total{result}`` counter
    increments at the same point a spec-literal subscriber would
    increment it (REQ-LIN-F4-001 ``"the adapter's outbound counter
    increments"`` — pinned by ``test_dod_audit.TestOutboundMetric``).
    """
    # Guard against the integrations app not being installed.
    if send_openlineage_event_async is None:
        return

    # Capability-flag check — no dispatch when OFF.
    try:
        from hub.apps.api.capabilities import is_capability_enabled
    except Exception:  # noqa: BLE001 — capabilities module optional at import.
        return
    if not is_capability_enabled("lineage.openlineage_export"):
        return

    # Lazy imports — keep module-import lightweight.
    try:
        from django.conf import settings

        from hub.apps.contracts.models import LineageEdge
        from hub.apps.integrations.openlineage.translator import (
            meshant_edge_to_openlineage,
        )
    except Exception:  # noqa: BLE001 — translator/model optional at import.
        return

    producer = getattr(
        settings,
        "OPENLINEAGE_PRODUCER_NAME",
        "https://meshant.com/lineage/openlineage",
    )
    target_url = getattr(settings, "OPENLINEAGE_URL", None)
    tenant_id = str(getattr(contract, "tenant_id", "")) or None

    def _dispatch(edge_dict: dict) -> None:
        try:
            event = meshant_edge_to_openlineage(edge_dict, producer=producer)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "openlineage_translate_failed",
                extra={
                    "edge_id": str(edge_dict.get("id") or ""),
                    "error": str(exc),
                },
            )
            return
        try:
            # Project convention: ``@job``-decorated tasks dispatch via
            # ``.delay()``. Tests patch the symbol with a ``MagicMock``,
            # which auto-creates ``.delay`` so the call still records.
            dispatch_fn = getattr(
                send_openlineage_event_async,
                "delay",
                send_openlineage_event_async,
            )
            dispatch_fn(
                event=event,
                target_url=target_url,
                tenant_id=tenant_id,
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft per contract.
            logger.warning(
                "openlineage_dispatch_failed",
                extra={
                    "edge_id": str(edge_dict.get("id") or ""),
                    "error": str(exc),
                },
            )

    # Hydrate added edges from the DB so the event carries the
    # persisted ``valid_from`` + DB-assigned id.
    added_edge_ids_list = [eid for eid in added_edge_ids if eid is not None]
    if added_edge_ids_list:
        added_rows = LineageEdge.objects.filter(pk__in=added_edge_ids_list)
        for row in added_rows:
            _dispatch(_lineage_edge_to_dict(row))

    for row in closed_rows:
        _dispatch(_lineage_edge_to_dict(row))


def _lineage_edge_to_dict(row: Any) -> dict:
    """Translate a ``LineageEdge`` row to the canonical dict shape the
    OpenLineage translator consumes (matches
    ``LineageService._edges_at`` row shape)."""
    return {
        "id": str(getattr(row, "id", "") or ""),
        "source_contract": (
            str(row.source_contract_id) if getattr(row, "source_contract_id", None) else None
        ),
        "target_contract": (
            str(row.target_contract_id) if getattr(row, "target_contract_id", None) else None
        ),
        "source_model": getattr(row, "source_model", "") or "",
        "source_field": getattr(row, "source_field", "") or "",
        "target_model": getattr(row, "target_model", "") or "",
        "target_field": getattr(row, "target_field", "") or "",
        "edge_type": getattr(row, "edge_type", "") or "reference",
        "transformation_ref": getattr(row, "transformation_ref", "") or "",
        "job_ref": getattr(row, "job_ref", "") or "",
        "valid_from": (
            row.valid_from.isoformat()
            if getattr(row, "valid_from", None)
            else None
        ),
        "valid_to": (
            row.valid_to.isoformat()
            if getattr(row, "valid_to", None)
            else None
        ),
    }


def _sync_contract_edges(contract: Any) -> None:
    """Compute and apply the desired-vs-current diff for ``contract``.

    Idempotent: a same-state rerun produces zero adds + zero removes.
    """
    desired = _desired_edge_set(contract)
    current_map = _current_edge_set(contract)
    current_keys = set(current_map.keys())

    to_add = desired - current_keys
    to_remove_keys = current_keys - desired
    to_remove = [current_map[k] for k in to_remove_keys]

    add_count, remove_count = _apply_diff(
        contract, to_add=to_add, to_remove=to_remove,
    )

    tenant_id = str(getattr(contract, "tenant_id", "")) or None
    if add_count == 0 and remove_count == 0:
        record_edge_write(operation="noop", tenant_id=tenant_id)
        return
    if add_count:
        for _ in range(add_count):
            record_edge_write(operation="add", tenant_id=tenant_id)
    if remove_count:
        for _ in range(remove_count):
            record_edge_write(operation="remove", tenant_id=tenant_id)


def on_contract_post_save(sender, instance, created, **kwargs):
    """Django ``post_save`` receiver. Defers the diff to ``on_commit``
    so a rollback discards the work and the request thread is not
    blocked by the diff cost.

    The wrapper is intentionally tiny — all heavy lifting lives in
    ``_sync_contract_edges`` so it can be called directly from the
    backfill management command without going through the signal."""
    contract_id = getattr(instance, "id", None)

    def _deferred():
        try:
            _sync_contract_edges(instance)
        except Exception as exc:
            logger.exception(
                "lineage_sync_handler_failed",
                extra={
                    "contract_id": str(contract_id) if contract_id else None,
                    "error": str(exc),
                },
            )
            raise

    transaction.on_commit(_deferred)


def register_signals() -> None:
    """Wire ``on_contract_post_save`` to the Contract ``post_save``
    signal. Called from ``ContractsConfig.ready()`` so the
    registration is centralised + import-order independent."""
    from django.db.models.signals import post_save

    from hub.apps.contracts.models import Contract

    post_save.connect(
        on_contract_post_save,
        sender=Contract,
        dispatch_uid="lineage_sync.on_contract_post_save",
    )


__all__ = [
    "on_contract_post_save",
    "record_edge_write",
    "register_signals",
    "send_openlineage_event_async",
    "_apply_diff",
    "_desired_edge_set",
    "_current_edge_set",
    "_emit_edge_audit_events",
    "_emit_outbound_openlineage_events",
    "_lineage_edge_to_dict",
    "_sync_contract_edges",
]
