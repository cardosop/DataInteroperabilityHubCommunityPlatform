"""
Phase 228.F3.8 — Severity classifier unit tests.

The severity classifier is a pure function that takes a lineage diff
+ a contract diff and returns one of CRITICAL / HIGH / MEDIUM / LOW
per REQ-LIN-F3-004.  It MUST be deterministic — same input, same
output, every time — so the tests are exhaustive on the spec mapping
table and pin the precedence rules:

* CRITICAL — breaking schema change downstream (a removed field that
  another contract depends on).  Beats every other classification.
* HIGH — transformation_ref change OR edge added/removed on a
  contract that has any subscriber.
* MEDIUM — cosmetic change (job_ref change, edge metadata cleanup).
* LOW — reference-only change (no semantic impact).

The classifier is intentionally LOW-by-default so that future edge
types added without a mapping entry don't accidentally page
everyone — they fall into LOW until the mapping is extended.
"""
from __future__ import annotations

import pytest

from hub.apps.contracts.lineage_severity import (
    ContractDiff,
    LineageDiff,
    LineageEdgeDelta,
    Severity,
    classify,
)


def _edge(
    edge_type: str = "reference",
    transformation_ref: str = "",
    job_ref: str = "",
    source_field: str = "x",
    target_field: str = "x",
) -> dict:
    return {
        "source_contract": "c1",
        "target_contract": "c2",
        "source_model": "default",
        "target_model": "default",
        "source_field": source_field,
        "target_field": target_field,
        "edge_type": edge_type,
        "transformation_ref": transformation_ref,
        "job_ref": job_ref,
    }


# ---------------------------------------------------------------------------
# CRITICAL — breaking schema change downstream
# ---------------------------------------------------------------------------


