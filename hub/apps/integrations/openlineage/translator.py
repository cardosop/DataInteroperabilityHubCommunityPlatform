"""
Phase 228 F4 (228.F4.4) — bidirectional OpenLineage ↔ Meshant
schema mapping.

The OpenLineage spec (https://openlineage.io/spec/) defines
``RunEvent`` / ``Job`` / ``Run`` / ``Dataset`` facets that don't
map 1:1 to Meshant's contract-centric ``LineageEdge`` shape. This
module is the only place in the codebase that knows the cross-
walk; every other module passes through translator boundaries.

Outbound (Meshant → OpenLineage)
--------------------------------

:func:`meshant_edge_to_openlineage` takes one Meshant edge dict
(the shape ``LineageService._edges_at`` returns) + the canonical
producer URL and returns an OpenLineage 2.0.0 ``RunEvent`` dict.

The ``edge_type`` taxonomy maps to ``eventType``:

* ``transformation`` / ``derivation`` → ``COMPLETE`` (the run
  finished and produced its target).
* ``upload`` / ``export`` → ``COMPLETE`` (the same; one-shot).
* ``reference`` → ``OTHER`` (no run semantics — pure structural
  link; OpenLineage's catch-all is OTHER per the spec).

Inputs/outputs are ``Dataset`` objects with ``namespace =
"meshant.contracts"`` + ``name = <contract_id>`` so external
receivers (Marquez, Datakin) can index by Meshant contract id
without knowing Meshant internals.

Each Dataset carries the custom ``meshant_contract_ref`` facet:
``{contract_id, model, field}``. The facet name is namespaced
under ``meshant_`` per the OpenLineage facet-naming convention
(snake-cased prefix).

Inbound (OpenLineage → Meshant)
-------------------------------

:func:`openlineage_to_meshant_edge` reads an inbound RunEvent and
extracts the canonical Meshant scope tuple. Two cohorts:

1. Events emitted BY Meshant via the outbound path — round-trip
   loss-lessly because the custom facet carries every Meshant
   field.
2. Events emitted by external producers (Airflow, dbt, custom)
   — fall back to the ``namespace == "meshant.contracts"`` +
   ``name == <uuid>`` convention when the custom facet is absent.

Validation
----------

:func:`validate_openlineage_event` runs ``jsonschema`` against an
embedded subset of the OpenLineage 2.0.0 schema. We do NOT fetch
the live schema URL at validation time (that would introduce a
network dependency on every inbound event); the embedded schema
is updated when we bump the ``openlineage-python`` dep.

Schema source: https://openlineage.io/spec/2-0-0/OpenLineage.json
The embedded subset focuses on the structural keys we care about
(eventType, eventTime, producer, schemaURL, run, job, inputs,
outputs) — Marquez does its own deep validation downstream.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

OPENLINEAGE_SCHEMA_URL = "https://openlineage.io/spec/2-0-0/OpenLineage.json"
"""Canonical schema URL surfaced in every outbound event."""

DEFAULT_DATASET_NAMESPACE = "meshant.contracts"
"""Namespace used when the source/target is a Meshant contract."""

MESHANT_CONTRACT_REF_FACET = "meshant_contract_ref"
"""Custom facet name (snake_case per OpenLineage convention)."""

# ``edge_type`` → OpenLineage ``eventType`` mapping.
_EDGE_TYPE_TO_EVENT_TYPE = {
    "transformation": "COMPLETE",
    "derivation": "COMPLETE",
    "upload": "COMPLETE",
    "export": "COMPLETE",
    "reference": "OTHER",
}

# Reverse map for inbound — we collapse multiple Meshant edge_types
# into ``transformation`` for COMPLETE because the upstream signal is
# "a run finished + this is its produced output". The producer can
# refine via the custom facet (we read the original ``edge_type``
# from the facet when present).
_EVENT_TYPE_TO_EDGE_TYPE_FALLBACK = {
    "COMPLETE": "transformation",
    "START": "transformation",
    "RUNNING": "transformation",
    "ABORT": "transformation",
    "FAIL": "transformation",
    "OTHER": "reference",
}

# Embedded subset of the OpenLineage 2.0.0 RunEvent schema. Updated
# in lock-step with the ``openlineage-python`` dep bump (228.F4.2).
# Keeps the structural invariants every outbound event must satisfy
# WITHOUT pulling the full upstream schema (which is large + contains
# vendor-specific facet definitions Meshant doesn't emit).
_OPENLINEAGE_RUN_EVENT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "OpenLineage RunEvent (Meshant subset)",
    "type": "object",
    "required": [
        "eventType",
        "eventTime",
        "producer",
        "schemaURL",
        "run",
        "job",
        "inputs",
        "outputs",
    ],
    "properties": {
        "eventType": {
            "type": "string",
            "enum": ["START", "RUNNING", "COMPLETE", "ABORT", "FAIL", "OTHER"],
        },
        "eventTime": {"type": "string", "format": "date-time"},
        "producer": {"type": "string", "format": "uri"},
        "schemaURL": {"type": "string", "format": "uri"},
        "run": {
            "type": "object",
            "required": ["runId"],
            "properties": {"runId": {"type": "string"}},
        },
        "job": {
            "type": "object",
            "required": ["namespace", "name"],
            "properties": {
                "namespace": {"type": "string"},
                "name": {"type": "string"},
            },
        },
        "inputs": {
            "type": "array",
            "items": {"$ref": "#/$defs/Dataset"},
        },
        "outputs": {
            "type": "array",
            "items": {"$ref": "#/$defs/Dataset"},
        },
    },
    "$defs": {
        "Dataset": {
            "type": "object",
            "required": ["namespace", "name"],
            "properties": {
                "namespace": {"type": "string"},
                "name": {"type": "string"},
                "facets": {"type": "object"},
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Outbound — Meshant → OpenLineage
# ---------------------------------------------------------------------------


def meshant_edge_to_openlineage(
    edge: dict[str, Any],
    *,
    producer: str,
    job_namespace: str = "meshant.lineage",
) -> dict[str, Any]:
    """Translate one Meshant lineage-edge dict into an OpenLineage
    2.0.0 ``RunEvent`` dict.

    The returned dict validates against
    :data:`_OPENLINEAGE_RUN_EVENT_SCHEMA` (cross-checked by the test
    suite's ``validate_openlineage_event`` call).

    Args:
        edge: The Meshant edge — shape matches
            ``LineageService._edges_at``'s return rows.
        producer: Canonical producer URL (settings.OPENLINEAGE_PRODUCER_NAME).
        job_namespace: Namespace for the synthetic Job that owns
            the Run. Defaults to ``meshant.lineage`` so external
            consumers can filter Meshant-emitted runs by namespace.
    """
    event_type = _EDGE_TYPE_TO_EVENT_TYPE.get(
        str(edge.get("edge_type") or "reference"),
        "OTHER",
    )
    run_id = str(edge.get("id") or "")
    if not run_id:
        # Edge dicts ALWAYS carry an ``id``; if absent, refuse to
        # emit (rather than silently filling a UUID — that would
        # decouple Meshant's audit trail from OpenLineage's).
        raise ValueError(
            "meshant_edge_to_openlineage: edge dict missing required ``id`` "
            "field; cannot emit OpenLineage event without a stable runId"
        )

    job_name = edge.get("transformation_ref") or edge.get("job_ref") or f"edge:{event_type.lower()}"

    event_time = edge.get("valid_from") or _dt.datetime.now(_dt.UTC).isoformat()

    return {
        "eventType": event_type,
        "eventTime": event_time,
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
        "run": {"runId": run_id},
        "job": {"namespace": job_namespace, "name": str(job_name)},
        "inputs": [_dataset_from_edge_side(edge, side="source")],
        "outputs": [_dataset_from_edge_side(edge, side="target")],
    }


def _dataset_from_edge_side(edge: dict[str, Any], *, side: str) -> dict[str, Any]:
    """Build the Dataset (input or output) for one side of the edge."""
    contract_key = "source_contract" if side == "source" else "target_contract"
    model_key = "source_model" if side == "source" else "target_model"
    field_key = "source_field" if side == "source" else "target_field"
    contract_id = str(edge.get(contract_key) or "")
    return {
        "namespace": DEFAULT_DATASET_NAMESPACE,
        "name": contract_id or "<external>",
        "facets": {
            MESHANT_CONTRACT_REF_FACET: {
                # Custom facet so receivers can correlate back to
                # Meshant resources without parsing the namespace.
                "contract_id": contract_id or None,
                "model": str(edge.get(model_key) or ""),
                "field": str(edge.get(field_key) or ""),
                "edge_type": str(edge.get("edge_type") or "reference"),
                "transformation_ref": str(edge.get("transformation_ref") or ""),
                "job_ref": str(edge.get("job_ref") or ""),
            },
        },
    }


# ---------------------------------------------------------------------------
# Inbound — OpenLineage → Meshant
# ---------------------------------------------------------------------------


def openlineage_to_meshant_edge(event: dict[str, Any]) -> dict[str, Any]:
    """Extract the canonical Meshant scope tuple from an inbound
    OpenLineage RunEvent.

    Returns a dict shaped to match the 9-field tuple
    ``lineage_sync._sync_contract_edges`` consumes. Missing fields
    default to ``""`` (empty string) so the diff's set-arithmetic
    is well-defined.
    """
    inputs = event.get("inputs") or []
    outputs = event.get("outputs") or []
    src = _meshant_facet(inputs[0] if inputs else {})
    tgt = _meshant_facet(outputs[0] if outputs else {})

    # Edge-type resolution priority:
    # 1. Custom facet's own ``edge_type`` (round-trip from outbound).
    # 2. ``eventType`` fallback for external producers.
    edge_type = (
        src.get("edge_type")
        or tgt.get("edge_type")
        or _EVENT_TYPE_TO_EDGE_TYPE_FALLBACK.get(event.get("eventType") or "OTHER", "reference")
    )

    job = event.get("job") or {}
    job_ref = (
        src.get("job_ref")
        or tgt.get("job_ref")
        or f"{job.get('namespace', '')}:{job.get('name', '')}".strip(":")
    )

    return {
        "source_contract": src.get("contract_id"),
        "target_contract": tgt.get("contract_id"),
        "source_model": src.get("model", ""),
        "source_field": src.get("field", ""),
        "target_model": tgt.get("model", ""),
        "target_field": tgt.get("field", ""),
        "edge_type": edge_type,
        "transformation_ref": (
            src.get("transformation_ref") or tgt.get("transformation_ref") or ""
        ),
        "job_ref": job_ref,
        "openlineage_run_id": (event.get("run") or {}).get("runId"),
    }


def _meshant_facet(dataset: dict[str, Any]) -> dict[str, Any]:
    """Read the Meshant custom facet from a Dataset; fall back to
    ``namespace + name`` convention when absent (external producer)."""
    facets = dataset.get("facets") or {}
    facet = facets.get(MESHANT_CONTRACT_REF_FACET)
    if isinstance(facet, dict):
        # Round-trip case — every field present.
        return {
            "contract_id": facet.get("contract_id"),
            "model": facet.get("model", ""),
            "field": facet.get("field", ""),
            "edge_type": facet.get("edge_type"),
            "transformation_ref": facet.get("transformation_ref", ""),
            "job_ref": facet.get("job_ref", ""),
        }
    # External-producer fallback: when ``namespace == DEFAULT_DATASET_NAMESPACE``
    # the ``name`` IS the contract id.
    if dataset.get("namespace") == DEFAULT_DATASET_NAMESPACE and dataset.get("name"):
        return {"contract_id": str(dataset["name"]), "model": "", "field": ""}
    return {"contract_id": None, "model": "", "field": ""}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_openlineage_event(event: dict[str, Any]) -> None:
    """Validate the event against the embedded OpenLineage 2.0.0
    schema. Raises ``jsonschema.ValidationError`` on failure; the
    caller turns the error into the appropriate API response.
    """
    from jsonschema import validate

    validate(instance=event, schema=_OPENLINEAGE_RUN_EVENT_SCHEMA)


__all__ = [
    "DEFAULT_DATASET_NAMESPACE",
    "MESHANT_CONTRACT_REF_FACET",
    "OPENLINEAGE_SCHEMA_URL",
    "meshant_edge_to_openlineage",
    "openlineage_to_meshant_edge",
    "validate_openlineage_event",
]
