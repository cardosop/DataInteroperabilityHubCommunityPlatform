#!/usr/bin/env python3
"""
Comprehensive Test Execution - Systematic Approach

Runs all tests systematically, evaluates results, and provides detailed reporting.
Follows engineering-grade practices:
- No mocks/stubs
- Fix root causes
- Follow best practices
"""

import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_all_apps() -> list[str]:
    """Get all Django apps in hub/apps."""
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "api-service",
                "bash",
                "-c",
                "cd /app/hub && python manage.py test --help 2>&1 | grep -A 1000 'test labels' | head -200",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Alternative: find all apps with tests
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "api-service",
                "find",
                "/app/hub/apps",
                "-name",
                "tests",
                "-type",
                "d",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            apps = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    # Convert /app/hub/apps/developer/tests to hub.apps.developer.tests
                    path = (
                        line.strip()
                        .replace("/app/hub/apps/", "hub.apps.")
                        .replace("/tests", ".tests")
                    )
                    apps.append(path)
            return sorted(apps)
    except Exception as e:
        print(f"Error getting apps: {e}")
    return []


def run_django_tests(app_path: str, timeout: int = 1800) -> dict[str, any]:
    """Run Django tests for a specific app."""
    print(f"\n{'=' * 80}")
    print(f"Running tests for: {app_path}")
    print(f"{'=' * 80}\n")

    start_time = time.time()

    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "api-service",
        "bash",
        "-c",
        f"cd /app/hub && python manage.py test {app_path} --verbosity=2 --keepdb --no-input 2>&1",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        duration = time.time() - start_time
        output = result.stdout + result.stderr

        # Parse results
        stats = parse_test_output(output)
        stats.update(
            {
                "app": app_path,
                "duration": duration,
                "exit_code": result.returncode,
                "output": output,
                "success": result.returncode == 0
                and stats.get("failed", 0) == 0
                and stats.get("errors", 0) == 0,
            }
        )

        return stats

    except subprocess.TimeoutExpired:
        return {
            "app": app_path,
            "duration": timeout,
            "exit_code": 124,
            "success": False,
            "status": "TIMEOUT",
            "output": f"Test execution timed out after {timeout} seconds",
        }
    except Exception as e:
        return {
            "app": app_path,
            "duration": time.time() - start_time,
            "exit_code": 1,
            "success": False,
            "status": "ERROR",
            "error": str(e),
        }


def parse_test_output(output: str) -> dict[str, int]:
    """Parse Django test output to extract statistics."""
    stats = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
    }

    # Look for "Ran X tests" line
    ran_match = re.search(r"Ran (\d+) test", output)
    if ran_match:
        stats["total"] = int(ran_match.group(1))

    # Look for "OK" or "FAILED" line
    if "OK" in output and "FAILED" not in output:
        stats["passed"] = stats["total"]
    elif "FAILED" in output:
        # Try to extract failure count
        failed_match = re.search(r"FAILED.*?\(failures=(\d+)\)", output)
        if failed_match:
            stats["failed"] = int(failed_match.group(1))

        error_match = re.search(r"\(errors=(\d+)\)", output)
        if error_match:
            stats["errors"] = int(error_match.group(1))

    # Look for skipped
    skipped_match = re.search(r"skipped=(\d+)", output)
    if skipped_match:
        stats["skipped"] = int(skipped_match.group(1))

    # Calculate passed
    stats["passed"] = stats["total"] - stats["failed"] - stats["errors"] - stats["skipped"]

    return stats


def main():
    """Main execution function."""
    print("=" * 80)
    print("Comprehensive Test Execution - Systematic Approach")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Get all apps
    print("Discovering test apps...")
    apps = get_all_apps()

    if not apps:
        # Fallback: use common apps
        apps = [
            "hub.apps.developer.tests",
            "hub.apps.audit.tests",
            "hub.apps.graphql.tests",
            "hub.apps.notifications.tests",
            "hub.apps.search.tests",
        ]
        print(f"Using fallback app list: {len(apps)} apps")
    else:
        print(f"Found {len(apps)} apps with tests")

    print()

    # Run tests for each app
    results = []
    for app in apps:
        result = run_django_tests(app)
        results.append(result)

        # Print summary
        if result.get("success"):
            print(
                f"✅ {app}: PASSED ({result.get('passed', 0)} tests, {result.get('duration', 0):.1f}s)"
            )
        else:
            print(f"❌ {app}: FAILED")
            print(f"   Duration: {result.get('duration', 0):.1f}s")
            if "failed" in result:
                print(f"   Failed: {result.get('failed', 0)}, Errors: {result.get('errors', 0)}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_apps = len(results)
    passed_apps = sum(1 for r in results if r.get("success"))
    failed_apps = total_apps - passed_apps

    total_tests = sum(r.get("total", 0) for r in results)
    total_passed = sum(r.get("passed", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)

    print(f"Apps: {passed_apps}/{total_apps} passed")
    print(f"Tests: {total_passed}/{total_tests} passed")
    print(f"Failures: {total_failed}, Errors: {total_errors}")

    # Failed apps
    if failed_apps > 0:
        print("\nFailed Apps:")
        for r in results:
            if not r.get("success"):
                print(
                    f"  - {r.get('app')}: {r.get('failed', 0)} failures, {r.get('errors', 0)} errors"
                )

    print(f"\nCompleted: {datetime.now().isoformat()}")

    return 0 if failed_apps == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
