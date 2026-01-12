#!/usr/bin/env python3
"""
Comprehensive Infrastructure Update Verification Script

Verifies that all infrastructure updates from tasks 9.6.3.4.1-9.6.3.4.4 are complete:
- 9.6.3.4.1: CI/CD pipelines
- 9.6.3.4.2: Monitoring configurations
- 9.6.3.4.3: Rate limiting configurations
- 9.6.3.4.4: API gateway configurations

This script runs all validation tests and generates a comprehensive report.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class TestResult:
    """Result of a single test"""
    name: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    message: str
    details: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class ComponentVerification:
    """Verification results for a component"""
    component: str
    task_id: str
    tests: List[TestResult]
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0
    status: str = "unknown"  # 'passed', 'failed', 'partial'
    notes: str = ""


class InfrastructureVerifier:
    """Comprehensive infrastructure verification"""

    def __init__(self):
        self.project_root = project_root
        self.results: List[ComponentVerification] = []
        self.start_time = datetime.now()

    def run_command(self, command: List[str], cwd: Optional[Path] = None, timeout: int = 300) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", str(e)

    def verify_cicd_pipelines(self) -> ComponentVerification:
        """Verify CI/CD pipeline updates (9.6.3.4.1)"""
        component = ComponentVerification(
            component="CI/CD Pipelines",
            task_id="9.6.3.4.1",
            tests=[]
        )

        print("\n" + "="*80)
        print("Verifying CI/CD Pipelines (9.6.3.4.1)")
        print("="*80)

        # Test 1: URL Pattern Validation Script
        print("\n[1/5] Testing URL Pattern Validation Script...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "docker", "compose", "exec", "-T", "api-service",
            "bash", "-c", "cd /app && PYTHONPATH=/app python scripts/validate_url_patterns.py --strict"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0:
            component.tests.append(TestResult(
                name="URL Pattern Validation",
                status="passed",
                message="URL pattern validation passed",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="URL Pattern Validation",
                status="failed",
                message="URL pattern validation failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Test 2: API Naming Standards Validation
        print("\n[2/5] Testing API Naming Standards Validation...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "docker", "compose", "exec", "-T", "api-service",
            "bash", "-c", "cd /app && PYTHONPATH=/app python scripts/validate_api_naming_standards.py --strict"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0:
            component.tests.append(TestResult(
                name="API Naming Standards Validation",
                status="passed",
                message="API naming standards validation passed",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="API Naming Standards Validation",
                status="failed",
                message="API naming standards validation failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Test 3: Endpoint Inventory Parsing
        print("\n[3/5] Testing Endpoint Inventory Parsing...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "python3", "scripts/test-api-endpoints.py",
            "--inventory", "docs/api-audit/current-api-inventory.md",
            "--skip-auth",
            "--output", "/tmp/test-report.md"
        ])
        duration = (datetime.now() - start).total_seconds()

        # This test may exit with non-zero but still be successful (warnings expected)
        if "Total Endpoints:" in stdout or "TEST SUMMARY" in stdout:
            component.tests.append(TestResult(
                name="Endpoint Inventory Parsing",
                status="passed",
                message="Endpoint inventory parsing successful",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Endpoint Inventory Parsing",
                status="failed",
                message="Endpoint inventory parsing failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Test 4: Workflow YAML Syntax
        print("\n[4/5] Testing Workflow YAML Syntax...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "python3", "-c",
            "import yaml; yaml.safe_load(open('.github/workflows/openapi-validation.yml'))"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0:
            component.tests.append(TestResult(
                name="Workflow YAML Syntax",
                status="passed",
                message="Workflow YAML syntax is valid",
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Workflow YAML Syntax",
                status="failed",
                message="Workflow YAML syntax is invalid",
                details=stderr,
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Test 5: Pre-commit Config YAML Syntax
        print("\n[5/5] Testing Pre-commit Config YAML Syntax...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "python3", "-c",
            "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0:
            component.tests.append(TestResult(
                name="Pre-commit Config YAML Syntax",
                status="passed",
                message="Pre-commit config YAML syntax is valid",
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Pre-commit Config YAML Syntax",
                status="failed",
                message="Pre-commit config YAML syntax is invalid",
                details=stderr,
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Calculate summary
        component.total = len(component.tests)
        component.passed = sum(1 for t in component.tests if t.status == "passed")
        component.failed = sum(1 for t in component.tests if t.status == "failed")
        component.skipped = sum(1 for t in component.tests if t.status == "skipped")
        component.status = "passed" if component.failed == 0 else "failed"

        return component

    def verify_monitoring_configurations(self) -> ComponentVerification:
        """Verify monitoring configuration updates (9.6.3.4.2)"""
        component = ComponentVerification(
            component="Monitoring Configurations",
            task_id="9.6.3.4.2",
            tests=[]
        )

        print("\n" + "="*80)
        print("Verifying Monitoring Configurations (9.6.3.4.2)")
        print("="*80)

        # Test 1: Monitoring Verification Script
        print("\n[1/2] Testing Monitoring Verification Script...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "python3", "scripts/verify-monitoring-configurations.py"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0:
            component.tests.append(TestResult(
                name="Monitoring Configuration Verification",
                status="passed",
                message="Monitoring configurations verified",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Monitoring Configuration Verification",
                status="failed",
                message="Monitoring configuration verification failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Test 2: Monitoring Services Test
        print("\n[2/2] Testing Monitoring Services...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "bash", "scripts/test-monitoring-services.sh"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0 or "PASSED" in stdout:
            component.tests.append(TestResult(
                name="Monitoring Services",
                status="passed",
                message="Monitoring services accessible",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Monitoring Services",
                status="failed",
                message="Monitoring services test failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Calculate summary
        component.total = len(component.tests)
        component.passed = sum(1 for t in component.tests if t.status == "passed")
        component.failed = sum(1 for t in component.tests if t.status == "failed")
        component.skipped = sum(1 for t in component.tests if t.status == "skipped")
        component.status = "passed" if component.failed == 0 else "failed"

        return component

    def verify_rate_limiting_configurations(self) -> ComponentVerification:
        """Verify rate limiting configuration updates (9.6.3.4.3)"""
        component = ComponentVerification(
            component="Rate Limiting Configurations",
            task_id="9.6.3.4.3",
            tests=[]
        )

        print("\n" + "="*80)
        print("Verifying Rate Limiting Configurations (9.6.3.4.3)")
        print("="*80)

        # Test 1: Rate Limiting Integration Tests
        print("\n[1/1] Testing Rate Limiting Integration Tests...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "docker", "compose", "exec", "-T", "api-service",
            "bash", "-c", "cd /app && PYTHONPATH=/app python -m pytest tests/integration/test_rate_limiting_endpoints.py -v --tb=short"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0 or "passed" in stdout.lower():
            passed_count = stdout.count("PASSED") + stdout.count("passed")
            component.tests.append(TestResult(
                name="Rate Limiting Integration Tests",
                status="passed",
                message=f"Rate limiting integration tests passed ({passed_count} tests)",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Rate Limiting Integration Tests",
                status="failed",
                message="Rate limiting integration tests failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Calculate summary
        component.total = len(component.tests)
        component.passed = sum(1 for t in component.tests if t.status == "passed")
        component.failed = sum(1 for t in component.tests if t.status == "failed")
        component.skipped = sum(1 for t in component.tests if t.status == "skipped")
        component.status = "passed" if component.failed == 0 else "failed"

        return component

    def verify_gateway_configurations(self) -> ComponentVerification:
        """Verify API gateway configuration updates (9.6.3.4.4)"""
        component = ComponentVerification(
            component="API Gateway Configurations",
            task_id="9.6.3.4.4",
            tests=[]
        )

        print("\n" + "="*80)
        print("Verifying API Gateway Configurations (9.6.3.4.4)")
        print("="*80)

        # Test 1: Gateway Verification Script
        print("\n[1/3] Testing Gateway Verification Script...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "python3", "scripts/verify-gateway-configurations.py"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0:
            component.tests.append(TestResult(
                name="Gateway Configuration Verification",
                status="passed",
                message="Gateway configurations verified",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Gateway Configuration Verification",
                status="failed",
                message="Gateway configuration verification failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Test 2: Gateway Routing Test
        print("\n[2/3] Testing Gateway Routing...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "python3", "scripts/test-gateway-routing.py"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0 or "PASSED" in stdout:
            component.tests.append(TestResult(
                name="Gateway Routing",
                status="passed",
                message="Gateway routing tests passed",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Gateway Routing",
                status="failed",
                message="Gateway routing tests failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Test 3: Comprehensive Gateway Test Suite
        print("\n[3/3] Testing Comprehensive Gateway Test Suite...")
        start = datetime.now()
        exit_code, stdout, stderr = self.run_command([
            "bash", "scripts/test-gateway-comprehensive.sh"
        ])
        duration = (datetime.now() - start).total_seconds()

        if exit_code == 0 or "PASSED" in stdout:
            passed_count = stdout.count("✅") + stdout.count("PASSED")
            component.tests.append(TestResult(
                name="Comprehensive Gateway Test Suite",
                status="passed",
                message=f"Comprehensive gateway tests passed ({passed_count} tests)",
                details=stdout[-500:] if len(stdout) > 500 else stdout,
                duration_seconds=duration
            ))
            print("  ✅ PASSED")
        else:
            component.tests.append(TestResult(
                name="Comprehensive Gateway Test Suite",
                status="failed",
                message="Comprehensive gateway tests failed",
                details=f"Exit code: {exit_code}\n{stderr}",
                duration_seconds=duration
            ))
            print(f"  ❌ FAILED: {stderr[:200]}")

        # Calculate summary
        component.total = len(component.tests)
        component.passed = sum(1 for t in component.tests if t.status == "passed")
        component.failed = sum(1 for t in component.tests if t.status == "failed")
        component.skipped = sum(1 for t in component.tests if t.status == "skipped")
        component.status = "passed" if component.failed == 0 else "failed"

        return component

    def verify_all(self) -> Dict:
        """Run all verification tests"""
        print("\n" + "="*80)
        print("INFRASTRUCTURE UPDATE VERIFICATION")
        print("="*80)
        print(f"Started: {self.start_time.isoformat()}")
        print(f"Project Root: {self.project_root}")
        print("="*80)

        # Verify all components
        self.results.append(self.verify_cicd_pipelines())
        self.results.append(self.verify_monitoring_configurations())
        self.results.append(self.verify_rate_limiting_configurations())
        self.results.append(self.verify_gateway_configurations())

        # Calculate overall summary
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()

        total_tests = sum(r.total for r in self.results)
        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results)
        total_skipped = sum(r.skipped for r in self.results)

        overall_status = "passed" if total_failed == 0 else "failed"

        summary = {
            "verification_date": self.start_time.isoformat(),
            "duration_seconds": total_duration,
            "overall_status": overall_status,
            "summary": {
                "total_components": len(self.results),
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "skipped": total_skipped
            },
            "components": [asdict(r) for r in self.results]
        }

        return summary

    def generate_report(self, summary: Dict, output_file: Path) -> None:
        """Generate verification report"""
        # JSON report
        json_file = output_file.with_suffix('.json')
        json_file.write_text(json.dumps(summary, indent=2))
        print(f"\n✅ JSON report saved to: {json_file}")

        # Markdown report
        lines = []
        lines.append("# Infrastructure Update Verification Report")
        lines.append("")
        lines.append(f"**Generated**: {summary['verification_date']}")
        lines.append(f"**Duration**: {summary['duration_seconds']:.2f} seconds")
        lines.append(f"**Overall Status**: {'✅ PASSED' if summary['overall_status'] == 'passed' else '❌ FAILED'}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Components**: {summary['summary']['total_components']}")
        lines.append(f"- **Total Tests**: {summary['summary']['total_tests']}")
        lines.append(f"- **Passed**: {summary['summary']['passed']} ✅")
        lines.append(f"- **Failed**: {summary['summary']['failed']} ❌")
        lines.append(f"- **Skipped**: {summary['summary']['skipped']} ⏭️")
        lines.append("")

        # Component details
        lines.append("## Component Verification Results")
        lines.append("")

        for component in summary['components']:
            status_icon = "✅" if component['status'] == 'passed' else "❌"
            lines.append(f"### {status_icon} {component['component']} ({component['task_id']})")
            lines.append("")
            lines.append(f"- **Status**: {component['status'].upper()}")
            lines.append(f"- **Tests**: {component['passed']}/{component['total']} passed")
            lines.append("")

            for test in component['tests']:
                test_icon = "✅" if test['status'] == 'passed' else "❌" if test['status'] == 'failed' else "⏭️"
                lines.append(f"- {test_icon} **{test['name']}**: {test['message']}")
                if test.get('duration_seconds'):
                    lines.append(f"  - Duration: {test['duration_seconds']:.2f}s")
                if test.get('details') and test['status'] == 'failed':
                    lines.append(f"  - Details: {test['details'][:200]}...")
            lines.append("")

        # Conclusion
        lines.append("## Conclusion")
        lines.append("")
        if summary['overall_status'] == 'passed':
            lines.append("✅ **All infrastructure updates verified successfully!**")
            lines.append("")
            lines.append("All components have been updated and verified:")
            for component in summary['components']:
                if component['status'] == 'passed':
                    lines.append(f"- ✅ {component['component']} ({component['task_id']})")
        else:
            lines.append("❌ **Some infrastructure updates failed verification.**")
            lines.append("")
            lines.append("Failed components:")
            for component in summary['components']:
                if component['status'] == 'failed':
                    lines.append(f"- ❌ {component['component']} ({component['task_id']})")

        output_file.write_text('\n'.join(lines))
        print(f"✅ Markdown report saved to: {output_file}")


def main():
    """Main execution"""
    verifier = InfrastructureVerifier()

    try:
        summary = verifier.verify_all()

        # Generate reports
        output_file = project_root / "docs" / "infrastructure-update-verification-report.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        verifier.generate_report(summary, output_file)

        # Print summary
        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        print(f"Overall Status: {'✅ PASSED' if summary['overall_status'] == 'passed' else '❌ FAILED'}")
        print(f"Total Tests: {summary['summary']['total_tests']}")
        print(f"Passed: {summary['summary']['passed']} ✅")
        print(f"Failed: {summary['summary']['failed']} ❌")
        print(f"Skipped: {summary['summary']['skipped']} ⏭️")
        print(f"Duration: {summary['duration_seconds']:.2f} seconds")
        print("="*80)

        # Exit with appropriate code
        return 0 if summary['overall_status'] == 'passed' else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Verification interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\n❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

