"""
Phase 228.F2 (REQ-LIN-F2-001 / F2.11 + F2.12) — lineage validator tests.

Three suites:

1. **Unit tests** for the three pure functions: cycle detection,
   field-existence walking nested object/array shapes, type
   compatibility matrix.

2. **Property-based tests** with ``hypothesis``: a randomised DAG +
   a randomised candidate edge, asserting the cycle-detection
   invariant ("a candidate edge u → v closes a cycle iff there's
   a v → u path in the existing graph").

The validator is a pure-function module so the tests don't need
django setup — they run as plain pytest.
"""
from __future__ import annotations

import pytest

from hub.apps.contracts.lineage_validator import (
    detect_cycle,
    validate_field_exists,
    validate_type_compatibility,
)


# ---------------------------------------------------------------------------
# detect_cycle — unit
# ---------------------------------------------------------------------------


def _edge(src_c, tgt_c, src_f="", tgt_f="", model_s="", model_t=""):
    """Compose an edge dict with the canonical key shape."""
    return {
        "source_contract": src_c,
        "target_contract": tgt_c,
        "source_model": model_s,
        "source_field": src_f,
        "target_model": model_t,
        "target_field": tgt_f,
    }


class TestDetectCycle:

    def test_empty_graph_no_cycle(self):
        assert detect_cycle([], _edge("A", "B")) is False

    def test_self_loop_is_a_cycle(self):
        assert detect_cycle([], _edge("A", "A", "x", "x")) is True

    def test_a_b_then_b_a_closes_cycle(self):
        existing = [_edge("A", "B")]
        candidate = _edge("B", "A")
        assert detect_cycle(existing, candidate) is True

    def test_a_b_then_b_c_does_not_cycle(self):
        existing = [_edge("A", "B")]
        candidate = _edge("B", "C")
        assert detect_cycle(existing, candidate) is False

    def test_long_chain_back_to_start_is_a_cycle(self):
        # A → B → C → D, candidate D → A closes.
        existing = [
            _edge("A", "B"),
            _edge("B", "C"),
            _edge("C", "D"),
        ]
        candidate = _edge("D", "A")
        assert detect_cycle(existing, candidate) is True

    def test_disjoint_components_dont_cycle(self):
        # A → B and C → D; candidate D → A does NOT close — A and D
        # are in separate components.
        existing = [
            _edge("A", "B"),
            _edge("C", "D"),
        ]
        candidate = _edge("D", "A")
        assert detect_cycle(existing, candidate) is False

    def test_cycle_at_field_level(self):
        # Same contract pair but different field qnames — only the
        # specific field-pair counts.
        existing = [
            _edge("A", "B", src_f="x", tgt_f="y"),
        ]
        candidate = _edge("B", "A", src_f="y", tgt_f="x")
        assert detect_cycle(existing, candidate) is True

    def test_field_pair_distinguished_from_other_pair(self):
        existing = [
            _edge("A", "B", src_f="x", tgt_f="y"),
        ]
        # Different source-field — not a cycle (distinct edge).
        candidate = _edge("B", "A", src_f="z", tgt_f="w")
        assert detect_cycle(existing, candidate) is False


# ---------------------------------------------------------------------------
# validate_field_exists — unit
# ---------------------------------------------------------------------------


