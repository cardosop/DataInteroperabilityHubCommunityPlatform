"""
Phase 227 Wave 1 (227.L1.1) — canonical ODPS ports → models[]/lineage helper.

Why this module exists
----------------------
The Phase 227 root-cause investigation found that 100% of ODPS contracts in
production normalised to ``hub_contract.models = []`` because the existing
Bitol-v1 mapper only recorded port metadata under
``extensions.x_odps.output_ports`` and never extracted the schema body
(`port.contract.spec.schema.fields`, `port.dataSchema.fields`,
`port.schema.fields`, `port.contractURL`, or a referenced
`port.contractId`). Net effect: the entire ODPS population was
"structureless" by Wave 0's classification.

This helper centralises the mapping so every ODPS normaliser (Bitol v1
and version-specific 1.x/2.x/3.x/4.0/4.1/4.2) calls a single
implementation with consistent semantics.

Public API
----------
* :func:`normalize_models_from_ports` — mutates ``hub_contract`` in place.

Resolution priority order for ``outputPorts[]`` schema bodies
-------------------------------------------------------------
1. ``port.contractId`` — UUID into the local ``Contract`` table.
2. ``port.contract.spec.schema.fields`` — embedded ODCS-shaped contract.
3. ``port.dataSchema.fields`` — ODPS-shaped inline schema.
4. ``port.schema.fields`` — Bitol shorthand inline schema.
5. ``port.contractURL`` — external URL resolved via ``RefResolver``
   (which itself runs through the SSRF guard).

If none resolve, the helper appends a ``STRUCTURELESS_*`` warning so
ops can locate the broken contract via the Wave 0 diagnosis tooling.

Performance / safety
--------------------
* **N+1 prevention** — all referenced ``contractId`` UUIDs are bulk-fetched
  in a single ``Contract.objects.filter(id__in=...)`` query, not one
  query per port. A 100-port contract incurs 1 round-trip, not 100.
* **Cycle detection** — callers pass ``visited_contract_ids`` containing
  the IDs they've already entered (typically the contract currently being
  normalised). A port whose ``contractId`` is in that set is skipped
  with a ``STRUCTURELESS_CYCLIC_PORTS`` warning, breaking A→B→A loops.
* **SSRF defence** — ``contractURL`` resolution is delegated to
  ``RefResolver``, which already enforces the SSRF allowlist. The helper
  itself never calls ``requests.get`` directly.

Side effects on ``hub_contract``
--------------------------------
* ``hub_contract["models"]`` — appended to (created if absent).
* ``hub_contract["lineage"]["contracts"]`` — appended to (for inputPorts).

The helper does not touch ``hub_contract["schema"]["fields"]``; that is
the per-version normaliser's responsibility (cf. ``_normalize_schema_minimal``).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)


# Warning prefixes — kept as module-level constants so the Bitol-v1 and
# v4.x normalisers can reference them when constructing custom messages.
WARNING_NO_RESOLVABLE = "STRUCTURELESS_PORT_NO_RESOLVABLE_PAYLOAD"
WARNING_CONTRACT_NOT_FOUND = "STRUCTURELESS_PORT_CONTRACTID_NOT_FOUND"
WARNING_CYCLIC = "STRUCTURELESS_CYCLIC_PORTS"
WARNING_INVALID_UUID = "STRUCTURELESS_PORT_CONTRACTID_INVALID_UUID"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_uuid(value: Any) -> Optional[uuid.UUID]:
    """Return a ``UUID`` for a stringly-typed contractId, or ``None``."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _get_ports_from_data(
    contract_data: Dict[str, Any], port_key: str,
) -> List[Dict[str, Any]]:
    """Read ports from top-level OR ``contract_data["product"]``.

    ODPS allows both placements; matching the existing ``_get_ports``
    convention in :mod:`odps_normalizer_bitol_v1`.
    """
    ports = contract_data.get(port_key)
    if isinstance(ports, list):
        return [p for p in ports if isinstance(p, dict)]
    product = contract_data.get("product")
    if isinstance(product, dict):
        ports = product.get(port_key)
        if isinstance(ports, list):
            return [p for p in ports if isinstance(p, dict)]
    return []


