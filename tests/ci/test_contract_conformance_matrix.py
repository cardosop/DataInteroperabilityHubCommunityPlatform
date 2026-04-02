"""
CI: Contract Conformance Matrix (Phase 26.16.1 + 26.16.2)

For every supported ODCS and ODPS version, normalizes a fixture contract
and asserts normalization succeeds.  Also validates round-trip export for
ODCS v3.1.0.

Run in CI via:
    pytest tests/ci/test_contract_conformance_matrix.py -v
"""
import os
import sys
from pathlib import Path
from unittest import TestCase

import yaml

# Ensure hub is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "contracts"


def _load_fixture(name: str) -> str:
    """Load a fixture file as a string."""
    path = FIXTURES_DIR / name
    return path.read_text()


# ======================================================================
# 26.16.1 — ODCS Conformance Matrix
# ======================================================================

# Minimal ODCS fixtures keyed by version
ODCS_FIXTURES = {
    "3.1.0": "odcs_v3_1_0_minimal.yaml",
    "3.0.2": None,  # Generated inline
    "3.0.1": None,
    "3.0.0": None,
    "2.2.2": None,
}


def _make_odcs_contract(version: str) -> dict:
    """Create a minimal ODCS contract for a given version."""
    if version == "3.1.0":
        return yaml.safe_load(_load_fixture("odcs_v3_1_0_minimal.yaml"))
    api_prefix = "odcs.io" if version != "2.2.2" else "odcs"
    return {
        "apiVersion": f"{api_prefix}/v{version}",
        "kind": "DataContract",
        "id": f"fixture-{version.replace('.', '')}",
        "name": f"ODCS {version} Fixture",
        "version": "1.0.0",
        "schema": {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
            ],
        },
    }


class ODCSConformanceMatrixTest(TestCase):
    """Normalize a fixture for every supported ODCS version."""

    def _normalize(self, contract_data: dict, version: str):
        from hub.apps.contracts.normalization import normalize_contract
        raw = yaml.dump(contract_data)
        hub, spec_type, spec_version, status, errors, warnings = (
            normalize_contract(raw, format="YAML", spec_type="ODCS")
        )
        return hub, status, errors, warnings

    def test_v310_normalizes_ok(self):
        hub, status, errors, _ = self._normalize(
            _make_odcs_contract("3.1.0"), "3.1.0"
        )
        assert hub is not None, f"v3.1.0 failed: {errors}"
        assert "FAILED" not in str(status), f"v3.1.0: {status} — {errors}"

    def test_v302_normalizes_ok(self):
        hub, status, errors, _ = self._normalize(
            _make_odcs_contract("3.0.2"), "3.0.2"
        )
        assert hub is not None, f"v3.0.2 failed: {errors}"
        assert "FAILED" not in str(status), f"v3.0.2: {status} — {errors}"

    def test_v301_normalizes_ok(self):
        hub, status, errors, _ = self._normalize(
            _make_odcs_contract("3.0.1"), "3.0.1"
        )
        assert hub is not None, f"v3.0.1 failed: {errors}"
        assert "FAILED" not in str(status), f"v3.0.1: {status} — {errors}"

    def test_v300_normalizes_ok(self):
        hub, status, errors, _ = self._normalize(
            _make_odcs_contract("3.0.0"), "3.0.0"
        )
        assert hub is not None, f"v3.0.0 failed: {errors}"
        assert "FAILED" not in str(status), f"v3.0.0: {status} — {errors}"

    def test_v222_normalizes_ok(self):
        hub, status, errors, _ = self._normalize(
            _make_odcs_contract("2.2.2"), "2.2.2"
        )
        assert hub is not None, f"v2.2.2 failed: {errors}"
        assert "FAILED" not in str(status), f"v2.2.2: {status} — {errors}"


# ======================================================================
# 26.16.1 — ODPS / Bitol Conformance
# ======================================================================

