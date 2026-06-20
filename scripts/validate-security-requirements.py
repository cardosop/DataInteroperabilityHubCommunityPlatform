#!/usr/bin/env python3
"""
Validate Security Requirements in OpenAPI Specifications

Validates that all OpenAPI 3.0 specifications have comprehensive security requirements:
- Authentication methods documented
- Authorization rules documented
- Rate limiting requirements documented
- Input validation requirements documented
- Security schemes properly defined
"""

import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def validate_security_requirements(file_path: Path) -> tuple[bool, list[str]]:
    """Validate security requirements in a single OpenAPI spec file."""
    errors = []
    warnings = []

    try:
        # Read spec
        with open(file_path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)

        if not spec or "openapi" not in spec:
            errors.append("Not a valid OpenAPI spec")
            return False, errors

        # Validate security schemes
        if "components" not in spec or "securitySchemes" not in spec["components"]:
            errors.append("Missing securitySchemes in components")
        else:
            security_schemes = spec["components"]["securitySchemes"]

            # Check for BearerAuth
            if "BearerAuth" not in security_schemes:
                errors.append("Missing BearerAuth security scheme")
            else:
                bearer_auth = security_schemes["BearerAuth"]
                if "description" not in bearer_auth or len(bearer_auth["description"]) < 50:
                    warnings.append("BearerAuth description is too short or missing")

            # Check for ApiKeyAuth
            if "ApiKeyAuth" not in security_schemes:
                errors.append("Missing ApiKeyAuth security scheme")
            else:
                api_key_auth = security_schemes["ApiKeyAuth"]
                if "description" not in api_key_auth or len(api_key_auth["description"]) < 50:
                    warnings.append("ApiKeyAuth description is too short or missing")

        # Validate paths
        if "paths" not in spec:
            errors.append("Missing paths section")
        else:
            for path, path_item in spec["paths"].items():
                if isinstance(path_item, dict):
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "patch", "delete"] and isinstance(
                            operation, dict
                        ):
                            # Check description contains security info
                            description = operation.get("description", "")

                            # Check for authentication documentation
                            if (
                                "Authentication" not in description
                                and "authentication" not in description.lower()
                            ):
                                warnings.append(
                                    f"{method.upper()} {path}: Missing authentication documentation in description"
                                )

                            # Check for rate limiting documentation
                            if (
                                "Rate Limiting" not in description
                                and "rate limit" not in description.lower()
                            ):
                                warnings.append(
                                    f"{method.upper()} {path}: Missing rate limiting documentation in description"
                                )

                            # Check for input validation documentation
                            if (
                                "Input Validation" not in description
                                and "input validation" not in description.lower()
                            ):
                                warnings.append(
                                    f"{method.upper()} {path}: Missing input validation documentation in description"
                                )

                            # Check for security array (if auth required)
                            if "security" not in operation:
                                # Check if auth should be required based on description
                                if "Required" in description and "Authentication" in description:
                                    warnings.append(
                                        f"{method.upper()} {path}: Missing security array but authentication is required"
                                    )

                            # Check for 429 response with rate limit headers
                            if "responses" in operation and "429" in operation["responses"]:
                                response_429 = operation["responses"]["429"]
                                if "headers" not in response_429:
                                    warnings.append(
                                        f"{method.upper()} {path}: 429 response missing rate limit headers"
                                    )
                                else:
                                    headers = response_429["headers"]
                                    required_headers = [
                                        "X-RateLimit-Limit",
                                        "X-RateLimit-Remaining",
                                        "X-RateLimit-Reset",
                                        "Retry-After",
                                    ]
                                    for header in required_headers:
                                        if header not in headers:
                                            warnings.append(
                                                f"{method.upper()} {path}: 429 response missing {header} header"
                                            )

        return len(errors) == 0, errors + warnings

    except Exception as e:
        return False, [f"Error reading file: {e}"]


def main():
    """Main entry point."""
    contracts_dir = PROJECT_ROOT / "docs" / "api-contracts" / "missing"

    if not contracts_dir.exists():
        print(f"❌ Directory not found: {contracts_dir}")
        sys.exit(1)

    print("Validating security requirements in OpenAPI specs")
    print("=" * 80)

    spec_files = list(contracts_dir.rglob("*.yaml")) + list(contracts_dir.rglob("*.yml"))
    total_errors = 0
    total_warnings = 0
    validated_count = 0

    for spec_file in sorted(spec_files):
        if spec_file.name == "README.md":
            continue

        print(f"\nValidating: {spec_file.relative_to(PROJECT_ROOT)}")
        _is_valid, issues = validate_security_requirements(spec_file)

        errors = [i for i in issues if not i.startswith("Warning:")]
        warnings = [i for i in issues if i.startswith("Warning:")]

        if errors:
            print(f"  ❌ Errors ({len(errors)}):")
            for error in errors:
                print(f"    - {error}")
            total_errors += len(errors)

        if warnings:
            print(f"  ⚠️  Warnings ({len(warnings)}):")
            for warning in warnings:
                print(f"    - {warning}")
            total_warnings += len(warnings)

        if not errors and not warnings:
            print("  ✅ All security requirements validated")
            validated_count += 1

    print("\n" + "=" * 80)
    print("Validation Summary:")
    print(
        f"  ✅ Validated: {validated_count}/{len([f for f in spec_files if f.name != 'README.md'])} files"
    )
    print(f"  ❌ Errors: {total_errors}")
    print(f"  ⚠️  Warnings: {total_warnings}")

    if total_errors > 0:
        print("\n❌ Validation failed with errors")
        sys.exit(1)
    elif total_warnings > 0:
        print("\n⚠️  Validation passed with warnings")
        sys.exit(0)
    else:
        print("\n✅ All security requirements validated successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
