"""
Tests for ODPS Bitol v1.0.0 normalizer and detection.

Covers:
- 26.3.1: Bitol ODPS version detection (schema URL, kind+apiVersion)
- 26.3.2: SUPPORTED_ODPS_VERSIONS / SUPPORTED_ODCS_VERSIONS constants
- 26.3.3: ODPSBitolNormalizerV1_0_0 normalizer (team, ports, registration)
- 26.3.4: ODCS v3.1.0 accepted as ODPS→ODCS link target
"""
from unittest import TestCase

from hub.apps.contracts.models import OriginalSpecType
from hub.apps.contracts.odps_version_detection import (
    detect_odps_version,
    _detect_bitol_odps_version,
)
from hub.apps.contracts.spec_detection import (
    detect_spec_type,
    is_odps_contract,
)
from hub.apps.contracts.business_rules import (
    SUPPORTED_ODPS_VERSIONS,
    SUPPORTED_ODCS_VERSIONS,
)
from hub.apps.contracts.normalization.odps_normalizer_bitol_v1 import (
    ODPSBitolNormalizerV1_0_0,
)


# ======================================================================
# Fixtures
# ======================================================================

def _bitol_v1_contract(**overrides):
    """Minimal valid Bitol ODPS v1.0.0 contract."""
    c = {
        "schema": (
            "https://bitol-io.github.io/"
            "open-data-product-standard/v1.0.0/schema.json"
        ),
        "kind": "DataProduct",
        "apiVersion": "v1.0.0",
        "product": {
            "details": {
                "en": {
                    "productID": "dp-bitol-001",
                    "name": "Bitol Test Product",
                }
            },
        },
    }
    c.update(overrides)
    return c


def _bitol_v09_contract(**overrides):
    """Minimal valid Bitol ODPS v0.9.0 contract."""
    c = {
        "schema": (
            "https://bitol-io.github.io/"
            "open-data-product-standard/v0.9.0/schema.json"
        ),
        "kind": "DataProduct",
        "apiVersion": "v0.9.0",
        "product": {
            "details": {
                "en": {
                    "productID": "dp-bitol-09",
                    "name": "Bitol 0.9 Product",
                }
            },
        },
    }
    c.update(overrides)
    return c


def _pre_bitol_v41_contract():
    """Pre-Bitol ODPS v4.1 contract."""
    return {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "product": {
            "details": {
                "en": {
                    "productID": "dp-41",
                    "name": "Pre-Bitol 4.1 Product",
                }
            },
        },
    }


# ======================================================================
# 26.3.1 — Bitol detection
# ======================================================================

class BitolVersionDetectionTest(TestCase):
    """Test _detect_bitol_odps_version and detect_odps_version."""

    def test_bitol_v1_schema_url(self):
        result = detect_odps_version(_bitol_v1_contract())
        assert result == "bitol-1.0.0"

    def test_bitol_v09_schema_url(self):
        result = detect_odps_version(_bitol_v09_contract())
        assert result == "bitol-0.9.0"

    def test_bitol_kind_apiversion_fallback(self):
        """kind: DataProduct + apiVersion: v1.0.0 without schema URL."""
        data = {
            "kind": "DataProduct",
            "apiVersion": "v1.0.0",
            "product": {"details": {"en": {"productID": "x", "name": "x"}}},
        }
        result = _detect_bitol_odps_version(data)
        assert result == "bitol-1.0.0"

    def test_odcs_not_detected_as_bitol(self):
        """ODCS contract with apiVersion must NOT match Bitol."""
        data = {
            "apiVersion": "odcs.io/v3.1.0",
            "kind": "DataContract",
        }
        result = _detect_bitol_odps_version(data)
        assert result == ""

    def test_pre_bitol_not_detected_as_bitol(self):
        result = detect_odps_version(_pre_bitol_v41_contract())
        assert result == "4.1"

    def test_non_dict_returns_unknown(self):
        assert detect_odps_version("not a dict") == "unknown"


