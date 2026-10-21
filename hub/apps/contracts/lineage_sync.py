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
3. ``to_add = desired - current`` → insert as new open rows.
4. ``to_remove = current - desired`` → close (set ``valid_to=NOW()``).
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

import contextlib
import logging
import re
from collections.abc import Callable as _Callable
from collections.abc import Iterable
from typing import Any

# Module-level import so tests can patch
# ``hub.apps.contracts.lineage_sync.send_openlineage_event_async`` at the
# import-site. The task module itself is best-effort importable — if the
# integrations app is not installed (vendored deployments), the helper
# resolves to ``None`` and ``_emit_outbound_openlineage_events`` becomes
# a no-op.
from django.db import transaction
from django.db.models.functions import Now

from hub.apps.audit.models import LINEAGE_EDGE_CREATED, LINEAGE_EDGE_DELETED
from hub.apps.audit.utils import create_audit_event
from hub.apps.observability.metrics import lineage_edge_writes_total
from hub.apps.tenants.request_tenant import tenant_context

send_openlineage_event_async: _Callable[..., object] | None = None
with contextlib.suppress(ImportError, RuntimeError):
    from hub.apps.integrations.openlineage.tasks import (
        send_openlineage_event_async,  # typed as Optional above; stays None when import fails
    )

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
        labels: dict[str, str] = {"operation": operation}
        if tenant_id:
            labels["tenant_id"] = str(tenant_id)
        lineage_edge_writes_total.labels(**labels).inc()
    except Exception:
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

    W4.5 — the malformed-entry filter actually FILTERS now: pre-fix the
    function's docstring promised ``None`` but the body always returned
    a tuple, so an anchorless entry (e.g. ``{"name": "..."}``) became a
    ``(None, None, "", ...)`` edge row that violated the open-row
    constraint inside ``_apply_diff`` — the whole diff transaction
    rolled back and EVERY legitimate edge in the same save was lost.
    """
    if not isinstance(entry, dict):
        return None
    source_id = entry.get("source_contract")
    target_id = entry.get("target_contract")
    if target_id == "self":
        target_id = str(contract.id)
    if not source_id and not target_id:
        # Anchorless entry — no relational edge can be derived.
        return None

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
    ``hub_contract_json.lineage`` subtree.

    Two canonical shapes coexist:

    * ``lineage.contracts`` — YAML/reference entries
      (``source_contract`` / ``target_contract`` / ``edge_type``).
    * ``lineage.entries`` — the F2 lineage-edit canonical form, where
      ``entries[*].input_fields[*].namespace`` carries the source
      contract UUID and the target-side fields are empty (the edit
      writer's defaults).

    The F2 edit endpoint (``lineage_edit_service``) writes relational
    rows AND re-serialises the JSON to the ``entries`` shape — a sync
    that ignored that shape tore the freshly-written rows down on the
    very next contract save, leaving every listing lineage graph empty
    (b6 lineage skips root cause).
    """
    payload = getattr(contract, "hub_contract_json", None) or {}
    if not isinstance(payload, dict):
        return set()
    lineage = payload.get("lineage") or {}
    if not isinstance(lineage, dict):
        return set()
    out: set[tuple] = set()

    raw_entries = lineage.get("contracts") or []
    if isinstance(raw_entries, list):
        for entry in raw_entries:
            tup = _normalize_lineage_entry(entry, contract)
            if tup is None:
                continue
            out.add(tup)

    f2_entries = lineage.get("entries") or []
    if isinstance(f2_entries, list):
        import uuid as _uuid

        for entry in f2_entries:
            if not isinstance(entry, dict):
                continue
            for field in entry.get("input_fields") or []:
                if not isinstance(field, dict):
                    continue
                src = field.get("namespace")
                if not isinstance(src, str) or not src:
                    continue
                try:
                    _uuid.UUID(src)
                except ValueError:
                    # Non-contract namespace (model namespace string) —
                    # not a relational edge source.
                    continue
                out.add(
                    (
                        src,
                        str(contract.id),
                        str(field.get("name") or ""),
                        str(field.get("field") or ""),
                        "",
                        "",
                        "reference",
                        "",
                        "",
                    )
                )
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
        except Exception as exc:
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
        except Exception as exc:
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
    except ImportError:
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
    # W12.9: kept — openlineage.translator raises RuntimeError when
    # Django apps aren't ready yet (signal handlers can run during
    # early startup); the (ImportError, RuntimeError) guard is the
    # deliberate degrade-to-no-op for that context.
    except (ImportError, RuntimeError):
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
        except (ValueError, TypeError, AttributeError) as exc:
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
        except Exception as exc:
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
            str(row.source_contract_id)
            if getattr(row, "source_contract_id", None)
            else None
        ),
        "target_contract": (
            str(row.target_contract_id)
            if getattr(row, "target_contract_id", None)
            else None
        ),
        "source_model": getattr(row, "source_model", "") or "",
        "source_field": getattr(row, "source_field", "") or "",
        "target_model": getattr(row, "target_model", "") or "",
        "target_field": getattr(row, "target_field", "") or "",
        "edge_type": getattr(row, "edge_type", "") or "reference",
        "transformation_ref": getattr(row, "transformation_ref", "") or "",
        "job_ref": getattr(row, "job_ref", "") or "",
        "valid_from": (
            row.valid_from.isoformat() if getattr(row, "valid_from", None) else None
        ),
        "valid_to": (
            row.valid_to.isoformat() if getattr(row, "valid_to", None) else None
        ),
    }


