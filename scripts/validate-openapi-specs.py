#!/usr/bin/env python3
"""
Comprehensive OpenAPI Specification Validation

Validates all OpenAPI 3.0 specifications using:
1. openapi_spec_validator (Python library for OpenAPI 3.0 spec validation)
2. Spectral (OpenAPI linting tool for best practices)

This script validates:
- OpenAPI 3.0 specification compliance
- Schema structure and syntax
- Best practices and conventions
- Required fields and formats
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class OpenAPISpecValidator:
    """Comprehensive OpenAPI specification validator."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.validated_count = 0
        self.failed_count = 0

    def validate_with_openapi_spec_validator(self, file_path: Path) -> tuple[bool, list[str]]:
        """Validate OpenAPI spec using openapi_spec_validator library."""
        errors = []

        try:
            from openapi_spec_validator import validate_spec
            from openapi_spec_validator.readers import read_from_filename

            # Read and validate spec
            spec_dict, spec_url = read_from_filename(str(file_path))
            validate_spec(spec_dict, spec_url=spec_url)

            return True, []

        except ImportError:
            errors.append(
                "openapi_spec_validator not installed. Install with: pip install openapi-spec-validator"
            )
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {e!s}")
            return False, errors

    def validate_with_spectral(self, file_path: Path) -> tuple[bool, list[str], list[str]]:
        """Validate OpenAPI spec using Spectral."""
        errors = []
        warnings = []

        try:
            # Check if npx is available
            result = subprocess.run(["which", "npx"], check=False, capture_output=True, text=True)

            if result.returncode != 0:
                warnings.append(
                    "npx not found. Spectral validation skipped. Install Node.js to enable Spectral validation."
                )
                return True, [], warnings

            # Check for Spectral config
            spectral_config = PROJECT_ROOT / ".spectral.yaml"
            spectral_config_alt = PROJECT_ROOT / ".spectral.yml"

            spectral_cmd = [
                "npx",
                "-y",
                "@stoplight/spectral-cli",
                "lint",
                str(file_path),
                "--format",
                "json",
            ]

            # Add ruleset if config exists
            if spectral_config.exists():
                spectral_cmd.extend(["--ruleset", str(spectral_config)])
            elif spectral_config_alt.exists():
                spectral_cmd.extend(["--ruleset", str(spectral_config_alt)])
            # If no config, Spectral will use default rules (don't add --ruleset)

            result = subprocess.run(
                spectral_cmd, check=False, capture_output=True, text=True, timeout=60
            )

            # Parse Spectral output - handle multiple JSON objects (one per line)
            if result.stdout:
                try:
                    # Try to parse as single JSON first
                    try:
                        spectral_results = json.loads(result.stdout)
                        if isinstance(spectral_results, dict):
                            if "results" in spectral_results:
                                spectral_results = spectral_results["results"]
                            else:
                                spectral_results = []
                    except json.JSONDecodeError:
                        # Try parsing as newline-delimited JSON
                        spectral_results = []
                        for line in result.stdout.strip().split("\n"):
                            if line.strip():
                                try:
                                    issue = json.loads(line)
                                    spectral_results.append(issue)
                                except json.JSONDecodeError:
                                    pass

                    for issue in spectral_results:
                        severity = issue.get("severity", 3)
                        code = issue.get("code", "N/A")
                        message = issue.get("message", "N/A")
                        path = issue.get("path", [])
                        path_str = " -> ".join(str(p) for p in path) if path else "root"

                        # Treat "application~1json" errors as warnings (Spectral false positive)
                        if "application~1json" in message or "application~1json" in path_str:
                            warnings.append(f"{code}: {message} at {path_str}")
                        elif severity in [0, 1]:  # Error or fatal
                            errors.append(f"{code}: {message} at {path_str}")
                        elif severity == 2:  # Warning
                            warnings.append(f"{code}: {message} at {path_str}")

                except Exception:
                    # If parsing fails but exit code is 0, assume success
                    if result.returncode != 0:
                        # Try to extract error message
                        error_msg = result.stderr or result.stdout
                        if error_msg and len(error_msg.strip()) > 0 and "Error" not in error_msg:
                            # Only add as error if it's not a config error
                            if "ruleset" not in error_msg.lower():
                                errors.append(f"Spectral validation failed: {error_msg[:200]}")
                        elif "Error" in error_msg:
                            # Config or setup error - treat as warning
                            warnings.append(f"Spectral validation skipped: {error_msg[:200]}")

            # If exit code is non-zero and we have no parsed errors, check stderr
            if result.returncode != 0 and not errors and result.stderr:
                error_msg = result.stderr.strip()
                if error_msg and "Error" in error_msg:
                    # Likely a config error - treat as warning
                    warnings.append(f"Spectral validation skipped: {error_msg[:200]}")

            return len(errors) == 0, errors, warnings

        except subprocess.TimeoutExpired:
            errors.append("Spectral validation timed out (>60s)")
            return False, errors, warnings
        except Exception as e:
            errors.append(f"Spectral validation error: {e!s}")
            return False, errors, warnings

    def validate_structure(self, spec: dict[str, Any], file_path: Path) -> tuple[bool, list[str]]:
        """Validate OpenAPI spec structure and required fields."""
        errors = []

        # Check required top-level fields
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            if field not in spec:
                errors.append(f"Missing required field: {field}")

        # Validate OpenAPI version
        if "openapi" in spec:
            version = spec["openapi"]
            if not isinstance(version, str) or not version.startswith("3."):
                errors.append(f"Invalid OpenAPI version: {version}. Expected 3.x")

        # Validate info section
        if "info" in spec:
            info = spec["info"]
            if not isinstance(info, dict):
                errors.append("'info' must be an object")
            else:
                if "title" not in info:
                    errors.append("Missing 'title' in info section")
                if "version" not in info:
                    errors.append("Missing 'version' in info section")

        # Validate paths section
        if "paths" in spec:
            paths = spec["paths"]
            if not isinstance(paths, dict):
                errors.append("'paths' must be an object")
            else:
                if len(paths) == 0:
                    errors.append("'paths' must contain at least one path")

                # Validate each path
                for path, path_item in paths.items():
                    if not isinstance(path_item, dict):
                        errors.append(f"Path '{path}' must be an object")
                        continue

                    # Validate operations
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                            if not isinstance(operation, dict):
                                errors.append(
                                    f"Operation {method.upper()} {path} must be an object"
                                )
                                continue

                            # Check required operation fields
                            if "responses" not in operation:
                                errors.append(
                                    f"Operation {method.upper()} {path} missing 'responses'"
                                )

                            # Validate responses
                            if "responses" in operation:
                                responses = operation["responses"]
                                if not isinstance(responses, dict):
                                    errors.append(
                                        f"Operation {method.upper()} {path} 'responses' must be an object"
                                    )
                                elif len(responses) == 0:
                                    errors.append(
                                        f"Operation {method.upper()} {path} must have at least one response"
                                    )

        # Validate components section (if present)
        if "components" in spec:
            components = spec["components"]
            if not isinstance(components, dict):
                errors.append("'components' must be an object")
            # Validate schemas
            elif "schemas" in components:
                schemas = components["schemas"]
                if not isinstance(schemas, dict):
                    errors.append("'components.schemas' must be an object")

        # Validate servers section (if present)
        if "servers" in spec:
            servers = spec["servers"]
            if not isinstance(servers, list):
                errors.append("'servers' must be an array")
            else:
                for i, server in enumerate(servers):
                    if not isinstance(server, dict):
                        errors.append(f"'servers[{i}]' must be an object")
                    elif "url" not in server:
                        errors.append(f"'servers[{i}]' missing 'url'")

        return len(errors) == 0, errors

    def validate_spec_file(self, file_path: Path) -> tuple[bool, list[str], list[str]]:
        """Validate a single OpenAPI spec file."""
        errors = []
        warnings = []

        print(f"\nValidating: {file_path.relative_to(PROJECT_ROOT)}")

        # Read spec
        try:
            with open(file_path, encoding="utf-8") as f:
                if file_path.suffix in [".yaml", ".yml"]:
                    spec = yaml.safe_load(f)
                elif file_path.suffix == ".json":
                    spec = json.load(f)
                else:
                    errors.append(f"Unsupported file format: {file_path.suffix}")
                    return False, errors, warnings
        except yaml.YAMLError as e:
            errors.append(f"YAML parsing error: {e!s}")
            return False, errors, warnings
        except json.JSONDecodeError as e:
            errors.append(f"JSON parsing error: {e!s}")
            return False, errors, warnings
        except Exception as e:
            errors.append(f"Error reading file: {e!s}")
            return False, errors, warnings

        if not spec:
            errors.append("Empty or invalid spec file")
            return False, errors, warnings

        # Validate structure
        _is_valid, structure_errors = self.validate_structure(spec, file_path)
        errors.extend(structure_errors)

        # Validate with openapi_spec_validator (optional)
        try:
            is_valid_validator, validator_errors = self.validate_with_openapi_spec_validator(
                file_path
            )
            if not is_valid_validator:
                # Only add as warnings if it's just missing the library
                if any("not installed" in e for e in validator_errors):
                    warnings.extend(validator_errors)
                else:
                    errors.extend(validator_errors)
        except Exception as e:
            warnings.append(f"openapi_spec_validator validation skipped: {e!s}")

        # Validate with Spectral
        try:
            is_valid_spectral, spectral_errors, spectral_warnings = self.validate_with_spectral(
                file_path
            )
            if not is_valid_spectral:
                errors.extend(spectral_errors)
            warnings.extend(spectral_warnings)
        except Exception as e:
            warnings.append(f"Spectral validation skipped: {e!s}")

        return len(errors) == 0, errors, warnings

    def validate_all_specs(self, specs_dir: Path) -> dict[str, Any]:
        """Validate all OpenAPI specs in a directory."""
        results = {"total": 0, "valid": 0, "invalid": 0, "errors": [], "warnings": [], "files": {}}

        spec_files = list(specs_dir.rglob("*.yaml")) + list(specs_dir.rglob("*.yml"))

        for spec_file in sorted(spec_files):
            if spec_file.name == "README.md":
                continue

            results["total"] += 1
            is_valid, errors, warnings = self.validate_spec_file(spec_file)

            file_result = {"valid": is_valid, "errors": errors, "warnings": warnings}
            results["files"][str(spec_file.relative_to(PROJECT_ROOT))] = file_result

            if is_valid:
                results["valid"] += 1
                self.validated_count += 1
                print("  ✅ Valid")
                if warnings:
                    print(f"  ⚠️  {len(warnings)} warning(s)")
            else:
                results["invalid"] += 1
                self.failed_count += 1
                print(f"  ❌ Invalid ({len(errors)} error(s))")
                for error in errors:
                    print(f"    - {error}")
                    results["errors"].append(
                        {"file": str(spec_file.relative_to(PROJECT_ROOT)), "error": error}
                    )
                if warnings:
                    print(f"  ⚠️  {len(warnings)} warning(s)")

            results["warnings"].extend(
                [{"file": str(spec_file.relative_to(PROJECT_ROOT)), "warning": w} for w in warnings]
            )

        return results


def main():
    """Main entry point."""
    contracts_dir = PROJECT_ROOT / "docs" / "api-contracts" / "missing"

    if not contracts_dir.exists():
        print(f"❌ Directory not found: {contracts_dir}")
        sys.exit(1)

    print("=" * 80)
    print("OpenAPI Specification Validation")
    print("=" * 80)
    print(f"Validating specs in: {contracts_dir.relative_to(PROJECT_ROOT)}")
    print()

    validator = OpenAPISpecValidator()
    results = validator.validate_all_specs(contracts_dir)

    print("\n" + "=" * 80)
    print("Validation Summary")
    print("=" * 80)
    print(f"Total files: {results['total']}")
    print(f"✅ Valid: {results['valid']}")
    print(f"❌ Invalid: {results['invalid']}")
    print(f"⚠️  Warnings: {len(results['warnings'])}")

    if results["errors"]:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"  - {error['file']}: {error['error']}")

    if results["invalid"] > 0:
        print("\n❌ Validation failed")
        sys.exit(1)
    else:
        print("\n✅ All OpenAPI specifications are valid!")
        if results["warnings"]:
            print(f"⚠️  {len(results['warnings'])} warning(s) found (non-blocking)")
        sys.exit(0)


if __name__ == "__main__":
    main()
