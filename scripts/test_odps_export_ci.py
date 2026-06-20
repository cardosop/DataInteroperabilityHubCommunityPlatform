#!/usr/bin/env python3
"""
Comprehensive CI validation tests for ODPS export functionality.

This script validates ODPS export capabilities without requiring database access:
1. ODPS generation from HubContract
2. JSON export formatting
3. YAML export formatting
4. Round-trip consistency

Usage:
    python scripts/test_odps_export_ci.py

Exit codes:
    0: All tests passed
    1: One or more tests failed
"""

import json
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_generator import (
    format_odps_as_json,
    format_odps_as_yaml,
    generate_odps_from_hubcontract,
)


def test_odps_generation_from_hubcontract():
    """Test ODPS generation from HubContract."""
    print("1. Testing ODPS generation from HubContract...")

    # Create comprehensive HubContract
    hub_contract = {
        "hub_contract_version": "1.0.0",
        "id": "test-product-export",
        "info": {
            "name": "CI Test Product",
            "description": "Test product for CI export validation",
            "version": "1.0.0",
        },
        "marketplace": {
            "license_summary": "MIT License",
            "intended_use": ["analytics", "research"],
            "pricing": {
                "model": "free",
                "currency": "USD",
            },
        },
        "data_schema": {
            "fields": [
                {
                    "name": "id",
                    "type": "string",
                    "description": "Unique identifier",
                },
                {
                    "name": "name",
                    "type": "string",
                    "description": "Name field",
                },
                {
                    "name": "value",
                    "type": "number",
                    "description": "Numeric value",
                },
            ]
        },
    }

    try:
        # Generate ODPS from HubContract
        odps_doc = generate_odps_from_hubcontract(
            hub_contract=hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        # Verify structure
        assert isinstance(odps_doc, dict), "ODPS document should be a dict"
        assert "schema" in odps_doc, "ODPS document should have schema field"
        assert "version" in odps_doc, "ODPS document should have version field"
        assert "product" in odps_doc, "ODPS document should have product field"
        assert odps_doc["version"] == "4.1", "ODPS version should be 4.1"

        # Verify product details
        assert "details" in odps_doc["product"], "ODPS product should have details"
        assert "en" in odps_doc["product"]["details"], "ODPS product should have English details"
        assert odps_doc["product"]["details"]["en"]["name"] == "CI Test Product", (
            "Product name should match"
        )

        print("   ✅ ODPS generation from HubContract works correctly")
        return True, odps_doc
    except Exception as e:
        print(f"   ❌ ODPS generation failed: {e}")
        return False, None


def test_json_export(odps_doc):
    """Test JSON export formatting."""
    print("\n2. Testing ODPS JSON export...")

    if not odps_doc:
        print("   ⚠️  Skipping JSON export test (no ODPS document)")
        return False

    try:
        # Export as JSON
        json_output = format_odps_as_json(odps_doc)

        # Verify output is valid JSON
        parsed = json.loads(json_output)

        # Verify structure is preserved
        assert parsed["schema"] == odps_doc["schema"], "Schema should match"
        assert parsed["version"] == odps_doc["version"], "Version should match"
        assert (
            parsed["product"]["details"]["en"]["name"]
            == odps_doc["product"]["details"]["en"]["name"]
        ), "Product name should match"

        # Verify JSON formatting
        assert json_output.strip().startswith("{"), "JSON should start with {"
        assert json_output.strip().endswith("}"), "JSON should end with }"

        print("   ✅ JSON export works correctly")
        return True, json_output
    except Exception as e:
        print(f"   ❌ JSON export failed: {e}")
        return False, None


def test_yaml_export(odps_doc):
    """Test YAML export formatting."""
    print("\n3. Testing ODPS YAML export...")

    if not YAML_AVAILABLE:
        print("   ⚠️  Skipping YAML export test (PyYAML not available)")
        return False, None

    if not odps_doc:
        print("   ⚠️  Skipping YAML export test (no ODPS document)")
        return False, None

    try:
        # Export as YAML
        yaml_output = format_odps_as_yaml(odps_doc)

        # Verify output is valid YAML
        parsed = yaml.safe_load(yaml_output)

        # Verify structure is preserved
        assert parsed["schema"] == odps_doc["schema"], "Schema should match"
        assert parsed["version"] == odps_doc["version"], "Version should match"
        assert (
            parsed["product"]["details"]["en"]["name"]
            == odps_doc["product"]["details"]["en"]["name"]
        ), "Product name should match"

        # Verify YAML formatting (should be block style, not flow style)
        assert "{" not in yaml_output[:200] or yaml_output[:200].count("{") < 3, (
            "YAML should use block style"
        )

        print("   ✅ YAML export works correctly")
        return True, yaml_output
    except ODPSExportError as e:
        if "PyYAML" in str(e):
            print("   ⚠️  Skipping YAML export test (PyYAML not available)")
            return False, None
        print(f"   ❌ YAML export failed: {e}")
        return False, None
    except Exception as e:
        print(f"   ❌ YAML export failed: {e}")
        return False, None


def test_round_trip_consistency(odps_doc):
    """Test round-trip consistency between JSON and YAML."""
    print("\n4. Testing round-trip consistency (JSON ↔ YAML)...")

    if not YAML_AVAILABLE:
        print("   ⚠️  Skipping round-trip test (PyYAML not available)")
        return False

    if not odps_doc:
        print("   ⚠️  Skipping round-trip test (no ODPS document)")
        return False

    try:
        # Export as JSON
        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Export as YAML
        yaml_output = format_odps_as_yaml(odps_doc)
        yaml_parsed = yaml.safe_load(yaml_output)

        # Verify core fields match
        assert json_parsed["schema"] == yaml_parsed["schema"], "Schema should match between formats"
        assert json_parsed["version"] == yaml_parsed["version"], (
            "Version should match between formats"
        )

        # Verify product details match
        if "product" in json_parsed and "product" in yaml_parsed:
            json_product = json_parsed["product"]
            yaml_product = yaml_parsed["product"]

            if "details" in json_product and "details" in yaml_product:
                json_details = json_product["details"]
                yaml_details = yaml_product["details"]

                if "en" in json_details and "en" in yaml_details:
                    assert json_details["en"].get("name") == yaml_details["en"].get("name"), (
                        "Product name should match between formats"
                    )

        print("   ✅ Round-trip consistency verified")
        return True
    except Exception as e:
        print(f"   ❌ Round-trip consistency test failed: {e}")
        return False


def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\n5. Testing error handling...")

    errors = []

    # Test invalid input for JSON export
    try:
        format_odps_as_json("not a dict")
        errors.append("JSON export should raise error for non-dict input")
    except ODPSExportError:
        pass  # Expected
    except Exception as e:
        errors.append(f"JSON export raised unexpected error: {e}")

    # Test invalid input for YAML export
    if YAML_AVAILABLE:
        try:
            format_odps_as_yaml("not a dict")
            errors.append("YAML export should raise error for non-dict input")
        except ODPSExportError:
            pass  # Expected
        except Exception as e:
            errors.append(f"YAML export raised unexpected error: {e}")

    # Test invalid HubContract
    try:
        generate_odps_from_hubcontract(
            hub_contract="not a dict",
            target_version="4.1",
        )
        errors.append("ODPS generation should raise error for non-dict HubContract")
    except ODPSExportError:
        pass  # Expected
    except Exception as e:
        errors.append(f"ODPS generation raised unexpected error: {e}")

    if errors:
        print("   ❌ Error handling test failed:")
        for error in errors:
            print(f"      - {error}")
        return False

    print("   ✅ Error handling works correctly")
    return True


def main():
    """Main entry point."""
    print("=" * 60)
    print("ODPS Export CI Validation Tests")
    print("=" * 60)
    print()

    all_passed = True

    # Test 1: ODPS generation from HubContract
    passed, odps_doc = test_odps_generation_from_hubcontract()
    if not passed:
        all_passed = False

    # Test 2: JSON export
    passed, _json_output = test_json_export(odps_doc)
    if not passed:
        all_passed = False

    # Test 3: YAML export
    passed, _yaml_output = test_yaml_export(odps_doc)
    if not passed and YAML_AVAILABLE:
        all_passed = False

    # Test 4: Round-trip consistency
    passed = test_round_trip_consistency(odps_doc)
    if not passed and YAML_AVAILABLE:
        all_passed = False

    # Test 5: Error handling
    passed = test_error_handling()
    if not passed:
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All ODPS export tests passed!")
        sys.exit(0)
    else:
        print("❌ Some ODPS export tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