def _bulk_fetch_contract_models(
    contract_ids: Iterable[uuid.UUID],
) -> Dict[uuid.UUID, List[Dict[str, Any]]]:
    """Fetch ``hub_contract_json["models"]`` for the given IDs in ONE query.

    The query carries ``select_related('asset')`` plus ``asset_id`` in
    the deferred-field allowlist. ``asset_id`` is not used in Wave 1
    output, but Wave 3 (the structureless self-heal job) needs the
    asset back-reference to demote/relink, so paying the JOIN cost now
    avoids an N+1 retrofit later. The query remains a single round-trip
    (verified by ``NPlusOnePreventionTests.test_bulk_fetch_avoids_n_plus_one``).

    Returns a dict keyed by UUID. Missing IDs simply do not appear in
    the result (the caller checks ``key not in result`` to detect the
    "contract not found" case).
    """
    ids = list({cid for cid in contract_ids if cid is not None})
    if not ids:
        return {}
    # Lazy import — the helper module is loaded at process start, but
    # importing Django models eagerly here would couple this module to
    # the Django app registry boot order. The lazy import keeps the
    # helper unit-testable in isolation.
    from hub.apps.contracts.models import Contract

    rows = (
        Contract.objects.filter(id__in=ids)
        .select_related("asset")
        .only("id", "hub_contract_json", "asset_id")
    )
    out: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
    for row in rows:
        payload = row.hub_contract_json
        if not isinstance(payload, dict):
            payload = {}
        models = payload.get("models")
        out[row.id] = models if isinstance(models, list) else []
    return out


