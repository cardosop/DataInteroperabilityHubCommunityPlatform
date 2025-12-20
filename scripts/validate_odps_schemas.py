#!/usr/bin/env python3
"""
Validate ODPS JSON Schema files.

This script validates that all ODPS schema files are:
1. Valid JSON
2. Valid JSON Schema (Draft 2020-12 or compatible)

Usage:
    python scripts/validate_odps_schemas.py [--strict]

Exit codes:
    0: All schemas are valid
    1: One or more schemas are invalid
    2: jsonschema library not available (non-strict mode only)
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

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
    if not JSONSCHEMA_AVAILABLE:
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
            jsonschema.validate(instance={}, schema=schema_data)
            return True, ""
        except Exception as validation_error:
            return False, f"Schema validation failed: {validation_error}"


def validate_odps_schemas(schemas_dir: Path, strict: bool = False) -> Tuple[bool, List[str]]:
    """
    Validate all ODPS schema files.

    Args:
        schemas_dir: Path to the schemas/odps directory
        strict: If True, require jsonschema library; if False, skip JSON Schema validation if unavailable

    Returns:
        Tuple of (all_valid, error_messages)
    """
    if not schemas_dir.exists():
        return False, [f"Schemas directory does not exist: {schemas_dir}"]

    if strict and not JSONSCHEMA_AVAILABLE:
        return False, ["jsonschema library is required in strict mode"]

    required_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]
    schema_filename = "odps-schema.json"
    errors = []
    all_valid = True

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

        required_props = ["$schema", "type"]
        for prop in required_props:
            if prop not in schema_data:
                errors.append(f"❌ {schema_path}: Missing required property '{prop}'")
                all_valid = False

        # Validate JSON Schema (if library available or strict mode)
        if JSONSCHEMA_AVAILABLE or strict:
            is_valid_schema, schema_error = validate_json_schema(schema_data, schema_path)
            if not is_valid_schema:
                errors.append(f"❌ {schema_path}: {schema_error}")
                all_valid = False
            else:
                print(f"✅ {schema_path}: Valid JSON Schema")
        else:
            print(f"✅ {schema_path}: Valid JSON (JSON Schema validation skipped - library not available)")

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
    all_valid, errors = validate_odps_schemas(schemas_dir, strict=args.strict)

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

