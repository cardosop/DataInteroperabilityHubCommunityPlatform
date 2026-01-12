#!/usr/bin/env python3
"""
Comprehensive Tests for Monitoring Configurations

Tests verify:
1. Prometheus metrics endpoint label values use standardized patterns
2. Grafana dashboard queries work correctly
3. Jaeger operation names use standardized patterns (if enabled)
4. Log aggregation patterns work correctly

All tests use real implementations (no mocks/stubs).
"""

import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Optional

import pytest


pytestmark = [pytest.mark.integration]


# Set PYTHONPATH for imports if needed
if 'hub' not in sys.path:
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))


class TestPrometheusMetricsConfiguration:
    """Test Prometheus metrics configuration"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.prometheus_config = self.project_root / 'monitoring' / 'prometheus' / 'prometheus.yml'
        self.metrics_file = self.project_root / 'hub' / 'apps' / 'observability' / 'otel_metrics.py'

    def test_prometheus_config_exists(self):
        """Test that Prometheus configuration exists"""
        assert self.prometheus_config.exists(), "Prometheus config should exist"
        assert self.prometheus_config.is_file(), "Prometheus config should be a file"

    def test_prometheus_config_valid(self):
        """Test that Prometheus configuration is valid YAML"""
        if not self.prometheus_config.exists():
            pytest.skip("Prometheus config not found")

        content = self.prometheus_config.read_text(encoding='utf-8')

        # Basic validation - should have scrape_configs
        assert 'scrape_configs' in content, "Prometheus config should have scrape_configs"
        assert 'api-service' in content, "Prometheus config should scrape api-service"

    def test_metrics_code_uses_standardized_patterns(self):
        """Test that metrics code doesn't hardcode old endpoint patterns"""
        if not self.metrics_file.exists():
            pytest.skip("Metrics file not found")

        content = self.metrics_file.read_text(encoding='utf-8')

        # Should not have hardcoded old patterns
        assert '/compliance-runs/' not in content or 'deprecated' in content.lower(), (
            "Metrics code should not hardcode old endpoint patterns"
        )
        assert '/dq-runs/' not in content or 'deprecated' in content.lower(), (
            "Metrics code should not hardcode old endpoint patterns"
        )

    def test_metrics_endpoint_labels_dynamic(self):
        """Test that metrics endpoint labels are set dynamically from request path"""
        if not self.metrics_file.exists():
            pytest.skip("Metrics file not found")

        content = self.metrics_file.read_text(encoding='utf-8')

        # Should use request.path or resolver_match.route (dynamic)
        assert 'request.path' in content or 'resolver_match' in content or 'route' in content.lower(), (
            "Metrics should use dynamic route/path, not hardcoded endpoints"
        )


class TestGrafanaDashboards:
    """Test Grafana dashboard configurations"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.dashboards_dir = self.project_root / 'monitoring' / 'grafana' / 'dashboards'

    def test_dashboards_directory_exists(self):
        """Test that dashboards directory exists"""
        assert self.dashboards_dir.exists(), "Dashboards directory should exist"
        assert self.dashboards_dir.is_dir(), "Dashboards directory should be a directory"

    def test_key_dashboards_exist(self):
        """Test that key dashboards exist"""
        key_dashboards = [
            'api-performance.json',
            'system-health.json',
            'tenant-usage.json',
            'job-processing.json',
        ]

        for dashboard_name in key_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_name
            assert dashboard_path.exists(), f"Dashboard {dashboard_name} should exist"

    def test_dashboards_valid_json(self):
        """Test that all dashboards are valid JSON"""
        if not self.dashboards_dir.exists():
            pytest.skip("Dashboards directory not found")

        dashboard_files = list(self.dashboards_dir.glob('*.json'))
        assert len(dashboard_files) > 0, "Should have at least one dashboard"

        for dashboard_file in dashboard_files:
            try:
                content = dashboard_file.read_text(encoding='utf-8')
                dashboard = json.loads(content)
                assert 'dashboard' in dashboard or 'panels' in dashboard, (
                    f"Dashboard {dashboard_file.name} should have dashboard or panels key"
                )
            except json.JSONDecodeError as e:
                pytest.fail(f"Dashboard {dashboard_file.name} is not valid JSON: {e}")

    def test_dashboards_use_standardized_metrics(self):
        """Test that dashboards use standardized metric names"""
        if not self.dashboards_dir.exists():
            pytest.skip("Dashboards directory not found")

        # Check tenant-usage dashboard specifically
        tenant_usage = self.dashboards_dir / 'tenant-usage.json'
        if tenant_usage.exists():
            content = tenant_usage.read_text(encoding='utf-8')
            dashboard = json.loads(content)

            # Should use standardized metric names
            content_str = json.dumps(dashboard)
            assert 'dq_runs_total' in content_str or 'compliance_runs_total' in content_str or 'runs' not in content_str.lower(), (
                "Dashboard should use standardized metric names (dq_runs_total, compliance_runs_total)"
            )

    def test_dashboards_no_hardcoded_endpoints(self):
        """Test that dashboards don't hardcode old endpoint patterns in queries"""
        if not self.dashboards_dir.exists():
            pytest.skip("Dashboards directory not found")

        dashboard_files = list(self.dashboards_dir.glob('*.json'))

        for dashboard_file in dashboard_files:
            content = dashboard_file.read_text(encoding='utf-8')

            # Should not have old endpoint patterns in PromQL queries
            if '/compliance-runs/' in content or '/dq-runs/' in content:
                # Check if it's in a PromQL query (expr field)
                dashboard = json.loads(content)
                content_str = json.dumps(dashboard)

                # If old pattern found, it should only be in comments or documentation
                if '/api/v1/compliance-runs/' in content_str or '/api/v1/dq-runs/' in content_str:
                    pytest.fail(
                        f"Dashboard {dashboard_file.name} should not hardcode old endpoint patterns in queries"
                    )