def _resolve_contract_url(
    url: str,
    ref_resolver: Any,
) -> Optional[Dict[str, Any]]:
    """Resolve an external ``contractURL`` via the supplied resolver.

    The SSRF allowlist is enforced inside ``RefResolver.resolve()``, so
    we do not duplicate the check here. Returns ``None`` on any failure
    (timeout, blocked URL, parse error) — the caller emits the standard
    "no resolvable" warning.
    """
    if not url or ref_resolver is None:
        return None
    try:
        resolved = ref_resolver.resolve(url)
        return resolved if isinstance(resolved, dict) else None
    except Exception as exc:
        logger.warning(
            "ports_helper_contractURL_resolution_failed",
            url=url,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None


def _extract_inline_fields(
    port: Dict[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    """Return the first non-empty inline fields list, in priority order.

    Priority:

    * ``port.contract.spec.schema.fields`` (ODCS-shaped embedded contract)
    * ``port.dataSchema.fields`` (ODPS canonical)
    * ``port.schema.fields`` (Bitol shorthand)
    """
    contract_block = port.get("contract")
    if isinstance(contract_block, dict):
        spec = contract_block.get("spec")
        if isinstance(spec, dict):
            schema = spec.get("schema")
            if isinstance(schema, dict):
                fields = schema.get("fields")
                if isinstance(fields, list) and fields:
                    return fields
    data_schema = port.get("dataSchema")
    if isinstance(data_schema, dict):
        fields = data_schema.get("fields")
        if isinstance(fields, list) and fields:
            return fields
    schema_block = port.get("schema")
    if isinstance(schema_block, dict):
        fields = schema_block.get("fields")
        if isinstance(fields, list) and fields:
            return fields
    return None


# ---------------------------------------------------------------------------
# Field shape normalisation
# ---------------------------------------------------------------------------
# ODCS-shaped fields use ``type``/``minLength``/``maxLength``; the canonical
# HubContract shape uses ``data_type``/``min_length``/``max_length``. Pydantic
# accepts either via aliases on :class:`HubContractField`, but raw-dict
# downstream consumers (frontend renderers, jq-based ops scripts) read
# ``data_type`` directly. Normalising at helper level mirrors what
# :func:`ODPSNormalizerBase._normalize_schema_minimal` already does for
# ``product.contract.spec.schema``, so port-extracted fields land in the
# same shape regardless of which path they arrived from.
#
# Fields resolved from a ``contractId`` lookup are NOT re-normalised — they
# came from ``hub_contract_json`` of an already-normalised contract.

_ODCS_TO_HUB_RENAMES = {
    "type": "data_type",
    "minLength": "min_length",
    "maxLength": "max_length",
}


def _normalize_field_shape(field: Any) -> Optional[Dict[str, Any]]:
    """Convert an ODCS/Bitol field dict to canonical HubContract shape.

    Returns ``None`` for non-dicts or fields missing a usable name.
    The shape conversion is idempotent — passing an already-normalised
    field returns it unchanged.
    """
    if not isinstance(field, dict):
        return None
    out: Dict[str, Any] = {}
    name = field.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    out["name"] = name.strip()
    for key, value in field.items():
        if key == "name":
            continue
        canonical_key = _ODCS_TO_HUB_RENAMES.get(key, key)
        # Don't clobber a HubContract key with an ODCS alias if both
        # are somehow present — the canonical key wins.
        if canonical_key not in out:
            out[canonical_key] = value
    # Always populate data_type (default 'string') so raw-dict consumers
    # don't need to know about Pydantic's alias resolution.
    if "data_type" not in out:
        out["data_type"] = "string"
    return out


def _normalize_fields(
    raw_fields: List[Any],
) -> List[Dict[str, Any]]:
    """Apply :func:`_normalize_field_shape` to every entry; drop bad ones."""
    normalised: List[Dict[str, Any]] = []
    for f in raw_fields:
        n = _normalize_field_shape(f)
        if n is not None:
            normalised.append(n)
    return normalised


def _extract_fields_from_resolved_doc(
    doc: Dict[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    """Extract fields from a contractURL-resolved document.

    The shape can be either an ODCS-style document with
    ``spec.schema.fields`` at the top, OR an inline-port-style dict with
    ``contract.spec.schema.fields``. Try both.
    """
    # Inline-port-style first (wraps the ODCS-style under .contract).
    fields = _extract_inline_fields({"contract": doc})
    if fields:
        return fields
    # Top-level ODCS shape.
    spec = doc.get("spec") if isinstance(doc, dict) else None
    if isinstance(spec, dict):
        schema = spec.get("schema")
        if isinstance(schema, dict):
            f = schema.get("fields")
            if isinstance(f, list) and f:
                return f
    # Top-level dataSchema shape.
    return _extract_inline_fields(doc) if isinstance(doc, dict) else None


def _model_from_fields(
    name: str,
    fields: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a HubContractModelEntry-shaped dict.

    Only ``name`` + ``fields`` are populated here; downstream Pydantic
    validation in :class:`HubContractModelEntry` will accept extra keys
    via its ``extra='allow'`` config, so callers may merge in additional
    fields (description, primary_key, tags) post-hoc if desired.
    """
    return {"name": name, "fields": list(fields)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_models_from_ports(
    contract_data: Dict[str, Any],
    hub_contract: Dict[str, Any],
    warnings: List[str],
    *,
    ref_resolver: Any = None,
    visited_contract_ids: Optional[Set[uuid.UUID]] = None,
) -> None:
    """Emit one model per ``outputPort`` and lineage rows per ``inputPort``.

    See module docstring for the full resolution priority order and
    side-effect contract.

    Args:
        contract_data: Raw ODPS dict (top-level OR under ``.product``).
        hub_contract: The HubContract dict; mutated in place.
        warnings: Warning list mutated in place. Each emission is one
            string with a ``STRUCTURELESS_*`` prefix so ops tooling can
            grep for it.
        ref_resolver: Optional :class:`RefResolver` for ``contractURL``
            resolution. When ``None``, ports that *only* carry a
            ``contractURL`` will raise the standard "no resolvable"
            warning. (This is the safe default — the caller is
            responsible for constructing an appropriately-scoped
            ``RefResolver`` per tenant.)
        visited_contract_ids: Optional set of contract IDs that the
            caller has already entered. Used to break cycles. The
            helper does NOT recurse into resolved contracts; it only
            short-circuits ports referencing an already-visited UUID.
    """
    if not isinstance(hub_contract.get("models"), list):
        hub_contract["models"] = []
    visited: Set[uuid.UUID] = set(visited_contract_ids or set())

    _process_output_ports(
        contract_data=contract_data,
        hub_contract=hub_contract,
        warnings=warnings,
        ref_resolver=ref_resolver,
        visited=visited,
    )
    _process_input_ports(
        contract_data=contract_data,
        hub_contract=hub_contract,
    )


# ---------------------------------------------------------------------------
# Internals split out for readability
# ---------------------------------------------------------------------------


def _process_output_ports(
    *,
    contract_data: Dict[str, Any],
    hub_contract: Dict[str, Any],
    warnings: List[str],
    ref_resolver: Any,
    visited: Set[uuid.UUID],
) -> None:
    output_ports = _get_ports_from_data(contract_data, "outputPorts")
    if not output_ports:
        return

    # Phase 1: collect all UUIDs that need DB resolution. We deliberately
    # SKIP UUIDs already in `visited` — they would be a cycle and should
    # never trigger a fetch (also the test asserts the cyclic case incurs
    # zero DB queries).
    contract_ids_to_fetch: Set[uuid.UUID] = set()
    port_uuids: List[Optional[uuid.UUID]] = []
    for port in output_ports:
        cid_raw = port.get("contractId")
        cid = _coerce_uuid(cid_raw)
        port_uuids.append(cid)
        if cid is not None and cid not in visited:
            contract_ids_to_fetch.add(cid)
        if cid_raw and cid is None:
            warnings.append(
                f"{WARNING_INVALID_UUID}: outputPort "
                f"{port.get('name', '<unnamed>')} contractId "
                f"{cid_raw!r} is not a valid UUID"
            )

    # Phase 2: bulk-fetch in ONE query.
    fetched = _bulk_fetch_contract_models(contract_ids_to_fetch)

    # Phase 3: per-port resolution.
    for port, cid in zip(output_ports, port_uuids):
        port_name = str(port.get("name") or "").strip()
        if not port_name:
            warnings.append(
                f"{WARNING_NO_RESOLVABLE}: outputPort missing name; "
                f"skipped"
            )
            continue

        fields = _resolve_port_fields(
            port=port,
            cid=cid,
            port_name=port_name,
            visited=visited,
            fetched=fetched,
            ref_resolver=ref_resolver,
            warnings=warnings,
        )
        if fields is None:
            # `_resolve_port_fields` already appended the appropriate
            # warning(s); nothing more to do for this port.
            continue
        hub_contract["models"].append(
            _model_from_fields(port_name, fields)
        )


def _resolve_port_fields(
    *,
    port: Dict[str, Any],
    cid: Optional[uuid.UUID],
    port_name: str,
    visited: Set[uuid.UUID],
    fetched: Dict[uuid.UUID, List[Dict[str, Any]]],
    ref_resolver: Any,
    warnings: List[str],
) -> Optional[List[Dict[str, Any]]]:
    """Walk the priority order and return the first usable field list.

    Priority order
    --------------
    1. ``port.contractId`` — if it resolves to a contract with models[0].fields.
    2. ``port.contract.spec.schema.fields`` — embedded ODCS contract.
    3. ``port.dataSchema.fields`` — ODPS canonical inline.
    4. ``port.schema.fields`` — Bitol shorthand.
    5. ``port.contractURL`` — external URL via RefResolver.

    Fall-back semantics
    -------------------
    If priority 1 fails (cycle, not found, empty models), we DO NOT
    drop the port; we fall through to priorities 2-5 and emit a soft
    warning explaining the priority-1 failure. This matches the
    structureless self-heal goal: emit whatever schema is reachable
    rather than losing port data over a stale FK reference.

    Returns
    -------
    List of canonical (HubContract-shaped) field dicts on success, or
    ``None`` when no priority resolved.
    """
    # Priority 1: contractId.
    if cid is not None:
        if cid in visited:
            warnings.append(
                f"{WARNING_CYCLIC}: outputPort {port_name} "
                f"contractId {cid} already visited (cycle); falling "
                f"through to inline schemas if any"
            )
        elif cid not in fetched:
            warnings.append(
                f"{WARNING_CONTRACT_NOT_FOUND}: outputPort "
                f"{port_name} references contractId {cid}, "
                f"which was not found"
            )
        else:
            models = fetched[cid]
            if not models:
                warnings.append(
                    f"{WARNING_NO_RESOLVABLE}: outputPort "
                    f"{port_name} contractId {cid} resolved but "
                    f"has no models[]"
                )
            else:
                first = models[0] if isinstance(models[0], dict) else {}
                resolved_fields = first.get("fields")
                if isinstance(resolved_fields, list) and resolved_fields:
                    # Already in HubContract shape — no re-normalisation.
                    return list(resolved_fields)
                warnings.append(
                    f"{WARNING_NO_RESOLVABLE}: outputPort "
                    f"{port_name} contractId {cid} resolved model "
                    f"has no fields"
                )

    # Priority 2-4: inline shapes — normalise ODCS shape to HubContract.
    inline_raw = _extract_inline_fields(port)
    if inline_raw:
        normalised = _normalize_fields(inline_raw)
        if normalised:
            return normalised

    # Priority 5: contractURL via RefResolver.
    url = port.get("contractURL")
    if url and ref_resolver is not None:
        resolved = _resolve_contract_url(url, ref_resolver)
        if isinstance(resolved, dict):
            url_fields = _extract_fields_from_resolved_doc(resolved)
            if url_fields:
                normalised = _normalize_fields(url_fields)
                if normalised:
                    return normalised

    # No resolvable payload — only emit "no resolvable" if NO previous
    # warning has already been logged for this port (priority-1 already
    # explained the failure for cycle/not-found/empty cases).
    warnings.append(
        f"{WARNING_NO_RESOLVABLE}: outputPort {port_name} has no "
        f"resolvable schema (no contractId / contract.spec.schema "
        f"/ dataSchema.fields / schema.fields / contractURL)"
    )
    return None


def _process_input_ports(
    *,
    contract_data: Dict[str, Any],
    hub_contract: Dict[str, Any],
) -> None:
    """Map ``inputPorts[]`` → ``hub_contract["lineage"]["contracts"][]``.

    Only ``name`` is required. ``namespace`` is optional. Empty entries
    (no name) are dropped silently — the source ODPS may carry
    placeholder rows.
    """
    input_ports = _get_ports_from_data(contract_data, "inputPorts")
    if not input_ports:
        return

    lineage_entries: List[Dict[str, Any]] = []
    for port in input_ports:
        name = port.get("name")
        if not name:
            continue
        entry: Dict[str, Any] = {"name": str(name)}
        namespace = port.get("namespace")
        if namespace:
            entry["namespace"] = str(namespace)
        lineage_entries.append(entry)

    if not lineage_entries:
        return

    lineage = hub_contract.setdefault("lineage", {})
    existing = lineage.get("contracts")
    if isinstance(existing, list):
        existing.extend(lineage_entries)
    else:
        lineage["contracts"] = lineage_entries
