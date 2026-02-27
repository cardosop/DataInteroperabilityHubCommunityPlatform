#!/usr/bin/env python3
"""
Comprehensive Integration Tests for API Gateway Configurations

Tests verify:
1. Traefik route configurations use standardized endpoint patterns
2. Kubernetes ingress rules are correctly configured
3. Gateway routing works correctly (if services available)
4. Ingress rules are applied correctly

All tests use real implementations (no mocks/stubs).
"""

import os
import sys
import json
import yaml
import subprocess
import requests
import re
from pathlib import Path
from typing import Dict, List, Optional

import pytest


pytestmark = [pytest.mark.integration]


class TestTraefikConfiguration:
    """Test Traefik route configurations"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.routes_file = self.project_root / 'infrastructure' / 'traefik' / 'dynamic' / 'routes.yml'
        self.k8s_configmap = self.project_root / 'k8s' / 'api-gateway' / 'traefik' / 'configmap.yaml'

    def test_traefik_routes_file_exists(self):
        """Test that Traefik routes file exists"""
        assert self.routes_file.exists(), "Traefik routes file should exist"
        assert self.routes_file.is_file(), "Traefik routes file should be a file"

    def test_compliance_service_route_configured(self):
        """Test that compliance service is configured (API Gateway architecture)"""
        if not self.routes_file.exists():
            pytest.skip("Traefik routes file not found")

        content = self.routes_file.read_text(encoding='utf-8')

        # Architecture: Traefik routes /api/v1 to api-gateway; API Gateway routes internally
        assert 'api-gateway' in content, "API gateway route should exist"
        assert 'PathPrefix(`/api/v1`)' in content, (
            "API gateway should use PathPrefix /api/v1"
        )
        assert 'compliance-service:' in content, "Should have compliance service definition"
        assert '/api/v1/compliance/compliance-runs' not in content, (
            "Should not use old compliance-runs pattern"
        )

    def test_dq_service_route_configured(self):
        """Test that DQ service is configured (API Gateway architecture)"""
        if not self.routes_file.exists():
            pytest.skip("Traefik routes file not found")

        content = self.routes_file.read_text(encoding='utf-8')

        # Architecture: Traefik routes /api/v1 to api-gateway; API Gateway routes internally
        assert 'api-gateway' in content, "API gateway route should exist"
        assert 'PathPrefix(`/api/v1`)' in content, (
            "API gateway should use PathPrefix /api/v1"
        )
        assert 'dq-service:' in content, "Should have DQ service definition"
        assert '/api/v1/dq/dq-runs' not in content, (
            "Should not use old dq-runs pattern"
        )

    def test_service_definitions_exist(self):
        """Test that service definitions exist"""
        if not self.routes_file.exists():
            pytest.skip("Traefik routes file not found")

        content = self.routes_file.read_text(encoding='utf-8')

        # Should have services section
        assert 'services:' in content, "Should have services section"
        assert 'compliance-service:' in content and 'loadBalancer:' in content, (
            "Should have compliance service definition"
        )
        assert 'dq-service:' in content and 'loadBalancer:' in content, (
            "Should have DQ service definition"
        )

    def test_k8s_configmap_configured(self):
        """Test that Kubernetes ConfigMap is configured correctly (API Gateway architecture)"""
        if not self.k8s_configmap.exists():
            pytest.skip("K8s ConfigMap not found")

        content = self.k8s_configmap.read_text(encoding='utf-8')

        # Architecture: api-gateway route with PathPrefix /api/v1; compliance/dq as backend defs
        assert 'PathPrefix(`/api/v1`)' in content, (
            "K8s ConfigMap should have api-gateway route with PathPrefix /api/v1"
        )
        assert 'compliance-service:' in content, "Should have compliance service definition"
        assert 'dq-service:' in content, "Should have DQ service definition"
        assert '/api/v1/compliance/compliance-runs' not in content, (
            "Should not use old compliance-runs pattern"
        )
        assert '/api/v1/dq/dq-runs' not in content, (
            "Should not use old dq-runs pattern"
        )


class TestKubernetesIngressRules:
    """Test Kubernetes ingress rules"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.ingress_files = list((self.project_root / 'k8s').rglob('**/ingress.yaml'))

    def test_ingress_files_exist(self):
        """Test that ingress files exist"""
        assert len(self.ingress_files) > 0, "Should have at least one ingress file"

    def test_compliance_service_ingress(self):
        """Test compliance service ingress configuration"""
        compliance_ingress = None
        for ingress_file in self.ingress_files:
            if 'compliance' in str(ingress_file).lower():
                compliance_ingress = ingress_file
                break

        if not compliance_ingress or not compliance_ingress.exists():
            pytest.skip("Compliance service ingress not found")

        content = compliance_ingress.read_text(encoding='utf-8')
        ingress = yaml.safe_load(content)

        # Should not have old patterns in paths
        if 'spec' in ingress and 'rules' in ingress['spec']:
            for rule in ingress['spec']['rules']:
                if 'http' in rule and 'paths' in rule['http']:
                    for path in rule['http']['paths']:
                        path_value = path.get('path', '')
                        assert '/compliance-runs' not in path_value, (
                            f"Compliance ingress should not use old pattern: {path_value}"
                        )

    def test_dq_service_ingress(self):
        """Test DQ service ingress configuration"""
        dq_ingress = None
        for ingress_file in self.ingress_files:
            if 'dq' in str(ingress_file).lower() and 'service' in str(ingress_file).lower():
                dq_ingress = ingress_file
                break

        if not dq_ingress or not dq_ingress.exists():
            pytest.skip("DQ service ingress not found")

        content = dq_ingress.read_text(encoding='utf-8')
        ingress = yaml.safe_load(content)

        # Should not have old patterns in paths
        if 'spec' in ingress and 'rules' in ingress['spec']:
            for rule in ingress['spec']['rules']:
                if 'http' in rule and 'paths' in rule['http']:
                    for path in rule['http']['paths']:
                        path_value = path.get('path', '')
                        assert '/dq-runs' not in path_value, (
                            f"DQ ingress should not use old pattern: {path_value}"
                        )

    def test_all_ingress_files_valid_yaml(self):
        """Test that all ingress files are valid YAML"""
        for ingress_file in self.ingress_files:
            try:
                content = ingress_file.read_text(encoding='utf-8')
                ingress = yaml.safe_load(content)
                assert ingress is not None, f"Ingress file {ingress_file.name} should be valid YAML"
            except yaml.YAMLError as e:
                pytest.fail(f"Ingress file {ingress_file.name} is not valid YAML: {e}")


