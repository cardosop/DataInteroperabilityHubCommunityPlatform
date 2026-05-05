"""
Phase 250.2.B.1 — TDD tests for the SchemaCompareService.

Pins the contract from D250.12 (Gap 3 closeout):

* The diff is **deterministic** — given the same contract + dataset
  schema, the output is byte-identical (no dict iteration order
  dependence, no random ID drift). Two calls in series MUST return
  equal `SchemaDriftResult` instances.
* `missing_fields` lists fields the contract REQUIRES that the
  dataset doesn't have. These are structural failures — the dataset
  is missing data the contract promises.
* `extra_fields` lists fields the dataset has but the contract
  doesn't declare. These are NOT failures by themselves (the
  dataset may have richer columns than the contract surface);
  reported for visibility only.
* `type_mismatches` lists fields where the contract type and the
  dataset's inferred type disagree. May or may not be structural —
  see compatibility-rules tests below.
* `structural_incompatibility` is True iff there's at least one
  ``missing_fields`` entry OR at least one ``type_mismatch`` that
  isn't a "compatible widening" (e.g., contract says ``integer``,
  dataset says ``string`` → structural; contract says ``integer``,
  dataset says ``long`` → compatible widening, NOT structural).
* WARN status: only ``extra_fields`` populated.
* FAIL status: ``structural_incompatibility=True``.
* Performance: 100-field diff is sub-200ms p95.

Both schema shapes are accepted:

* HubContract format: ``{"schema": {"fields": [{"name": str, "type": str, ...}, ...]}}``
* Inferred (dataset) format: ``{"fields": [{"name": str, "data_type": str, ...}, ...]}``

The service normalises both to a canonical internal representation
before diffing so the algorithm is shape-agnostic.
"""
from __future__ import annotations

import pytest


pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Canonical fixtures — kept inline + small so tests stay readable.
# ---------------------------------------------------------------------------


def _contract_schema(*fields: dict) -> dict:
    """Build a HubContract schema with the given fields.

    Mirrors the wire shape produced by the ODCS normaliser:
    ``{"schema": {"fields": [{"name": "id", "type": "integer"}, ...]}}``.
    """
    return {"schema": {"fields": list(fields)}}


def _inferred_schema(*fields: dict) -> dict:
    """Build an inferred-from-data schema (the shape produced by
    :mod:`hub.apps.datasets.schema_inference`)."""
    return {"fields": list(fields)}


# ---------------------------------------------------------------------------
# 250.2.B.1 — SchemaDriftResult dataclass shape
# ---------------------------------------------------------------------------


class TestSchemaDriftResultShape:

    def test_imports_cleanly(self):
        from hub.apps.contracts.services.schema_compare import SchemaDriftResult  # noqa: F401

    def test_default_no_drift_result_is_clean(self):
        from hub.apps.contracts.services.schema_compare import SchemaDriftResult

        result = SchemaDriftResult(
            missing_fields=[],
            extra_fields=[],
            type_mismatches=[],
            structural_incompatibility=False,
        )
        assert result.detected is False  # Convenience property
        assert result.severity == "NONE"  # NONE | WARN | FAIL
        assert result.to_dict() == {
            "detected": False,
            "severity": "NONE",
            "missing_fields": [],
            "extra_fields": [],
            "type_mismatches": [],
            "structural_incompatibility": False,
        }

    def test_serialised_dict_is_deterministic(self):
        """Two equivalent SchemaDriftResults serialise to byte-identical
        JSON dicts so the workflow's state_data hash stays stable."""
        import json
        from hub.apps.contracts.services.schema_compare import SchemaDriftResult

        a = SchemaDriftResult(
            missing_fields=["x", "y"],
            extra_fields=["z"],
            type_mismatches=[],
            structural_incompatibility=True,
        )
        b = SchemaDriftResult(
            missing_fields=["x", "y"],
            extra_fields=["z"],
            type_mismatches=[],
            structural_incompatibility=True,
        )
        assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(
            b.to_dict(), sort_keys=True
        )


# ---------------------------------------------------------------------------
# 250.2.B.1 — diff algorithm
# ---------------------------------------------------------------------------


