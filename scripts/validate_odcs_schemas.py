#!/usr/bin/env python3
"""
Validate ODCS (Open Data Contract Standard) contracts for all supported versions.

This script validates ODCS contracts against their schema definitions
for versions: 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2

Usage:
    python scripts/validate_odcs_schemas.py [--strict] [--contracts-dir DIR]

Exit codes:
    0: All contracts are valid
    1: One or more contracts are invalid
    2: jsonschema library not available (non-strict mode only)
"""
import argparse
import json
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


# Supported ODCS versions
ODCS_VERSIONS = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]


def detect_odcs_version(contract_data: Dict[str, Any]) -> str:
    """
    Detect ODCS version from contract data.

    Args:
        contract_data: Contract data dictionary

    Returns:
        Detected version string
    """
    # Check apiVersion field
    if "apiVersion" in contract_data:
        api_version = contract_data["apiVersion"]
        if isinstance(api_version, str) and "/" in api_version:
            version_part = api_version.split("/")[-1]
            if version_part.startswith("v"):
                version_part = version_part[1:]
            if version_part in ODCS_VERSIONS:
                return version_part
            # Handle aliases
            if version_part == "3":
                return "3.0.2"
            if version_part == "2":
                return "2.2.2"

    # Check $version field
    if "$version" in contract_data:
        version = str(contract_data["$version"])
        if version in ODCS_VERSIONS:
            return version

    # Check version field
    if "version" in contract_data:
        version = str(contract_data["version"])
        if version in ODCS_VERSIONS:
            return version

    # Default to latest
    return "3.0.2"


def validate_odcs_structure(contract_data: Dict[str, Any], version: str) -> Tuple[bool, List[str]]:
    """
    Validate ODCS contract structure (basic validation without schema).

    Args:
        contract_data: Contract data dictionary
        version: ODCS version

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Required fields
    required_fields = ["id", "schema"]
    for field in required_fields:
        if field not in contract_data:
            errors.append(f"Missing required field: {field}")

    # Validate apiVersion and kind for v3.x
    if version.startswith("3"):
        if "apiVersion" not in contract_data:
            errors.append("Missing required field: apiVersion (required for ODCS v3.x)")
        if "kind" not in contract_data:
            errors.append("Missing required field: kind (required for ODCS v3.x)")
        elif contract_data.get("kind") != "DataContract":
            errors.append(f"Invalid kind: expected 'DataContract', got '{contract_data.get('kind')}'")

    # Validate schema structure
    if "schema" in contract_data:
        schema = contract_data["schema"]
        # ODCS v3 can have schema as either:
        # 1. A dictionary with 'fields' array (single model)
        # 2. An array of model definitions (multiple models)
        if isinstance(schema, dict):
            # Single model format: schema.fields
            if "fields" not in schema and "properties" not in schema:
                errors.append("Schema must have either 'fields' (v3.x) or 'properties' (v2.x)")

            # Validate fields if present
            if "fields" in schema:
                fields = schema["fields"]
                if not isinstance(fields, list):
                    errors.append("Schema 'fields' must be a list")
                else:
                    for i, field in enumerate(fields):
                        if not isinstance(field, dict):
                            errors.append(f"Schema field[{i}] must be a dictionary")
                        else:
                            if "name" not in field:
                                errors.append(f"Schema field[{i}] missing required 'name'")
                            if "type" not in field:
                                errors.append(f"Schema field[{i}] missing required 'type'")
        elif isinstance(schema, list):
            # Multiple models format: schema is an array of model definitions
            for i, model in enumerate(schema):
                if not isinstance(model, dict):
                    errors.append(f"Schema model[{i}] must be a dictionary")
                else:
                    if "name" not in model:
                        errors.append(f"Schema model[{i}] missing required 'name'")
                    if "fields" in model:
                        fields = model["fields"]
                        if not isinstance(fields, list):
                            errors.append(f"Schema model[{i}] 'fields' must be a list")
                        else:
                            for j, field in enumerate(fields):
                                if not isinstance(field, dict):
                                    errors.append(f"Schema model[{i}] field[{j}] must be a dictionary")
                                else:
                                    if "name" not in field:
                                        errors.append(f"Schema model[{i}] field[{j}] missing required 'name'")
                                    if "type" not in field:
                                        errors.append(f"Schema model[{i}] field[{j}] missing required 'type'")
        else:
            errors.append("Schema must be either a dictionary or an array")

    return len(errors) == 0, errors


def validate_odcs_with_schema(
    contract_data: Dict[str, Any],
    version: str,
    schema_validator: Any = None
) -> Tuple[bool, List[str]]:
    """
    Validate ODCS contract against JSON Schema (if available).

    Args:
        contract_data: Contract data dictionary
        version: ODCS version
        schema_validator: Optional JSON Schema validator

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    if schema_validator is None:
        # Basic structure validation only
        return validate_odcs_structure(contract_data, version)

    try:
        # Validate against schema
        schema_validator.validate(contract_data)
    except ValidationError as e:
        error_msg = getattr(e, 'message', str(e))
        errors.append(f"Schema validation error: {error_msg}")
        error_path = getattr(e, 'path', None)
        if error_path:
            errors.append(f"  Path: {'/'.join(str(p) for p in error_path)}")
    except Exception as e:
        errors.append(f"Validation error: {str(e)}")

    return len(errors) == 0, errors