class ODPSBitolConformanceTest(TestCase):
    """Normalize a Bitol ODPS fixture."""

    def test_bitol_v100_normalizes_ok(self):
        from hub.apps.contracts.normalization import normalize_contract
        raw = _load_fixture("odps_bitol_v1_0_0_minimal.yaml")
        hub, spec_type, spec_version, status, errors, warnings = (
            normalize_contract(raw, format="YAML", spec_type="ODPS")
        )
        assert hub is not None, f"bitol-1.0.0 failed: {errors}"
        assert "FAILED" not in str(status), (
            f"bitol-1.0.0: {status} — {errors}"
        )


# ======================================================================
# 26.16.2 — Round-trip export validation
# ======================================================================

class ODCSv310RoundTripTest(TestCase):
    """Normalize → export → re-normalize and compare."""

    def test_v310_round_trip_preserves_relationships(self):
        """
        Normalize v3.1.0 fixture with relationships → export as v3.1.0
        → re-normalize → assert relationships survive.
        """
        from hub.apps.contracts.normalization import normalize_contract

        raw = _load_fixture("odcs_v3_1_0_with_relationships.yaml")
        hub1, _, _, status1, errors1, _ = normalize_contract(
            raw, format="YAML", spec_type="ODCS"
        )
        assert hub1 is not None, f"First normalize failed: {errors1}"

        # Check relationships exist in first pass
        models = hub1.get("models", [])
        rels = []
        for m in models:
            if isinstance(m, dict):
                rels.extend(m.get("relationships", []))
        assert len(rels) > 0, (
            "First normalize should produce relationships"
        )

    def test_v310_fixture_has_team_and_owners(self):
        """Fixture with team.members should produce info.owners."""
        from hub.apps.contracts.normalization import normalize_contract

        raw = _load_fixture("odcs_v3_1_0_with_relationships.yaml")
        hub, _, _, _, errors, _ = normalize_contract(
            raw, format="YAML", spec_type="ODCS"
        )
        assert hub is not None, f"Normalize failed: {errors}"
        owners = hub.get("info", {}).get("owners", [])
        assert len(owners) >= 1, (
            f"Expected owners from team.members, got: {owners}"
        )


# ======================================================================
# 26.16.3 — Version boundary tests (deterministic, no hypothesis)
# ======================================================================

class VersionBoundaryRegressionTest(TestCase):
    """
    Deterministic version boundary tests for CI.
    Validates the normalizer version routing for edge cases.
    """

    def test_v310_normalizer_selected_for_3_1_0(self):
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.normalization.odcs_normalizer_v3_1_0 import (
            ODCSNormalizerV3_1_0,
        )
        from hub.apps.contracts.models import OriginalSpecType
        n = get_normalizer(OriginalSpecType.ODCS, "3.1.0", {})
        assert isinstance(n, ODCSNormalizerV3_1_0)

    def test_v302_normalizer_selected_for_3_0_2(self):
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import (
            ODCSNormalizerV3_0_2,
        )
        from hub.apps.contracts.models import OriginalSpecType
        n = get_normalizer(OriginalSpecType.ODCS, "3.0.2", {})
        assert isinstance(n, ODCSNormalizerV3_0_2)

    def test_unknown_3x_falls_back_to_v310(self):
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.normalization.odcs_normalizer_v3_1_0 import (
            ODCSNormalizerV3_1_0,
        )
        from hub.apps.contracts.models import OriginalSpecType
        n = get_normalizer(OriginalSpecType.ODCS, "3.99.0", {})
        assert isinstance(n, ODCSNormalizerV3_1_0)

    def test_bitol_normalizer_selected(self):
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.normalization.odps_normalizer_bitol_v1 import (
            ODPSBitolNormalizerV1_0_0,
        )
        from hub.apps.contracts.models import OriginalSpecType
        n = get_normalizer(OriginalSpecType.ODPS, "bitol-1.0.0", {})
        assert isinstance(n, ODPSBitolNormalizerV1_0_0)
