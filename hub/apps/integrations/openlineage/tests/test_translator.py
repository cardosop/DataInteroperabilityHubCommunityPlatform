"""
Phase 228 F4 (228.F4.20) — translator tests.

Pins the bidirectional schema mapping between Meshant's internal
``LineageEdge`` shape and OpenLineage 2.0.0 ``RunEvent``. Real
``jsonschema`` validation against the upstream spec; no mocks of
internal code paths.

Coverage:

* Outbound (Meshant → OpenLineage) — every internal lineage event
  type produces a ``RunEvent`` that validates against the
  OpenLineage spec.
* Inbound (OpenLineage → Meshant) — a real RunEvent maps to the
  canonical Meshant scope tuple the signal handler diff understands.
* Round-trip — outbound→inbound→outbound is fixed-point under the
  scope-equality predicate.
* Validation rejects malformed inputs (missing required keys,
  invalid eventType).
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest

# ---------------------------------------------------------------------------
# Outbound translation (Meshant → OpenLineage)
# ---------------------------------------------------------------------------


def _meshant_edge(*, source_contract=None, target_contract=None, edge_type="reference"):
    """Build a minimal Meshant lineage-edge dict (the shape that
    ``LineageService._edges_at`` returns)."""
    return {
        "id": str(uuid.uuid4()),
        "source_contract": source_contract or str(uuid.uuid4()),
        "target_contract": target_contract or str(uuid.uuid4()),
        "source_model": "orders",
        "source_field": "order_id",
        "target_model": "fulfillment",
        "target_field": "order_ref",
        "edge_type": edge_type,
        "transformation_ref": "dbt://models/orders_fulfillment.sql",
        "job_ref": "airflow://dag/orders_etl/run/2026-04-30",
        "valid_from": _dt.datetime(2026, 4, 30, tzinfo=_dt.UTC).isoformat(),
        "valid_to": None,
    }


def test_outbound_produces_openlineage_run_event_shape():
    """A Meshant edge translates into a dict matching the
    OpenLineage RunEvent canonical structure."""
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
    )

    edge = _meshant_edge()
    event = meshant_edge_to_openlineage(edge, producer="https://meshant.com/")

    # Top-level required keys per OpenLineage spec.
    for key in (
        "eventType",
        "eventTime",
        "producer",
        "schemaURL",
        "run",
        "job",
        "inputs",
        "outputs",
    ):
        assert key in event, f"OpenLineage event missing required key {key!r}; got {event!r}"
    assert event["eventType"] in {"START", "RUNNING", "COMPLETE", "ABORT", "FAIL", "OTHER"}
    assert event["producer"] == "https://meshant.com/"
    # Schema URL pins to the OpenLineage major version.
    assert "openlineage.io" in event["schemaURL"]


def test_outbound_event_validates_against_jsonschema():
    """The translated event passes jsonschema validation against
    the embedded OpenLineage 2.0.0 schema."""
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
        validate_openlineage_event,
    )

    edge = _meshant_edge()
    event = meshant_edge_to_openlineage(edge, producer="https://meshant.com/")
    # No exception → valid.
    validate_openlineage_event(event)


def test_outbound_inputs_outputs_carry_dataset_facets():
    """Inputs/outputs are OpenLineage ``Dataset`` objects with
    ``namespace`` + ``name`` + the Meshant-custom ``meshant.contract_ref``
    facet so receivers can correlate back to Meshant resources."""
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
    )

    edge = _meshant_edge(source_contract="src-uuid", target_contract="tgt-uuid")
    event = meshant_edge_to_openlineage(edge, producer="https://meshant.com/")

    assert len(event["inputs"]) == 1
    assert len(event["outputs"]) == 1
    inp = event["inputs"][0]
    assert "namespace" in inp and "name" in inp
    # Custom Meshant facet.
    assert "facets" in inp
    assert "meshant_contract_ref" in inp["facets"], (
        f"input must carry meshant_contract_ref facet for receiver correlation; "
        f"got facets={list(inp.get('facets') or [])}"
    )
    facet = inp["facets"]["meshant_contract_ref"]
    assert facet["contract_id"] == "src-uuid"


def test_outbound_event_type_maps_from_edge_type():
    """The ``edge_type`` taxonomy maps to OpenLineage ``eventType``:
    a transformation/derivation edge is a COMPLETE RunEvent (the
    transformation finished and produced its output); a reference
    edge is OTHER (no run semantics — just a structural link)."""
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
    )

    transformation = meshant_edge_to_openlineage(
        _meshant_edge(edge_type="transformation"),
        producer="x",
    )
    reference = meshant_edge_to_openlineage(
        _meshant_edge(edge_type="reference"),
        producer="x",
    )
    assert transformation["eventType"] == "COMPLETE"
    assert reference["eventType"] == "OTHER"


# ---------------------------------------------------------------------------
# Inbound translation (OpenLineage → Meshant)
# ---------------------------------------------------------------------------


def test_inbound_run_event_to_meshant_edge_tuple():
    """A canonical OpenLineage RunEvent maps to the Meshant scope
    tuple the signal handler diff understands."""
    from hub.apps.integrations.openlineage.translator import (
        openlineage_to_meshant_edge,
    )

    event = {
        "eventType": "COMPLETE",
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "https://airflow.example.com/",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "etl", "name": "orders_to_fulfillment"},
        "inputs": [
            {
                "namespace": "meshant.contracts",
                "name": "src-uuid",
                "facets": {
                    "meshant_contract_ref": {
                        "contract_id": "src-uuid",
                        "model": "orders",
                        "field": "order_id",
                    },
                },
            },
        ],
        "outputs": [
            {
                "namespace": "meshant.contracts",
                "name": "tgt-uuid",
                "facets": {
                    "meshant_contract_ref": {
                        "contract_id": "tgt-uuid",
                        "model": "fulfillment",
                        "field": "order_ref",
                    },
                },
            },
        ],
    }
    tup = openlineage_to_meshant_edge(event)
    # The tuple matches the canonical 9-field shape from lineage_sync.
    assert tup["source_contract"] == "src-uuid"
    assert tup["target_contract"] == "tgt-uuid"
    assert tup["source_model"] == "orders"
    assert tup["target_model"] == "fulfillment"
    assert tup["edge_type"] == "transformation"  # COMPLETE → transformation
    assert tup["job_ref"] == "etl:orders_to_fulfillment"


def test_inbound_event_without_meshant_facet_falls_back_to_namespace():
    """An external producer (Marquez, Datakin) that didn't add the
    Meshant custom facet still maps cleanly: the input/output
    ``name`` is treated as the contract id when ``namespace ==
    meshant.contracts``; otherwise the contract id is None and the
    edge_type defaults to ``reference``."""
    from hub.apps.integrations.openlineage.translator import (
        openlineage_to_meshant_edge,
    )

    event = {
        "eventType": "COMPLETE",
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "https://external.example.com/",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "external", "name": "ingest"},
        "inputs": [{"namespace": "meshant.contracts", "name": "src-uuid"}],
        "outputs": [{"namespace": "meshant.contracts", "name": "tgt-uuid"}],
    }
    tup = openlineage_to_meshant_edge(event)
    assert tup["source_contract"] == "src-uuid"
    assert tup["target_contract"] == "tgt-uuid"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_preserves_scope_tuple():
    """outbound → inbound → ``source_contract`` + ``target_contract``
    + ``edge_type`` + ``source_field`` round-trip identically. The
    full tuple isn't always equal (eventTime / runId regenerate),
    but the **scope** the diff cares about must survive."""
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
        openlineage_to_meshant_edge,
    )

    original = _meshant_edge(edge_type="transformation")
    event = meshant_edge_to_openlineage(original, producer="https://meshant.com/")
    round_tripped = openlineage_to_meshant_edge(event)

    for key in (
        "source_contract",
        "target_contract",
        "source_model",
        "source_field",
        "target_model",
        "target_field",
        "edge_type",
    ):
        assert round_tripped[key] == original[key], (
            f"round-trip lost {key!r}: original={original[key]!r}, "
            f"round_tripped={round_tripped[key]!r}"
        )


# ---------------------------------------------------------------------------
# Validation rejection
# ---------------------------------------------------------------------------


def test_validation_rejects_missing_required_keys():
    from jsonschema import ValidationError

    from hub.apps.integrations.openlineage.translator import validate_openlineage_event

    bad = {"eventType": "COMPLETE"}  # missing eventTime / producer / run / job
    with pytest.raises(ValidationError):
        validate_openlineage_event(bad)


def test_validation_rejects_invalid_event_type():
    from jsonschema import ValidationError

    from hub.apps.integrations.openlineage.translator import validate_openlineage_event

    bad = {
        "eventType": "BOGUS",  # not in enum
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "https://x/",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "x", "name": "y"},
        "inputs": [],
        "outputs": [],
    }
    with pytest.raises(ValidationError):
        validate_openlineage_event(bad)


# ---------------------------------------------------------------------------
# Phase 8 — previously uncovered translator paths
# ---------------------------------------------------------------------------


def test_outbound_raises_value_error_when_edge_missing_id():
    """``meshant_edge_to_openlineage`` requires the edge dict to have
    a non-empty ``id`` key."""
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
    )

    edge = _meshant_edge()
    edge["id"] = ""
    with pytest.raises(ValueError, match="missing required.*id"):
        meshant_edge_to_openlineage(edge, producer="x")


def test_inbound_unknown_event_type_falls_back_to_reference():
    """An event with an unknown/custom ``eventType`` should map to
    ``edge_type='reference'`` via the fallback table."""
    from hub.apps.integrations.openlineage.translator import (
        openlineage_to_meshant_edge,
    )

    event = {
        "eventType": "CUSTOM_PRODUCER_EVENT",
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "x",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "x", "name": "y"},
        "inputs": [
            {"namespace": "meshant.contracts", "name": "src-uuid",
             "facets": {"meshant_contract_ref": {"contract_id": "src-uuid"}}},
        ],
        "outputs": [
            {"namespace": "meshant.contracts", "name": "tgt-uuid",
             "facets": {"meshant_contract_ref": {"contract_id": "tgt-uuid"}}},
        ],
    }
    tup = openlineage_to_meshant_edge(event)
    assert tup["edge_type"] == "reference", (
        f"unknown eventType should fall back to 'reference'; got {tup['edge_type']}"
    )


@pytest.mark.parametrize("edge_type", ["derivation", "upload", "export"])
def test_outbound_edge_types_map_to_complete(edge_type):
    """Edge types ``derivation``, ``upload``, and ``export`` all map
    to ``COMPLETE`` RunEvents (only ``transformation`` was tested)."""
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
    )

    edge = _meshant_edge(edge_type=edge_type)
    event = meshant_edge_to_openlineage(edge, producer="x")
    assert event["eventType"] == "COMPLETE", (
        f"edge_type={edge_type!r} should map to COMPLETE; got {event['eventType']}"
    )
