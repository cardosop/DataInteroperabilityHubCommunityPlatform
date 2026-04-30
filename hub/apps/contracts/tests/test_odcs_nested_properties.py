"""
Phase 227 Wave 1 (227.L2.*) — recursive nested-properties walker for ODCS.

Why this test file exists
-------------------------
ODCS allows arbitrarily nested ``object``/``array`` field types via either
``properties`` (JSON-Schema-style dict, post-v3.0.x) or ``fields``
(ODCS-style list, ≤v3.0.x), and the canonical contract pipeline must
descend into them so the resulting ``hub_contract.models[*].fields[*]``
mirrors the nesting. Pre-Wave-1, ``_map_fields`` only iterated the
top-level field list and dropped every level deeper — every nested
schema collapsed to a flat record, losing customer.address.street etc.

This test file pins the recursive walker's behaviour:

* 3-level nested object — ``customer.address.street`` survives.
* Array of objects — ``orders[].items[].sku`` survives via ``items``.
* Depth bound — depth 19/20 succeed; depth 21 raises
  ``ValidationError(code="SCHEMA_TOO_DEEP")`` BEFORE Python's own
  recursion-limit kicks in (1000).
* ``properties`` vs ``fields`` keyword equivalence — both accepted,
  identical normalised output.
* Per-version coverage — every ODCS normaliser inherits the walker.
* Property-based: random nested schemas of depth ≤MAX always normalise
  cleanly. Hypothesis is used when available; the test gracefully
  skips when the dev-only dep is missing in the test container.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _odcs_field(
    name: str,
    type_: str = "string",
    **extras: Any,
) -> Dict[str, Any]:
    """Build an ODCS-shaped field dict (uses ``type``, not ``data_type``)."""
    out: Dict[str, Any] = {"name": name, "type": type_}
    out.update(extras)
    return out


def _build_chain_via_properties(depth: int) -> Dict[str, Any]:
    """Return an ODCS schema dict with one chain of nested ``object``s
    of *exactly* the given depth, using JSON-Schema-style ``properties``.

    depth=0 → flat scalar field.
    depth=N → root.l1.l2…lN where lN is a string ``leaf``.
    """
    leaf: Dict[str, Any] = {"name": "leaf", "type": "string"}
    current = leaf
    for level in range(depth, 0, -1):
        current = {
            "name": f"l{level}",
            "type": "object",
            "properties": {current["name"]: {"type": current["type"], **{
                k: v for k, v in current.items() if k not in ("name", "type")
            }}},
        }
    return {"fields": [current]}


def _build_chain_via_fields(depth: int) -> Dict[str, Any]:
    """Same as ``_build_chain_via_properties`` but uses ODCS-style ``fields``
    (list of named entries) for the nested objects — mirrors ≤v3.0.x.
    """
    leaf: Dict[str, Any] = {"name": "leaf", "type": "string"}
    current = leaf
    for level in range(depth, 0, -1):
        current = {
            "name": f"l{level}",
            "type": "object",
            "fields": [current],
        }
    return {"fields": [current]}


def _walk_first_chain(field_list: List[Dict[str, Any]]) -> List[str]:
    """Walk a chain of nested fields (taking the first nested entry at
    each level) and return the list of names from root to leaf."""
    names: List[str] = []
    cursor: List[Dict[str, Any]] | None = field_list
    while cursor:
        f = cursor[0]
        names.append(f["name"])
        nested = f.get("fields") or (
            [f["items"]] if isinstance(f.get("items"), dict) else None
        )
        cursor = nested if isinstance(nested, list) and nested else None
    return names


# ---------------------------------------------------------------------------
# Direct unit tests for ``_map_fields`` (Phase 227 L2.1)
# ---------------------------------------------------------------------------


class TestThreeLevelNestedObject:
    """``customer.address.street`` survives normalisation."""

    def _normalize(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        from hub.apps.contracts.normalization_engine import _map_fields
        return _map_fields(schema, [], [], [])

    def test_three_level_object_chain_via_properties(self):
        schema = {
            "fields": [
                {
                    "name": "customer",
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "object",
                            "properties": {
                                "street": {"type": "string"},
                                "zip": {"type": "string"},
                            },
                        },
                        "name": {"type": "string"},
                    },
                },
                {"name": "id", "type": "string"},
            ]
        }
        fields = self._normalize(schema)
        assert [f["name"] for f in fields] == ["customer", "id"]
        customer = fields[0]
        assert customer["data_type"] == "object"
        assert "fields" in customer, customer
        sub_names = sorted(f["name"] for f in customer["fields"])
        assert sub_names == ["address", "name"]
        address = next(f for f in customer["fields"] if f["name"] == "address")
        assert address["data_type"] == "object"
        leaf_names = sorted(f["name"] for f in address["fields"])
        assert leaf_names == ["street", "zip"]
        street = next(f for f in address["fields"] if f["name"] == "street")
        assert street["data_type"] == "string"

    def test_three_level_object_chain_via_fields_keyword(self):
        """ODCS ≤v3.0.x uses ``fields`` (list) for nested objects."""
        schema = {
            "fields": [
                {
                    "name": "customer",
                    "type": "object",
                    "fields": [
                        {
                            "name": "address",
                            "type": "object",
                            "fields": [
                                {"name": "street", "type": "string"},
                            ],
                        }
                    ],
                }
            ]
        }
        fields = self._normalize(schema)
        # Walk the chain: customer → address → street.
        assert _walk_first_chain(fields) == ["customer", "address", "street"]


class TestArrayOfObjects:
    """``orders[].items[].sku`` survives normalisation via ``items``."""

    def _normalize(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        from hub.apps.contracts.normalization_engine import _map_fields
        return _map_fields(schema, [], [], [])

    def test_array_of_array_of_objects(self):
        schema = {
            "fields": [
                {
                    "name": "orders",
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "sku": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                }
            ]
        }
        fields = self._normalize(schema)
        orders = fields[0]
        assert orders["data_type"] == "array"
        assert "items" in orders
        order_item = orders["items"]
        assert order_item["data_type"] == "object"
        line_items = next(f for f in order_item["fields"] if f["name"] == "items")
        assert line_items["data_type"] == "array"
        sku_holder = line_items["items"]
        assert sku_holder["data_type"] == "object"
        sku = next(f for f in sku_holder["fields"] if f["name"] == "sku")
        assert sku["data_type"] == "string"


# ---------------------------------------------------------------------------
# Depth-bound enforcement (Phase 227 L2.1, L2.3)
# ---------------------------------------------------------------------------


class TestDepthBoundary:
    """The walker respects ``CONTRACTS_MAX_NESTING_DEPTH`` and raises
    ``ValidationError(code="SCHEMA_TOO_DEEP")`` instead of letting Python's
    1000-level recursion limit fire (which would corrupt the request).
    """

    def _normalize(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        from hub.apps.contracts.normalization_engine import _map_fields
        return _map_fields(schema, [], [], [])

    def test_depth_19_succeeds(self):
        schema = _build_chain_via_properties(depth=19)
        fields = self._normalize(schema)
        # 19 nested objects + 1 leaf scalar = chain of 20 names.
        chain = _walk_first_chain(fields)
        assert len(chain) == 20

    def test_depth_20_at_limit_succeeds(self):
        """Boundary case: max depth is INCLUSIVE — depth 20 normalises."""
        schema = _build_chain_via_properties(depth=20)
        fields = self._normalize(schema)
        chain = _walk_first_chain(fields)
        assert len(chain) == 21

    def test_depth_21_raises_schema_too_deep(self):
        """Beyond MAX_NESTING_DEPTH → ValidationError code='SCHEMA_TOO_DEEP'."""
        from django.core.exceptions import ValidationError
        schema = _build_chain_via_properties(depth=21)
        with pytest.raises(ValidationError) as exc:
            self._normalize(schema)
        assert exc.value.code == "SCHEMA_TOO_DEEP", (
            f"Expected code=SCHEMA_TOO_DEEP; got code={exc.value.code!r}"
        )

    def test_depth_overrun_message_includes_path(self):
        """The error message should include the path that overran so ops
        can locate the offending field in a 100-field contract."""
        from django.core.exceptions import ValidationError
        schema = _build_chain_via_properties(depth=25)
        with pytest.raises(ValidationError) as exc:
            self._normalize(schema)
        msg = str(exc.value)
        # The chain root is "l1"; somewhere down the chain the walker
        # records the path.
        assert "l1" in msg, (
            f"Error message should reference the offending path; got {msg!r}"
        )

    def test_depth_check_fires_before_python_recursion_limit(self):
        """A schema deep enough to trigger Python's RecursionError (1000+)
        must surface as our typed error, NOT a raw RecursionError. This
        protects API surfaces from 500-ing on malicious inputs."""
        from django.core.exceptions import ValidationError
        # Build a depth-200 schema — well beyond 20 but still under
        # Python's limit. Must raise OUR typed error, not RecursionError.
        schema = _build_chain_via_properties(depth=200)
        with pytest.raises(ValidationError):
            self._normalize(schema)


# ---------------------------------------------------------------------------
# `properties` ↔ `fields` keyword equivalence (Phase 227 L2.5)
# ---------------------------------------------------------------------------


class TestPropertiesFieldsEquivalence:
    """Both ``properties`` (dict) and ``fields`` (list) shapes for nested
    objects MUST produce identical normalised output. This protects
    customers who mix ODCS spec generations within the same payload."""

    def _normalize(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        from hub.apps.contracts.normalization_engine import _map_fields
        return _map_fields(schema, [], [], [])

    @staticmethod
    def _strip_volatile(field: Dict[str, Any]) -> Dict[str, Any]:
        """Remove keys that may legitimately differ between paths (e.g.,
        ordering of dict-derived properties); compare the structural skeleton.
        """
        return {
            "name": field["name"],
            "data_type": field.get("data_type"),
            "fields": [
                TestPropertiesFieldsEquivalence._strip_volatile(f)
                for f in field.get("fields", [])
            ] if field.get("fields") else None,
        }

    def test_two_level_object_via_properties_matches_via_fields(self):
        a = self._normalize(_build_chain_via_properties(depth=2))
        b = self._normalize(_build_chain_via_fields(depth=2))
        # Compare structural skeleton — names + data_types + nesting shape.
        assert self._strip_volatile(a[0]) == self._strip_volatile(b[0]), (
            f"properties path produced {a!r} but fields path produced {b!r}"
        )

    def test_six_level_object_via_properties_matches_via_fields(self):
        a = self._normalize(_build_chain_via_properties(depth=6))
        b = self._normalize(_build_chain_via_fields(depth=6))
        assert self._strip_volatile(a[0]) == self._strip_volatile(b[0])


# ---------------------------------------------------------------------------
# Per-ODCS-version end-to-end coverage (Phase 227 L2.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version_module,version_class,spec_version,api_version",
    [
        (
            "hub.apps.contracts.normalization.odcs_normalizer_v2_2_2",
            "ODCSNormalizerV2_2_2",
            "2.2.2",
            "2.2.2",
        ),
        (
            "hub.apps.contracts.normalization.odcs_normalizer_v3_0_0",
            "ODCSNormalizerV3_0_0",
            "3.0.0",
            "v3.0.0",
        ),
        (
            "hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview",
            "ODCSNormalizerV3_0_0_Preview",
            "3.0.0-preview",
            "v3.0.0",
        ),
        (
            "hub.apps.contracts.normalization.odcs_normalizer_v3_0_1",
            "ODCSNormalizerV3_0_1",
            "3.0.1",
            "v3.0.1",
        ),
        (
            "hub.apps.contracts.normalization.odcs_normalizer_v3_0_2",
            "ODCSNormalizerV3_0_2",
            "3.0.2",
            "v3.0.2",
        ),
        (
            "hub.apps.contracts.normalization.odcs_normalizer_v3_1_0",
            "ODCSNormalizerV3_1_0",
            "3.1.0",
            "v3.1.0",
        ),
    ],
)
def test_each_odcs_version_walks_nested_properties(
    version_module: str,
    version_class: str,
    spec_version: str,
    api_version: str,
):
    """Every ODCS normaliser inherits the recursive walker via the base.

    A 2-level ``customer.address.street`` schema MUST round-trip through
    the full ``normalize()`` pipeline of every supported version.
    """
    import importlib
    module = importlib.import_module(version_module)
    normalizer_cls = getattr(module, version_class)
    normalizer = normalizer_cls()

    contract_data = {
        "kind": "DataContract",
        "apiVersion": api_version,
        "id": "nested-test",
        "name": "Nested test",
        "version": "1.0.0",
        "status": "active",
        "schema": [
            {
                "name": "customers",
                "fields": [
                    {
                        "name": "customer",
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "object",
                                "properties": {
                                    "street": {"type": "string"},
                                },
                            }
                        },
                    },
                ],
            }
        ],
    }
    result = normalizer.normalize(contract_data, spec_version=spec_version)
    assert result.hub_contract is not None, (
        f"{version_class} normalisation failed: errors={result.errors}"
    )
    # The engine round-trips the canonical dict through Pydantic with
    # ``by_alias=True``, so the emitted key is ``type`` (the alias),
    # NOT ``data_type``. Helper picks whichever is present.
    def _type(f: Dict[str, Any]) -> Any:
        return f.get("data_type") or f.get("type")

    models = result.hub_contract.get("models") or []
    assert models, f"{version_class}: no models[] emitted"
    fields = models[0]["fields"]
    customer = next((f for f in fields if f["name"] == "customer"), None)
    assert customer is not None, f"{version_class}: customer field missing"
    assert _type(customer) == "object"
    assert "fields" in customer, (
        f"{version_class}: nested customer.fields missing"
    )
    address = next(
        (f for f in customer["fields"] if f["name"] == "address"), None,
    )
    assert address is not None, (
        f"{version_class}: customer.address missing — recursion didn't fire"
    )
    street = next(
        (f for f in address["fields"] if f["name"] == "street"), None,
    )
    assert street is not None, (
        f"{version_class}: customer.address.street missing — "
        f"3rd-level recursion didn't fire"
    )
    assert _type(street) == "string"


# ---------------------------------------------------------------------------
# HubContractField Pydantic model (Phase 227 L2.2)
# ---------------------------------------------------------------------------


class TestHubContractFieldRecursive:
    """``HubContractField`` accepts ``fields[]`` and ``items`` as
    self-referential Optional members; an ``object``-typed field with no
    ``fields`` raises ValidationError — the floor invariant we ship
    Wave 1 to enforce."""

    def test_object_with_nested_fields_validates(self):
        from hub.apps.contracts.typed_models import HubContractField
        f = HubContractField(
            name="customer",
            data_type="object",
            fields=[
                HubContractField(name="email", data_type="string"),
            ],
        )
        assert f.fields is not None
        assert f.fields[0].name == "email"

    def test_array_with_items_validates(self):
        from hub.apps.contracts.typed_models import HubContractField
        f = HubContractField(
            name="tags",
            data_type="array",
            items=HubContractField(name="item", data_type="string"),
        )
        assert f.items is not None
        assert f.items.data_type == "string"

    def test_object_without_fields_rejected(self):
        """An ``object``-typed field with no ``fields[]`` is structurally
        empty — exactly the structureless population Wave 0 detected.
        Pydantic-level rejection makes this fail-fast at the API edge."""
        from hub.apps.contracts.typed_models import HubContractField
        from pydantic import ValidationError as PydanticValidationError
        with pytest.raises(PydanticValidationError):
            HubContractField(name="customer", data_type="object")

    def test_object_with_empty_fields_list_rejected(self):
        from hub.apps.contracts.typed_models import HubContractField
        from pydantic import ValidationError as PydanticValidationError
        with pytest.raises(PydanticValidationError):
            HubContractField(name="customer", data_type="object", fields=[])


# ---------------------------------------------------------------------------
# Hypothesis property-based test (Phase 227 L2.6)
# ---------------------------------------------------------------------------
#
# Hypothesis is a dev-only dependency (added to requirements-dev.txt). When
# the test container hasn't been rebuilt with the new dep, we skip ONLY
# this property test rather than the entire module — the rest of the file
# (unit + per-version coverage) must still run.
# ---------------------------------------------------------------------------

try:
    import hypothesis  # noqa: F401
    from hypothesis import given, settings as hyp_settings, strategies as st
    _HYPOTHESIS_AVAILABLE = True
except ImportError:
    _HYPOTHESIS_AVAILABLE = False


@pytest.mark.skipif(
    not _HYPOTHESIS_AVAILABLE,
    reason="hypothesis dev-dep not installed in this environment",
)
def test_random_nested_schema_under_limit_normalizes():
    """Property: any ODCS-shaped field with depth ≤ MAX normalises
    cleanly (no ValidationError, no RecursionError) and the canonical
    result preserves the field's name + data_type at the root.

    Width is intentionally kept low (≤3 children per level) so the test
    completes in seconds even at the chosen max_examples; what we care
    about is the walker's correctness, not throughput.
    """
    from hub.apps.contracts.normalization_engine import _map_fields

    name_st = st.from_regex(r"^[a-z][a-z0-9_]{0,8}$", fullmatch=True)
    scalar_field_st = st.builds(
        lambda n, t: {"name": n, "type": t},
        name_st,
        st.sampled_from(["string", "integer", "number", "boolean", "date"]),
    )

    def extend(children_st):
        object_st = st.builds(
            lambda n, kids: {"name": n, "type": "object", "fields": kids},
            name_st,
            st.lists(
                children_st, min_size=1, max_size=3,
                unique_by=lambda f: f["name"],
            ),
        )
        array_st = st.builds(
            lambda n, item: {"name": n, "type": "array", "items": item},
            name_st,
            children_st,
        )
        return st.one_of(scalar_field_st, object_st, array_st)

    field_st = st.recursive(scalar_field_st, extend, max_leaves=20)

    @hyp_settings(max_examples=50, deadline=2_000)
    @given(field=field_st)
    def _check(field):
        out = _map_fields({"fields": [field]}, [], [], [])
        assert isinstance(out, list)
        assert len(out) == 1
        assert out[0]["name"] == field["name"]
        # ODCS ``type`` is renamed to ``data_type`` in the canonical shape.
        assert out[0]["data_type"] == field["type"]

    _check()