def _sync_contract_edges(contract: Any) -> None:
    """Compute and apply the desired-vs-current diff for ``contract``.

    Idempotent: a same-state rerun produces zero adds + zero removes.

    Self-contained worker: the diff runs inside ``tenant_context`` —
    both call paths (the post_save on_commit deferral AND the backfill
    management command) are covered, never relying on a caller's wrap.
    """
    tenant_id = str(getattr(contract, "tenant_id", "")) or None
    if not tenant_id:
        return
    with tenant_context(tenant_id):
        _sync_contract_edges_in_context(contract, tenant_id=tenant_id)


def _sync_contract_edges_in_context(contract: Any, *, tenant_id: str) -> None:
    """The tenant-context-wrapped body of ``_sync_contract_edges``."""
    desired = _desired_edge_set(contract)
    current_map = _current_edge_set(contract)
    current_keys = set(current_map.keys())

    to_add = desired - current_keys
    to_remove_keys = current_keys - desired
    to_remove = [current_map[k] for k in to_remove_keys]

    add_count, remove_count = _apply_diff(
        contract,
        to_add=to_add,
        to_remove=to_remove,
    )

    if add_count == 0 and remove_count == 0:
        record_edge_write(operation="noop", tenant_id=tenant_id)
        return
    if add_count:
        for _ in range(add_count):
            record_edge_write(operation="add", tenant_id=tenant_id)
    if remove_count:
        for _ in range(remove_count):
            record_edge_write(operation="remove", tenant_id=tenant_id)

    # W4.5 (R2-I2) — the ``LineageEdge`` transitions above run through
    # queryset ``.update()`` (the SCD2 close) and bulk inserts, which
    # bypass every signal/cache path. When the edge set actually
    # changed, invalidate the affected contract's lineage caches so
    # the lineage GET reflects the new edges instead of the cached
    # pre-save snapshot. ``transaction.on_commit`` covers BOTH call
    # shapes uniformly: from the post-save handler (already post-
    # commit, autocommit) it executes immediately; from the backfill
    # command (inside its atomic) it defers to that transaction's
    # commit. Fail-soft — a cache outage must not undo a committed
    # edge diff.
    def _invalidate_after_edge_diff():
        try:
            from hub.apps.contracts.caching import invalidate_lineage_cache

            invalidate_lineage_cache(str(contract.id))
        except (
            Exception
        ) as exc:  # noqa: BLE001 - fail-soft: cache outage must not undo the diff
            logger.warning(
                "lineage_sync_cache_invalidation_failed contract_id=%s error=%s",
                contract.id,
                exc,
            )

    transaction.on_commit(_invalidate_after_edge_diff)


def on_contract_post_save(sender, instance, created, **_kwargs):
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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 UC mirror lineage (openspec add-databricks-uc-read task 1.6)
#
# The UC metadata sync (task 1.5) calls ``sync_uc_lineage`` after each
# workspace delta so the mirror's view → table dependencies extend the
# existing ``LineageEdge`` graph WITHOUT changing the lineage API's
# public shape (the same table, the same SCD Type 2 semantics).
#
# Provider boundary: the reader resolves the databricks_admin mirror
# models by STRING reference (``apps.get_model``) — this module never
# imports a provider estate model (the GATE-29-clean pattern), and an
# absent app degrades to a no-op.
# ─────────────────────────────────────────────────────────────────────────────

UC_LINEAGE_JOB_REF_PREFIX = "databricks_uc_metadata_sync"


def _get_uc_models() -> dict | None:
    """The UC mirror models by string reference, or None when the
    databricks_admin app is not installed."""
    from django.apps import apps

    try:
        return {
            "table": apps.get_model("databricks_admin", "UCTable"),
            "view": apps.get_model("databricks_admin", "UCView"),
        }
    except LookupError:
        return None