class TestCritical:

    def test_field_removed_with_downstream_dependents_is_critical(self):
        # A field referenced by another contract was deleted from
        # the source contract.  This is the canonical breaking
        # change — downstream pipelines reading this field will
        # fail.
        contract_diff = ContractDiff(
            removed_fields=[("orders", "customer_id")],
            added_fields=[],
            modified_fields=[],
        )
        diff = LineageDiff(
            added=[],
            removed=[],
            modified=[],
            downstream_field_dependencies={
                ("orders", "customer_id"): ["downstream_contract_a"],
            },
        )
        assert classify(diff, contract_diff) == Severity.CRITICAL

    def test_field_removed_without_dependents_is_not_critical(self):
        # The field was removed but no downstream contract references
        # it.  Adding a derivation edge keeps it HIGH (not CRITICAL).
        contract_diff = ContractDiff(
            removed_fields=[("orders", "internal_only")],
            added_fields=[],
            modified_fields=[],
        )
        diff = LineageDiff(
            added=[_edge(edge_type="derivation")],
            removed=[],
            modified=[],
            downstream_field_dependencies={},
        )
        result = classify(diff, contract_diff)
        # Must NOT be CRITICAL since no downstream depends on the
        # removed field AND no derivation was REMOVED (only added).
        assert result != Severity.CRITICAL

    # REQ-LIN-F3-004 spec scenario "Removed derivation edge classified
    # CRITICAL" — pinned exactly per spec.
    def test_removed_derivation_edge_classified_critical(self):
        diff = LineageDiff(
            added=[],
            removed=[_edge(edge_type="derivation")],
            modified=[],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.CRITICAL


# ---------------------------------------------------------------------------
# HIGH — transformation change OR edge add/remove on subscribed contract
# ---------------------------------------------------------------------------


class TestHigh:

    def test_transformation_ref_change_is_high(self):
        # A transformation_ref change means the semantic of the
        # column-level mapping changed — downstream consumers may
        # see different values even though the column shape is
        # unchanged.
        old = _edge(edge_type="derivation", transformation_ref="UPPER(x)")
        new = _edge(edge_type="derivation", transformation_ref="LOWER(x)")
        diff = LineageDiff(
            added=[],
            removed=[],
            modified=[
                LineageEdgeDelta(before=old, after=new, fields_changed=["transformation_ref"]),
            ],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.HIGH

    def test_derivation_edge_added_is_high(self):
        # Adding a derivation edge changes the lineage graph
        # structurally; downstream subscribers benefit from being
        # told.
        diff = LineageDiff(
            added=[_edge(edge_type="derivation")],
            removed=[],
            modified=[],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.HIGH

    # NOTE: removed-derivation is CRITICAL per spec scenario; covered
    # by ``TestCritical.test_removed_derivation_edge_classified_critical``.


# ---------------------------------------------------------------------------
# MEDIUM — cosmetic change (job_ref change, metadata cleanup)
# ---------------------------------------------------------------------------


class TestMedium:

    def test_job_ref_only_change_is_medium(self):
        old = _edge(edge_type="derivation", job_ref="job-v1")
        new = _edge(edge_type="derivation", job_ref="job-v2")
        diff = LineageDiff(
            added=[],
            removed=[],
            modified=[
                LineageEdgeDelta(before=old, after=new, fields_changed=["job_ref"]),
            ],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.MEDIUM


# ---------------------------------------------------------------------------
# LOW — reference-only change (no semantic impact)
# ---------------------------------------------------------------------------


class TestLow:

    def test_reference_only_added_is_low(self):
        diff = LineageDiff(
            added=[_edge(edge_type="reference")],
            removed=[],
            modified=[],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.LOW

    def test_reference_only_removed_is_low(self):
        diff = LineageDiff(
            added=[],
            removed=[_edge(edge_type="reference")],
            modified=[],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.LOW

    def test_no_change_is_low(self):
        diff = LineageDiff(
            added=[], removed=[], modified=[],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.LOW


# ---------------------------------------------------------------------------
# Precedence — when multiple categories apply, the highest wins
# ---------------------------------------------------------------------------


class TestPrecedence:

    def test_critical_beats_high_when_both_apply(self):
        # Field-removed-with-dependents (CRITICAL) AND a transformation
        # change in the same diff — CRITICAL must win.
        old = _edge(edge_type="derivation", transformation_ref="UPPER(x)")
        new = _edge(edge_type="derivation", transformation_ref="LOWER(x)")
        diff = LineageDiff(
            added=[],
            removed=[],
            modified=[
                LineageEdgeDelta(before=old, after=new, fields_changed=["transformation_ref"]),
            ],
            downstream_field_dependencies={
                ("orders", "customer_id"): ["other"],
            },
        )
        contract_diff = ContractDiff(
            removed_fields=[("orders", "customer_id")],
            added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.CRITICAL

    def test_high_beats_medium_when_both_apply(self):
        # Both a transformation_ref change (HIGH) AND a job_ref
        # change (MEDIUM) — HIGH wins.
        old1 = _edge(edge_type="derivation", transformation_ref="A")
        new1 = _edge(edge_type="derivation", transformation_ref="B")
        old2 = _edge(edge_type="derivation", job_ref="j1")
        new2 = _edge(edge_type="derivation", job_ref="j2")
        diff = LineageDiff(
            added=[], removed=[],
            modified=[
                LineageEdgeDelta(before=old1, after=new1,
                                 fields_changed=["transformation_ref"]),
                LineageEdgeDelta(before=old2, after=new2,
                                 fields_changed=["job_ref"]),
            ],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        assert classify(diff, contract_diff) == Severity.HIGH


# ---------------------------------------------------------------------------
# Determinism — REQ-LIN-F3-004 mandates the classifier is pure
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_same_input_yields_same_output(self):
        diff = LineageDiff(
            added=[_edge(edge_type="derivation")],
            removed=[], modified=[],
            downstream_field_dependencies={},
        )
        contract_diff = ContractDiff(
            removed_fields=[], added_fields=[], modified_fields=[],
        )
        first = classify(diff, contract_diff)
        second = classify(diff, contract_diff)
        third = classify(diff, contract_diff)
        assert first == second == third