class TestGatewayRouting:
    """Test gateway routing functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.gateway_url = os.getenv('GATEWAY_URL', 'http://localhost')

    def _check_service_available(self, url: str, timeout: int = 2) -> bool:
        """Check if service is available"""
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code in [200, 401, 403, 404]
        except Exception:
            return False

    def test_compliance_endpoint_routing(self):
        """Test that compliance endpoints are routable"""
        if not self._check_service_available(self.api_url):
            pytest.skip("API service not available")

        try:
            # Test compliance runs endpoint
            response = requests.get(
                f"{self.api_url}/api/v1/compliance/runs/",
                timeout=5
            )

            # Should return 401 (auth required) or 404 (not found), not 500 (server error)
            assert response.status_code != 500, (
                f"Compliance endpoint should not return 500 (got {response.status_code})"
            )
            assert response.status_code in [200, 401, 403, 404], (
                f"Compliance endpoint should be routable (got {response.status_code})"
            )
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not connect to API: {e}")

    def test_dq_endpoint_routing(self):
        """Test that DQ endpoints are routable"""
        if not self._check_service_available(self.api_url):
            pytest.skip("API service not available")

        try:
            # Test DQ runs endpoint
            response = requests.get(
                f"{self.api_url}/api/v1/dq/runs/",
                timeout=5
            )

            # Should return 401 (auth required) or 404 (not found), not 500 (server error)
            assert response.status_code != 500, (
                f"DQ endpoint should not return 500 (got {response.status_code})"
            )
            assert response.status_code in [200, 401, 403, 404], (
                f"DQ endpoint should be routable (got {response.status_code})"
            )
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not connect to API: {e}")

    def test_old_patterns_not_routable(self):
        """Test that old endpoint patterns are not routable (should return 404)"""
        if not self._check_service_available(self.api_url):
            pytest.skip("API service not available")

        try:
            # Test old compliance-runs pattern
            response = requests.get(
                f"{self.api_url}/api/v1/compliance/compliance-runs/",
                timeout=5
            )

            # Should return 404 (not found) or 401 (auth required), not 200
            assert response.status_code in [404, 401, 403], (
                f"Old compliance-runs pattern should not be routable (got {response.status_code})"
            )

            # Test old dq-runs pattern
            response = requests.get(
                f"{self.api_url}/api/v1/dq/dq-runs/",
                timeout=5
            )

            # Should return 404 (not found) or 401 (auth required), not 200
            assert response.status_code in [404, 401, 403], (
                f"Old dq-runs pattern should not be routable (got {response.status_code})"
            )
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not connect to API: {e}")


class TestGatewayVerificationScript:
    """Test gateway verification script"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.verify_script = self.project_root / 'scripts' / 'verify-gateway-configurations.py'
        self.routing_script = self.project_root / 'scripts' / 'test-gateway-routing.py'

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

        assert "All API gateway configurations use standardized endpoint patterns" in result.stdout or "No issues found" in result.stdout, (
            "Script should report success"
        )

    def test_routing_script_exists(self):
        """Test that routing test script exists"""
        assert self.routing_script.exists(), "Routing test script should exist"

    def test_routing_script_runs(self):
        """Test that routing test script runs successfully"""
        result = subprocess.run(
            [sys.executable, str(self.routing_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, (
            f"Routing script should exit with code 0.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        assert "All tests passed" in result.stdout or "Tests Passed" in result.stdout, (
            "Script should report success"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

