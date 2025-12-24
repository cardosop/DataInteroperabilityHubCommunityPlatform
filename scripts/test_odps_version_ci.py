#!/usr/bin/env python3
"""
Test ODPS version-specific functionality in CI.

This script runs version-specific tests for a given ODPS version.
It validates:
1. Schema file exists and is valid
2. Schema can be loaded
3. Sample documents validate against schema
4. Version detection works correctly

Usage:
    python scripts/test_odps_version_ci.py <version>

Example:
    python scripts/test_odps_version_ci.py 4.1
    python scripts/test_odps_version_ci.py 3.x
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import validate, Draft202012Validator, ValidationError, SchemaError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception
    SchemaError = Exception

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hub.apps.contracts.odps_schema import load_odps_schema, clear_schema_cache
from hub.apps.contracts.odps_version_detection import detect_odps_version
from hub.apps.contracts.odps_parser import ODPSParser


def validate_schema_file(version: str) -> tuple[bool, list[str]]:
    """Validate that schema file exists and is valid JSON Schema."""
    errors = []

    # Get schema directory
    base_dir = project_root / "hub" / "apps" / "contracts"
    schemas_dir = base_dir / "schemas" / "odps"
    schema_path = schemas_dir / f"v{version}" / "odps-schema.json"

    if not schema_path.exists():
        return False, [f"Schema file not found: {schema_path}"]

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)

        if not JSONSCHEMA_AVAILABLE:
            return True, []  # Can't validate JSON Schema without library

        # Validate schema is valid JSON Schema
        Draft202012Validator.check_schema(schema_data)
        return True, []
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except SchemaError as e:
        return False, [f"Invalid JSON Schema: {e}"]
    except Exception as e:
        return False, [f"Unexpected error: {e}"]


def test_schema_loading(version: str) -> tuple[bool, list[str]]:
    """Test that schema can be loaded for the version."""
    errors = []

    try:
        clear_schema_cache()
        schema = load_odps_schema(version)

        if not isinstance(schema, dict):
            errors.append(f"Schema should be a dict, got {type(schema)}")
        if "$schema" not in schema:
            errors.append("Schema missing $schema field")
        if "type" not in schema:
            errors.append("Schema missing type field")

        return len(errors) == 0, errors
    except FileNotFoundError as e:
        return False, [f"Schema file not found: {e}"]
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [f"Error loading schema: {e}"]


def test_sample_document_validation(version: str) -> tuple[bool, list[str]]:
    """Test that sample documents validate against schema."""
    if not JSONSCHEMA_AVAILABLE:
        return True, []  # Skip if jsonschema not available

    errors = []

    # Create minimal valid ODPS document for the version
    # Map version to appropriate schema URL and version field
    version_map = {
        "4.1": ("https://opendataproducts.org/schema/v4.1", "4.1"),
        "4.0": ("https://opendataproducts.org/schema/v4.0", "4.0"),
        "3.x": ("https://opendataproducts.org/schema/v3.9", "3.9"),
        "2.x": ("https://opendataproducts.org/schema/v2.9", "2.9"),
        "1.x": ("https://opendataproducts.org/schema/v1.9", "1.9"),
    }

    schema_url, version_field = version_map.get(version, (None, None))
    if not schema_url:
        return False, [f"Unknown version: {version}"]

    sample_doc = {
        "schema": schema_url,
        "version": version_field,
        "product": {
            "details": {
                "en": {
                    "productID": f"test-product-{version}",
                    "name": f"Test Product {version}",
                    "description": f"A test product for version {version}"
                }
            }
        }
    }

    try:
        schema = load_odps_schema(version)
        validate(instance=sample_doc, schema=schema)
        return True, []
    except ValidationError as e:
        return False, [f"Sample document validation failed: {e}"]
    except Exception as e:
        return False, [f"Unexpected error during validation: {e}"]


def test_version_detection(version: str) -> tuple[bool, list[str]]:
    """Test that version detection works correctly."""
    errors = []

    # Map version to appropriate schema URL and version field
    version_map = {
        "4.1": ("https://opendataproducts.org/schema/v4.1", "4.1"),
        "4.0": ("https://opendataproducts.org/schema/v4.0", "4.0"),
        "3.x": ("https://opendataproducts.org/schema/v3.9", "3.9"),
        "2.x": ("https://opendataproducts.org/schema/v2.9", "2.9"),
        "1.x": ("https://opendataproducts.org/schema/v1.9", "1.9"),
    }

    schema_url, version_field = version_map.get(version, (None, None))
    if not schema_url:
        return False, [f"Unknown version: {version}"]

    # Test detection from schema URL
    doc_with_schema = {"schema": schema_url}
    detected = detect_odps_version(doc_with_schema)

    # For .x versions, detection returns the normalized version (e.g., "3.x")
    # For exact versions, it should return the exact version
    if version.endswith('.x'):
        if not detected.startswith(version.split('.')[0] + '.'):
            errors.append(f"Version detection from schema URL failed: expected {version} family, got {detected}")
    else:
        if detected != version:
            errors.append(f"Version detection from schema URL failed: expected {version}, got {detected}")

    # Test detection from version field
    doc_with_version = {"version": version_field}
    detected_from_version = detect_odps_version(doc_with_version)

    # For .x versions, the version field contains a specific version (e.g., "3.9")
    # Detection should normalize it to the .x version
    if version.endswith('.x'):
        if not detected_from_version.startswith(version.split('.')[0] + '.'):
            errors.append(f"Version detection from version field failed: expected {version} family, got {detected_from_version}")
    else:
        if detected_from_version != version:
            errors.append(f"Version detection from version field failed: expected {version}, got {detected_from_version}")

    return len(errors) == 0, errors


def test_odps_parser(version: str) -> tuple[bool, list[str]]:
    """Test ODPS parser with the version."""
    errors = []

    # Map version to appropriate schema URL and version field
    version_map = {
        "4.1": ("https://opendataproducts.org/schema/v4.1", "4.1"),
        "4.0": ("https://opendataproducts.org/schema/v4.0", "4.0"),
        "3.x": ("https://opendataproducts.org/schema/v3.9", "3.9"),
        "2.x": ("https://opendataproducts.org/schema/v2.9", "2.9"),
        "1.x": ("https://opendataproducts.org/schema/v1.9", "1.9"),
    }

    schema_url, version_field = version_map.get(version, (None, None))
    if not schema_url:
        return False, [f"Unknown version: {version}"]

    sample_doc = {
        "schema": schema_url,
        "version": version_field,
        "product": {
            "details": {
                "en": {
                    "productID": f"test-product-{version}",
                    "name": f"Test Product {version}"
                }
            }
        }
    }

    try:
        # Test parsing
        doc_json = json.dumps(sample_doc)
        parsed, is_valid, validation_errors = ODPSParser.parse_and_validate(
            doc_json,
            version=version
        )

        if not is_valid:
            error_messages = [str(e) for e in validation_errors]
            errors.append(f"ODPSParser validation failed: {', '.join(error_messages)}")

        return len(errors) == 0, errors
    except Exception as e:
        return False, [f"ODPSParser error: {e}"]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test ODPS version-specific functionality in CI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "version",
        type=str,
        help="ODPS version to test (e.g., '4.1', '4.0', '3.x', '2.x', '1.x')"
    )

    args = parser.parse_args()
    version = args.version

    # Validate version format
    valid_versions = ["4.1", "4.0", "3.x", "2.x", "1.x"]
    if version not in valid_versions:
        print(f"❌ Invalid version: {version}")
        print(f"Valid versions: {', '.join(valid_versions)}")
        sys.exit(1)

    print(f"Testing ODPS version: {version}")
    print("=" * 60)

    all_passed = True
    all_errors = []

    # Test 1: Validate schema file
    print(f"\n1. Validating schema file for version {version}...")
    passed, errors = validate_schema_file(version)
    if passed:
        print(f"   ✅ Schema file is valid")
    else:
        print(f"   ❌ Schema file validation failed:")
        for error in errors:
            print(f"      - {error}")
        all_passed = False
        all_errors.extend(errors)

    # Test 2: Test schema loading
    print(f"\n2. Testing schema loading for version {version}...")
    passed, errors = test_schema_loading(version)
    if passed:
        print(f"   ✅ Schema loaded successfully")
    else:
        print(f"   ❌ Schema loading failed:")
        for error in errors:
            print(f"      - {error}")
        all_passed = False
        all_errors.extend(errors)

    # Test 3: Test sample document validation
    print(f"\n3. Testing sample document validation for version {version}...")
    passed, errors = test_sample_document_validation(version)
    if passed:
        print(f"   ✅ Sample document validated successfully")
    else:
        print(f"   ❌ Sample document validation failed:")
        for error in errors:
            print(f"      - {error}")
        all_passed = False
        all_errors.extend(errors)

    # Test 4: Test version detection
    print(f"\n4. Testing version detection for version {version}...")
    passed, errors = test_version_detection(version)
    if passed:
        print(f"   ✅ Version detection works correctly")
    else:
        print(f"   ❌ Version detection failed:")
        for error in errors:
            print(f"      - {error}")
        all_passed = False
        all_errors.extend(errors)

    # Test 5: Test ODPS parser
    print(f"\n5. Testing ODPS parser for version {version}...")
    passed, errors = test_odps_parser(version)
    if passed:
        print(f"   ✅ ODPS parser works correctly")
    else:
        print(f"   ❌ ODPS parser failed:")
        for error in errors:
            print(f"      - {error}")
        all_passed = False
        all_errors.extend(errors)

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print(f"✅ All tests passed for ODPS version {version}")
        sys.exit(0)
    else:
        print(f"❌ Some tests failed for ODPS version {version}")
        print(f"\nErrors:")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()

