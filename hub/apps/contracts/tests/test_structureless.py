"""
Phase 227 Wave 0 — tests for the canonical "structureless" predicate
and the per-contract triage classifier.

A contract is "structureless" when its normalized HubContract carries no
structural payload (empty/missing `models[]` AND empty/missing
`schema.fields[]`). Wave 0 needs a single source of truth so both the
renormalize_contracts dry-run filter and the runbook triage logic match.

These tests intentionally avoid mocks: every case constructs real
hub_contract_json shapes that mirror what the normalizers produce on
staging, including the ODPS-outputports gap and the ODCS-no-schema gap
that motivate Phase 227.
"""

from hub.apps.contracts.structureless import (
    StructurelessClassification,
    classify_structureless_contract,
    is_structureless,
    structureless_filter_q,
)


class _StubContract:
    """Minimal stand-in for `hub.apps.contracts.models.Contract`.

    `is_structureless` only reads `hub_contract_json`; `classify_*` reads
    `original_spec_type` and `original_raw`. The stub keeps tests decoupled
    from migrations / DB while exercising the real predicate code paths
    end-to-end.
    """

    def __init__(self, hub_contract_json=None, original_spec_type="", original_raw=""):
        self.hub_contract_json = hub_contract_json
        self.original_spec_type = original_spec_type
        self.original_raw = original_raw


# ---------------------------------------------------------------------------
# is_structureless
# ---------------------------------------------------------------------------


def test_null_hub_contract_json_is_structureless():
    contract = _StubContract(hub_contract_json=None)
    assert is_structureless(contract) is True


def test_empty_hub_contract_json_is_structureless():
    contract = _StubContract(hub_contract_json={})
    assert is_structureless(contract) is True


def test_explicit_empty_models_and_schema_is_structureless():
    contract = _StubContract(hub_contract_json={"models": [], "schema": {"fields": []}})
    assert is_structureless(contract) is True


def test_models_with_one_entry_is_not_structureless():
    contract = _StubContract(
        hub_contract_json={
            "models": [{"name": "orders", "fields": [{"name": "id"}]}],
            "schema": {"fields": []},
        }
    )
    assert is_structureless(contract) is False


def test_schema_fields_alone_is_not_structureless():
    """Legacy ODCS path: structure may live under schema.fields[]."""
    contract = _StubContract(
        hub_contract_json={
            "models": [],
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }
    )
    assert is_structureless(contract) is False


def test_missing_schema_key_with_empty_models_is_structureless():
    contract = _StubContract(hub_contract_json={"models": []})
    assert is_structureless(contract) is True


def test_models_with_empty_fields_array_is_still_structureless():
    """A model entry with no fields contributes no structure."""
    contract = _StubContract(hub_contract_json={"models": [{"name": "orders", "fields": []}]})
    assert is_structureless(contract) is True


def test_schema_present_but_fields_null_is_structureless():
    contract = _StubContract(hub_contract_json={"models": [], "schema": {"fields": None}})
    assert is_structureless(contract) is True


def test_non_dict_hub_contract_json_is_structureless():
    """Defensive: malformed payload (string/list) treated as structureless."""
    assert is_structureless(_StubContract(hub_contract_json="garbage")) is True
    assert is_structureless(_StubContract(hub_contract_json=[1, 2, 3])) is True


# ---------------------------------------------------------------------------
# structureless_filter_q
# ---------------------------------------------------------------------------


def test_structureless_filter_q_returns_q_object():
    """The filter helper must return a Django Q so it composes with
    other filters in renormalize_contracts.
    """
    from django.db.models import Q

    q = structureless_filter_q()
    assert isinstance(q, Q)


# ---------------------------------------------------------------------------
# classify_structureless_contract
# ---------------------------------------------------------------------------


def test_odps_with_outputports_classifies_as_pure_odps_with_outputports():
    contract = _StubContract(
        original_spec_type="ODPS",
        original_raw=(
            "apiVersion: dataproduct.open-data-product-initiative.org/v1\n"
            "kind: DataProduct\n"
            "spec:\n"
            "  outputPorts:\n"
            "    - name: orders\n"
            "      contract:\n"
            "        spec:\n"
            "          schema:\n"
            "            fields:\n"
            "              - name: id\n"
        ),
        hub_contract_json={"models": []},
    )
    classification = classify_structureless_contract(contract)
    assert classification == StructurelessClassification.PURE_ODPS_WITH_OUTPUTPORTS


def test_odcs_without_schema_block_classifies_as_odcs_no_schema_block():
    contract = _StubContract(
        original_spec_type="ODCS",
        original_raw=(
            "apiVersion: 3.0.0\n"
            "kind: DataContract\n"
            "name: orders\n"
            "description: Top-level only, no schema:\n"
        ),
        hub_contract_json={"models": []},
    )
    classification = classify_structureless_contract(contract)
    assert classification == StructurelessClassification.ODCS_NO_SCHEMA_BLOCK


def test_odcs_with_schema_block_but_empty_classifies_as_odcs_no_schema_block():
    """Schema header present but block is empty/lacks fields — same triage path."""
    contract = _StubContract(
        original_spec_type="ODCS",
        original_raw=("apiVersion: 3.0.0\nkind: DataContract\nschema: {}\n"),
        hub_contract_json={"models": []},
    )
    classification = classify_structureless_contract(contract)
    assert classification == StructurelessClassification.ODCS_NO_SCHEMA_BLOCK


def test_unknown_spec_type_classifies_as_other():
    contract = _StubContract(
        original_spec_type="LEGACY_CSV",
        original_raw="name,description\nfoo,bar\n",
        hub_contract_json=None,
    )
    classification = classify_structureless_contract(contract)
    assert classification == StructurelessClassification.OTHER


def test_odps_without_outputports_classifies_as_other():
    """ODPS with neither inputPorts nor outputPorts — needs investigation,
    not a Wave-3 self-heal candidate.
    """
    contract = _StubContract(
        original_spec_type="ODPS",
        original_raw="apiVersion: ...\nkind: DataProduct\nspec: {}\n",
        hub_contract_json={"models": []},
    )
    classification = classify_structureless_contract(contract)
    assert classification == StructurelessClassification.OTHER


def test_classification_is_serializable_by_value():
    """JSONL emission depends on `.value` being a stable string."""
    assert isinstance(StructurelessClassification.PURE_ODPS_WITH_OUTPUTPORTS.value, str)
    assert (
        StructurelessClassification.PURE_ODPS_WITH_OUTPUTPORTS.value == "pure_odps_with_outputports"
    )
    assert StructurelessClassification.ODCS_NO_SCHEMA_BLOCK.value == "odcs_no_schema_block"
    assert StructurelessClassification.OTHER.value == "other"
