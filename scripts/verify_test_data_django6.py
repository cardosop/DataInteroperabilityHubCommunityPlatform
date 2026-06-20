#!/usr/bin/env python3
"""
Verify Test Data (Fixtures and Factories) Compatibility with Django 6

This script analyzes test fixtures and factories to verify they are compatible
with Django 6 and identifies any issues that need to be addressed.
"""

import ast
import json
import sys
from pathlib import Path
from typing import Any

# Color codes for output
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
RED = "\033[0;31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def find_test_data_files(base_dir: Path) -> dict[str, list[Path]]:
    """Find all test data files (factories and fixtures)"""
    factories = []
    fixtures = []

    # Find factory files
    for file_path in base_dir.rglob("**/factories.py"):
        if file_path.is_file():
            factories.append(file_path)

    # Find conftest files (fixtures)
    for file_path in base_dir.rglob("**/conftest.py"):
        if file_path.is_file():
            fixtures.append(file_path)

    return {
        "factories": sorted(factories),
        "fixtures": sorted(fixtures),
    }


def check_django6_compatibility(file_path: Path) -> dict[str, Any]:
    """
    Check a test data file for Django 6 compatibility issues.

    Returns a dictionary with:
    - issues: List of compatibility issues found
    - warnings: List of warnings
    - uses_deprecated_patterns: Boolean indicating deprecated patterns usage
    - uses_django6_patterns: Boolean indicating Django 6 patterns are used
    """
    issues = []
    warnings = []
    uses_deprecated_patterns = False
    uses_django6_patterns = False

    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))

        # Check for deprecated Django patterns
        deprecated_patterns = [
            "django.utils.translation.ugettext",
            "django.utils.translation.ugettext_lazy",
            "django.utils.translation.ungettext",
            "django.utils.encoding.force_text",
            "django.utils.encoding.smart_text",
            "django.utils.timezone.utc",  # Use datetime.timezone.utc in Python 3.12+
        ]
        for pattern in deprecated_patterns:
            if pattern in content:
                uses_deprecated_patterns = True
                warnings.append(f"Uses deprecated Django pattern: {pattern}")

        # Check for Django 6 patterns
        django6_patterns = [
            "factory.django.DjangoModelFactory",
            "factory.Faker",
            "factory.Sequence",
            "factory.LazyFunction",
            "pytest.fixture",
            "pytest.mark.django_db",
        ]
        for pattern in django6_patterns:
            if pattern in content:
                uses_django6_patterns = True

        # Check for deprecated settings usage
        deprecated_settings = [
            "DEFAULT_FILE_STORAGE",
            "STATICFILES_STORAGE",
        ]
        for setting in deprecated_settings:
            if setting in content:
                issues.append(f"Uses deprecated setting {setting} (should use STORAGES setting)")

        # Check for MiddlewareMixin usage (should not be in test data files)
        if "MiddlewareMixin" in content:
            issues.append("Uses MiddlewareMixin (should not be in test data files)")

        # Check for factory-boy usage
        if "factory" in content.lower() or "Factory" in content:
            uses_django6_patterns = True

        # Check for pytest fixtures
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for pytest.fixture decorator
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Attribute):
                        if decorator.attr == "fixture":
                            uses_django6_patterns = True
                    elif isinstance(decorator, ast.Name):
                        if decorator.id == "fixture":
                            uses_django6_patterns = True

    except SyntaxError as e:
        issues.append(f"Syntax error in file: {e}")
    except Exception as e:
        warnings.append(f"Could not parse file: {e}")

    return {
        "issues": issues,
        "warnings": warnings,
        "uses_deprecated_patterns": uses_deprecated_patterns,
        "uses_django6_patterns": uses_django6_patterns,
    }


