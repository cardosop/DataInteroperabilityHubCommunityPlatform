"""
Integration tests for docker-compose.test.yml configuration.

Tests test-environment-specific configurations: file exists, valid YAML,
required services, test-specific network and volumes. No mocks; uses real YAML.
Closes gap identified in Phase 8.2 Docker Compose Test Gap Analysis.
"""

import sys
from pathlib import Path

import pytest
import yaml

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="module")
def test_compose_file():
    """Path to docker-compose.test.yml."""
    return project_root / "docker-compose.test.yml"


@pytest.fixture(scope="module")
def test_compose_config(test_compose_file):
    """Load docker-compose.test.yml configuration."""
    with open(test_compose_file, "r") as f:
        return yaml.safe_load(f)


class TestDockerComposeTest:
    """Integration tests for docker-compose.test.yml."""

    def test_test_compose_file_exists(self, test_compose_file):
        """docker-compose.test.yml must exist."""
        assert (
            test_compose_file.exists()
        ), f"docker-compose.test.yml not found at {test_compose_file}"

    def test_test_compose_valid_yaml(self, test_compose_config):
        """docker-compose.test.yml must be valid YAML with services."""
        assert test_compose_config is not None
        assert "services" in test_compose_config

    def test_test_network_defined(self, test_compose_config):
        """Test environment must use hub-test-net."""
        networks = test_compose_config.get("networks", {})
        assert "hub-test-net" in networks, "hub-test-net must be defined"
        assert networks.get("hub-test-net", {}).get("driver") == "bridge"

    def test_test_volumes_defined(self, test_compose_config):
        """Test-specific volumes must be defined."""
        volumes = test_compose_config.get("volumes", {})
        required = [
            "postgres-test-data",
            "redis-cache-test-data",
            "redis-queue-test-data",
            "redis-events-test-data",
            "redis-channels-test-data",
            "minio-test-data",
            "fuseki-test-data",
        ]
        for name in required:
            assert name in volumes, f"Required test volume {name} not defined"

    def test_test_infrastructure_services_exist(self, test_compose_config):
        """Required infrastructure services must exist in test compose."""
        services = test_compose_config.get("services", {})
        required = [
            "postgres-test",
            "redis-cache-test",
            "minio-test",
            "fuseki-test",
        ]
        for name in required:
            assert name in services, f"Required test service {name} not found"

    def test_test_services_use_test_network(self, test_compose_config):
        """All services must use hub-test-net."""
        services = test_compose_config.get("services", {})
        for name, config in services.items():
            networks = config.get("networks", [])
            if isinstance(networks, dict):
                networks = list(networks.keys())
            assert "hub-test-net" in networks, f"Service {name} must be on hub-test-net"

    def test_test_containers_have_test_names(self, test_compose_config):
        """Container names should include test identifier."""
        services = test_compose_config.get("services", {})
        for name, config in services.items():
            if "container_name" in config:
                cname = config["container_name"]
                msg = f"Service {name} container_name should indicate test: {cname!r}"
                assert "test" in cname or "hub-test" in cname, msg

    def test_test_all_services_have_build_or_image(self, test_compose_config):
        """Every service must have build or image."""
        services = test_compose_config.get("services", {})
        for name, config in services.items():
            assert (
                "build" in config or "image" in config
            ), f"Service {name} must have build or image"
