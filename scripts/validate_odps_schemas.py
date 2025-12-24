#!/usr/bin/env python3
"""
Validate ODPS JSON Schema files.

This script validates that all ODPS schema files are:
1. Valid JSON
2. Valid JSON Schema (Draft 2020-12 or compatible)
3. Schema files match their version directories
4. Schema $id and schema URL patterns match version
5. Required structure fields are present

Usage:
    python scripts/validate_odps_schemas.py [--strict] [--version VERSION]

Exit codes:
    0: All schemas are valid
    1: One or more schemas are invalid
    2: jsonschema library not available (non-strict mode only)
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

try:
    import jsonschema
    from jsonschema import Draft202012Validator, SchemaError, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    Draft202012Validator = None
    SchemaError = Exception
    ValidationError = Exception


def validate_json_file(file_path: Path) -> Tuple[bool, str, dict]:
    """
    Validate that a file is valid JSON.

    Args:
        file_path: Path to the JSON file

    Returns:
        Tuple of (is_valid, error_message, data)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return True, "", data
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}", {}
    except Exception as e:
        return False, f"Error reading file: {e}", {}


def validate_json_schema(schema_data: dict, file_path: Path) -> Tuple[bool, str]:
    """
    Validate that a dictionary is valid JSON Schema.

    Args:
        schema_data: The schema data dictionary
        file_path: Path to the schema file (for error messages)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not JSONSCHEMA_AVAILABLE or Draft202012Validator is None:
        return False, "jsonschema library not available"

    try:
        # Validate the schema itself
        Draft202012Validator.check_schema(schema_data)
        return True, ""
    except SchemaError as e:
        return False, f"Invalid JSON Schema: {e}"
    except Exception as e:
        # For older drafts, try basic validation
        try:
            if jsonschema:
                jsonschema.validate(instance={}, schema=schema_data)
            return True, ""
        except Exception as validation_error:
            return False, f"Schema validation failed: {validation_error}"


def validate_schema_version_consistency(
    schema_data: dict, version_dir: str, schema_path: Path
) -> Tuple[bool, List[str]]:
    """
    Validate that schema file matches its version directory.

    Args:
        schema_data: The schema data dictionary
        version_dir: Version directory name (e.g., "v4.1", "v3.x")
        schema_path: Path to the schema file (for error messages)

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    normalized_version = version_dir.lstrip("v")  # Remove "v" prefix

    # Version patterns to check in $id and schema URLs (with v prefix)
    version_patterns = {
        "4.1": r"v4\.1",
        "4.0": r"v4\.0",
        "3.x": r"v3\.",
        "2.x": r"v2\.",
        "1.x": r"v1\.",
    }

    # Version patterns for version field (without v prefix)
    version_field_patterns = {
        "4.1": r"^4\.1",
        "4.0": r"^4\.0",
        "3.x": r"^3\.",
        "2.x": r"^2\.",
        "1.x": r"^1\.",
    }

    expected_pattern = version_patterns.get(normalized_version, "")
    expected_version_pattern = version_field_patterns.get(normalized_version, "")

    # Check $id field contains version (with v prefix)
    schema_id = schema_data.get("$id", "")
    if schema_id and expected_pattern:
        if not re.search(expected_pattern, schema_id):
            errors.append(
                f"$id field '{schema_id}' does not contain expected version pattern '{expected_pattern}'"
            )

    # Check schema field pattern (if present) - should contain version with v prefix
    schema_url = schema_data.get("schema", "")
    if schema_url and expected_pattern:
        if not re.search(expected_pattern, schema_url):
            errors.append(
                f"schema URL '{schema_url}' does not contain expected version pattern '{expected_pattern}'"
            )

    # Check version field (if present) - should match version without v prefix
    version_field = schema_data.get("version", "")
    if version_field and expected_version_pattern:
        if not re.search(expected_version_pattern, str(version_field)):
            errors.append(
                f"version field '{version_field}' does not match expected pattern '{expected_version_pattern}'"
            )

    return len(errors) == 0, errors


