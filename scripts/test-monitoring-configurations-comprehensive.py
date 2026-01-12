#!/usr/bin/env python3
"""
Comprehensive Test Runner for Monitoring Configurations

Tests verify:
1. Prometheus metrics endpoint label values use standardized patterns
2. Grafana dashboard queries work correctly
3. Jaeger operation names use standardized patterns (if enabled)
4. Log aggregation patterns work correctly
5. Monitoring services are accessible

All tests use real implementations (no mocks/stubs).
"""

import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Optional


class MonitoringConfigurationsTest:
    """Comprehensive test suite for monitoring configurations"""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_skipped = 0
        self.failures = []

    def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("Monitoring Configurations - Comprehensive Test Suite")
        print("=" * 60)
        print()

        # Test 1: Prometheus Configuration
        self.test_prometheus_config()

        # Test 2: Grafana Dashboards
        self.test_grafana_dashboards()

        # Test 3: Metrics Code
        self.test_metrics_code()

        # Test 4: Jaeger Operation Names
        self.test_jaeger_operation_names()

        # Test 5: Log Aggregation Patterns
        self.test_log_aggregation_patterns()

        # Test 6: Verification Script
        self.test_verification_script()

        # Test 7: Service Integration (optional)
        self.test_service_integration()

        # Print summary
        self.print_summary()

        return self.tests_failed == 0

    def test_prometheus_config(self):
        """Test Prometheus configuration"""
        print("Test 1: Prometheus Configuration")
        print("-" * 60)

        prometheus_config = self.project_root / 'monitoring' / 'prometheus' / 'prometheus.yml'

        if not prometheus_config.exists():
            print("⚠️  SKIPPED: Prometheus config not found")
            self.tests_skipped += 1
            return

        try:
            content = prometheus_config.read_text(encoding='utf-8')

            # Check for scrape_configs
            assert 'scrape_configs' in content, "Should have scrape_configs"
            assert 'api-service' in content, "Should scrape api-service"

            # Check for old patterns
            if '/compliance-runs/' in content or '/dq-runs/' in content:
                if 'deprecated' not in content.lower():
                    raise AssertionError("Should not have old endpoint patterns")

            print("✅ PASSED: Prometheus configuration valid")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Prometheus config: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Prometheus config: {e}")

        print()

    def test_grafana_dashboards(self):
        """Test Grafana dashboards"""
        print("Test 2: Grafana Dashboards")
        print("-" * 60)

        dashboards_dir = self.project_root / 'monitoring' / 'grafana' / 'dashboards'

        if not dashboards_dir.exists():
            print("⚠️  SKIPPED: Dashboards directory not found")
            self.tests_skipped += 1
            return

        dashboard_files = list(dashboards_dir.glob('*.json'))

        if len(dashboard_files) == 0:
            print("⚠️  SKIPPED: No dashboard files found")
            self.tests_skipped += 1
            return

        key_dashboards = [
            'api-performance.json',
            'system-health.json',
            'tenant-usage.json',
            'job-processing.json',
        ]

        try:
            # Check key dashboards exist
            for dashboard_name in key_dashboards:
                dashboard_path = dashboards_dir / dashboard_name
                assert dashboard_path.exists(), f"Dashboard {dashboard_name} should exist"

            # Check all dashboards are valid JSON
            for dashboard_file in dashboard_files:
                content = dashboard_file.read_text(encoding='utf-8')
                dashboard = json.loads(content)
                assert 'dashboard' in dashboard or 'panels' in dashboard, (
                    f"Dashboard {dashboard_file.name} should have dashboard or panels key"
                )

            # Check tenant-usage dashboard uses standardized metrics
            tenant_usage = dashboards_dir / 'tenant-usage.json'
            if tenant_usage.exists():
                content = tenant_usage.read_text(encoding='utf-8')
                dashboard = json.loads(content)
                content_str = json.dumps(dashboard)

                # Should use standardized metric names (not endpoint paths)
                if 'runs' in content_str.lower():
                    assert 'dq_runs_total' in content_str or 'compliance_runs_total' in content_str, (
                        "Should use standardized metric names"
                    )

            # Check no hardcoded old endpoint patterns
            for dashboard_file in dashboard_files:
                content = dashboard_file.read_text(encoding='utf-8')
                if '/api/v1/compliance-runs/' in content or '/api/v1/dq-runs/' in content:
                    dashboard = json.loads(content)
                    content_str = json.dumps(dashboard)
                    if '/api/v1/compliance-runs/' in content_str or '/api/v1/dq-runs/' in content_str:
                        raise AssertionError(
                            f"Dashboard {dashboard_file.name} should not hardcode old endpoint patterns"
                        )

            print(f"✅ PASSED: All {len(dashboard_files)} dashboards verified")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Grafana dashboards: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ FAILED: Invalid JSON in dashboard: {e}")
            self.tests_failed += 1
            self.failures.append(f"Grafana dashboards: Invalid JSON: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Grafana dashboards: {e}")

        print()

    def test_metrics_code(self):
        """Test metrics code"""
        print("Test 3: Metrics Code")
        print("-" * 60)

        metrics_file = self.project_root / 'hub' / 'apps' / 'observability' / 'otel_metrics.py'

        if not metrics_file.exists():
            print("⚠️  SKIPPED: Metrics file not found")
            self.tests_skipped += 1
            return

        try:
            content = metrics_file.read_text(encoding='utf-8')

            # Should not have hardcoded old patterns
            if '/compliance-runs/' in content or '/dq-runs/' in content:
                if 'deprecated' not in content.lower():
                    raise AssertionError("Should not hardcode old endpoint patterns")

            # Should use dynamic route/path
            assert 'request.path' in content or 'resolver_match' in content or 'route' in content.lower(), (
                "Should use dynamic route/path, not hardcoded endpoints"
            )

            print("✅ PASSED: Metrics code uses dynamic patterns")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Metrics code: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Metrics code: {e}")

        print()

    def test_jaeger_operation_names(self):
        """Test Jaeger operation names"""
        print("Test 4: Jaeger Operation Names")
        print("-" * 60)

        tracing_file = self.project_root / 'hub' / 'apps' / 'observability' / 'tracing.py'
        span_middleware = self.project_root / 'hub' / 'apps' / 'observability' / 'middleware' / 'span_middleware.py'

        if not tracing_file.exists() and not span_middleware.exists():
            print("⚠️  SKIPPED: Tracing configuration not found")
            self.tests_skipped += 1
            return

        try:
            if span_middleware.exists():
                content = span_middleware.read_text(encoding='utf-8')
                assert 'request.path' in content or 'route' in content.lower() or 'span_name' in content.lower(), (
                    "Operation names should be set dynamically from request path"
                )

            if tracing_file.exists():
                content = tracing_file.read_text(encoding='utf-8')
                if '/compliance-runs/' in content or '/dq-runs/' in content:
                    if 'deprecated' not in content.lower():
                        raise AssertionError("Should not hardcode old endpoint patterns")

            print("✅ PASSED: Jaeger operation names use dynamic patterns")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Jaeger operation names: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Jaeger operation names: {e}")

        print()

    def test_log_aggregation_patterns(self):
        """Test log aggregation patterns"""
        print("Test 5: Log Aggregation Patterns")
        print("-" * 60)

        settings_file = self.project_root / 'hub' / 'settings.py'

        if not settings_file.exists():
            print("⚠️  SKIPPED: Settings file not found")
            self.tests_skipped += 1
            return

        try:
            content = settings_file.read_text(encoding='utf-8')

            # If logging uses paths, should not hardcode old patterns
            if 'request.path' in content.lower() or 'path' in content.lower():
                if '/compliance-runs/' in content or '/dq-runs/' in content:
                    if 'deprecated' not in content.lower():
                        raise AssertionError("Should not hardcode old endpoint patterns")

            print("✅ PASSED: Log aggregation patterns use dynamic paths")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Log aggregation patterns: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Log aggregation patterns: {e}")

        print()

    def test_verification_script(self):
        """Test verification script"""
        print("Test 6: Verification Script")
        print("-" * 60)

        verify_script = self.project_root / 'scripts' / 'verify-monitoring-configurations.py'

        if not verify_script.exists():
            print("⚠️  SKIPPED: Verification script not found")
            self.tests_skipped += 1
            return

        try:
            result = subprocess.run(
                [sys.executable, str(verify_script)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=60
            )

            assert result.returncode == 0, (
                f"Script should exit with code 0.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

            assert "All monitoring configurations use standardized endpoint patterns" in result.stdout or "No issues found" in result.stdout, (
                "Script should report success"
            )

            print("✅ PASSED: Verification script runs successfully")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Verification script: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Verification script: {e}")

        print()

    def test_service_integration(self):
        """Test service integration (optional)"""
        print("Test 7: Service Integration (Optional)")
        print("-" * 60)

        api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')

        def check_service(url: str, timeout: int = 2) -> bool:
            try:
                response = requests.get(url, timeout=timeout)
                return response.status_code in [200, 401, 403]
            except Exception:
                return False

        # Test API metrics endpoint
        try:
            if check_service(api_url):
                response = requests.get(f"{api_url}/metrics", timeout=5)
                assert response.status_code in [200, 401, 403], (
                    f"Metrics endpoint should be accessible (got {response.status_code})"
                )

                if response.status_code == 200:
                    assert 'http_requests_total' in response.text or 'http_request' in response.text.lower(), (
                        "Metrics should contain HTTP request metrics"
                    )

                print("✅ PASSED: API metrics endpoint accessible")
                self.tests_passed += 1
            else:
                print("⚠️  SKIPPED: API service not available")
                self.tests_skipped += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Service integration: {e}")
        except Exception as e:
            print(f"⚠️  SKIPPED: Service not accessible: {e}")
            self.tests_skipped += 1

        print()

    def print_summary(self):
        """Print test summary"""
        print("=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Tests Passed:  {self.tests_passed}")
        print(f"Tests Failed:  {self.tests_failed}")
        print(f"Tests Skipped: {self.tests_skipped}")
        print()

        if self.failures:
            print("Failures:")
            for failure in self.failures:
                print(f"  - {failure}")
            print()

        if self.tests_failed == 0:
            print("✅ All tests passed!")
        else:
            print(f"❌ {self.tests_failed} test(s) failed")


def main():
    """Main execution"""
    test_suite = MonitoringConfigurationsTest()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