class BitolSpecDetectionTest(TestCase):
    """Test detect_spec_type and is_odps_contract for Bitol."""

    def test_is_odps_contract_bitol(self):
        assert is_odps_contract(_bitol_v1_contract()) is True

    def test_detect_spec_type_bitol_v1(self):
        spec_type, spec_version = detect_spec_type(
            _bitol_v1_contract()
        )
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "bitol-1.0.0"

    def test_detect_spec_type_bitol_v09(self):
        spec_type, spec_version = detect_spec_type(
            _bitol_v09_contract()
        )
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "bitol-0.9.0"

    def test_detect_spec_type_pre_bitol(self):
        spec_type, spec_version = detect_spec_type(
            _pre_bitol_v41_contract()
        )
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

    def test_odcs_not_misclassified_as_bitol(self):
        """ODCS v3.1.0 must not be detected as Bitol ODPS."""
        data = {
            "apiVersion": "odcs.io/v3.1.0",
            "kind": "DataContract",
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}],
            },
        }
        spec_type, _ = detect_spec_type(data)
        assert spec_type == OriginalSpecType.ODCS


# ======================================================================
# 26.3.2 — Version constants
# ======================================================================

class VersionConstantsTest(TestCase):
    """Test updated version constants."""

    def test_bitol_in_supported_odps(self):
        assert "bitol-1.0.0" in SUPPORTED_ODPS_VERSIONS
        assert "bitol-0.9.0" in SUPPORTED_ODPS_VERSIONS

    def test_pre_bitol_in_supported_odps(self):
        assert "4.2" in SUPPORTED_ODPS_VERSIONS
        assert "4.1" in SUPPORTED_ODPS_VERSIONS
        assert "1.x" in SUPPORTED_ODPS_VERSIONS

    def test_odcs_3_1_0_in_supported(self):
        assert "3.1.0" in SUPPORTED_ODCS_VERSIONS

    def test_odcs_existing_versions_preserved(self):
        for v in ("2.2.2", "3.0.0", "3.0.1", "3.0.2"):
            assert v in SUPPORTED_ODCS_VERSIONS, f"{v} missing"


# ======================================================================
# 26.3.3 — Bitol normalizer
# ======================================================================

class BitolNormalizerStructureTest(TestCase):
    """Basic structure tests."""

    def test_can_instantiate(self):
        n = ODPSBitolNormalizerV1_0_0()
        assert n is not None

    def test_spec_type_is_odps(self):
        n = ODPSBitolNormalizerV1_0_0()
        assert n.spec_type == OriginalSpecType.ODPS


class BitolNormalizerSupportsTest(TestCase):
    """Test version support."""

    def setUp(self):
        self.n = ODPSBitolNormalizerV1_0_0()

    def test_supports_bitol_1_0_0(self):
        assert self.n.supports(
            OriginalSpecType.ODPS, "bitol-1.0.0", {}
        ) is True

    def test_supports_bitol_0_9_0(self):
        assert self.n.supports(
            OriginalSpecType.ODPS, "bitol-0.9.0", {}
        ) is True

    def test_supports_bitol_1_0_1(self):
        assert self.n.supports(
            OriginalSpecType.ODPS, "bitol-1.0.1", {}
        ) is True

    def test_does_not_support_pre_bitol(self):
        assert self.n.supports(
            OriginalSpecType.ODPS, "4.1", {}
        ) is False

    def test_does_not_support_none(self):
        assert self.n.supports(
            OriginalSpecType.ODPS, None, {}
        ) is False


class BitolNormalizerTeamTest(TestCase):
    """Test Bitol team object mapping."""

    def setUp(self):
        self.n = ODPSBitolNormalizerV1_0_0()

    def test_team_object_mapped_to_owners(self):
        contract = _bitol_v1_contract(team={
            "members": [
                {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "role": "owner",
                    "id": "u-001",
                },
            ]
        })
        result = self.n.normalize(contract, spec_version="bitol-1.0.0")
        hc = result.hub_contract
        assert hc is not None

        owners = hc.get("info", {}).get("owners", [])
        assert len(owners) >= 1
        assert owners[0]["name"] == "Alice"

        team = hc.get("team", [])
        assert len(team) >= 1

    def test_team_under_product(self):
        """team nested under product should also be found."""
        contract = _bitol_v1_contract()
        contract["product"]["team"] = {
            "members": [
                {"name": "Bob", "email": "bob@test.com", "role": "admin"},
            ]
        }
        result = self.n.normalize(contract, spec_version="bitol-1.0.0")
        hc = result.hub_contract
        assert hc is not None
        owners = hc.get("info", {}).get("owners", [])
        assert any(o.get("name") == "Bob" for o in owners)