class TestSchemaCompare:
    """Behavioural pin for ``SchemaCompareService.compare(contract_schema,
    inferred_schema)``."""

    def _compare(self, contract: dict, inferred: dict):
        from hub.apps.contracts.services.schema_compare import SchemaCompareService

        return SchemaCompareService.compare(
            contract_schema=contract,
            inferred_schema=inferred,
        )

    # --- 1. Identical schemas: no drift, no severity ---

    def test_identical_schemas_no_drift(self):
        contract = _contract_schema(
            {"name": "id", "type": "integer"},
            {"name": "email", "type": "string"},
        )
        inferred = _inferred_schema(
            {"name": "id", "data_type": "integer"},
            {"name": "email", "data_type": "string"},
        )
        r = self._compare(contract, inferred)
        assert r.missing_fields == []
        assert r.extra_fields == []
        assert r.type_mismatches == []
        assert r.structural_incompatibility is False
        assert r.severity == "NONE"
        assert r.detected is False

    def test_field_name_matching_is_case_sensitive(self):
        """Contract says ``Email``, dataset says ``email`` → MISSING (the
        contract field is not present in the dataset). Case-folding would
        hide real schema bugs."""
        contract = _contract_schema(
            {"name": "Email", "type": "string"},
        )
        inferred = _inferred_schema(
            {"name": "email", "data_type": "string"},
        )
        r = self._compare(contract, inferred)
        assert "Email" in r.missing_fields
        assert "email" in r.extra_fields

    # --- 2. Missing fields → structural ---

    def test_missing_required_field_is_structural_fail(self):
        contract = _contract_schema(
            {"name": "id", "type": "integer"},
            {"name": "email", "type": "string"},
        )
        inferred = _inferred_schema(
            {"name": "id", "data_type": "integer"},
        )
        r = self._compare(contract, inferred)
        assert r.missing_fields == ["email"]
        assert r.structural_incompatibility is True
        assert r.severity == "FAIL"
        assert r.detected is True

    # --- 3. Extra fields only → WARN, NOT structural ---

    def test_extra_fields_only_is_warn_not_structural(self):
        """Phase 250.2.B.3 — extras alone NEVER trigger structural FAIL.

        The dataset may legitimately have richer columns than the
        contract surface (audit columns, internal IDs); only structural
        incompatibility blocks intake."""
        contract = _contract_schema(
            {"name": "id", "type": "integer"},
        )
        inferred = _inferred_schema(
            {"name": "id", "data_type": "integer"},
            {"name": "internal_audit_ts", "data_type": "timestamp"},
        )
        r = self._compare(contract, inferred)
        assert r.extra_fields == ["internal_audit_ts"]
        assert r.missing_fields == []
        assert r.type_mismatches == []
        assert r.structural_incompatibility is False
        assert r.severity == "WARN"
        assert r.detected is True

    # --- 4. Type mismatch — structural vs compatible widening ---

    def test_incompatible_type_mismatch_is_structural(self):
        """Contract says ``integer``, dataset says ``string`` — these are
        not interchangeable; mark as structural."""
        contract = _contract_schema({"name": "id", "type": "integer"})
        inferred = _inferred_schema({"name": "id", "data_type": "string"})
        r = self._compare(contract, inferred)
        assert len(r.type_mismatches) == 1
        m = r.type_mismatches[0]
        assert m["field"] == "id"
        assert m["contract_type"] == "integer"
        assert m["dataset_type"] == "string"
        assert m["compatible"] is False
        assert r.structural_incompatibility is True
        assert r.severity == "FAIL"

    def test_compatible_widening_integer_to_long_is_warn_not_fail(self):
        """Contract says ``integer``, dataset says ``long`` — long can
        hold any integer value, so the widening is safe (the dataset is
        more permissive than the contract requires)."""
        contract = _contract_schema({"name": "id", "type": "integer"})
        inferred = _inferred_schema({"name": "id", "data_type": "long"})
        r = self._compare(contract, inferred)
        assert len(r.type_mismatches) == 1
        m = r.type_mismatches[0]
        assert m["compatible"] is True
        assert r.structural_incompatibility is False
        assert r.severity == "WARN"

    def test_compatible_widening_float_to_double_is_warn_not_fail(self):
        contract = _contract_schema({"name": "value", "type": "float"})
        inferred = _inferred_schema({"name": "value", "data_type": "double"})
        r = self._compare(contract, inferred)
        assert r.type_mismatches[0]["compatible"] is True
        assert r.structural_incompatibility is False

    def test_type_aliases_treated_as_equal(self):
        """ODCS uses ``string``; pandas-inferred uses ``str``; both should
        be considered the same type — no mismatch."""
        contract = _contract_schema({"name": "name", "type": "string"})
        inferred = _inferred_schema({"name": "name", "data_type": "str"})
        r = self._compare(contract, inferred)
        assert r.type_mismatches == []
        assert r.structural_incompatibility is False
        assert r.severity == "NONE"

    def test_unknown_dataset_type_treated_as_mismatch(self):
        """Unrecognised types fall back to string-equality checks; if
        they don't match the contract type, surface as a non-compatible
        mismatch so ops can investigate."""
        contract = _contract_schema({"name": "x", "type": "integer"})
        inferred = _inferred_schema({"name": "x", "data_type": "weird-custom"})
        r = self._compare(contract, inferred)
        assert len(r.type_mismatches) == 1
        assert r.type_mismatches[0]["compatible"] is False

    # --- 5. Determinism: ordering must be stable ---

    def test_diff_is_deterministic_under_dict_order_changes(self):
        """Inputs with shuffled dict insertion order MUST produce
        equal SchemaDriftResults. Critical for cache-key stability and
        for test assertions on the wire format."""
        contract_a = _contract_schema(
            {"name": "id", "type": "integer"},
            {"name": "email", "type": "string"},
            {"name": "name", "type": "string"},
        )
        contract_b = _contract_schema(
            {"name": "name", "type": "string"},
            {"name": "id", "type": "integer"},
            {"name": "email", "type": "string"},
        )
        inferred = _inferred_schema(
            {"name": "id", "data_type": "integer"},
            {"name": "email", "data_type": "string"},
            # `name` missing from dataset → triggers MISSING in both runs
        )

        ra = self._compare(contract_a, inferred)
        rb = self._compare(contract_b, inferred)
        # Same logical inputs → identical output regardless of field
        # ordering in the contract.
        assert ra.to_dict() == rb.to_dict()
        # The MISSING list MUST be sorted lexicographically so a
        # field-rename in the contract doesn't reorder the wire output.
        assert ra.missing_fields == sorted(ra.missing_fields)

    # --- 6. Edge cases ---

    def test_empty_contract_means_all_dataset_fields_are_extra(self):
        contract = _contract_schema()
        inferred = _inferred_schema(
            {"name": "id", "data_type": "integer"},
            {"name": "email", "data_type": "string"},
        )
        r = self._compare(contract, inferred)
        assert sorted(r.extra_fields) == ["email", "id"]
        assert r.missing_fields == []
        assert r.severity == "WARN"

    def test_empty_dataset_means_all_contract_fields_are_missing(self):
        contract = _contract_schema(
            {"name": "id", "type": "integer"},
            {"name": "email", "type": "string"},
        )
        inferred = _inferred_schema()
        r = self._compare(contract, inferred)
        assert sorted(r.missing_fields) == ["email", "id"]
        assert r.severity == "FAIL"

    def test_handles_missing_schema_key_gracefully(self):
        """If the contract is malformed (no top-level ``schema`` key),
        the comparator MUST NOT crash; it returns an empty contract
        view (everything in the dataset becomes ``extra``)."""
        contract = {}
        inferred = _inferred_schema({"name": "id", "data_type": "integer"})
        r = self._compare(contract, inferred)
        assert r.extra_fields == ["id"]
        assert r.missing_fields == []

    def test_handles_missing_fields_key_gracefully(self):
        """Same as above for inferred schema with no ``fields`` key."""
        contract = _contract_schema({"name": "id", "type": "integer"})
        inferred = {}
        r = self._compare(contract, inferred)
        assert r.missing_fields == ["id"]


