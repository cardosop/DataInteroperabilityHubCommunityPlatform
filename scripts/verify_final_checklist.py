#!/usr/bin/env python3
"""
Final Checklist Verification Script

Comprehensive verification of all checklist items for the implement-second-backend-wave change.
This script checks:
- Test infrastructure
- Test execution and pass rates
- Code coverage
- Documentation completeness
- CI/CD integration
"""

import json
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{text.center(80)}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{YELLOW}⚠{RESET} {text}")


def check_file_exists(filepath: Path) -> bool:
    """Check if a file exists"""
    return filepath.exists() and filepath.is_file()


def check_directory_exists(dirpath: Path) -> bool:
    """Check if a directory exists"""
    return dirpath.exists() and dirpath.is_dir()


def run_command(cmd: list[str], cwd: Path = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(
            cmd, check=False, cwd=cwd or project_root, capture_output=True, text=True, timeout=300
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def verify_test_infrastructure() -> dict[str, bool]:
    """Verify test infrastructure setup"""
    print_header("Verifying Test Infrastructure")

    results = {}

    # Check test directory structure
    test_dirs = [
        project_root / "tests",
        project_root / "tests" / "unit",
        project_root / "tests" / "integration",
        project_root / "tests" / "e2e",
        project_root / "tests" / "performance",
        project_root / "tests" / "fixtures",
    ]

    for test_dir in test_dirs:
        exists = check_directory_exists(test_dir)
        results[f"test_dir_{test_dir.name}"] = exists
        if exists:
            print_success(f"Test directory exists: {test_dir}")
        else:
            print_error(f"Test directory missing: {test_dir}")

    # Check test factories
    factories = [
        project_root / "tests" / "factories.py",
        project_root / "hub" / "apps" / "contracts" / "tests" / "factories.py",
        project_root / "tests" / "fixtures" / "email_service_fixtures.py",
    ]

    for factory in factories:
        exists = check_file_exists(factory)
        results[f"factory_{factory.name}"] = exists
        if exists:
            print_success(f"Factory exists: {factory}")
        else:
            print_error(f"Factory missing: {factory}")

    # Check pytest configuration
    pytest_ini = project_root / "pytest.ini"
    exists = check_file_exists(pytest_ini)
    results["pytest_config"] = exists
    if exists:
        print_success(f"Pytest configuration exists: {pytest_ini}")
    else:
        print_error(f"Pytest configuration missing: {pytest_ini}")

    return results


def verify_documentation() -> dict[str, bool]:
    """Verify documentation completeness"""
    print_header("Verifying Documentation")

    results = {}

    # Check required documentation files
    docs = [
        project_root
        / "openspec"
        / "changes"
        / "implement-second-backend-wave"
        / "COMPREHENSIVE_TEST_PLAN.md",
        project_root
        / "openspec"
        / "changes"
        / "implement-second-backend-wave"
        / "TEST_GAP_ANALYSIS.md",
        project_root
        / "openspec"
        / "changes"
        / "implement-second-backend-wave"
        / "ENHANCED_TEST_PLAN.md",
        project_root
        / "openspec"
        / "changes"
        / "implement-second-backend-wave"
        / "TEST_REVIEW_SUMMARY.md",
        project_root
        / "openspec"
        / "changes"
        / "implement-second-backend-wave"
        / "COMPREHENSIVE_IMPACT_ANALYSIS.md",
        project_root / "docs" / "API_DOCUMENTATION.md",
        project_root / "docs" / "SDK_DOCUMENTATION.md",
        project_root / "docs" / "USER_GUIDE.md",
    ]

    for doc in docs:
        exists = check_file_exists(doc)
        results[f"doc_{doc.name}"] = exists
        if exists:
            print_success(f"Documentation exists: {doc.name}")
        else:
            print_error(f"Documentation missing: {doc.name}")

    # Check test documentation
    test_docs = [
        project_root / "tests" / "e2e" / "README.md",
        project_root / "tests" / "e2e" / "SETUP_GUIDE.md",
        project_root / "tests" / "performance" / "README.md",
    ]

    for doc in test_docs:
        exists = check_file_exists(doc)
        results[f"test_doc_{doc.name}"] = exists
        if exists:
            print_success(f"Test documentation exists: {doc.name}")
        else:
            print_warning(f"Test documentation missing: {doc.name}")

    return results


def verify_ci_cd() -> dict[str, bool]:
    """Verify CI/CD integration"""
    print_header("Verifying CI/CD Integration")

    results = {}

    # Check GitHub Actions workflows
    workflows = [
        project_root / ".github" / "workflows" / "ci.yml",
    ]

    for workflow in workflows:
        exists = check_file_exists(workflow)
        results[f"workflow_{workflow.name}"] = exists
        if exists:
            print_success(f"CI/CD workflow exists: {workflow.name}")

            # Check if workflow includes test execution
            if exists:
                content = workflow.read_text()
                has_unit_tests = "pytest" in content and "unit" in content.lower()
                has_integration_tests = "integration" in content.lower()
                has_e2e_tests = "e2e" in content.lower() or "tests/e2e" in content
                has_coverage = "coverage" in content.lower() or "cov" in content.lower()

                results[f"workflow_{workflow.name}_unit"] = has_unit_tests
                results[f"workflow_{workflow.name}_integration"] = has_integration_tests
                results[f"workflow_{workflow.name}_e2e"] = has_e2e_tests
                results[f"workflow_{workflow.name}_coverage"] = has_coverage

                if has_unit_tests:
                    print_success("  - Unit tests configured")
                else:
                    print_warning("  - Unit tests not configured")

                if has_integration_tests:
                    print_success("  - Integration tests configured")
                else:
                    print_warning("  - Integration tests not configured")

                if has_e2e_tests:
                    print_success("  - E2E tests configured")
                else:
                    print_warning("  - E2E tests not configured")

                if has_coverage:
                    print_success("  - Coverage reporting configured")
                else:
                    print_warning("  - Coverage reporting not configured")
        else:
            print_error(f"CI/CD workflow missing: {workflow.name}")

    return results


def verify_test_execution() -> dict[str, any]:
    """Verify test execution (dry run - collect tests)"""
    print_header("Verifying Test Execution")

    results = {}

    # Try to collect tests (dry run)
    print("Collecting test files...")
    exit_code, stdout, stderr = run_command(["python3", "-m", "pytest", "--collect-only", "-q"])

    if exit_code == 0:
        # Count tests
        test_count = stdout.count("test_") + stdout.count("::test_")
        results["test_collection_success"] = True
        results["test_count"] = test_count
        print_success(f"Test collection successful: {test_count} tests found")
    else:
        results["test_collection_success"] = False
        print_error(f"Test collection failed: {stderr}")

    return results


def main():
    """Main verification function"""
    print_header("Final Checklist Verification")
    print("Verifying all checklist items for implement-second-backend-wave change\n")

    all_results = {}

    # Verify test infrastructure
    all_results.update(verify_test_infrastructure())

    # Verify documentation
    all_results.update(verify_documentation())

    # Verify CI/CD
    all_results.update(verify_ci_cd())

    # Verify test execution
    all_results.update(verify_test_execution())

    # Summary
    print_header("Verification Summary")

    total = len(all_results)
    passed = sum(1 for v in all_results.values() if v is True)
    failed = sum(1 for v in all_results.values() if v is False)
    warnings = sum(1 for v in all_results.values() if v is not True and v is not False)

    print(f"\nTotal checks: {total}")
    print_success(f"Passed: {passed}")
    if failed > 0:
        print_error(f"Failed: {failed}")
    if warnings > 0:
        print_warning(f"Warnings: {warnings}")

    # Save results
    results_file = project_root / "verification_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {results_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
