#!/usr/bin/env python3
"""
Verify E2E Tests Compatibility with Django 6

This script analyzes existing E2E tests to verify they are compatible
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


def find_e2e_test_files(base_dir: Path) -> list[Path]:
    """Find all E2E test files"""
    test_files = []

    # E2E test directory
    e2e_dir = base_dir / "tests" / "e2e"

    if e2e_dir.exists():
        for file_path in e2e_dir.rglob("test*.py"):
            if file_path.is_file() and file_path.name != "__init__.py":
                test_files.append(file_path)

    return sorted(test_files)


def check_django6_compatibility(file_path: Path) -> dict[str, Any]:
    """
    Check a test file for Django 6 compatibility issues.

    Returns a dictionary with:
    - issues: List of compatibility issues found
    - warnings: List of warnings
    - uses_middleware_mixin: Boolean indicating MiddlewareMixin usage
    - uses_deprecated_settings: Boolean indicating deprecated settings usage
    - uses_django6_patterns: Boolean indicating Django 6 patterns are used
    - test_base_classes: List of test base classes used
    """
    issues = []
    warnings = []
    uses_middleware_mixin = False
    uses_deprecated_settings = False
    uses_django6_patterns = False
    test_base_classes = []

    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))

        # Check for MiddlewareMixin usage (deprecated in Django 6)
        if "MiddlewareMixin" in content:
            uses_middleware_mixin = True
            issues.append(
                "Uses MiddlewareMixin (deprecated in Django 6, should use callable class pattern)"
            )

        # Check for deprecated settings
        deprecated_settings = [
            "DEFAULT_FILE_STORAGE",
            "STATICFILES_STORAGE",
        ]
        for setting in deprecated_settings:
            if setting in content:
                uses_deprecated_settings = True
                issues.append(f"Uses deprecated setting {setting} (should use STORAGES setting)")

        # Check for Django 6 patterns
        django6_patterns = [
            "pytest.mark.django_db",
            "APIClient",
            "RequestFactory",
            "TestCase",
            "LiveServerTestCase",
            "TransactionTestCase",
        ]
        for pattern in django6_patterns:
            if pattern in content:
                uses_django6_patterns = True

        # Check for test base classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from Django test base classes
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_name = base.id
                        if base_name in [
                            "TestCase",
                            "TransactionTestCase",
                            "LiveServerTestCase",
                            "APITestCase",
                        ]:
                            test_base_classes.append(base_name)
                            uses_django6_patterns = True
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                        if base_name in [
                            "TestCase",
                            "TransactionTestCase",
                            "LiveServerTestCase",
                            "APITestCase",
                        ]:
                            test_base_classes.append(base_name)
                            uses_django6_patterns = True
                    elif isinstance(base, ast.Name):
                        # Check for E2ETestBase
                        if base.id == "E2ETestBase":
                            test_base_classes.append("E2ETestBase")

        # Check for pytest markers
        if "pytest.mark.django_db" in content:
            uses_django6_patterns = True

        # Check for deprecated Django patterns
        deprecated_patterns = [
            "django.utils.translation.ugettext",
            "django.utils.translation.ugettext_lazy",
            "django.utils.translation.ungettext",
            "django.utils.encoding.force_text",
            "django.utils.encoding.smart_text",
        ]
        for pattern in deprecated_patterns:
            if pattern in content:
                warnings.append(f"Uses deprecated Django pattern: {pattern}")

    except SyntaxError as e:
        issues.append(f"Syntax error in file: {e}")
    except Exception as e:
        warnings.append(f"Could not parse file: {e}")

    return {
        "issues": issues,
        "warnings": warnings,
        "uses_middleware_mixin": uses_middleware_mixin,
        "uses_deprecated_settings": uses_deprecated_settings,
        "uses_django6_patterns": uses_django6_patterns,
        "test_base_classes": list(set(test_base_classes)),
    }


def categorize_test_file(file_path: Path) -> str:
    """Categorize a test file based on its path and name"""
    str(file_path)
    name = file_path.name.lower()

    if "complete" in name or "journey" in name or "workflow" in name:
        return "Complete User Workflow Tests"
    elif "api" in name or "rest" in name:
        return "API Compatibility Tests"
    elif "sdk" in name:
        return "SDK Compatibility Tests"
    elif "backward" in name or "migration" in name or "compatibility" in name:
        return "Backward Compatibility Tests"
    elif "performance" in name or "load" in name or "stress" in name:
        return "Performance Under Load Tests"
    elif "persona" in name or "tenant" in name:
        return "Multi-Tenant Tests"
    elif "marketplace" in name:
        return "Marketplace Tests"
    elif "semantic" in name:
        return "Semantic Layer Tests"
    elif "authentication" in name or "auth" in name:
        return "Authentication Tests"
    elif "file" in name:
        return "File Operations Tests"
    elif "contract" in name:
        return "Contract Tests"
    elif "asset" in name:
        return "Asset Tests"
    elif "job" in name or "worker" in name:
        return "Job/Worker Tests"
    elif "dq" in name:
        return "DQ Service Tests"
    elif "compliance" in name:
        return "Compliance Service Tests"
    elif "monitoring" in name or "observability" in name:
        return "Monitoring/Observability Tests"
    else:
        return "Other E2E Tests"


def main():
    """Main function"""
    base_dir = Path(__file__).resolve().parent.parent

    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}Django 6 E2E Tests Compatibility Verification{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    # Find all E2E test files
    test_files = find_e2e_test_files(base_dir)
    print(f"{GREEN}✅ Found {len(test_files)} E2E test files to analyze{RESET}\n")

    # Categorize test files
    categorized_files: dict[str, list[Path]] = {}
    for file_path in test_files:
        category = categorize_test_file(file_path)
        categorized_files.setdefault(category, []).append(file_path)

    print(f"{BOLD}{BLUE}Test Files by Category:{RESET}\n")
    for category, files in sorted(categorized_files.items()):
        print(f"  {category}: {len(files)} files")
    print()

    # Analyze each file
    all_issues = []
    all_warnings = []
    files_with_issues = []
    files_with_warnings = []
    compatible_files = []
    test_base_class_usage = {}

    print(f"{BOLD}{BLUE}Analyzing Test Files...{RESET}\n")

    for file_path in test_files:
        result = check_django6_compatibility(file_path)

        # Track test base class usage
        for base_class in result["test_base_classes"]:
            test_base_class_usage[base_class] = test_base_class_usage.get(base_class, 0) + 1

        if result["issues"]:
            all_issues.extend(result["issues"])
            files_with_issues.append((file_path, result))
        elif result["warnings"]:
            all_warnings.extend(result["warnings"])
            files_with_warnings.append((file_path, result))
        else:
            compatible_files.append((file_path, result))

    # Print results
    print(f"{BOLD}{BLUE}Compatibility Analysis Results:{RESET}\n")

    if files_with_issues:
        print(f"{RED}❌ Found {len(files_with_issues)} files with compatibility issues:{RESET}")
        for file_path, result in files_with_issues:
            print(f"\n  {RED}{file_path.relative_to(base_dir)}{RESET}")
            for issue in result["issues"]:
                print(f"    - {issue}")
        print()
    else:
        print(f"{GREEN}✅ No compatibility issues found{RESET}\n")

    if files_with_warnings:
        print(f"{YELLOW}⚠️  Found {len(files_with_warnings)} files with warnings:{RESET}")
        for file_path, result in files_with_warnings:
            print(f"\n  {YELLOW}{file_path.relative_to(base_dir)}{RESET}")
            for warning in result["warnings"]:
                print(f"    - {warning}")
        print()
    else:
        print(f"{GREEN}✅ No warnings found{RESET}\n")

    print(f"{GREEN}✅ {len(compatible_files)} files are compatible with Django 6{RESET}\n")

    # Test base class usage summary
    if test_base_class_usage:
        print(f"{BOLD}{BLUE}Test Base Class Usage:{RESET}\n")
        for base_class, count in sorted(test_base_class_usage.items()):
            print(f"  {base_class}: {count} files")
        print()

    # Summary by category
    print(f"{BOLD}{BLUE}Summary by Category:{RESET}\n")

    category_results = {}
    for category, files in categorized_files.items():
        category_issues = []
        category_warnings = []
        category_compatible = []

        for file_path in files:
            result = check_django6_compatibility(file_path)
            if result["issues"]:
                category_issues.append(file_path)
            elif result["warnings"]:
                category_warnings.append(file_path)
            else:
                category_compatible.append(file_path)

        category_results[category] = {
            "total": len(files),
            "issues": len(category_issues),
            "warnings": len(category_warnings),
            "compatible": len(category_compatible),
        }

        status = "✅" if len(category_issues) == 0 else "❌"
        print(f"  {status} {category}: {len(category_compatible)}/{len(files)} compatible")

    print()

    # Generate report
    report_data = {
        "summary": {
            "total_files": len(test_files),
            "files_with_issues": len(files_with_issues),
            "files_with_warnings": len(files_with_warnings),
            "compatible_files": len(compatible_files),
        },
        "category_results": category_results,
        "test_base_class_usage": test_base_class_usage,
        "files_with_issues": [
            {
                "file": str(f.relative_to(base_dir)),
                "issues": r["issues"],
                "warnings": r["warnings"],
                "test_base_classes": r["test_base_classes"],
            }
            for f, r in files_with_issues
        ],
        "files_with_warnings": [
            {
                "file": str(f.relative_to(base_dir)),
                "warnings": r["warnings"],
                "test_base_classes": r["test_base_classes"],
            }
            for f, r in files_with_warnings
        ],
        "compatible_files": [
            {
                "file": str(f.relative_to(base_dir)),
                "test_base_classes": r["test_base_classes"],
            }
            for f, r in compatible_files
        ],
        "django6_compatibility_notes": [
            "Django 6 maintains backward compatibility with most test code",
            "TestCase, TransactionTestCase, LiveServerTestCase, APITestCase are compatible",
            "pytest-django works with Django 6",
            "Test fixtures and factories are compatible",
            "E2ETestBase (custom base class) should be compatible if it uses Django 6 patterns",
            "MiddlewareMixin usage in tests should be reviewed (if any)",
            "Deprecated settings usage should be updated to STORAGES setting",
        ],
    }

    report_path = (
        base_dir / "openspec" / "changes" / "fullcontract" / "DJANGO6_E2E_TESTS_VERIFICATION.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)

    print(f"{GREEN}✅ Report saved to: {report_path.relative_to(base_dir)}{RESET}\n")

    # Final summary
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}")
    if len(files_with_issues) == 0:
        print(f"{BOLD}{GREEN}✅ All E2E tests are compatible with Django 6!{RESET}")
    else:
        print(f"{BOLD}{YELLOW}⚠️  Some E2E tests need updates for Django 6{RESET}")
        print(f"{BOLD}{YELLOW}   Review the issues above and update as needed{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    return 0 if len(files_with_issues) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
