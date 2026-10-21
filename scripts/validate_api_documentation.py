#!/usr/bin/env python3
"""
Validate API documentation completeness.

This script validates that all API endpoints are properly documented
and all required documentation files exist.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_file_exists(file_path, description):
    """Check if file exists."""
    full_path = project_root / file_path
    if full_path.exists():
        print(f"✓ {description}: {file_path}")
        return True
    else:
        print(f"✗ {description}: {file_path} - MISSING")
        return False


def check_documentation_files():
    """Check all required documentation files exist."""
    print("Checking Documentation Files")
    print("=" * 50)
    print()

    required_files = [
        ("docs/API_DOCUMENTATION.md", "API Documentation"),
        ("docs/API_BEST_PRACTICES.md", "API Best Practices"),
        ("docs/API_ERROR_CODES.md", "API Error Codes"),
        ("docs/API_ENDPOINTS_REFERENCE.md", "API Endpoints Reference"),
        ("docs/API_CHANGELOG.md", "API Changelog"),
        ("docs/DEVELOPER_GUIDE_NORMALIZATION.md", "Normalization Developer Guide"),
        ("docs/DEVELOPER_GUIDE_LINEAGE.md", "Lineage Developer Guide"),
        ("docs/DEVELOPER_GUIDE_IMPLEMENTATION_PATTERNS.md", "Implementation Patterns Guide"),
        ("docs/USER_GUIDE_CONTRACTS.md", "Contracts User Guide"),
        ("docs/PERFORMANCE_OPTIMIZATIONS.md", "Performance Optimizations"),
        ("examples/README.md", "Examples README"),
        ("examples/contracts/odcs_complete_example.json", "Complete ODCS Example"),
        ("examples/contracts/odcs_minimal_example.json", "Minimal ODCS Example"),
        ("examples/api/create_contract.py", "Create Contract Example"),
        ("examples/api/list_contracts_with_filters.py", "List Contracts Example"),
        ("examples/api/get_lineage.py", "Get Lineage Example"),
    ]

    all_exist = True
    for file_path, description in required_files:
        if not check_file_exists(file_path, description):
            all_exist = False

    return all_exist


def check_openapi_endpoints():
    """Check OpenAPI endpoints are configured."""
    print()
    print("Checking OpenAPI Configuration")
    print("=" * 50)
    print()

    # Check views.py has OpenAPI views
    views_file = project_root / "hub/apps/api/views.py"
    if views_file.exists():
        content = views_file.read_text()
        if "OpenAPISchemaView" in content and "SwaggerUIView" in content and "ReDocView" in content:
            print("✓ OpenAPI views configured")
        else:
            print("✗ OpenAPI views not found")
            return False

    # Check urls.py has OpenAPI routes
    urls_file = project_root / "hub/urls.py"
    if urls_file.exists():
        content = urls_file.read_text()
        if "api-docs" in content:
            print("✓ OpenAPI routes configured")
        else:
            print("✗ OpenAPI routes not found")
            return False

    # Check settings.py has drf-spectacular configured
    settings_file = project_root / "hub/settings.py"
    if settings_file.exists():
        content = settings_file.read_text()
        if "drf_spectacular" in content and "SPECTACULAR_SETTINGS" in content:
            print("✓ drf-spectacular configured")
        else:
            print("✗ drf-spectacular not configured")
            return False

    return True


def check_example_code():
    """Check example code files."""
    print()
    print("Checking Example Code")
    print("=" * 50)
    print()

    example_files = [
        "examples/api/create_contract.py",
        "examples/api/list_contracts_with_filters.py",
        "examples/api/get_lineage.py",
    ]

    all_exist = True
    for file_path in example_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - MISSING")
            all_exist = False

    return all_exist


def main():
    """Main validation function."""
    print("API Documentation Validation")
    print("=" * 50)
    print()

    results = {
        "documentation_files": check_documentation_files(),
        "openapi_config": check_openapi_endpoints(),
        "example_code": check_example_code(),
    }

    print()
    print("Validation Summary")
    print("=" * 50)
    print()

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{check}: {status}")

    print()
    if all_passed:
        print("All documentation checks passed!")
        sys.exit(0)
    else:
        print("Some documentation checks failed. Please review and fix.")
        sys.exit(1)


if __name__ == "__main__":
    main()