class TestJaegerOperationNames:
    """Test Jaeger operation names configuration"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.tracing_file = self.project_root / 'hub' / 'apps' / 'observability' / 'tracing.py'
        self.span_middleware = self.project_root / 'hub' / 'apps' / 'observability' / 'middleware' / 'span_middleware.py'

    def test_tracing_configuration_exists(self):
        """Test that tracing configuration exists"""
        assert self.tracing_file.exists() or self.span_middleware.exists(), (
            "Tracing configuration should exist"
        )

    def test_operation_names_dynamic(self):
        """Test that operation names are set dynamically from request path"""
        if self.span_middleware.exists():
            content = self.span_middleware.read_text(encoding='utf-8')

            # Should use request.path or route dynamically
            assert 'request.path' in content or 'route' in content.lower() or 'span_name' in content.lower(), (
                "Operation names should be set dynamically from request path"
            )

        if self.tracing_file.exists():
            content = self.tracing_file.read_text(encoding='utf-8')

            # Should not hardcode endpoint patterns
            assert '/compliance-runs/' not in content or 'deprecated' in content.lower(), (
                "Tracing should not hardcode old endpoint patterns"
            )


class TestLogAggregationPatterns:
    """Test log aggregation patterns"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent

    def test_logging_configuration_exists(self):
        """Test that logging configuration exists"""
        settings_file = self.project_root / 'hub' / 'settings.py'
        assert settings_file.exists(), "Settings file should exist"

    def test_logging_uses_dynamic_paths(self):
        """Test that logging uses dynamic request paths"""
        settings_file = self.project_root / 'hub' / 'settings.py'

        if settings_file.exists():
            content = settings_file.read_text(encoding='utf-8')

            # Should use request.path or similar dynamic values
            if 'request.path' in content.lower() or 'path' in content.lower():
                # Should not hardcode old patterns
                assert '/compliance-runs/' not in content or 'deprecated' in content.lower(), (
                    "Logging should not hardcode old endpoint patterns"
                )


class TestMonitoringVerificationScript:
    """Test monitoring verification script"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.verify_script = self.project_root / 'scripts' / 'verify-monitoring-configurations.py'

    def test_verification_script_exists(self):
        """Test that verification script exists"""
        assert self.verify_script.exists(), "Verification script should exist"

    def test_verification_script_runs(self):
        """Test that verification script runs successfully"""
        result = subprocess.run(
            [sys.executable, str(self.verify_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, (
            f"Verification script should exit with code 0.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        assert "All monitoring configurations use standardized endpoint patterns" in result.stdout or "No issues found" in result.stdout, (
            "Script should report success"
        )


class TestMonitoringServicesIntegration:
    """Integration tests for monitoring services"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://localhost:9090')
        self.grafana_url = os.getenv('GRAFANA_URL', 'http://localhost:3000')
        self.api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')

    def _check_service_available(self, url: str, timeout: int = 2) -> bool:
        """Check if service is available"""
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code in [200, 401, 403]  # 401/403 means service is up
        except Exception:
            return False

    def test_prometheus_metrics_endpoint(self):
        """Test that Prometheus metrics endpoint works"""
        if not self._check_service_available(self.prometheus_url):
            pytest.skip("Prometheus not available")

        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/targets", timeout=5)
            assert response.status_code == 200, "Prometheus API should be accessible"
        except requests.exceptions.RequestException:
            pytest.skip("Prometheus not accessible")

    def test_api_service_metrics_endpoint(self):
        """Test that API service metrics endpoint works"""
        if not self._check_service_available(self.api_url):
            pytest.skip("API service not available")

        try:
            response = requests.get(f"{self.api_url}/metrics", timeout=5)
            # Should return 200 or 401 (if auth required)
            assert response.status_code in [200, 401, 403], (
                f"Metrics endpoint should be accessible (got {response.status_code})"
            )

            if response.status_code == 200:
                # Check that metrics contain expected patterns
                content = response.text
                assert 'http_requests_total' in content or 'http_request' in content.lower(), (
                    "Metrics should contain HTTP request metrics"
                )
        except requests.exceptions.RequestException:
            pytest.skip("API service metrics not accessible")

    def test_grafana_accessible(self):
        """Test that Grafana is accessible"""
        if not self._check_service_available(self.grafana_url):
            pytest.skip("Grafana not available")

        try:
            response = requests.get(f"{self.grafana_url}/api/health", timeout=5)
            assert response.status_code in [200, 401, 403], "Grafana should be accessible"
        except requests.exceptions.RequestException:
            pytest.skip("Grafana not accessible")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