# ---------------------------------------------------------------------------
# 250.2.B.7 — performance contract
# ---------------------------------------------------------------------------


class TestPerformance:
    """``SchemaCompareService.compare`` p95 ≤ 200 ms on 100-field contracts.

    This is a soft pin: we measure the median of 50 runs (100x lower
    than the spec budget) so flaky CI runners don't false-fail. The
    real load test for the wire endpoint lives in the staging
    locust suite.
    """

    def test_100_field_diff_under_perf_budget(self):
        import time

        from hub.apps.contracts.services.schema_compare import SchemaCompareService

        contract = _contract_schema(
            *[
                {"name": f"col_{i}", "type": "string"}
                for i in range(100)
            ]
        )
        # Half the fields renamed → forces a real diff (not a no-op).
        inferred = _inferred_schema(
            *[
                {"name": f"col_{i}", "data_type": "string"}
                for i in range(50)
            ],
            *[
                {"name": f"renamed_{i}", "data_type": "string"}
                for i in range(50)
            ],
        )

        runs = []
        for _ in range(50):
            t0 = time.perf_counter()
            SchemaCompareService.compare(
                contract_schema=contract,
                inferred_schema=inferred,
            )
            runs.append(time.perf_counter() - t0)
        median_ms = sorted(runs)[len(runs) // 2] * 1000
        # Comfortable margin under the 200 ms budget — the algorithm is
        # O(n) with two dict lookups per field, so 100-field diffs
        # should take << 1 ms in practice.
        assert median_ms < 50, (
            f"100-field diff median {median_ms:.2f} ms exceeds the "
            f"50 ms soft budget (spec budget is 200 ms p95)"
        )