def _strip_sql_comments_and_literals(sql: str) -> str:
    """Remove block/line comments and string literals so a table name
    appearing ONLY in prose can never fabricate an edge."""
    stripped = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    stripped = re.sub(r"--[^\n]*", " ", stripped)
    stripped = re.sub(r"'(?:[^']|'')*'", " ", stripped)
    return stripped


def _sql_identifier_tokens(sql: str) -> set[str]:
    """Identifier tokens from the view SQL.

    Quoted identifier CHAINS (`` `finance`.`invoices` `` /
    `` "finance"."invoices" ``) are extracted as ONE token so the
    qualified reference survives segmentation (the 1.6 review fix: a
    per-segment split would degrade `` `finance`.`invoices` `` to a bare
    ``invoices`` token and miss the cross-schema reference). Bare
    (possibly dot-qualified) word tokens are extracted as before.
    """
    tokens = set()
    for match in re.finditer(
        r'(?:`[^`]+`|"[^"]+")(?:\s*\.\s*(?:`[^`]+`|"[^"]+"))*', sql
    ):
        tokens.add(match.group(0))
    tokens.update(
        re.findall(r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*", sql)
    )
    return tokens


def _referenced_tables_for_view(view, tables: list[tuple[str, str, Any]]) -> list[Any]:
    """The mirrored tables referenced by the view's SQL.

    Resolution rules (the 1.6 review contract):

    * Dot-qualified tokens resolve against ``schema.table`` and
      ``full_name`` candidates — cross-schema references included. When
      the SAME 2-part name exists in several catalogs, the VIEW's OWN
      catalog wins; an ambiguity OUTSIDE it is skipped (never a
      query-order-dependent guess).
    * BARE tokens resolve ONLY against the VIEW's own schema — an
      ambiguous sibling-schema name must never fabricate an edge.
    """
    sql = _strip_sql_comments_and_literals(getattr(view, "view_definition", "") or "")
    if not sql:
        return []
    tokens = _sql_identifier_tokens(sql)

    view_catalog = getattr(
        getattr(getattr(view, "schema", None), "catalog", None), "name", ""
    )
    view_schema = getattr(getattr(view, "schema", None), "name", "")

    qualified: dict[str, list[Any]] = {}
    own_names: dict[str, Any] = {}
    for schema_name, catalog_name, table in tables:
        qualified.setdefault(f"{schema_name}.{table.name}".lower(), []).append(table)
        if table.full_name:
            qualified.setdefault(table.full_name.lower(), []).append(table)
        if schema_name == view_schema and catalog_name == view_catalog:
            own_names.setdefault(table.name.lower(), table)

    matched: list[Any] = []
    seen_ids: set = set()
    for token in tokens:
        norm = token.lower().replace("`", "").replace('"', "").replace(" ", "")
        table: Any | None = None
        if "." in norm:
            candidates = qualified.get(norm) or []
            if len(candidates) == 1:
                table = candidates[0]
            elif len(candidates) > 1:
                own_catalog = [
                    candidate
                    for candidate in candidates
                    if getattr(getattr(candidate, "schema", None), "catalog", None)
                    and candidate.schema.catalog.name == view_catalog
                ]
                if len(own_catalog) == 1:
                    table = own_catalog[0]
        else:
            table = own_names.get(norm)
        if table is not None and table.id not in seen_ids:
            seen_ids.add(table.id)
            matched.append(table)
    return matched


def sync_uc_lineage(*, tenant, workspace_id: str) -> dict:
    """1.6 — diff the UC mirror's view → table dependencies into the
    ``LineageEdge`` graph. Idempotent (same-state rerun = zero writes);
    SCD Type 2 close-then-insert with DB-side ``NOW()`` — the same
    semantics as the contract path.

    Self-contained worker: the diff runs inside ``tenant_context``
    (established here — the uc_sync caller's own wrap stays as harmless
    nesting).

    Returns ``{"added": n, "removed": n}``.
    """
    with tenant_context(str(tenant.id)):
        return _sync_uc_lineage_in_context(tenant=tenant, workspace_id=workspace_id)


def _sync_uc_lineage_in_context(*, tenant, workspace_id: str) -> dict:
    """The tenant-context-wrapped body of ``sync_uc_lineage``."""
    from hub.apps.contracts.models import LineageEdge, LineageEdgeType

    models = _get_uc_models()
    if models is None:
        return {"added": 0, "removed": 0}

    job_ref = f"{UC_LINEAGE_JOB_REF_PREFIX}:{workspace_id}"
    tables = list(
        models["table"]
        .objects.filter(schema__catalog__workspace_id=workspace_id)
        .select_related("schema__catalog")
    )
    views = list(
        models["view"]
        .objects.filter(schema__catalog__workspace_id=workspace_id)
        .select_related("schema__catalog")
    )
    table_pairs = [
        (table.schema.name, table.schema.catalog.name, table) for table in tables
    ]

    # Desired open-edge set (canonical 9-tuple, NULL contract anchors —
    # UC objects are external to the contract graph by design).
    desired: set[tuple] = set()
    for view in views:
        for table in _referenced_tables_for_view(view, table_pairs):
            desired.add(
                (
                    None,
                    None,
                    table.full_name,
                    "",
                    view.full_name,
                    "",
                    LineageEdgeType.REFERENCE,
                    view.full_name,
                    job_ref,
                )
            )

    current: dict[tuple, Any] = {}
    for row in LineageEdge.objects.filter(
        tenant=tenant, job_ref=job_ref, valid_to__isnull=True
    ):
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
        current[key] = row

    to_add = desired - set(current.keys())
    to_remove = [current[key] for key in (set(current.keys()) - desired)]

    with transaction.atomic():
        removed = 0
        if to_remove:
            ids = [row.pk for row in to_remove]
            removed = LineageEdge.objects.filter(pk__in=ids).update(valid_to=Now())
        added = 0
        added_rows: list[tuple[Any, tuple]] = []
        for tup in to_add:
            row = LineageEdge.objects.create(
                tenant=tenant,
                source_contract_id=tup[0],
                target_contract_id=tup[1],
                source_model=tup[2],
                source_field=tup[3],
                target_model=tup[4],
                target_field=tup[5],
                edge_type=tup[6],
                transformation_ref=tup[7],
                job_ref=tup[8],
                created_by_run="uc_lineage_sync",
            )
            added_rows.append((row, tup))
            added += 1

    tenant_id = str(getattr(tenant, "id", "")) or None
    for _ in range(added):
        record_edge_write(operation="add", tenant_id=tenant_id)
    for _ in range(removed):
        record_edge_write(operation="remove", tenant_id=tenant_id)
    if added == 0 and removed == 0:
        record_edge_write(operation="noop", tenant_id=tenant_id)

    # Best-effort audit for every mutation (the REQ-LIN-007 discipline;
    # failures are swallowed + logged — never roll back the diff). The
    # created rows carry their REAL edge id — the 1.6 review fix (the
    # first pass emitted resource_id=None, losing the row linkage the
    # contract path preserves).
    _emit_uc_edge_audit_events(
        tenant=tenant,
        workspace_id=workspace_id,
        added_rows=added_rows,
        closed_rows=to_remove,
    )
    return {"added": added, "removed": removed}


def _emit_uc_edge_audit_events(
    *, tenant, workspace_id: str, added_rows, closed_rows
) -> None:
    """Best-effort audit rows for UC lineage mutations."""
    for row, tup in added_rows:
        try:
            create_audit_event(
                resource_type="LINEAGE_EDGE",
                action=LINEAGE_EDGE_CREATED,
                actor_user=None,
                tenant=tenant,
                resource_id=str(row.id),
                details={
                    "via": "uc_lineage_sync",
                    "workspace_id": workspace_id,
                    "source_model": tup[2],
                    "target_model": tup[4],
                },
            )
        except Exception as exc:
            logger.warning(
                "uc_lineage_edge_created_audit_failed",
                extra={"error": str(exc)},
            )
    for row in closed_rows:
        try:
            create_audit_event(
                resource_type="LINEAGE_EDGE",
                action=LINEAGE_EDGE_DELETED,
                actor_user=None,
                tenant=tenant,
                resource_id=str(row.pk) if hasattr(row, "pk") else None,
                details={
                    "via": "uc_lineage_sync",
                    "workspace_id": workspace_id,
                },
            )
        except Exception as exc:
            logger.warning(
                "uc_lineage_edge_deleted_audit_failed",
                extra={"error": str(exc)},
            )


__all__ = [
    "_apply_diff",
    "_current_edge_set",
    "_desired_edge_set",
    "_emit_edge_audit_events",
    "_emit_outbound_openlineage_events",
    "_lineage_edge_to_dict",
    "_referenced_tables_for_view",
    "_sync_contract_edges",
    "on_contract_post_save",
    "record_edge_write",
    "register_signals",
    "send_openlineage_event_async",
    "sync_uc_lineage",
]
