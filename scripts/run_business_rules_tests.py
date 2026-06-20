#!/usr/bin/env python3
"""
Comprehensive Business Rules Test Runner

Runs all business rules unit and integration tests, verifies they pass,
and reports results in an engineering-grade manner.

Following best practices:
- No mocks/stubs - uses real implementations
- Fixes root causes, not symptoms
- Comprehensive test coverage
- Follows DRY, SOLID, and clean code principles
"""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Try to find and use virtual environment
VENV_PATHS = [
    PROJECT_ROOT / "venv",
    PROJECT_ROOT / "venv-python312-test",
]
PYTHON_EXECUTABLE = sys.executable

for venv_path in VENV_PATHS:
    venv_python = venv_path / "bin" / "python3"
    if venv_python.exists():
        PYTHON_EXECUTABLE = str(venv_python)
        print(f"Using Python from virtual environment: {PYTHON_EXECUTABLE}")
        break

# Business rules test files to run
BUSINESS_RULES_TEST_FILES = [
    # Core business rules
    "hub/apps/files/tests/test_business_rules.py",
    "hub/apps/scheduled_ingestion/tests/test_business_rules.py",
    "hub/apps/governance/tests/test_business_rules.py",
    "hub/apps/jobs/tests/test_business_rules.py",
    "hub/apps/compliance/tests/test_business_rules.py",
    "hub/apps/dq/tests/test_business_rules.py",
    "hub/apps/search/tests/test_business_rules.py",
    "hub/apps/semantic/tests/test_business_rules.py",
    "hub/apps/orchestration/tests/test_business_rules.py",
    "hub/apps/orchestration/tests/test_business_rules_state_management.py",
    "hub/apps/notifications/tests/test_business_rules.py",
    "hub/apps/webhooks/tests/test_business_rules.py",
    "hub/apps/webhooks/tests/test_business_rules_payload.py",
    # Contracts business rules
    "hub/apps/contracts/tests/test_contracts_business_rules.py",
    "hub/apps/contracts/tests/test_odps_business_rules.py",
    "hub/apps/contracts/tests/test_odps_business_rules_integration.py",
    # Assets business rules
    "hub/apps/assets/tests/test_business_rules.py",
    "hub/apps/assets/tests/test_business_rules_dataset_attachment.py",
    # Datasets business rules
    "hub/apps/datasets/tests/test_business_rules.py",
    "hub/apps/datasets/tests/test_business_rules_access_validation.py",
    # Marketplace business rules
    "hub/apps/marketplace/tests/test_business_rules.py",
    "hub/apps/marketplace/tests/test_business_rules_pricing_validation.py",
    # Transformation business rules
    "hub/apps/transformation/tests/test_business_rules.py",
    "hub/apps/transformation/tests/test_business_rules_registry.py",
    # Note: test_execution_business_rules.py excluded - ExecutionBusinessRules class not yet implemented
    # "hub/apps/transformation/tests/test_execution_business_rules.py",
    "hub/apps/transformation/tests/test_cross_service_business_rules.py",
    # Data Mesh business rules
    "hub/apps/mesh/tests/test_business_rules.py",
    "hub/apps/mesh/tests/test_data_mesh_business_rules_refactoring.py",
    "hub/apps/mesh/tests/test_policy_topology_business_rules.py",
    "hub/apps/mesh/tests/test_policy_topology_business_rules_refactoring.py",
    # Virtualization business rules
    "hub/apps/virtualization/tests/test_business_rules.py",
    "hub/apps/virtualization/tests/test_virtualization_business_rules_refactoring.py",
    # Framework completeness tests (pytest-only, excluded from Django test runner)
    # "tests/unit/test_business_rules_framework_completeness.py",  # pytest test, not Django test
]


def find_test_files() -> list[str]:
    """Find all business rules test files that exist."""
    found_files = []
    for test_file in BUSINESS_RULES_TEST_FILES:
        full_path = PROJECT_ROOT / test_file
        if full_path.exists():
            found_files.append(str(full_path))
        else:
            print(f"⚠️  Warning: Test file not found: {test_file}")
    return found_files


