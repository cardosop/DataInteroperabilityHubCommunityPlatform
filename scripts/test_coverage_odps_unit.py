#!/usr/bin/env python3
"""
Comprehensive Unit Test Coverage for ODPS Modules

This script runs unit tests for all ODPS modules (normalizers, generators, resolvers)
with coverage measurement and validation. It ensures 90%+ coverage for ODPS modules
and generates detailed coverage reports.

Engineering-grade implementation:
- No mocks/stubs - uses real implementations
- Root cause fixes - addresses underlying issues
- Comprehensive coverage - all modules tested
- Best practices - follows testing standards
"""

import os
import sys
import subprocess
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
NC = '\033[0m'  # No Color
BOLD = '\033[1m'


class ODPSUnitTestCoverage:
    """Comprehensive unit test coverage runner for ODPS modules."""

    # Target coverage threshold
    TARGET_COVERAGE = 90.0

    # ODPS modules to test
    ODPS_MODULES = {
        'normalizers': [
            'hub.apps.contracts.normalization.odps_normalizer',
            'hub.apps.contracts.normalization.odps_normalizer_base',
            'hub.apps.contracts.normalization.odps_normalizer_v4_1',
            'hub.apps.contracts.normalization.odps_normalizer_v4_0',
            'hub.apps.contracts.normalization.odps_normalizer_v3_x',
            'hub.apps.contracts.normalization.odps_normalizer_v2_x',
            'hub.apps.contracts.normalization.odps_normalizer_v1_x',
        ],
        'generators': [
            'hub.apps.contracts.odps_generator',
        ],
        'resolvers': [
            'hub.apps.contracts.ref_resolver',
        ],
    }

    # Test files for each module category
    TEST_FILES = {
        'normalizers': [
            'hub/apps/contracts/tests/test_odps_normalizer.py',
            'hub/apps/contracts/tests/test_odps_normalizer_base.py',
            'hub/apps/contracts/tests/test_odps_normalizer_v4_1.py',
            'hub/apps/contracts/tests/test_odps_normalizer_v4_0.py',
        ],
        'generators': [
            'hub/apps/contracts/tests/test_odps_generator.py',
            'hub/apps/contracts/tests/test_odps_generator_assembly.py',
            'hub/apps/contracts/tests/test_odps_generator_contract.py',
            'hub/apps/contracts/tests/test_odps_generator_lifecycle.py',
            'hub/apps/contracts/tests/test_odps_generator_marketplace.py',
            'hub/apps/contracts/tests/test_odps_generator_product_strategy.py',
        ],
        'resolvers': [
            'hub/apps/contracts/tests/test_ref_resolver.py',
            'hub/apps/contracts/tests/test_ref_resolver_caching.py',
            'hub/apps/contracts/tests/test_ref_resolver_performance.py',
        ],
    }

    def __init__(self):
        """Initialize the coverage runner."""
        self.project_root = PROJECT_ROOT
        self.results: Dict[str, Dict] = {}
        self.coverage_data: Dict[str, float] = {}

    def print_header(self, text: str):
        """Print a formatted header."""
        print(f"\n{BOLD}{BLUE}{'=' * 80}{NC}")
        print(f"{BOLD}{BLUE}{text.center(80)}{NC}")
        print(f"{BOLD}{BLUE}{'=' * 80}{NC}\n")

    def print_section(self, text: str):
        """Print a formatted section header."""
        print(f"\n{BOLD}{text}{NC}")
        print(f"{'-' * len(text)}")

    def run_command(self, cmd: List[str], cwd: Optional[Path] = None, use_docker: bool = True) -> Tuple[int, str, str]:
        """
        Run a command and return exit code, stdout, and stderr.

        Args:
            cmd: Command to run as list
            cwd: Working directory (default: project root)
            use_docker: If True, run command in Docker container (default: True)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if cwd is None:
            cwd = self.project_root

        # Check if we should use Docker (Django is in the container)
        if use_docker:
            # Check if Docker container is running
            check_cmd = ['docker', 'ps', '--filter', 'name=hub-api', '--format', '{{.Names}}']
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)
            if check_result.returncode == 0 and 'hub-api' in check_result.stdout:
                # Run command in Docker container
                docker_cmd = ['docker', 'exec', '-w', '/app', 'hub-api'] + cmd
                try:
                    result = subprocess.run(
                        docker_cmd,
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        timeout=600  # 10 minute timeout
                    )
                    return result.returncode, result.stdout, result.stderr
                except subprocess.TimeoutExpired:
                    return 1, "", "Command timed out after 10 minutes"
                except Exception as e:
                    return 1, "", str(e)
            else:
                print(f"{YELLOW}Warning: Docker container 'hub-api' not running, trying local execution{NC}")
                use_docker = False

        # Fallback to local execution
        if not use_docker:
            try:
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired:
                return 1, "", "Command timed out after 10 minutes"
            except Exception as e:
                return 1, "", str(e)

    def run_unit_tests_with_coverage(
        self,
        category: str,
        modules: List[str],
        test_files: List[str]
    ) -> Dict:
        """
        Run unit tests with coverage for a specific category.

        Args:
            category: Category name (normalizers, generators, resolvers)
            modules: List of modules to measure coverage for
            test_files: List of test files to run

        Returns:
            Dictionary with test results and coverage data
        """
        self.print_section(f"Running {category.upper()} Unit Tests")

        # Build coverage arguments
        cov_args = []
        for module in modules:
            cov_args.extend(['--cov', module])

        # Build test file paths
        test_paths = []
        for test_file in test_files:
            test_path = self.project_root / test_file
            if test_path.exists():
                test_paths.append(str(test_path))
            else:
                print(f"{YELLOW}Warning: Test file not found: {test_file}{NC}")

        if not test_paths:
            print(f"{RED}Error: No test files found for {category}{NC}")
            return {
                'success': False,
                'coverage': 0.0,
                'tests_run': 0,
                'tests_passed': 0,
                'tests_failed': 0,
                'error': 'No test files found'
            }

        # Run pytest with coverage
        # Override pytest.ini addopts to remove --reuse-db which may not be supported
        # We'll use --override-ini to replace addopts with compatible options
        cmd = [
            'python3', '-m', 'pytest',
            '--override-ini=addopts=--strict-markers --disable-warnings --tb=short --asyncio-mode=auto',
            *cov_args,
            '--cov-report=term-missing',
            '--cov-report=xml:coverage.xml',
            '--cov-report=json:coverage.json',
            '-v',
            *test_paths
        ]

        print(f"Running: {' '.join(cmd)}")
        exit_code, stdout, stderr = self.run_command(cmd)

        # If still failing, try without any override (let pytest handle it)
        if exit_code != 0 and '--reuse-db' in stderr:
            print(f"{YELLOW}Warning: Retrying without --reuse-db override{NC}")
            cmd_retry = [
                'python3', '-m', 'pytest',
                *cov_args,
                '--cov-report=term-missing',
                '--cov-report=xml:coverage.xml',
                '--cov-report=json:coverage.json',
                '--tb=short',
                '-v',
                *test_paths
            ]
            # Try to run with a custom pytest.ini that doesn't have --reuse-db
            # Create temporary pytest.ini without --reuse-db
            import tempfile
            import shutil
            original_pytest_ini = self.project_root / 'pytest.ini'
            backup_pytest_ini = self.project_root / 'pytest.ini.backup'

            try:
                # Backup original
                if original_pytest_ini.exists():
                    shutil.copy2(original_pytest_ini, backup_pytest_ini)
                    # Read and modify
                    with open(original_pytest_ini, 'r') as f:
                        content = f.read()
                    # Remove --reuse-db from addopts
                    modified_content = content.replace('--reuse-db', '').replace('    --reuse-db', '')
                    with open(original_pytest_ini, 'w') as f:
                        f.write(modified_content)

                exit_code, stdout, stderr = self.run_command(cmd_retry, use_docker=True)
            finally:
                # Restore original
                if backup_pytest_ini.exists():
                    shutil.move(backup_pytest_ini, original_pytest_ini)

        # Parse coverage from JSON report
        # Coverage files are in Docker container, copy them if needed
        coverage_json_path = self.project_root / 'coverage.json'

        # Try to copy coverage.json from Docker container if it doesn't exist locally
        if not coverage_json_path.exists():
            try:
                import subprocess
                result = subprocess.run(
                    ['docker', 'cp', 'hub-api:/app/coverage.json', str(coverage_json_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    print(f"{YELLOW}Warning: Could not copy coverage.json from Docker container{NC}")
            except Exception as e:
                print(f"{YELLOW}Warning: Could not copy coverage.json from Docker: {e}{NC}")
        coverage_data = {}
        overall_coverage = 0.0

        if coverage_json_path.exists():
            try:
                with open(coverage_json_path, 'r') as f:
                    coverage_json = json.load(f)

                # Calculate coverage for each module
                totals = coverage_json.get('totals', {})
                overall_coverage = totals.get('percent_covered', 0.0)

                # Get per-file coverage
                files = coverage_json.get('files', {})
                for module in modules:
                    # Find matching files
                    module_parts = module.split('.')
                    for file_path, file_data in files.items():
                        if all(part in file_path for part in module_parts):
                            file_coverage = file_data.get('summary', {}).get('percent_covered', 0.0)
                            coverage_data[module] = file_coverage
                            break
            except Exception as e:
                print(f"{YELLOW}Warning: Could not parse coverage JSON: {e}{NC}")

        # Parse test results from stdout
        tests_run = 0
        tests_passed = 0
        tests_failed = 0

        if exit_code == 0:
            # Try to extract test counts from pytest output
            for line in stdout.split('\n'):
                if 'passed' in line.lower() and 'failed' in line.lower():
                    # Format: "X passed, Y failed in Z.XXs"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'passed':
                            try:
                                tests_passed = int(parts[i-1])
                            except (ValueError, IndexError):
                                pass
                        elif part == 'failed':
                            try:
                                tests_failed = int(parts[i-1])
                            except (ValueError, IndexError):
                                pass
                    tests_run = tests_passed + tests_failed
                    break

        result = {
            'success': exit_code == 0,
            'coverage': overall_coverage,
            'module_coverage': coverage_data,
            'tests_run': tests_run,
            'tests_passed': tests_passed,
            'tests_failed': tests_failed,
            'exit_code': exit_code,
            'stdout': stdout,
            'stderr': stderr
        }

        # Print summary
        if exit_code == 0:
            print(f"{GREEN}✓ Tests passed: {tests_passed}{NC}")
            if tests_failed > 0:
                print(f"{RED}✗ Tests failed: {tests_failed}{NC}")
            print(f"{BLUE}Coverage: {overall_coverage:.2f}%{NC}")
            if overall_coverage < self.TARGET_COVERAGE:
                print(f"{YELLOW}Warning: Coverage {overall_coverage:.2f}% is below target {self.TARGET_COVERAGE}%{NC}")
        else:
            print(f"{RED}✗ Tests failed with exit code {exit_code}{NC}")
            if stderr:
                print(f"{RED}Error output:{NC}")
                print(stderr[:500])  # First 500 chars

        return result

    def validate_coverage(self) -> Tuple[bool, List[str]]:
        """
        Validate that coverage meets requirements.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        for category, result in self.results.items():
            coverage = result.get('coverage', 0.0)
            if coverage < self.TARGET_COVERAGE:
                issues.append(
                    f"{category}: Coverage {coverage:.2f}% is below target {self.TARGET_COVERAGE}%"
                )

            # Check module-level coverage
            module_coverage = result.get('module_coverage', {})
            for module, mod_cov in module_coverage.items():
                if mod_cov < self.TARGET_COVERAGE:
                    issues.append(
                        f"{category}/{module}: Coverage {mod_cov:.2f}% is below target {self.TARGET_COVERAGE}%"
                    )

        return len(issues) == 0, issues

    def generate_report(self) -> str:
        """
        Generate a comprehensive coverage report.

        Returns:
            Report as string
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("ODPS Unit Test Coverage Report")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().isoformat()}")
        report_lines.append(f"Target Coverage: {self.TARGET_COVERAGE}%")
        report_lines.append("")

        # Summary
        report_lines.append("SUMMARY")
        report_lines.append("-" * 80)
        total_tests = 0
        total_passed = 0
        total_failed = 0
        avg_coverage = 0.0

        for category, result in self.results.items():
            total_tests += result.get('tests_run', 0)
            total_passed += result.get('tests_passed', 0)
            total_failed += result.get('tests_failed', 0)
            avg_coverage += result.get('coverage', 0.0)

        avg_coverage = avg_coverage / len(self.results) if self.results else 0.0

        report_lines.append(f"Total Tests Run: {total_tests}")
        report_lines.append(f"Total Tests Passed: {total_passed}")
        report_lines.append(f"Total Tests Failed: {total_failed}")
        report_lines.append(f"Average Coverage: {avg_coverage:.2f}%")
        report_lines.append("")

        # Detailed results
        report_lines.append("DETAILED RESULTS")
        report_lines.append("-" * 80)

        for category, result in self.results.items():
            report_lines.append(f"\n{category.upper()}:")
            report_lines.append(f"  Tests Run: {result.get('tests_run', 0)}")
            report_lines.append(f"  Tests Passed: {result.get('tests_passed', 0)}")
            report_lines.append(f"  Tests Failed: {result.get('tests_failed', 0)}")
            report_lines.append(f"  Overall Coverage: {result.get('coverage', 0.0):.2f}%")

            module_coverage = result.get('module_coverage', {})
            if module_coverage:
                report_lines.append("  Module Coverage:")
                for module, coverage in module_coverage.items():
                    status = "✓" if coverage >= self.TARGET_COVERAGE else "✗"
                    report_lines.append(f"    {status} {module}: {coverage:.2f}%")

        # Validation
        report_lines.append("")
        report_lines.append("VALIDATION")
        report_lines.append("-" * 80)
        is_valid, issues = self.validate_coverage()

        if is_valid:
            report_lines.append("✓ All coverage requirements met")
        else:
            report_lines.append("✗ Coverage requirements not met:")
            for issue in issues:
                report_lines.append(f"  - {issue}")

        return "\n".join(report_lines)

    def run(self) -> int:
        """
        Run all unit tests with coverage.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        self.print_header("ODPS Unit Test Coverage - Comprehensive Testing")

        # Run tests for each category
        for category in ['normalizers', 'generators', 'resolvers']:
            modules = self.ODPS_MODULES.get(category, [])
            test_files = self.TEST_FILES.get(category, [])

            result = self.run_unit_tests_with_coverage(category, modules, test_files)
            self.results[category] = result

            if not result.get('success', False):
                print(f"{RED}Error: {category} tests failed{NC}")

        # Generate and print report
        self.print_section("Coverage Report")
        report = self.generate_report()
        print(report)

        # Save report to file
        report_path = self.project_root / 'odps_unit_test_coverage_report.txt'
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"\n{GREEN}Report saved to: {report_path}{NC}")

        # Validate coverage
        is_valid, issues = self.validate_coverage()

        if is_valid:
            print(f"\n{GREEN}{BOLD}✓ All coverage requirements met!{NC}")
            return 0
        else:
            print(f"\n{RED}{BOLD}✗ Coverage requirements not met:{NC}")
            for issue in issues:
                print(f"  {RED}- {issue}{NC}")
            return 1


def main():
    """Main entry point."""
    runner = ODPSUnitTestCoverage()
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
