"""
Unit Tests for Spec Detection and Metadata Tracking
"""
import pytest
from hub.apps.contracts.spec_detection import (
    detect_spec_type,
    detect_odps_version,
    is_odps_contract,
    extract_original_spec_metadata,
    extract_conformance_info,
    store_original_spec_metadata
)
from hub.apps.contracts.models import OriginalSpecType


class TestDetectSpecType:
    """Test spec type detection"""

    def test_detect_odcs(self):
        """Test detecting ODCS"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODCS
        assert spec_version == '3.0.2'

    def test_detect_odcs_with_v_prefix(self):
        """Test detecting ODCS with v prefix"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODCS
        assert 'v' not in spec_version or spec_version.startswith('v')

    def test_detect_odps_version_4_1(self):
        """Test: Unit test for ODPS version detection - version 4.1"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        version = detect_odps_version(contract)
        assert version == "4.1"

    def test_detect_odps_version_4_0(self):
        """Test: Unit test for ODPS version detection - version 4.0"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0"
        }
        version = detect_odps_version(contract)
        assert version == "4.0"

    def test_detect_odps_version_3_x(self):
        """Test: Unit test for ODPS version detection - version 3.x"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9"
        }
        version = detect_odps_version(contract)
        assert version == "3.x"

    def test_detect_odps_version_2_x(self):
        """Test: Unit test for ODPS version detection - version 2.x"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9"
        }
        version = detect_odps_version(contract)
        assert version == "2.x"

    def test_detect_odps_version_1_x(self):
        """Test: Unit test for ODPS version detection - version 1.x"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9"
        }
        version = detect_odps_version(contract)
        assert version == "1.x"

    def test_detect_odps_version_unknown(self):
        """Test ODPS version detection returns None for non-ODPS contracts"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        version = detect_odps_version(contract)
        assert version is None

    def test_is_odps_contract_with_schema_url_opendataproducts_org(self):
        """Test is_odps_contract() with opendataproducts.org schema URL"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        assert is_odps_contract(contract) is True

    def test_is_odps_contract_with_schema_url_schemas_opendataproducts_io(self):
        """Test is_odps_contract() with schemas.opendataproducts.io URL"""
        contract = {
            "schema": "https://schemas.opendataproducts.io/spec/v4.1/product.json"
        }
        assert is_odps_contract(contract) is True

    def test_is_odps_contract_with_product_field(self):
        """Test is_odps_contract() with product field"""
        contract = {
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }
        assert is_odps_contract(contract) is True

    def test_is_odps_contract_with_open_data_product_in_url(self):
        """Test is_odps_contract() with 'open-data-product' in schema URL"""
        contract = {
            "schema": "https://example.com/open-data-product/v4.1"
        }
        assert is_odps_contract(contract) is True

    def test_is_odps_contract_false_for_odcs(self):
        """Test is_odps_contract() returns False for ODCS contracts"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        assert is_odps_contract(contract) is False

    def test_detect_spec_type_odps_4_1(self):
        """Test: Unit test for ODPS detection (all versions) - version 4.1"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

    def test_detect_spec_type_odps_4_0(self):
        """Test: Unit test for ODPS detection (all versions) - version 4.0"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.0"

    def test_detect_spec_type_odps_3_x(self):
        """Test: Unit test for ODPS detection (all versions) - version 3.x"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "3.9"  # Normalized to latest 3.x version

    def test_detect_spec_type_odps_2_x(self):
        """Test: Unit test for ODPS detection (all versions) - version 2.x"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "2.9"  # Normalized to latest 2.x version

    def test_detect_spec_type_odps_1_x(self):
        """Test: Unit test for ODPS detection (all versions) - version 1.x"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "1.9"  # Normalized to latest 1.x version

    def test_detect_spec_type_odps_before_odcs(self):
        """Test: Integration test for ODPS spec detection - ODPS takes precedence"""
        # Contract that could be misclassified as ODCS if ODPS detection wasn't first
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}},
            # These fields might confuse detection if ODPS wasn't checked first
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract"
        }
        spec_type, spec_version = detect_spec_type(contract)
        # Should detect as ODPS, not ODCS
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

    def test_detect_spec_type_odps_with_schemas_opendataproducts_io(self):
        """Test ODPS detection with schemas.opendataproducts.io URL"""
        contract = {
            "schema": "https://schemas.opendataproducts.io/spec/v4.1/product.json",
            "version": "4.1"
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

    def test_detect_spec_type_odps_with_version_field_only(self):
        """Test ODPS detection using version field when schema URL is missing"""
        contract = {
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

    def test_detect_spec_type_odps_unknown_version_defaults_to_latest(self):
        """Test ODPS detection with unknown version defaults to 4.1"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v5.0",  # Unsupported version
            "product": {"details": {"en": {"productID": "test"}}}
        }
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"  # Defaults to latest

    def test_detect_spec_type_odcs_when_not_odps(self):
        """Test that ODCS detection still works when contract is not ODPS"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODCS
        assert spec_version == '3.0.2'

    def test_detect_spec_type_fallback_to_odcs(self):
        """Test that detection falls back to ODCS when neither ODPS nor ODCS detected"""
        contract = {'id': 'test', 'name': 'Test'}
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODCS
        assert spec_version == '3.0.2'

    def test_integration_odps_spec_detection_complete_flow(self):
        """Test: Integration test for ODPS spec detection - complete flow"""
        # Test complete ODPS detection flow with all indicators
        odps_contracts = [
            {
                "name": "ODPS 4.1 with opendataproducts.org",
                "contract": {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "version": "4.1",
                    "product": {
                        "details": {
                            "en": {
                                "productID": "test-product-4.1",
                                "name": "Test Product 4.1"
                            }
                        }
                    }
                },
                "expected_type": OriginalSpecType.ODPS,
                "expected_version": "4.1"
            },
            {
                "name": "ODPS 4.0 with schemas.opendataproducts.io",
                "contract": {
                    "schema": "https://schemas.opendataproducts.io/spec/v4.0/product.json",
                    "version": "4.0",
                    "product": {"details": {"en": {"productID": "test"}}}
                },
                "expected_type": OriginalSpecType.ODPS,
                "expected_version": "4.0"
            },
            {
                "name": "ODPS 3.x with product field",
                "contract": {
                    "schema": "https://opendataproducts.org/schema/v3.9",
                    "product": {"details": {"en": {"productID": "test"}}}
                },
                "expected_type": OriginalSpecType.ODPS,
                "expected_version": "3.9"
            },
            {
                "name": "ODPS with version field only",
                "contract": {
                    "version": "4.1",
                    "product": {"details": {"en": {"productID": "test"}}}
                },
                "expected_type": OriginalSpecType.ODPS,
                "expected_version": "4.1"
            }
        ]

        for test_case in odps_contracts:
            contract = test_case["contract"]

            # Test is_odps_contract()
            assert is_odps_contract(contract) is True, \
                f"Contract '{test_case['name']}' should be detected as ODPS"

            # Test detect_odps_version()
            detected_version = detect_odps_version(contract)
            if "version" in contract or "schema" in contract:
                assert detected_version is not None, \
                    f"Version should be detected for '{test_case['name']}'"

            # Test detect_spec_type()
            spec_type, spec_version = detect_spec_type(contract)
            assert spec_type == test_case["expected_type"], \
                f"Spec type should be {test_case['expected_type']} for '{test_case['name']}'"
            assert spec_version == test_case["expected_version"], \
                f"Spec version should be {test_case['expected_version']} for '{test_case['name']}'"

            # Test extract_original_spec_metadata()
            metadata = extract_original_spec_metadata(contract)
            assert metadata["type"] == test_case["expected_type"], \
                f"Metadata type should be {test_case['expected_type']}"
            assert metadata["version"] == test_case["expected_version"], \
                f"Metadata version should be {test_case['expected_version']}"

    def test_integration_odps_vs_odcs_detection_priority(self):
        """Test: Integration test - ODPS detection takes priority over ODCS"""
        # Contract with both ODPS and ODCS indicators
        # ODPS should be detected first
        mixed_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}},
            "apiVersion": "odcs.io/v3.0.2",  # ODCS indicator
            "kind": "DataContract"  # ODCS indicator
        }

        # Should detect as ODPS (checked first)
        spec_type, spec_version = detect_spec_type(mixed_contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

        # Verify is_odps_contract() returns True
        assert is_odps_contract(mixed_contract) is True

        # Verify version detection works
        version = detect_odps_version(mixed_contract)
        assert version == "4.1"

    def test_integration_odps_detection_with_all_indicators(self):
        """Test: Integration test - ODPS detection with all possible indicators"""
        # Contract with all ODPS indicators
        comprehensive_odps_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "comprehensive-test",
                        "name": "Comprehensive Test Product",
                        "description": "A product with all ODPS indicators"
                    }
                }
            }
        }

        # All detection methods should work
        assert is_odps_contract(comprehensive_odps_contract) is True
        assert detect_odps_version(comprehensive_odps_contract) == "4.1"

        spec_type, spec_version = detect_spec_type(comprehensive_odps_contract)
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

        # Metadata extraction should work
        metadata = extract_original_spec_metadata(comprehensive_odps_contract)
        assert metadata["type"] == OriginalSpecType.ODPS
        assert metadata["version"] == "4.1"


class TestExtractOriginalSpecMetadata:
    """Test extracting original spec metadata"""

    def test_extract_odcs_metadata(self):
        """Test extracting ODCS metadata"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        metadata = extract_original_spec_metadata(contract)
        assert metadata['type'] == OriginalSpecType.ODCS
        assert 'version' in metadata


class TestExtractConformanceInfo:
    """Test extracting conformance information"""

    def test_extract_dct_conforms_to(self):
        """Test extracting dct:conformsTo"""
        contract = {'dct:conformsTo': 'https://example.com/spec'}
        conforms_to = extract_conformance_info(contract, OriginalSpecType.ODCS)
        assert conforms_to is not None
        assert conforms_to['uri'] == 'https://example.com/spec'


class TestStoreOriginalSpecMetadata:
    """Test storing original spec metadata in HubContract"""

    def test_store_metadata(self):
        """Test storing metadata in HubContract"""
        hub_contract = {'id': 'test'}
        original_contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract', 'id': 'test'}
        result = store_original_spec_metadata(hub_contract, original_contract)
        assert 'original_spec' in result
        assert result['original_spec']['type'] == OriginalSpecType.ODCS

