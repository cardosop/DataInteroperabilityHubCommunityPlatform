"""
Integration tests for docker-compose.production.yml configuration.

Tests production-specific configurations: network, volumes, no DEBUG,
LOG_LEVEL, resource limits, restart policies. No mocks; uses real YAML.
Closes gap identified in Phase 8.2 / 8.3 Docker Compose Test Update Plan.
"""

import sys
from pathlib import Path

import pytest
import yaml

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def _env_to_dict(environment):
    """Normalize environment (list of KEY=VALUE or dict) to dict."""
    if isinstance(environment, dict):
        return environment
    if isinstance(environment, list):
        result = {}
        for item in environment:
            if isinstance(item, str) and "=" in item:
                k, _, v = item.partition("=")
                result[k] = v
            elif isinstance(item, dict):
                result.update(item)
        return result
    return {}


@pytest.fixture(scope="module")
def production_compose_file():
    """Path to docker-compose.production.yml."""
    return project_root / "docker-compose.production.yml"


@pytest.fixture(scope="module")
def production_compose_config(production_compose_file):
    """Load docker-compose.production.yml configuration."""
    with open(production_compose_file, "r") as f:
        return yaml.safe_load(f)


@pytest.mark.integration
class TestDockerComposeProduction:
    """Integration tests for docker-compose.production.yml."""

    def test_production_compose_file_exists(self, production_compose_file):
        """docker-compose.production.yml must exist."""
        assert (
            production_compose_file.exists()
        ), f"docker-compose.production.yml not found at {production_compose_file}"

    def test_production_compose_valid_yaml(self, production_compose_config):
        """docker-compose.production.yml must be valid YAML with services."""
        assert production_compose_config is not None
        assert "services" in production_compose_config

    def test_production_network_defined(self, production_compose_config):
        """Production must use hub-net-production."""
        networks = production_compose_config.get("networks", {})
        assert "hub-net-production" in networks, "hub-net-production must be defined"
        assert networks.get("hub-net-production", {}).get("driver") == "bridge"

    def test_production_volumes_defined(self, production_compose_config):
        """Production-specific volumes must be defined (matches docker-compose.production.yml)."""
        volumes = production_compose_config.get("volumes", {})
        required = [
            "pgdata-production",
            "redis-cache-data-production",
            "redis-queue-data-production",
            "redis-events-data-production",
            "redis-channels-data-production",
            "minio-data-production",
            "fuseki-data-production",
        ]
        for name in required:
            assert name in volumes, f"Required production volume {name} not defined"

    def test_production_infrastructure_services_exist(self, production_compose_config):
        """Required infrastructure services must exist in production compose."""
        services = production_compose_config.get("services", {})
        required = [
            "postgres",
            "redis-cache",
            "redis-queue",
            "redis-events",
            "redis-channels",
            "minio",
            "fuseki",
        ]
        for name in required:
            assert name in services, f"Required production service {name} not found"

    def test_production_application_services_exist(self, production_compose_config):
        """Core application services must exist in production compose."""
        services = production_compose_config.get("services", {})
        required = ["api-service", "worker-service"]
        for name in required:
            assert name in services, f"Required production application service {name} not found"

    def test_production_services_use_production_network(self, production_compose_config):
        """All services must use hub-net-production."""
        services = production_compose_config.get("services", {})
        for service_name, service_config in services.items():
            networks = service_config.get("networks", [])
            net_list = list(networks) if isinstance(networks, list) else list(networks.keys())
            assert (
                "hub-net-production" in net_list
            ), f"Service {service_name} must be on hub-net-production"

    def test_production_no_debug(self, production_compose_config):
        """Application services must not have DEBUG=True in production."""
        services = production_compose_config.get("services", {})
        app_services = ["api-service", "worker-service"]
        for service_name in app_services:
            if service_name not in services:
                continue
            raw_env = services[service_name].get("environment", {})
            env = _env_to_dict(raw_env)
            if "DEBUG" in env:
                val = str(env["DEBUG"]).strip().lower()
                assert val in (
                    "false",
                    "0",
                    "no",
                ), f"Service {service_name} must have DEBUG=False in production, got {env.get('DEBUG')}"

    def test_production_environment_variables(self, production_compose_config):
        """Application services must have ENVIRONMENT=production and appropriate LOG_LEVEL."""
        services = production_compose_config.get("services", {})
        app_services = ["api-service", "worker-service"]
        for service_name in app_services:
            if service_name not in services:
                continue
            raw_env = services[service_name].get("environment", {})
            env = _env_to_dict(raw_env)
            assert (
                env.get("ENVIRONMENT") == "production"
            ), f"Service {service_name} must have ENVIRONMENT=production, got {env.get('ENVIRONMENT')}"
            log_level = env.get("LOG_LEVEL", "").upper()
            assert log_level in (
                "INFO",
                "WARNING",
                "ERROR",
                "",
            ), f"Service {service_name} LOG_LEVEL should be INFO/WARNING/ERROR for production, got {env.get('LOG_LEVEL')}"

    def test_production_resource_limits(self, production_compose_config):
        """Services with deploy must have resource limits and reservations."""
        services = production_compose_config.get("services", {})
        for service_name, service_config in services.items():
            deploy = service_config.get("deploy", {})
            if not deploy or not isinstance(deploy, dict):
                continue
            resources = deploy.get("resources", {})
            if not resources:
                continue
            assert (
                "limits" in resources
            ), f"Service {service_name} with deploy must have resources.limits"
            assert (
                "reservations" in resources
            ), f"Service {service_name} with deploy must have resources.reservations"
            limits = resources.get("limits", {})
            assert limits.get("memory"), f"Service {service_name} must have memory limit"

    def test_production_restart_policy(self, production_compose_config):
        """Production services must have restart policy (restart: always or deploy.restart_policy)."""
        services = production_compose_config.get("services", {})
        for service_name, service_config in services.items():
            has_restart = "restart" in service_config
            deploy = service_config.get("deploy", {})
            has_deploy_restart = isinstance(deploy, dict) and "restart_policy" in deploy
            assert (
                has_restart or has_deploy_restart
            ), f"Service {service_name} must have restart or deploy.restart_policy"

    def test_production_container_names(self, production_compose_config):
        """Container names must include production identifier where set."""
        services = production_compose_config.get("services", {})
        for service_name, service_config in services.items():
            if "container_name" not in service_config:
                continue
            name = service_config["container_name"]
            assert (
                "production" in name
            ), f"Service {service_name} container_name must include 'production': {name}"

    def test_production_all_services_have_build_or_image(self, production_compose_config):
        """All services must have build or image."""
        services = production_compose_config.get("services", {})
        for service_name, service_config in services.items():
            assert (
                "build" in service_config or "image" in service_config
            ), f"Service {service_name} must have build or image"

    def test_production_env_file_format_if_present(self, production_compose_config):
        """When env_file is present, it must be a string or list of strings (no mocks)."""
        services = production_compose_config.get("services", {})
        for service_name, service_config in services.items():
            if "env_file" not in service_config:
                continue
            env_file = service_config["env_file"]
            assert isinstance(
                env_file, (str, list)
            ), f"Service {service_name} env_file must be string or list, got {type(env_file)}"
            if isinstance(env_file, list):
                for path in env_file:
                    assert isinstance(
                        path, str
                    ), f"Service {service_name} env_file list entries must be strings, got {type(path)}"