class BitolNormalizerPortsTest(TestCase):
    """Test outputPorts / inputPorts mapping."""

    def setUp(self):
        self.n = ODPSBitolNormalizerV1_0_0()

    def test_output_ports_mapped(self):
        contract = _bitol_v1_contract(outputPorts=[
            {
                "name": "api-out",
                "contractId": "c-uuid-001",
                "customProperties": [
                    {"key": "region", "value": "eu-west-1"}
                ],
                "tags": ["production", "api"],
                "authoritativeDefinitions": [
                    {"url": "https://example.com/def"}
                ],
            }
        ])
        result = self.n.normalize(contract, spec_version="bitol-1.0.0")
        hc = result.hub_contract
        assert hc is not None

        x_odps = hc.get("extensions", {}).get("x_odps", {})
        out_ports = x_odps.get("output_ports", [])
        assert len(out_ports) == 1
        assert out_ports[0]["name"] == "api-out"
        assert out_ports[0]["contract_id"] == "c-uuid-001"
        assert out_ports[0]["tags"] == ["production", "api"]
        assert len(out_ports[0]["custom_properties"]) == 1
        assert len(out_ports[0]["authoritative_definitions"]) == 1

    def test_input_ports_mapped(self):
        contract = _bitol_v1_contract(inputPorts=[
            {
                "name": "kafka-in",
                "description": "Kafka consumer",
                "tags": ["streaming"],
            }
        ])
        result = self.n.normalize(contract, spec_version="bitol-1.0.0")
        hc = result.hub_contract
        assert hc is not None

        x_odps = hc.get("extensions", {}).get("x_odps", {})
        in_ports = x_odps.get("input_ports", [])
        assert len(in_ports) == 1
        assert in_ports[0]["name"] == "kafka-in"
        assert in_ports[0]["tags"] == ["streaming"]

    def test_ports_under_product(self):
        """Ports nested under product should also be found."""
        contract = _bitol_v1_contract()
        contract["product"]["outputPorts"] = [
            {"name": "nested-out", "contractId": "c-002"}
        ]
        result = self.n.normalize(contract, spec_version="bitol-1.0.0")
        hc = result.hub_contract
        assert hc is not None
        x_odps = hc.get("extensions", {}).get("x_odps", {})
        out_ports = x_odps.get("output_ports", [])
        assert len(out_ports) == 1
        assert out_ports[0]["contract_id"] == "c-002"

    def test_no_ports_no_error(self):
        """Contract without ports should normalise without errors."""
        contract = _bitol_v1_contract()
        result = self.n.normalize(contract, spec_version="bitol-1.0.0")
        assert result.hub_contract is not None
        assert len(result.errors) == 0


class BitolNormalizerRegistryTest(TestCase):
    """Test normalizer is registered and discoverable."""

    def test_get_normalizer_bitol_v1(self):
        from hub.apps.contracts.normalization import get_normalizer
        n = get_normalizer(OriginalSpecType.ODPS, "bitol-1.0.0", {})
        assert n is not None
        assert isinstance(n, ODPSBitolNormalizerV1_0_0)

    def test_get_normalizer_bitol_v09(self):
        from hub.apps.contracts.normalization import get_normalizer
        n = get_normalizer(OriginalSpecType.ODPS, "bitol-0.9.0", {})
        assert n is not None
        assert isinstance(n, ODPSBitolNormalizerV1_0_0)


# ======================================================================
# 26.3.4 — ODCS v3.1.0 as valid ODPS→ODCS link target
# ======================================================================

class ODCSv31LinkTargetTest(TestCase):
    """
    Verify ODCS v3.1.0 is accepted as a valid ODPS→ODCS link target.

    The linking validation (linking_validation.validate_odps_to_odcs_link)
    checks original_spec_type == ODCS, NOT version.  Since ODCS v3.1.0
    stores original_spec_type="ODCS", it is inherently accepted.
    This test confirms that invariant.
    """

    def test_odcs_v310_stores_odcs_spec_type(self):
        """ODCS v3.1.0 normalizer stores original_spec_type as ODCS."""
        from hub.apps.contracts.normalization.odcs_normalizer_v3_1_0 import (
            ODCSNormalizerV3_1_0,
        )
        n = ODCSNormalizerV3_1_0()
        assert n.spec_type == OriginalSpecType.ODCS

    def test_linking_validation_does_not_filter_by_version(self):
        """
        The linking validation function signature accepts any ODCS
        contract regardless of version — confirmed by code inspection.
        The function at linking_validation:366 checks
        ``odcs_contract.original_spec_type != OriginalSpecType.ODCS``
        with no version filter.
        """
        from hub.apps.contracts.linking_validation import (
            validate_odps_to_odcs_link,
        )
        import inspect
        source = inspect.getsource(validate_odps_to_odcs_link)
        # Confirm no version filtering
        assert "original_spec_version" not in source, (
            "validate_odps_to_odcs_link should NOT filter by version"
        )