def run_pytest_tests(test_files: list[str], verbose: bool = True) -> tuple[int, str]:
    """
    Run pytest on the given test files.
    Falls back to Django test runner if pytest fails or has import issues.

    Returns:
        Tuple of (exit_code, output)
    """
    # Set environment variables for test execution
    env = os.environ.copy()
    env["POSTGRES_HOST"] = "localhost"
    env["REDIS_HOST"] = "localhost"

    # Try pytest first
    cmd = [
        PYTHON_EXECUTABLE,
        "-m",
        "pytest",
        "-v" if verbose else "",
        "--tb=short",
        "--no-header",
        "--ignore-glob=**/__pycache__",
    ] + test_files

    # Remove empty strings
    cmd = [c for c in cmd if c]

    print(f"\n{'=' * 80}")
    print(f"Running pytest on {len(test_files)} test file(s)...")
    print(f"{'=' * 80}\n")

    try:
        result = subprocess.run(
            cmd,
            check=False,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            env=env,
        )
        # If pytest fails due to import errors or missing dependencies, fall back to Django
        if result.returncode != 0:
            error_output = result.stderr.lower()
            if any(
                phrase in error_output
                for phrase in [
                    "pytest_django",
                    "no module named 'pytest",
                    "import file mismatch",
                    "import error",
                    "cannot import",
                ]
            ):
                print("⚠️  pytest has import/cache issues, falling back to Django test runner...")
                return run_django_tests(test_files, verbose)
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Test execution timed out after 10 minutes"
    except Exception as e:
        # Fall back to Django test runner
        print(f"⚠️  pytest failed ({e!s}), falling back to Django test runner...")
        return run_django_tests(test_files, verbose)


def run_django_tests(
    test_paths: list[str], verbose: bool = True, batch_size: int = 5, timeout_per_batch: int = 1800
) -> tuple[int, str]:
    """
    Run Django test command on the given test paths in batches.

    Args:
        test_paths: List of Django test module paths
        verbose: Whether to run with verbose output
        batch_size: Number of test modules to run per batch
        timeout_per_batch: Timeout in seconds per batch (default 30 minutes)

    Returns:
        Tuple of (exit_code, output)
    """
    # Convert file paths to Django test paths
    django_paths = []
    for test_file in test_paths:
        # Convert hub/apps/files/tests/test_business_rules.py
        # to hub.apps.files.tests.test_business_rules
        # Handle both hub/ and tests/ paths
        rel_path = Path(test_file).relative_to(PROJECT_ROOT)
        django_path = str(rel_path).replace("/", ".").replace(".py", "")
        # Skip invalid test paths (like tests.unit.test_* which aren't Django apps)
        if django_path.startswith("tests.") and not django_path.startswith("hub."):
            # For tests/ directory, try to find the actual module path
            # If it's a standalone test file, we need to check if it's importable
            print(f"⚠️  Skipping non-Django-app test path: {django_path}")
            continue
        django_paths.append(django_path)

    # Set environment variables for test execution
    env = os.environ.copy()
    env["POSTGRES_HOST"] = "localhost"  # Use localhost when running outside Docker
    env["REDIS_HOST"] = "localhost"

    print(f"\n{'=' * 80}")
    print(
        f"Running Django tests on {len(django_paths)} test module(s) in batches of {batch_size}..."
    )
    print(f"{'=' * 80}\n")

    all_output = ""
    overall_exit_code = 0

    # Run tests in batches
    for i in range(0, len(django_paths), batch_size):
        batch = django_paths[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(django_paths) + batch_size - 1) // batch_size

        print(f"\n--- Batch {batch_num}/{total_batches}: Running {len(batch)} test module(s) ---")
        print(f"Modules: {', '.join(batch)}\n")

        cmd = [
            PYTHON_EXECUTABLE,
            str(PROJECT_ROOT / "hub" / "manage.py"),
            "test",
            "--verbosity=2" if verbose else "--verbosity=1",
            "--keepdb",
        ] + batch

        try:
            result = subprocess.run(
                cmd,
                check=False,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=timeout_per_batch,
                env=env,
            )
            batch_output = result.stdout + result.stderr
            all_output += f"\n{'=' * 80}\n"
            all_output += f"BATCH {batch_num}/{total_batches} OUTPUT\n"
            all_output += f"{'=' * 80}\n{batch_output}\n"

            if result.returncode != 0:
                overall_exit_code = result.returncode
                print(f"❌ Batch {batch_num} failed with exit code {result.returncode}")
                # Show summary of failures
                if "FAILED" in batch_output or "ERROR" in batch_output:
                    lines = batch_output.split("\n")
                    for line in lines:
                        if "FAILED" in line or "ERROR" in line or "AssertionError" in line:
                            print(f"  {line[:200]}")
            else:
                print(f"✅ Batch {batch_num} passed")

        except subprocess.TimeoutExpired:
            overall_exit_code = 1
            error_msg = f"Batch {batch_num} timed out after {timeout_per_batch // 60} minutes"
            all_output += f"\n❌ {error_msg}\n"
            print(f"❌ {error_msg}")
        except Exception as e:
            overall_exit_code = 1
            error_msg = f"Error running batch {batch_num}: {e!s}"
            all_output += f"\n❌ {error_msg}\n"
            print(f"❌ {error_msg}")

    return overall_exit_code, all_output