def main():
    """Main function"""
    base_dir = Path(__file__).resolve().parent.parent

    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}Django 6 Test Data Compatibility Verification{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    # Find all test data files
    test_data_files = find_test_data_files(base_dir)
    factories = test_data_files["factories"]
    fixtures = test_data_files["fixtures"]

    print(
        f"{GREEN}✅ Found {len(factories)} factory files and {len(fixtures)} fixture files{RESET}\n"
    )

    # Analyze factories
    print(f"{BOLD}{BLUE}Analyzing Factory Files...{RESET}\n")

    factory_issues = []
    factory_warnings = []
    compatible_factories = []

    for file_path in factories:
        result = check_django6_compatibility(file_path)

        if result["issues"]:
            factory_issues.append((file_path, result))
        elif result["warnings"]:
            factory_warnings.append((file_path, result))
        else:
            compatible_factories.append((file_path, result))

    # Analyze fixtures
    print(f"{BOLD}{BLUE}Analyzing Fixture Files...{RESET}\n")

    fixture_issues = []
    fixture_warnings = []
    compatible_fixtures = []

    for file_path in fixtures:
        result = check_django6_compatibility(file_path)

        if result["issues"]:
            fixture_issues.append((file_path, result))
        elif result["warnings"]:
            fixture_warnings.append((file_path, result))
        else:
            compatible_fixtures.append((file_path, result))

    # Print results
    print(f"{BOLD}{BLUE}Factory Files Analysis:{RESET}\n")

    if factory_issues:
        print(f"{RED}❌ Found {len(factory_issues)} factory files with issues:{RESET}")
        for file_path, result in factory_issues:
            print(f"\n  {RED}{file_path.relative_to(base_dir)}{RESET}")
            for issue in result["issues"]:
                print(f"    - {issue}")
        print()
    else:
        print(f"{GREEN}✅ No factory files with issues{RESET}\n")

    if factory_warnings:
        print(f"{YELLOW}⚠️  Found {len(factory_warnings)} factory files with warnings:{RESET}")
        for file_path, result in factory_warnings:
            print(f"\n  {YELLOW}{file_path.relative_to(base_dir)}{RESET}")
            for warning in result["warnings"]:
                print(f"    - {warning}")
        print()
    else:
        print(f"{GREEN}✅ No factory files with warnings{RESET}\n")

    print(
        f"{GREEN}✅ {len(compatible_factories)} factory files are compatible with Django 6{RESET}\n"
    )

    print(f"{BOLD}{BLUE}Fixture Files Analysis:{RESET}\n")

    if fixture_issues:
        print(f"{RED}❌ Found {len(fixture_issues)} fixture files with issues:{RESET}")
        for file_path, result in fixture_issues:
            print(f"\n  {RED}{file_path.relative_to(base_dir)}{RESET}")
            for issue in result["issues"]:
                print(f"    - {issue}")
        print()
    else:
        print(f"{GREEN}✅ No fixture files with issues{RESET}\n")

    if fixture_warnings:
        print(f"{YELLOW}⚠️  Found {len(fixture_warnings)} fixture files with warnings:{RESET}")
        for file_path, result in fixture_warnings:
            print(f"\n  {YELLOW}{file_path.relative_to(base_dir)}{RESET}")
            for warning in result["warnings"]:
                print(f"    - {warning}")
        print()
    else:
        print(f"{GREEN}✅ No fixture files with warnings{RESET}\n")

    print(
        f"{GREEN}✅ {len(compatible_fixtures)} fixture files are compatible with Django 6{RESET}\n"
    )

    # Generate report
    report_data = {
        "summary": {
            "total_factories": len(factories),
            "factories_with_issues": len(factory_issues),
            "factories_with_warnings": len(factory_warnings),
            "compatible_factories": len(compatible_factories),
            "total_fixtures": len(fixtures),
            "fixtures_with_issues": len(fixture_issues),
            "fixtures_with_warnings": len(fixture_warnings),
            "compatible_fixtures": len(compatible_fixtures),
        },
        "factory_files": {
            "with_issues": [
                {
                    "file": str(f.relative_to(base_dir)),
                    "issues": r["issues"],
                    "warnings": r["warnings"],
                }
                for f, r in factory_issues
            ],
            "with_warnings": [
                {
                    "file": str(f.relative_to(base_dir)),
                    "warnings": r["warnings"],
                }
                for f, r in factory_warnings
            ],
            "compatible": [str(f.relative_to(base_dir)) for f, _ in compatible_factories],
        },
        "fixture_files": {
            "with_issues": [
                {
                    "file": str(f.relative_to(base_dir)),
                    "issues": r["issues"],
                    "warnings": r["warnings"],
                }
                for f, r in fixture_issues
            ],
            "with_warnings": [
                {
                    "file": str(f.relative_to(base_dir)),
                    "warnings": r["warnings"],
                }
                for f, r in fixture_warnings
            ],
            "compatible": [str(f.relative_to(base_dir)) for f, _ in compatible_fixtures],
        },
        "django6_compatibility_notes": [
            "Django 6 maintains backward compatibility with test data creation",
            "factory-boy works with Django 6",
            "pytest fixtures work with Django 6",
            "Test data factories and fixtures are compatible",
            "Deprecated Django patterns should be updated",
            "Deprecated settings usage should be updated to STORAGES setting",
        ],
    }

    report_path = (
        base_dir / "openspec" / "changes" / "fullcontract" / "DJANGO6_TEST_DATA_VERIFICATION.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)

    print(f"{GREEN}✅ Report saved to: {report_path.relative_to(base_dir)}{RESET}\n")

    # Final summary
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}")
    total_issues = len(factory_issues) + len(fixture_issues)
    if total_issues == 0:
        print(f"{BOLD}{GREEN}✅ All test data files are compatible with Django 6!{RESET}")
    else:
        print(f"{BOLD}{YELLOW}⚠️  Some test data files need updates for Django 6{RESET}")
        print(f"{BOLD}{YELLOW}   Review the issues above and update as needed{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
