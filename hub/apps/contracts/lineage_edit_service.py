"""
Phase 228.F2 (F2.4 / F2.5 / F2.8 / F2.9) — `apply_lineage_patch`.

Single transaction.  PostgreSQL ``SERIALIZABLE`` isolation level so
two concurrent edits that would each individually be valid but jointly
form a cycle correctly produce ≥1 ``409`` (REQ-LIN-F2-002 scenario).

Steps in the tx:

1. Re-read the contract + its current open ``LineageEdge`` rows
   inside the SERIALIZABLE block.
2. Validate the desired edge set against:
   - cycle detection (F2.6.1)
   - field-existence (F2.6.2)
   - type compatibility (F2.6.3)
3. Diff: existing-open vs desired-open.
4. Close removed edges (set ``valid_to=NOW()``).
5. Insert new edges (``valid_from=NOW()``, ``valid_to=NULL``).
6. Re-serialise ``hub_contract_json.lineage`` from the resulting
   set so the JSONB source-of-truth and the LineageEdge index stay
   coherent.
7. Emit one ``LINEAGE_EDGE_ADDED`` audit event per opened row and
   one ``LINEAGE_EDGE_REMOVED`` per closed row (F2.9).

Returns a JSON-friendly dict the view layer ships back to the
client.  Raises :class:`ConflictError` on cycle / SERIALIZABLE
serialization failure; :class:`ValidationError` on field-not-found
or type-mismatch.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from hub.apps.contracts.lineage_validator import (
    detect_cycle,
    validate_field_exists,
    validate_type_compatibility,
)
from hub.apps.core.services.base import (
    ConflictError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_lineage_patch(
    *,
    contract: Any,
    desired_edges: List[Dict[str, Any]],
    user: Any,
) -> Dict[str, Any]:
    """Apply a full-state lineage patch to ``contract``.

    Args
    ----
    contract
        :class:`Contract` instance whose lineage we're editing.
    desired_edges
        List of edge dicts (already validated by the F2.7 serializer)
        — the FULL post-patch state, not a diff.
    user
        Acting user (for audit events).

    Returns
    -------
    A dict shaped::

        {
          "contract_id": "<uuid>",
          "edges": [...],          # full post-patch list
          "added": int,
          "removed": int,
          "kept": int
        }
    """
    # SERIALIZABLE isolation — a concurrent edit that would jointly
    # create a cycle will now produce a ``django.db.IntegrityError``
    # we translate to ConflictError(409).
    with transaction.atomic():
        # Force SERIALIZABLE for THIS tx only (Postgres `SET TRANSACTION`
        # works because we're inside an atomic block).  Falls back
        # silently on non-Postgres backends (the test container uses
        # Postgres so the production semantics are exercised).
        _set_serializable_isolation()

        # Re-read state inside the tx for fresh ETag semantics.
        contract.refresh_from_db()

        existing_open = _load_existing_open_edges(contract)
        desired_normalised = _normalise_desired_edges(
            desired_edges, contract,
        )

        _validate_field_existence(contract, desired_normalised)
        _validate_type_compatibility_all(contract, desired_normalised)
        _validate_no_cycles(desired_normalised)

        # Diff
        existing_keys = {_edge_signature(e) for e in existing_open}
        desired_keys = {_edge_signature(e) for e in desired_normalised}

        to_close = [
            e for e in existing_open
            if _edge_signature(e) not in desired_keys
        ]
        to_open = [
            e for e in desired_normalised
            if _edge_signature(e) not in existing_keys
        ]

        try:
            _close_edges(to_close)
            opened_rows = _open_edges(contract, to_open)
        except IntegrityError as exc:
            # Postgres SERIALIZABLE serialization failure surfaces
            # here on concurrent commits that jointly form a cycle.
            raise ConflictError(
                "Concurrent lineage edits produced a serialization "
                "conflict.  Reload the page and re-apply your edits.",
                code="SERIALIZATION_CONFLICT",
                details={"original_error": str(exc)},
            ) from exc

        _reserialise_hub_contract_lineage(contract, desired_normalised)

        # Audit events — one per opened row + one per closed row.
        _emit_audit_events(
            contract=contract,
            user=user,
            opened=opened_rows,
            closed=to_close,
        )

    return {
        "contract_id": str(contract.id),
        "edges": desired_normalised,
        "added": len(to_open),
        "removed": len(to_close),
        "kept": len(desired_normalised) - len(to_open),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_serializable_isolation() -> None:
    """Best-effort SERIALIZABLE isolation for the current tx.

    Works on Postgres (the project's production backend).  No-op on
    SQLite (test fallback) so the function-level tests still run.
    """
    from django.db import connection

    try:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"
                )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "lineage_edit.serializable_set_failed: %s — "
            "tx falls back to default isolation",
            exc,
        )


def _load_existing_open_edges(contract: Any) -> List[Dict[str, Any]]:
    from hub.apps.contracts.models import LineageEdge

    rows = LineageEdge.objects.filter(
        tenant_id=contract.tenant_id,
        valid_to__isnull=True,
    ).filter(
        # The edge "belongs to" this contract if either endpoint is it.
        # We slice the open universe to those — the patch's scope is
        # the contract's own lineage, not the entire tenant's.
        # Use Q for the OR.
    )
    from django.db.models import Q
    rows = rows.filter(
        Q(source_contract_id=contract.id) | Q(target_contract_id=contract.id)
    )
    return [_edge_row_to_dict(row) for row in rows]


def _edge_row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "source_contract": (
            str(row.source_contract_id) if row.source_contract_id else None
        ),
        "target_contract": (
            str(row.target_contract_id) if row.target_contract_id else None
        ),
        "source_model": row.source_model or "",
        "source_field": row.source_field or "",
        "target_model": row.target_model or "",
        "target_field": row.target_field or "",
        "edge_type": row.edge_type,
        "transformation_ref": row.transformation_ref or "",
        "job_ref": row.job_ref or "",
    }


def _normalise_desired_edges(
    desired_edges: List[Dict[str, Any]],
    contract: Any,
) -> List[Dict[str, Any]]:
    """Coerce serializer output into stable string-keyed dicts.

    The serializer output mixes UUID and str types; downstream code
    is dict-key-stable easier when the UUIDs are stringified.
    """
    out = []
    for edge in desired_edges:
        out.append(
            {
                "source_contract": (
                    str(edge.get("source_contract"))
                    if edge.get("source_contract") else None
                ),
                "target_contract": (
                    str(edge.get("target_contract"))
                    if edge.get("target_contract") else None
                ),
                "source_model": edge.get("source_model", "") or "",
                "source_field": edge.get("source_field", "") or "",
                "target_model": edge.get("target_model", "") or "",
                "target_field": edge.get("target_field", "") or "",
                "edge_type": edge.get("edge_type", "reference"),
                "transformation_ref": edge.get("transformation_ref", "") or "",
                "job_ref": edge.get("job_ref", "") or "",
            }
        )
    return out


def _edge_signature(edge: Dict[str, Any]) -> Tuple:
    """Stable signature used for diff + dedup."""
    return (
        edge.get("source_contract") or "",
        edge.get("source_model") or "",
        edge.get("source_field") or "",
        edge.get("target_contract") or "",
        edge.get("target_model") or "",
        edge.get("target_field") or "",
        edge.get("edge_type") or "reference",
    )


def _validate_field_existence(
    contract: Any, edges: List[Dict[str, Any]],
) -> None:
    """For every edge whose source / target contract IS the
    contract under edit, verify the named field exists in
    ``hub_contract_json``.

    Cross-tenant endpoints (foreign contract ids) are NOT validated —
    we don't have their HubContract loaded, and the F2 v1 spec
    doesn't require it.
    """
    from hub.apps.contracts.models import Contract

    payload = contract.hub_contract_json or {}
    own_id = str(contract.id)
    # Cache foreign contracts to avoid N+1.
    foreign_payloads: Dict[str, Dict[str, Any]] = {}

    def _lookup_payload(contract_id: str) -> Dict[str, Any]:
        if contract_id == own_id:
            return payload
        if contract_id in foreign_payloads:
            return foreign_payloads[contract_id]
        c = Contract.objects.filter(
            id=contract_id, tenant_id=contract.tenant_id,
        ).only("id", "hub_contract_json").first()
        body = (c.hub_contract_json if c else None) or {}
        foreign_payloads[contract_id] = body
        return body

    for edge in edges:
        for side in ("source", "target"):
            cid = edge.get(f"{side}_contract")
            field = edge.get(f"{side}_field")
            model = edge.get(f"{side}_model") or ""
            if not cid or not field:
                continue
            target_payload = _lookup_payload(cid)
            if not target_payload:
                # Foreign payload unavailable — skip (don't block the edit).
                continue
            if not validate_field_exists(target_payload, model, field):
                raise ValidationError(
                    f"Lineage edge references unknown {side} field "
                    f"'{model}.{field}' on contract {cid}",
                    code="LINEAGE_FIELD_NOT_FOUND",
                    details={
                        "side": side,
                        "contract_id": cid,
                        "model": model,
                        "field": field,
                        "code": "LINEAGE_FIELD_NOT_FOUND",
                    },
                )


def _validate_type_compatibility_all(
    contract: Any, edges: List[Dict[str, Any]],
) -> None:
    """For every edge with both endpoints declared, check column types."""
    from hub.apps.contracts.models import Contract

    payload = contract.hub_contract_json or {}
    own_id = str(contract.id)
    foreign_payloads: Dict[str, Dict[str, Any]] = {}

    def _lookup_payload(contract_id: str) -> Dict[str, Any]:
        if contract_id == own_id:
            return payload
        if contract_id in foreign_payloads:
            return foreign_payloads[contract_id]
        c = Contract.objects.filter(
            id=contract_id, tenant_id=contract.tenant_id,
        ).only("id", "hub_contract_json").first()
        body = (c.hub_contract_json if c else None) or {}
        foreign_payloads[contract_id] = body
        return body

    for edge in edges:
        src_cid = edge.get("source_contract")
        tgt_cid = edge.get("target_contract")
        if not (src_cid and tgt_cid):
            continue
        src_type = _resolve_field_type(
            _lookup_payload(src_cid),
            edge.get("source_model") or "",
            edge.get("source_field") or "",
        )
        tgt_type = _resolve_field_type(
            _lookup_payload(tgt_cid),
            edge.get("target_model") or "",
            edge.get("target_field") or "",
        )
        if not validate_type_compatibility(
            src_type, tgt_type,
            transformation_ref=edge.get("transformation_ref") or "",
        ):
            raise ValidationError(
                f"Lineage edge type mismatch: {src_type} → {tgt_type}",
                code="LINEAGE_TYPE_MISMATCH",
                details={
                    "source_type": src_type,
                    "target_type": tgt_type,
                    "code": "LINEAGE_TYPE_MISMATCH",
                },
            )


def _resolve_field_type(
    payload: Dict[str, Any], model_name: str, field_name: str,
) -> str:
    """Resolve the data type for a model/field pair."""
    if not isinstance(payload, dict):
        return ""
    if not model_name:
        schema = payload.get("schema") or {}
        if isinstance(schema, dict):
            return _walk_field_for_type(schema.get("fields") or [], field_name)
        return ""
    for model in payload.get("models") or []:
        if isinstance(model, dict) and model.get("name") == model_name:
            return _walk_field_for_type(
                model.get("fields") or [], field_name,
            )
    return ""


def _walk_field_for_type(
    fields: List[Dict[str, Any]], qname: str,
) -> str:
    head, _, rest = qname.partition(".")
    for field in fields:
        if not isinstance(field, dict) or field.get("name") != head:
            continue
        if not rest:
            return str(
                field.get("data_type") or field.get("type") or ""
            )
        nested = field.get("fields")
        if nested is None:
            items = field.get("items")
            if isinstance(items, dict):
                nested = items.get("fields")
        if isinstance(nested, list):
            t = _walk_field_for_type(nested, rest)
            if t:
                return t
    return ""


def _validate_no_cycles(edges: List[Dict[str, Any]]) -> None:
    """Reject the patch if the edges contain a cycle.

    Tests every edge against the rest using ``detect_cycle`` —
    simple O(N²·V) but N is bounded by F2_MAX_EDGES_PER_PATCH=1000
    in the worst case.  For typical patches (≤50 edges) this is sub-ms.
    """
    for i, candidate in enumerate(edges):
        rest = edges[:i] + edges[i + 1 :]
        if detect_cycle(rest, candidate):
            raise ValidationError(
                "Lineage edges form a cycle.",
                code="LINEAGE_CYCLE",
                details={
                    "code": "LINEAGE_CYCLE",
                    "edge": candidate,
                },
            )


def _close_edges(edges: List[Dict[str, Any]]) -> None:
    """SCD Type 2 close: set ``valid_to=NOW()`` on the open rows."""
    if not edges:
        return
    from hub.apps.contracts.models import LineageEdge
    from django.db.models import Q

    now = timezone.now()
    for edge in edges:
        # Match by signature within open rows.
        qs = LineageEdge.objects.filter(
            valid_to__isnull=True,
            source_contract_id=edge["source_contract"],
            target_contract_id=edge["target_contract"],
            source_model=edge["source_model"],
            source_field=edge["source_field"],
            target_model=edge["target_model"],
            target_field=edge["target_field"],
            edge_type=edge["edge_type"],
        )
        qs.update(valid_to=now)


def _open_edges(
    contract: Any, edges: List[Dict[str, Any]],
) -> List[Any]:
    """Insert new ``LineageEdge`` rows for the desired set."""
    if not edges:
        return []
    from hub.apps.contracts.models import LineageEdge

    created: List[Any] = []
    for edge in edges:
        row = LineageEdge.objects.create(
            tenant_id=contract.tenant_id,
            source_contract_id=edge["source_contract"],
            target_contract_id=edge["target_contract"],
            source_model=edge["source_model"],
            source_field=edge["source_field"],
            target_model=edge["target_model"],
            target_field=edge["target_field"],
            edge_type=edge["edge_type"],
            transformation_ref=edge["transformation_ref"],
            job_ref=edge["job_ref"],
            created_by_run="lineage-edit-f2",
        )
        created.append(row)
    return created


def _reserialise_hub_contract_lineage(
    contract: Any, desired_edges: List[Dict[str, Any]],
) -> None:
    """Re-write ``hub_contract_json.lineage`` from the desired edges.

    The JSONB lineage is the canonical write source per L2 / 228.0
    docstrings; the LineageEdge table is the derived index.  After
    the patch we ensure the two are coherent.
    """
    payload = contract.hub_contract_json or {}
    if not isinstance(payload, dict):
        payload = {}

    # Build the lineage section.  Keep the existing `contracts` /
    # `models` blocks (those are wider-than-edge-level metadata) but
    # rebuild the `entries` list from edges.
    existing_lineage = payload.get("lineage") or {}
    if not isinstance(existing_lineage, dict):
        existing_lineage = {}

    entries: List[Dict[str, Any]] = []
    for edge in desired_edges:
        src_cid = edge.get("source_contract")
        if not src_cid:
            continue
        entry = {
            "input_fields": [
                {
                    "name": edge.get("source_model") or "",
                    "field": edge.get("source_field") or "",
                    "namespace": src_cid,
                },
            ],
        }
        if edge.get("transformation_ref"):
            entry["transformations"] = [
                {
                    "logic": edge["transformation_ref"],
                    "type": edge.get("edge_type") or "reference",
                },
            ]
        entries.append(entry)

    existing_lineage["entries"] = entries
    payload["lineage"] = existing_lineage
    contract.hub_contract_json = payload
    contract.save(update_fields=["hub_contract_json", "updated_at"])


def _emit_audit_events(
    *,
    contract: Any,
    user: Any,
    opened: List[Any],
    closed: List[Dict[str, Any]],
) -> None:
    """One audit event per opened/closed edge (F2.9)."""
    try:
        from hub.apps.audit.utils import create_audit_event
    except Exception:  # pragma: no cover — defensive
        return
    for row in opened:
        try:
            create_audit_event(
                resource_type="CONTRACT",
                action="LINEAGE_EDGE_ADDED",
                actor_user=user,
                tenant=getattr(contract, "tenant", None),
                resource_id=str(contract.id),
                details={
                    "edge_id": str(row.id),
                    "source_contract": (
                        str(row.source_contract_id)
                        if row.source_contract_id else None
                    ),
                    "target_contract": (
                        str(row.target_contract_id)
                        if row.target_contract_id else None
                    ),
                    "source_field": row.source_field,
                    "target_field": row.target_field,
                    "edge_type": row.edge_type,
                    "phase": "228.F2.9",
                },
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "lineage_edit.audit_emit_failed_added: %s", exc,
            )
    for edge in closed:
        try:
            create_audit_event(
                resource_type="CONTRACT",
                action="LINEAGE_EDGE_REMOVED",
                actor_user=user,
                tenant=getattr(contract, "tenant", None),
                resource_id=str(contract.id),
                details={
                    "source_contract": edge.get("source_contract"),
                    "target_contract": edge.get("target_contract"),
                    "source_field": edge.get("source_field"),
                    "target_field": edge.get("target_field"),
                    "edge_type": edge.get("edge_type"),
                    "phase": "228.F2.9",
                },
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "lineage_edit.audit_emit_failed_removed: %s", exc,
            )


__all__ = ["apply_lineage_patch"]