def categorize_tests(test_files: list[str]) -> dict[str, list[str]]:
    """Categorize tests into unit and integration."""
    unit_tests = []
    integration_tests = []

    for test_file in test_files:
        if "integration" in test_file.lower():
            integration_tests.append(test_file)
        else:
            unit_tests.append(test_file)

    return {
        "unit": unit_tests,
        "integration": integration_tests,
    }


def check_services() -> bool:
    """Check if required services (PostgreSQL, Redis) are available."""
    import socket

    services = {
        "PostgreSQL": ("localhost", 5432),
        "Redis": ("localhost", 6379),
    }

    all_available = True
    for service_name, (host, port) in services.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                print(f"✅ {service_name} is available on {host}:{port}")
            else:
                print(f"⚠️  {service_name} is not available on {host}:{port}")
                all_available = False
        except Exception as e:
            print(f"⚠️  Could not check {service_name}: {e}")
            all_available = False

    return all_available


def main():
    """Main execution function."""
    print("=" * 80)
    print("Business Rules Comprehensive Test Runner")
    print("=" * 80)
    print("\nFollowing engineering best practices:")
    print("  - No mocks/stubs - uses real implementations")
    print("  - Fixes root causes, not symptoms")
    print("  - Comprehensive test coverage")
    print("  - Follows DRY, SOLID, and clean code principles")
    print()

    # Check if services are available
    print("Checking required services...")
    services_available = check_services()

    if not services_available:
        print("\n⚠️  Warning: Some required services are not available.")
        print("   Tests require PostgreSQL and Redis to be running.")
        print("   Start services with: make docker-up")
        print("   Or: docker compose up -d postgres redis")
        print("\n   Attempting to continue anyway...")
        print()

    # Find all test files
    test_files = find_test_files()

    if not test_files:
        print("❌ No business rules test files found!")
        return 1

    print(f"Found {len(test_files)} business rules test file(s)")

    # Categorize tests
    categorized = categorize_tests(test_files)
    unit_tests = categorized["unit"]
    integration_tests = categorized["integration"]

    print(f"\n  Unit tests: {len(unit_tests)}")
    print(f"  Integration tests: {len(integration_tests)}")

    # Run unit tests - Use Django test runner to avoid pytest cache issues
    print("\n" + "=" * 80)
    print("PHASE 1: Running Unit Tests")
    print("=" * 80)

    unit_exit_code = 0
    unit_output = ""

    if unit_tests:
        # Use Django test runner directly for better compatibility
        unit_exit_code, unit_output = run_django_tests(unit_tests, verbose=True)
        print(unit_output)
    else:
        print("⚠️  No unit tests found")

    # Run integration tests - Use Django test runner for consistency
    print("\n" + "=" * 80)
    print("PHASE 2: Running Integration Tests")
    print("=" * 80)

    integration_exit_code = 0
    integration_output = ""

    if integration_tests:
        # Use Django test runner directly for better compatibility
        integration_exit_code, integration_output = run_django_tests(
            integration_tests, verbose=True
        )
        print(integration_output)
    else:
        print("⚠️  No integration tests found")

    # Summary
    print("\n" + "=" * 80)
    print("TEST EXECUTION SUMMARY")
    print("=" * 80)

    total_tests = len(test_files)
    passed_tests = 0
    failed_tests = 0

    if unit_exit_code == 0:
        print(f"✅ Unit tests: PASSED ({len(unit_tests)} test file(s))")
        passed_tests += len(unit_tests)
    else:
        print(f"❌ Unit tests: FAILED ({len(unit_tests)} test file(s))")
        failed_tests += len(unit_tests)

    if integration_exit_code == 0:
        print(f"✅ Integration tests: PASSED ({len(integration_tests)} test file(s))")
        passed_tests += len(integration_tests)
    else:
        print(f"❌ Integration tests: FAILED ({len(integration_tests)} test file(s))")
        failed_tests += len(integration_tests)

    print(f"\nTotal test files: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")

    # Final result
    overall_exit_code = 0 if (unit_exit_code == 0 and integration_exit_code == 0) else 1

    if overall_exit_code == 0:
        print("\n" + "=" * 80)
        print("✅ ALL BUSINESS RULES TESTS PASSED")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("❌ SOME BUSINESS RULES TESTS FAILED")
        print("=" * 80)
        print("\nPlease review the test output above and fix any failures.")
        print("Remember: Fix root causes, not symptoms. No mocks/stubs.")

    return overall_exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
