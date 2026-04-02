"""
Phase 25.3.2 — Guard against PREFECT_INTEGRATION_SERVICE_URL misconfiguration.

Previously the URL pointed at the Prefect orchestration API (port 4200)
instead of the prefect-integration-service FastAPI (port 8084), causing
every deployment sync call to silently fail in Kubernetes.

These tests validate configuration files so the mistake cannot recur.
"""

import os
import pathlib

import pytest

# Project root — works from any pytest invocation CWD
_ROOT = pathlib.Path(__file__).resolve().parents[3]  # hub/tests/regression -> project root


class TestPrefectIntegrationServiceUrl:
    """Validate PREFECT_INTEGRATION_SERVICE_URL across config files."""

    def _read(self, relpath: str) -> str:
        path = _ROOT / relpath
        if not path.exists():
            pytest.skip(f"{relpath} not found")
        return path.read_text()

    # --- helm/values.yaml ---------------------------------------------------

    def test_helm_values_uses_port_8084(self):
        content = self._read("helm/values.yaml")
        # Find the PREFECT_INTEGRATION_SERVICE_URL line
        for line in content.splitlines():
            stripped = line.strip()
            if "PREFECT_INTEGRATION_SERVICE_URL" in stripped and not stripped.startswith("#"):
                assert ":8084" in stripped, (
                    f"helm/values.yaml must point PREFECT_INTEGRATION_SERVICE_URL "
                    f"to port 8084, got: {stripped}"
                )
                assert ":4200" not in stripped, (
                    f"helm/values.yaml still points at Prefect server :4200 "
                    f"instead of integration service :8084: {stripped}"
                )
                return
        pytest.fail("PREFECT_INTEGRATION_SERVICE_URL not found in helm/values.yaml")

    # --- .env.production.template -------------------------------------------

    def test_env_production_template_uses_port_8084(self):
        content = self._read(".env.production.template")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("PREFECT_INTEGRATION_SERVICE_URL="):
                value = stripped.split("=", 1)[1]
                assert ":8084" in value, (
                    f".env.production.template must use port 8084, got: {value}"
                )
                assert ":4200" not in value, (
                    f".env.production.template still points at :4200: {value}"
                )
                return
        pytest.skip("PREFECT_INTEGRATION_SERVICE_URL not in .env.production.template")

    # --- docker-compose.yml -------------------------------------------------

    def test_docker_compose_uses_port_8084(self):
        content = self._read("docker-compose.yml")
        for line in content.splitlines():
            if "PREFECT_INTEGRATION_SERVICE_URL" in line and not line.strip().startswith("#"):
                assert ":4200" not in line, (
                    f"docker-compose.yml points at :4200: {line.strip()}"
                )
                return
        pytest.skip("PREFECT_INTEGRATION_SERVICE_URL not in docker-compose.yml")

    # --- docker-compose.test.yml --------------------------------------------

    def test_docker_compose_test_uses_port_8084(self):
        content = self._read("docker-compose.test.yml")
        for line in content.splitlines():
            if "PREFECT_INTEGRATION_SERVICE_URL" in line and not line.strip().startswith("#"):
                assert ":8084" in line, (
                    f"docker-compose.test.yml must use port 8084: {line.strip()}"
                )
                assert ":4200" not in line, (
                    f"docker-compose.test.yml points at :4200: {line.strip()}"
                )
                return
        pytest.skip("PREFECT_INTEGRATION_SERVICE_URL not in docker-compose.test.yml")

    # --- k8s configmap ------------------------------------------------------

    def test_k8s_configmap_uses_port_8084(self):
        content = self._read("k8s/api-service/base/configmap.yaml")
        for line in content.splitlines():
            if "PREFECT_INTEGRATION_SERVICE_URL" in line and not line.strip().startswith("#"):
                assert ":8084" in line, (
                    f"k8s configmap must use port 8084: {line.strip()}"
                )
                assert ":4200" not in line, (
                    f"k8s configmap points at :4200: {line.strip()}"
                )
                return
        pytest.skip("PREFECT_INTEGRATION_SERVICE_URL not in k8s configmap")