# ======================================================================
# Review fixes — edge-case regression tests
# ======================================================================

class BitolVersionValidationEdgeCasesTest(TestCase):
    """
    Verify validate_odps_version handles Bitol versions correctly,
    including patch versions not explicitly in SUPPORTED_ODPS_VERSIONS.
    """

    def test_bitol_1_0_0_exact_supported(self):
        """Exact bitol-1.0.0 is in SUPPORTED_ODPS_VERSIONS."""
        from hub.apps.contracts.business_rules import ODPSBusinessRules
        rules = ODPSBusinessRules()
        doc = _bitol_v1_contract()
        result = rules.validate_odps_version(doc)
        assert result.is_valid, f"Expected valid: {result.errors}"

    def test_bitol_patch_version_supported_via_prefix(self):
        """bitol-1.0.1 should be accepted via prefix matching."""
        from hub.apps.contracts.business_rules import ODPSBusinessRules
        rules = ODPSBusinessRules()
        # Simulate a patch version detected by the version detector
        # by passing a doc that would detect as bitol-1.0.1
        doc = {
            "schema": (
                "https://bitol-io.github.io/"
                "open-data-product-standard/v1.0.1/schema.json"
            ),
            "kind": "DataProduct",
            "product": {"details": {"en": {"productID": "x", "name": "x"}}},
        }
        result = rules.validate_odps_version(doc)
        assert result.is_valid, (
            f"bitol-1.0.1 should be accepted: {result.errors}"
        )

    def test_bitol_0_9_0_supported(self):
        """bitol-0.9.0 should be supported."""
        from hub.apps.contracts.business_rules import ODPSBusinessRules
        rules = ODPSBusinessRules()
        result = rules.validate_odps_version(_bitol_v09_contract())
        assert result.is_valid, f"Expected valid: {result.errors}"


class BitolPortDictCustomPropertiesTest(TestCase):
    """Test that customProperties as a dict (not list) is coerced."""

    def test_custom_properties_dict_coerced_to_list(self):
        n = ODPSBitolNormalizerV1_0_0()
        contract = _bitol_v1_contract(outputPorts=[
            {
                "name": "api-out",
                "customProperties": {"key": "region", "value": "us"},
            }
        ])
        result = n.normalize(contract, spec_version="bitol-1.0.0")
        hc = result.hub_contract
        assert hc is not None
        x_odps = hc.get("extensions", {}).get("x_odps", {})
        out_ports = x_odps.get("output_ports", [])
        assert len(out_ports) == 1
        # Should be a list even though source was a dict
        cp = out_ports[0].get("custom_properties")
        assert isinstance(cp, list), f"Expected list, got {type(cp)}"
        assert len(cp) == 1


class BitolDetectionApiVersionOnlyTest(TestCase):
    """Edge case: Bitol contract with only apiVersion, no schema URL."""

    def test_detect_version_apiversion_only(self):
        data = {
            "kind": "DataProduct",
            "apiVersion": "v0.9.0",
            "product": {"details": {"en": {"productID": "x", "name": "x"}}},
        }
        result = detect_odps_version(data)
        assert result == "bitol-0.9.0"

    def test_detect_spec_type_apiversion_only(self):
        data = {
            "kind": "DataProduct",
            "apiVersion": "v1.0.0",
            "product": {"details": {"en": {"productID": "x", "name": "x"}}},
        }
        spec_type, spec_version = detect_spec_type(data)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "bitol-1.0.0"

    def test_two_part_apiversion_not_bitol(self):
        """apiVersion without 3-part semver must NOT match Bitol."""
        data = {
            "kind": "DataProduct",
            "apiVersion": "v2.0",
        }
        result = _detect_bitol_odps_version(data)
        assert result == "", (
            f"Two-part version should not match Bitol: {result}"
        )