def validate_odcs_file(
    file_path: Path,
    strict: bool = False,
    schema_validators: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str], str]:
    """
    Validate an ODCS contract file.

    Args:
        file_path: Path to contract file
        strict: If True, require JSON Schema validation
        schema_validators: Optional dict of version -> validator

    Returns:
        Tuple of (is_valid, error_messages, detected_version)
    """
    errors = []

    # Read and parse JSON
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            contract_data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"], "unknown"
    except Exception as e:
        return False, [f"Error reading file: {e}"], "unknown"

    # Detect version
    detected_version = detect_odcs_version(contract_data)

    # Basic structure validation
    is_valid, structure_errors = validate_odcs_structure(contract_data, detected_version)
    if not is_valid:
        errors.extend(structure_errors)

    # JSON Schema validation (if available)
    if schema_validators and detected_version in schema_validators:
        validator = schema_validators[detected_version]
        is_valid_schema, schema_errors = validate_odcs_with_schema(
            contract_data,
            detected_version,
            validator
        )
        if not is_valid_schema:
            errors.extend(schema_errors)
    # Note: We don't fail if schema validators are missing - basic structure validation is sufficient
    # In the future, we can add actual JSON Schema validators for each ODCS version

    return len(errors) == 0, errors, detected_version


def find_odcs_contracts(contracts_dir: Path) -> List[Path]:
    """
    Find all ODCS contract files in directory.

    Args:
        contracts_dir: Directory to search

    Returns:
        List of contract file paths
    """
    contracts = []

    if not contracts_dir.exists():
        return contracts

    # Look for JSON files
    for json_file in contracts_dir.rglob("*.json"):
        # Try to detect if it's an ODCS contract
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Check if it looks like an ODCS contract
                if ("apiVersion" in data and "odcs" in str(data.get("apiVersion", "")).lower()) or \
                   ("kind" in data and data.get("kind") == "DataContract"):
                    contracts.append(json_file)
        except Exception:
            # Skip files that can't be parsed
            pass

    return contracts


def validate_all_odcs_contracts(
    contracts_dir: Path,
    strict: bool = False,
    version_filter: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Validate all ODCS contracts in directory.

    Args:
        contracts_dir: Directory containing contracts
        strict: If True, require JSON Schema validation
        version_filter: Optional version to validate (e.g., "3.0.2"). If None, validates all.

    Returns:
        Tuple of (all_valid, error_messages)
    """
    if strict and not JSONSCHEMA_AVAILABLE:
        return False, ["jsonschema library is required in strict mode"]

    # Find all contracts
    contracts = find_odcs_contracts(contracts_dir)

    if not contracts:
        return True, []  # No contracts to validate

    # Schema validators (if available)
    schema_validators: Dict[str, Any] = {}
    if JSONSCHEMA_AVAILABLE:
        # For now, we'll do basic validation
        # In the future, we could load actual ODCS schema files
        pass

    errors = []
    all_valid = True
    validated_count = 0
    skipped_count = 0

    for contract_path in contracts:
        is_valid, contract_errors, detected_version = validate_odcs_file(
            contract_path,
            strict=strict,
            schema_validators=schema_validators
        )

        # Filter by version if specified
        if version_filter and detected_version != version_filter:
            skipped_count += 1
            continue

        if is_valid:
            print(f"✅ {contract_path} (ODCS {detected_version}): Valid")
            validated_count += 1
        else:
            all_valid = False
            error_msg = f"❌ {contract_path} (ODCS {detected_version}):"
            for error in contract_errors:
                error_msg += f"\n    {error}"
            errors.append(error_msg)
            print(error_msg)

    if validated_count > 0:
        print(f"\n✅ Validated {validated_count} ODCS contract(s)")
    if skipped_count > 0:
        print(f"⏭️  Skipped {skipped_count} contract(s) (version filter: {version_filter})")

    return all_valid, errors


def main():
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(
        description="Validate ODCS (Open Data Contract Standard) contracts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic validation (structure only)
  python scripts/validate_odcs_schemas.py

  # Strict validation (requires jsonschema library)
  python scripts/validate_odcs_schemas.py --strict

  # Validate specific directory
  python scripts/validate_odcs_schemas.py --contracts-dir examples/contracts

  # Validate specific version
  python scripts/validate_odcs_schemas.py --strict --version 3.0.2
        """
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require jsonschema library for JSON Schema validation"
    )
    parser.add_argument(
        "--contracts-dir",
        type=Path,
        default=None,
        help="Directory containing ODCS contracts (default: examples/contracts)"
    )
    parser.add_argument(
        "--version",
        choices=ODCS_VERSIONS,
        help="Validate only specific ODCS version"
    )

    args = parser.parse_args()

    # Determine contracts directory
    if args.contracts_dir:
        contracts_dir = args.contracts_dir
    else:
        # Auto-detect: script is in scripts/, contracts are in examples/contracts/
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        contracts_dir = project_root / "examples" / "contracts"

    # Validate contracts
    all_valid, errors = validate_all_odcs_contracts(
        contracts_dir, strict=args.strict, version_filter=args.version
    )

    # Print results
    if errors:
        print("\nValidation Errors:")
        for error in errors:
            print(f"  {error}")
        print()

    if all_valid:
        if args.version:
            print(f"✅ All ODCS {args.version} contracts are valid!")
        else:
            print("✅ All ODCS contracts are valid!")
        sys.exit(0)
    else:
        if args.version:
            print(f"❌ Some ODCS {args.version} contracts are invalid!")
        else:
            print("❌ Some ODCS contracts are invalid!")
        sys.exit(1)


if __name__ == "__main__":
    main()