class TestValidateFieldExists:

    def test_top_level_schema_field(self):
        payload = {
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }
        assert validate_field_exists(payload, "", "id") is True
        assert validate_field_exists(payload, "", "missing") is False

    def test_model_level_field(self):
        payload = {
            "models": [
                {"name": "orders", "fields": [{"name": "order_id"}]}
            ],
        }
        assert validate_field_exists(payload, "orders", "order_id") is True
        assert validate_field_exists(payload, "orders", "missing") is False
        assert validate_field_exists(payload, "missing-model", "x") is False

    def test_nested_object_field(self):
        payload = {
            "models": [
                {
                    "name": "customers",
                    "fields": [
                        {
                            "name": "address",
                            "data_type": "object",
                            "fields": [
                                {"name": "street", "data_type": "string"},
                            ],
                        },
                    ],
                },
            ],
        }
        # Dot-separated qname walks nested shape.
        assert validate_field_exists(
            payload, "customers", "address.street",
        ) is True
        assert validate_field_exists(
            payload, "customers", "address.missing",
        ) is False

    def test_array_items_field(self):
        payload = {
            "models": [
                {
                    "name": "orders",
                    "fields": [
                        {
                            "name": "items",
                            "data_type": "array",
                            "items": {
                                "fields": [
                                    {"name": "sku", "data_type": "string"},
                                ],
                            },
                        },
                    ],
                },
            ],
        }
        assert validate_field_exists(payload, "orders", "items.sku") is True

    def test_empty_payload(self):
        assert validate_field_exists({}, "", "anything") is False
        assert validate_field_exists(None, "", "anything") is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_type_compatibility — unit
# ---------------------------------------------------------------------------


class TestValidateTypeCompatibility:

    @pytest.mark.parametrize(
        "src,tgt,expected",
        [
            ("string", "string", True),
            ("integer", "long", True),
            ("integer", "decimal", True),
            ("integer", "string", False),  # narrowing — needs xform
            ("float", "double", True),
            ("date", "string", True),
            ("string", "integer", False),
            ("boolean", "integer", False),
        ],
    )
    def test_widening_matrix(self, src, tgt, expected):
        assert validate_type_compatibility(src, tgt) is expected

    def test_unknown_types_accepted(self):
        # Defensive default: missing type info → can't reject.
        assert validate_type_compatibility(None, "string") is True
        assert validate_type_compatibility("string", None) is True

    def test_transformation_ref_bypasses_matrix(self):
        # An explicit transformation_ref means "lossy cast acknowledged".
        assert validate_type_compatibility(
            "string", "integer", transformation_ref="CAST(x AS INTEGER)",
        ) is True

    def test_case_and_whitespace_normalised(self):
        assert validate_type_compatibility(" String ", "STRING") is True


# ---------------------------------------------------------------------------
# Property-based tests (F2.12)
# ---------------------------------------------------------------------------


hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st  # noqa: E402


@st.composite
def _random_dag_edges(draw):
    """Generate a random DAG over up to 8 nodes (no duplicate edges).

    By construction the edges are sorted (u < v) so the resulting
    graph is acyclic — a property tests can rely on for the
    'cycle exists ↔ reverse path exists' assertion.
    """
    n = draw(st.integers(min_value=2, max_value=8))
    nodes = [chr(ord("A") + i) for i in range(n)]
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if draw(st.booleans()):
                edges.append(_edge(nodes[i], nodes[j]))
    return nodes, edges


@given(graph=_random_dag_edges(), pair=st.tuples(st.sampled_from("ABCDEFGH"), st.sampled_from("ABCDEFGH")))
def test_cycle_detection_iff_reverse_path_exists(graph, pair):
    """Property: ``detect_cycle(existing, u→v)`` is True iff the
    existing graph has a path v→u.

    The "iff" holds because the new edge u→v closes a cycle
    precisely when v can already reach u.  We compute reachability
    independently in the test (Floyd-Warshall-style transitive
    closure) and compare against ``detect_cycle``."""
    nodes, edges = graph
    u, v = pair
    if u not in nodes or v not in nodes:
        return  # sampled_from outside graph; skip

    # Transitive closure.
    adj = {n: set() for n in nodes}
    for e in edges:
        adj[e["source_contract"]].add(e["target_contract"])
    # Floyd-Warshall.
    closure = {n: set(adj[n]) for n in nodes}
    for k in nodes:
        for i in nodes:
            for j in nodes:
                if k in closure[i] and j in closure[k]:
                    closure[i].add(j)

    expected_cycle = (u in closure[v]) or (u == v)

    candidate = _edge(u, v)
    assert detect_cycle(edges, candidate) is expected_cycle
