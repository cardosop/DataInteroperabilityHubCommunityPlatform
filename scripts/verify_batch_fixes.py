#!/usr/bin/env python
"""
Script to verify batch fixes and re-run test batches.

This script:
1. Re-runs batches with signal fixes to verify they work
2. Investigates actual execution errors
3. Continues with other FAILED batches (starting with smallest)
4. Generates comprehensive reports

Usage:
    python scripts/verify_batch_fixes.py [--batches BATCH1,BATCH2] [--all-failed] [--report-dir DIR]

Environment Variables:
    POSTGRES_HOST: Database host (default: localhost)
    POSTGRES_PORT: Database port (default: 5432)
    POSTGRES_DB: Database name (default: hub)
    POSTGRES_USER: Database user (default: hub)
    POSTGRES_PASSWORD: Database password (default: hub)
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


class BatchResult:
    """Container for batch execution results."""

    def __init__(self, batch_name: str, app_path: str):
        self.batch_name = batch_name
        self.app_path = app_path
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.duration: float = 0.0
        self.exit_code: int = 0
        self.total_tests: int = 0
        self.passed: int = 0
        self.failed: int = 0
        self.errors: int = 0
        self.skipped: int = 0
        self.output: str = ""
        self.status: str = "PENDING"
        self.error_summary: list[str] = []

    @property
    def success(self) -> bool:
        """Check if batch execution was successful."""
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "batch_name": self.batch_name,
            "app_path": self.app_path,
            "status": self.status,
            "duration": self.duration,
            "exit_code": self.exit_code,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "success": self.success,
            "error_summary": self.error_summary,
        }


class BatchVerifier:
    """Verifies batch fixes and runs test batches."""

    # Batches with signal fixes applied
    SIGNAL_FIX_BATCHES = [
        ("hub/apps/developer", "Developer App"),
        ("hub/apps/audit", "Audit App"),
        ("hub/apps/graphql", "GraphQL App"),
        ("hub/apps/notifications", "Notifications App"),
        ("hub/apps/search", "Search App"),
    ]

    # Other FAILED batches (sorted by size - smallest first)
    OTHER_FAILED_BATCHES = [
        ("hub/apps/rate_limiting", "Rate Limiting App"),
        ("hub/apps/files", "Files App"),
        ("hub/apps/dq", "Data Quality App"),
        ("hub/apps/scheduled_ingestion", "Scheduled Ingestion App"),
        ("hub/apps/observability", "Observability App"),
    ]

    def __init__(self, project_root: Path, report_dir: Path | None = None):
        self.project_root = project_root
        self.report_dir = report_dir or (project_root / "test_reports_comprehensive")
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # Find Python executable
        self.python_executable = sys.executable
        venv_paths = [
            project_root / "venv" / "bin" / "python3",
            project_root / "venv-python312-test" / "bin" / "python3",
        ]
        for venv_python in venv_paths:
            if venv_python.exists():
                self.python_executable = str(venv_python)
                break

    def get_environment(self) -> dict[str, str]:
        """Get environment variables for test execution."""
        env = os.environ.copy()

        # Detect if running in Docker
        is_in_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"

        # Set POSTGRES_HOST: use "postgres" (Docker service name) if in Docker, else "localhost"
        default_postgres_host = "postgres" if is_in_docker else "localhost"
        env["POSTGRES_HOST"] = os.environ.get("POSTGRES_HOST", default_postgres_host)

        env["POSTGRES_PORT"] = os.environ.get("POSTGRES_PORT", "5432")
        env["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "hub")
        env["POSTGRES_USER"] = os.environ.get("POSTGRES_USER", "hub")
        env["POSTGRES_PASSWORD"] = os.environ.get("POSTGRES_PASSWORD", "hub")

        # Set REDIS_HOST: use service name if in Docker, else "localhost"
        default_redis_host = "redis-cache" if is_in_docker else "localhost"
        env["REDIS_HOST"] = os.environ.get("REDIS_HOST", default_redis_host)
        env["REDIS_PORT"] = os.environ.get("REDIS_PORT", "6379")

        env["DJANGO_SETTINGS_MODULE"] = os.environ.get("DJANGO_SETTINGS_MODULE", "hub.settings")
        env["USE_PRODUCTION_DB_FOR_SDK_TESTS"] = "0"
        return env

    def run_batch(self, app_path: str, batch_name: str, timeout: int = 1800) -> BatchResult:
        """
        Run tests for a specific app/batch.

        Args:
            app_path: Django app path (e.g., 'hub/apps/developer')
            batch_name: Human-readable batch name
            timeout: Timeout in seconds (default: 30 minutes)

        Returns:
            BatchResult with execution details
        """
        result = BatchResult(batch_name, app_path)
        result.start_time = time.time()

        print(f"\n{'=' * 80}")
        print(f"Running: {batch_name} ({app_path})")
        print(f"{'=' * 80}")

        # Convert app path to Django test path
        # e.g., 'hub/apps/developer' -> 'hub.apps.developer.tests'
        django_test_path = app_path.replace("/", ".") + ".tests"

        # Build command
        cmd = [
            self.python_executable,
            str(self.project_root / "hub" / "manage.py"),
            "test",
            "--verbosity=2",
            "--keepdb",
            "--no-input",
            django_test_path,
        ]

        env = self.get_environment()

        try:
            process = subprocess.run(
                cmd,
                check=False,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            result.end_time = time.time()
            result.duration = result.end_time - result.start_time
            result.exit_code = process.returncode
            result.output = process.stdout + process.stderr

            # Parse output to extract test statistics
            self._parse_test_output(result)

            if result.success:
                result.status = "PASSED"
                print(f"✅ {batch_name}: PASSED ({result.passed} tests, {result.duration:.1f}s)")
            else:
                result.status = "FAILED"
                print(
                    f"❌ {batch_name}: FAILED ({result.failed} failed, {result.errors} errors, {result.duration:.1f}s)"
                )
                self._extract_errors(result)

        except subprocess.TimeoutExpired:
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time
            result.exit_code = 1
            result.status = "TIMEOUT"
            result.error_summary.append(f"Test execution timed out after {timeout} seconds")
            print(f"⏱️  {batch_name}: TIMEOUT (exceeded {timeout}s)")

        except Exception as e:
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time
            result.exit_code = 1
            result.status = "ERROR"
            result.error_summary.append(f"Execution error: {e!s}")
            print(f"❌ {batch_name}: ERROR - {e}")

        return result

    def _parse_test_output(self, result: BatchResult):
        """Parse test output to extract statistics."""
        output = result.output

        # Try to extract test counts from Django test output
        import re

        # Pattern: "Ran X tests in Y.YYs"
        ran_match = re.search(r"Ran (\d+) test", output)
        if ran_match:
            result.total_tests = int(ran_match.group(1))

        # Pattern: "OK" or "FAILED (failures=X, errors=Y)"
        if "OK" in output and "FAILED" not in output and "ERROR" not in output:
            result.passed = result.total_tests
        else:
            # Try to extract failure/error counts
            failures_match = re.search(r"failures=(\d+)", output)
            if failures_match:
                result.failed = int(failures_match.group(1))

            errors_match = re.search(r"errors=(\d+)", output)
            if errors_match:
                result.errors = int(errors_match.group(1))

            # Calculate passed (total - failed - errors - skipped)
            skipped_match = re.search(r"skipped=(\d+)", output)
            if skipped_match:
                result.skipped = int(skipped_match.group(1))

            if result.total_tests > 0:
                result.passed = result.total_tests - result.failed - result.errors - result.skipped

    def _extract_errors(self, result: BatchResult):
        """Extract error summaries from test output."""
        lines = result.output.split("\n")
        error_lines = []

        for i, line in enumerate(lines):
            if any(
                keyword in line for keyword in ["FAILED", "ERROR", "AssertionError", "Exception"]
            ):
                # Capture error context (current line + next few lines)
                context = [line]
                for j in range(1, min(5, len(lines) - i)):
                    context.append(lines[i + j])
                error_lines.append("\n".join(context))

        # Limit to first 10 errors
        result.error_summary = error_lines[:10]

    def verify_signal_fixes(
        self, batches: list[tuple[str, str]] | None = None
    ) -> list[BatchResult]:
        """
        Verify signal fixes by re-running batches.

        Args:
            batches: Optional list of (app_path, batch_name) tuples. If None, uses SIGNAL_FIX_BATCHES.

        Returns:
            List of BatchResult objects
        """
        batches = batches or self.SIGNAL_FIX_BATCHES
        results = []

        print("\n" + "=" * 80)
        print("VERIFYING SIGNAL FIXES")
        print("=" * 80)
        print(f"Running {len(batches)} batch(es) to verify signal disconnection fixes...")

        for app_path, batch_name in batches:
            result = self.run_batch(app_path, batch_name)
            results.append(result)

        return results

    def run_failed_batches(self, batches: list[tuple[str, str]] | None = None) -> list[BatchResult]:
        """
        Run other FAILED batches (starting with smallest).

        Args:
            batches: Optional list of (app_path, batch_name) tuples. If None, uses OTHER_FAILED_BATCHES.

        Returns:
            List of BatchResult objects
        """
        batches = batches or self.OTHER_FAILED_BATCHES
        results = []

        print("\n" + "=" * 80)
        print("RUNNING OTHER FAILED BATCHES")
        print("=" * 80)
        print(f"Running {len(batches)} batch(es) (starting with smallest)...")

        for app_path, batch_name in batches:
            result = self.run_batch(app_path, batch_name)
            results.append(result)

        return results

    def generate_report(self, results: list[BatchResult], report_name: str):
        """Generate a comprehensive test report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.report_dir / f"{report_name}_{timestamp}.md"

        with open(report_file, "w") as f:
            f.write(f"# {report_name}\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Summary\n\n")

            total = len(results)
            passed = sum(1 for r in results if r.success)
            failed = total - passed

            f.write(f"- **Total Batches**: {total}\n")
            f.write(f"- **Passed**: {passed}\n")
            f.write(f"- **Failed**: {failed}\n")
            f.write(f"- **Success Rate**: {(passed / total * 100) if total > 0 else 0:.1f}%\n\n")

            f.write("## Batch Results\n\n")

            for result in results:
                status_icon = "✅" if result.success else "❌"
                f.write(f"### {status_icon} {result.batch_name}\n\n")
                f.write(f"- **App Path**: `{result.app_path}`\n")
                f.write(f"- **Status**: {result.status}\n")
                f.write(f"- **Duration**: {result.duration:.1f}s\n")
                f.write(
                    f"- **Tests**: {result.total_tests} total, {result.passed} passed, {result.failed} failed, {result.errors} errors, {result.skipped} skipped\n\n"
                )

                if result.error_summary:
                    f.write("#### Errors\n\n")
                    for error in result.error_summary[:5]:  # Limit to 5 errors
                        f.write(f"```\n{error}\n```\n\n")

            # Detailed output for failed batches
            failed_results = [r for r in results if not r.success]
            if failed_results:
                f.write("## Detailed Error Output\n\n")
                for result in failed_results:
                    f.write(f"### {result.batch_name}\n\n")
                    f.write("```\n")
                    # Write last 2000 characters of output
                    f.write(result.output[-2000:])
                    f.write("\n```\n\n")

        print(f"\n📄 Report saved to: {report_file}")
        return report_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify batch fixes and re-run test batches")
    parser.add_argument(
        "--batches",
        help='Comma-separated list of app paths to test (e.g., "hub/apps/developer,hub/apps/audit")',
    )
    parser.add_argument(
        "--signal-fixes",
        action="store_true",
        help="Verify signal fixes (re-run batches with signal fixes applied)",
    )
    parser.add_argument("--all-failed", action="store_true", help="Run all other FAILED batches")
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="Directory for test reports (default: test_reports_comprehensive)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Timeout per batch in seconds (default: 1800 = 30 minutes)",
    )

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    verifier = BatchVerifier(project_root, args.report_dir)

    results = []

    # Parse custom batches if provided
    custom_batches = None
    if args.batches:
        batch_list = []
        for batch_str in args.batches.split(","):
            batch_str = batch_str.strip()
            # Convert app path to batch name
            batch_name = batch_str.split("/")[-1].replace("_", " ").title()
            batch_list.append((batch_str, batch_name))
        custom_batches = batch_list

    # Run signal fix verification
    if args.signal_fixes or (not args.batches and not args.all_failed):
        print("Running signal fix verification batches...")
        signal_results = verifier.verify_signal_fixes(custom_batches if custom_batches else None)
        results.extend(signal_results)
        verifier.generate_report(signal_results, "SIGNAL_FIX_VERIFICATION")

    # Run other failed batches
    if args.all_failed:
        print("Running other FAILED batches...")
        failed_results = verifier.run_failed_batches(custom_batches if custom_batches else None)
        results.extend(failed_results)
        verifier.generate_report(failed_results, "FAILED_BATCHES_EXECUTION")

    # Run custom batches
    if args.batches and not args.signal_fixes and not args.all_failed:
        print("Running custom batches...")
        custom_results = []
        if custom_batches:
            for app_path, batch_name in custom_batches:
                result = verifier.run_batch(app_path, batch_name, timeout=args.timeout)
                custom_results.append(result)
        results.extend(custom_results)
        verifier.generate_report(custom_results, "CUSTOM_BATCHES_EXECUTION")

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed

    print(f"Total Batches: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed Batches:")
        for result in results:
            if not result.success:
                print(f"  ❌ {result.batch_name} ({result.app_path})")
        sys.exit(1)
    else:
        print("\n✅ All batches passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
