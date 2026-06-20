#!/usr/bin/env python3
"""
Systematic Test Execution and Fix Cycle

Runs tests, evaluates results, identifies issues, and provides fixes.
Follows engineering-grade practices:
- No mocks/stubs
- Fix root causes
- Follow best practices
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_django_test(app_path: str, timeout: int = 600) -> dict:
    """Run Django test for an app and return results."""
    print(f"\n{'=' * 80}")
    print(f"Testing: {app_path}")
    print(f"{'=' * 80}\n")

    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "api-service",
        "bash",
        "-c",
        f"cd /app/hub && timeout {timeout} python manage.py test {app_path} --verbosity=1 --keepdb --no-input 2>&1",
    ]

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=timeout + 10
        )
        output = result.stdout + result.stderr

        # Parse results
        stats = parse_django_test_output(output)
        stats.update(
            {
                "app": app_path,
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
            "exit_code": 124,
            "success": False,
            "status": "TIMEOUT",
            "output": f"Test execution timed out after {timeout} seconds",
        }
    except Exception as e:
        return {
            "app": app_path,
            "exit_code": 1,
            "success": False,
            "status": "ERROR",
            "error": str(e),
        }


def parse_django_test_output(output: str) -> dict[str, int]:
    """Parse Django test output."""
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

    # Look for OK or FAILED
    if "OK" in output and "FAILED" not in output:
        stats["passed"] = stats["total"]
    elif "FAILED" in output:
        failed_match = re.search(r"FAILED.*?\(failures=(\d+)\)", output)
        if failed_match:
            stats["failed"] = int(failed_match.group(1))

        error_match = re.search(r"\(errors=(\d+)\)", output)
        if error_match:
            stats["errors"] = int(error_match.group(1))

    skipped_match = re.search(r"skipped=(\d+)", output)
    if skipped_match:
        stats["skipped"] = int(skipped_match.group(1))

    stats["passed"] = stats["total"] - stats["failed"] - stats["errors"] - stats["skipped"]

    return stats


def get_signal_fix_batches() -> list[str]:
    """Get list of signal fix verification batches."""
    return [
        "hub.apps.developer.tests",
        "hub.apps.audit.tests",
        "hub.apps.graphql.tests",
        "hub.apps.notifications.tests",
        "hub.apps.search.tests",
    ]


def main():
    """Main execution."""
    print("=" * 80)
    print("Systematic Test Execution and Fix Cycle")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Start with signal fix batches
    batches = get_signal_fix_batches()

    print(f"Running {len(batches)} test batches...")
    print()

    results = []
    for batch in batches:
        result = run_django_test(batch, timeout=1800)
        results.append(result)

        if result.get("success"):
            print(f"✅ {batch}: PASSED")
        else:
            print(f"❌ {batch}: FAILED")
            if "failed" in result:
                print(f"   Failed: {result.get('failed', 0)}, Errors: {result.get('errors', 0)}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r.get("success"))
    failed = total - passed

    total_tests = sum(r.get("total", 0) for r in results)
    total_passed = sum(r.get("passed", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)

    print(f"Batches: {passed}/{total} passed")
    print(f"Tests: {total_passed}/{total_tests} passed")
    print(f"Failures: {total_failed}, Errors: {total_errors}")

    if failed > 0:
        print("\nFailed Batches:")
        for r in results:
            if not r.get("success"):
                print(
                    f"  - {r.get('app')}: {r.get('failed', 0)} failures, {r.get('errors', 0)} errors"
                )

    print(f"\nCompleted: {datetime.now().isoformat()}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