def validate_schema_structure(schema_data: dict, schema_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate that schema has required structure.

    Args:
        schema_data: The schema data dictionary
        schema_path: Path to the schema file (for error messages)

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check required fields
    required_fields = ["$schema", "type"]
    for field in required_fields:
        if field not in schema_data:
            errors.append(f"Missing required field '{field}'")

    # Check $schema is valid JSON Schema draft URL
    schema_url = schema_data.get("$schema", "")
    if schema_url and not schema_url.startswith("https://json-schema.org/draft/"):
        errors.append(f"Invalid $schema URL '{schema_url}' (should start with 'https://json-schema.org/draft/')")

    # Check type is "object" (ODPS schemas should be object schemas)
    schema_type = schema_data.get("type")
    if schema_type and schema_type != "object":
        errors.append(f"Schema type should be 'object', got '{schema_type}'")

    return len(errors) == 0, errors


def validate_odps_schemas(
    schemas_dir: Path, strict: bool = False, version_filter: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Validate all ODPS schema files.

    Args:
        schemas_dir: Path to the schemas/odps directory
        strict: If True, require jsonschema library; if False, skip JSON Schema validation if unavailable
        version_filter: Optional version to validate (e.g., "4.1", "4.0", "3.x"). If None, validates all.

    Returns:
        Tuple of (all_valid, error_messages)
    """
    if not schemas_dir.exists():
        return False, [f"Schemas directory does not exist: {schemas_dir}"]

    if strict and not JSONSCHEMA_AVAILABLE:
        return False, ["jsonschema library is required in strict mode"]

    required_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]

    # Filter versions if specified
    if version_filter:
        # Normalize version filter (add "v" prefix if needed)
        if not version_filter.startswith("v"):
            version_filter = f"v{version_filter}"
        if version_filter not in required_versions:
            return False, [f"Invalid version filter: {version_filter}. Must be one of {required_versions}"]
        required_versions = [version_filter]

    schema_filename = "odps-schema.json"
    errors = []
    all_valid = True
    validated_count = 0

    for version in required_versions:
        schema_path = schemas_dir / version / schema_filename

        # Check file exists
        if not schema_path.exists():
            errors.append(f"❌ Schema file missing: {schema_path}")
            all_valid = False
            continue

        # Validate JSON
        is_valid_json, json_error, schema_data = validate_json_file(schema_path)
        if not is_valid_json:
            errors.append(f"❌ {schema_path}: {json_error}")
            all_valid = False
            continue

        # Validate JSON Schema structure (basic checks)
        if not isinstance(schema_data, dict):
            errors.append(f"❌ {schema_path}: Schema must be a JSON object")
            all_valid = False
            continue

        # Validate required structure
        is_valid_structure, structure_errors = validate_schema_structure(schema_data, schema_path)
        if not is_valid_structure:
            for error in structure_errors:
                errors.append(f"❌ {schema_path}: {error}")
            all_valid = False
            continue

        # Validate version consistency
        is_valid_version, version_errors = validate_schema_version_consistency(schema_data, version, schema_path)
        if not is_valid_version:
            for error in version_errors:
                errors.append(f"❌ {schema_path}: Version consistency error - {error}")
            all_valid = False
            continue

        # Validate JSON Schema (if library available or strict mode)
        if JSONSCHEMA_AVAILABLE or strict:
            is_valid_schema, schema_error = validate_json_schema(schema_data, schema_path)
            if not is_valid_schema:
                errors.append(f"❌ {schema_path}: {schema_error}")
                all_valid = False
                continue
            else:
                print(f"✅ {schema_path}: Valid JSON Schema (version {version.lstrip('v')})")
                validated_count += 1
        else:
            print(f"✅ {schema_path}: Valid JSON (version {version.lstrip('v')}, JSON Schema validation skipped - library not available)")
            validated_count += 1

    if validated_count > 0:
        print(f"\n✅ Validated {validated_count} ODPS schema file(s)")

    return all_valid, errors


def main():
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(
        description="Validate ODPS JSON Schema files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic validation (skips JSON Schema validation if library not available)
  python scripts/validate_odps_schemas.py

  # Strict validation (requires jsonschema library)
  python scripts/validate_odps_schemas.py --strict

  # Validate specific version
  python scripts/validate_odps_schemas.py --strict --version 4.1
        """
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require jsonschema library for JSON Schema validation"
    )
    parser.add_argument(
        "--schemas-dir",
        type=Path,
        default=None,
        help="Path to schemas/odps directory (default: auto-detect from script location)"
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Validate only specific ODPS version (e.g., '4.1', '4.0', '3.x'). If not specified, validates all versions."
    )

    args = parser.parse_args()

    # Determine schemas directory
    if args.schemas_dir:
        schemas_dir = args.schemas_dir
    else:
        # Auto-detect: script is in scripts/, schemas are in hub/apps/contracts/schemas/odps/
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        schemas_dir = project_root / "hub" / "apps" / "contracts" / "schemas" / "odps"

    # Validate schemas
    all_valid, errors = validate_odps_schemas(schemas_dir, strict=args.strict, version_filter=args.version)

    # Print results
    if errors:
        print("\nValidation Errors:")
        for error in errors:
            print(f"  {error}")
        print()

    if all_valid:
        print("✅ All ODPS schema files are valid!")
        sys.exit(0)
    else:
        print("❌ Some ODPS schema files are invalid!")
        sys.exit(1)


if __name__ == "__main__":
    main()

