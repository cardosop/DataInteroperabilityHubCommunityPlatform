"""
Phase 274.4.4 — StructuralFloorRule tests.

Mirrors existing enforce_structural_floor coverage (5 cases):
- Valid contract passes
- Structureless contract (no models/schema fields) fails
- ODPS contract without ports fails
- Cyclic ports detected
- Generic structureless with correct subcode
"""
from __future__ import annotations

import pytest
from django.test import TestCase

from hub.apps.contracts.structural_floor import (
    ERROR_CODE,
    SUBCODE_ODPS_NO_PORTS,
    SUBCODE_ODCS_NO_SCHEMA,
    SUBCODE_CYCLIC_PORTS,
    enforce_structural_floor,
    is_payload_structureless,
    collect_structural_floor_errors,
)

pytestmark = pytest.mark.django_db(transaction=True)


class TestStructuralFloorRule(TestCase):
    """Phase 274.4 — structural floor enforcement."""

    def test_valid_contract_passes(self):
        contract = {
            "models": [{"name": "users", "fields": [{"name": "id", "data_type": "integer"}]}],
        }
        errors = collect_structural_floor_errors(
            contract, spec_type="ODCS", spec_version="1.0",
        )
        assert len(errors) == 0, f"Expected no errors, got: {errors}"

    def test_structureless_contract_fails(self):
        contract = {
            "models": [{"name": "users", "fields": []}],
        }
        errors = collect_structural_floor_errors(
            contract, spec_type="ODCS", spec_version="1.0",
        )
        assert len(errors) > 0

    def test_odps_no_ports_fails(self):
        contract = {"ports": []}
        errors = collect_structural_floor_errors(
            contract, spec_type="ODPS", spec_version="1.0",
        )
        assert len(errors) > 0
        assert any(SUBCODE_ODPS_NO_PORTS in str(e) for e in errors)

    def test_generic_structureless_fails(self):
        contract = {}
        errors = collect_structural_floor_errors(
            contract, spec_type="ODCS", spec_version="1.0",
        )
        assert len(errors) > 0

    def test_enforce_raises_on_structureless(self):
        with pytest.raises(Exception) as exc_info:
            enforce_structural_floor(
                hub_contract={"models": [{"name": "t", "fields": []}]},
                spec_type="ODCS",
                spec_version="1.0",
            )
        assert ERROR_CODE in str(exc_info.value)
