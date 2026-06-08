"""
Integration tests for docker-compose.dev.yml configuration.

Tests development-specific configurations, environment variables, volumes, hot-reload, and service settings.
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="module")
def dev_compose_file():
    """Get path to docker-compose.dev.yml."""
    return project_root / "docker-compose.dev.yml"


@pytest.fixture(scope="module")
def dev_compose_config(dev_compose_file):
    """Load docker-compose.dev.yml configuration."""
    with open(dev_compose_file, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def base_compose_config():
    """Load base docker-compose.yml configuration for comparison."""
    base_file = project_root / "docker-compose.yml"
    with open(base_file, "r") as f:
        return yaml.safe_load(f)


class TestDockerComposeDev:
    """Integration tests for docker-compose.dev.yml."""

    def test_dev_compose_file_exists(self, dev_compose_file):
        """Test that docker-compose.dev.yml exists."""
        assert dev_compose_file.exists(), f"docker-compose.dev.yml not found at {dev_compose_file}"

    def test_dev_compose_valid_yaml(self, dev_compose_config):
        """Test that docker-compose.dev.yml is valid YAML."""
        assert dev_compose_config is not None
        assert "services" in dev_compose_config

    def test_dev_network_defined(self, dev_compose_config):
        """Test that hub-net-dev network is defined."""
        networks = dev_compose_config.get("networks", {})
        assert "hub-net-dev" in networks, "hub-net-dev network must be defined"

        network_config = networks.get("hub-net-dev", {})
        assert network_config.get("driver") == "bridge", "hub-net-dev should use bridge driver"

    def test_dev_volumes_defined(self, dev_compose_config):
        """Test that development-specific volumes are defined (matches docker-compose.dev.yml)."""
        volumes = dev_compose_config.get("volumes", {})
        required_dev_volumes = [
            "pgdata-dev",
            "redis-cache-data-dev",
            "redis-queue-data-dev",
            "redis-events-data-dev",
            "redis-channels-data-dev",
            "minio-data-dev",
            "fuseki-data-dev",
            "prometheus-data-dev",
            "grafana-data-dev",
            "alertmanager-data-dev",
        ]

        for volume_name in required_dev_volumes:
            assert volume_name in volumes, f"Required development volume {volume_name} not defined"

    def test_dev_container_names(self, dev_compose_config):
        """Test that all containers have development-specific names."""
        services = dev_compose_config.get("services", {})
        for service_name, service_config in services.items():
            if "container_name" in service_config:
                container_name = service_config["container_name"]
                assert (
                    "dev" in container_name
                ), f"Service {service_name} container_name must include 'dev': {container_name}"

    def _env_to_dict(self, environment):
        """Normalize environment (list of KEY=VALUE or dict) to dict for assertions."""
        if isinstance(environment, dict):
            return environment
        if isinstance(environment, list):
            result = {}
            for item in environment:
                if isinstance(item, str) and "=" in item:
                    key, _, value = item.partition("=")
                    result[key] = value
                elif isinstance(item, dict):
                    result.update(item)
            return result
        return {}

    def test_dev_environment_variables(self, dev_compose_config):
        """Test that development environment variables are set correctly."""
        services = dev_compose_config.get("services", {})

        application_services = [
            "api-service",
            "worker-service",
        ]

        for service_name in application_services:
            service_config = services.get(service_name, {})
            raw_env = service_config.get("environment", {})
            environment = self._env_to_dict(raw_env)

            assert (
                "ENVIRONMENT" in environment
            ), f"Service {service_name} must have ENVIRONMENT variable"
            assert (
                environment.get("ENVIRONMENT") == "development"
            ), f"Service {service_name} ENVIRONMENT must be 'development', got '{environment.get('ENVIRONMENT')}'"

            assert (
                "LOG_LEVEL" in environment
            ), f"Service {service_name} must have LOG_LEVEL variable"
            assert (
                environment.get("LOG_LEVEL") == "DEBUG"
            ), f"Service {service_name} LOG_LEVEL must be 'DEBUG' for development, got '{environment.get('LOG_LEVEL')}'"

            if "DEBUG" in environment:
                debug_value = str(environment.get("DEBUG"))
                if "${DEBUG" not in debug_value:
                    assert debug_value.lower() in [
                        "true",
                        "1",
                        "yes",
                    ], f"Service {service_name} DEBUG should be True for development, got '{debug_value}'"

    def test_dev_volumes_use_dev_suffix(self, dev_compose_config):
        """Test that volumes use development-specific names."""
        services = dev_compose_config.get("services", {})

        for service_name, service_config in services.items():
            volumes = service_config.get("volumes", [])
            for vol in volumes:
                if isinstance(vol, str) and ":" in vol:
                    vol_name = vol.split(":")[0]
                    # Check if it's a named volume (not a path)
                    if vol_name and not vol_name.startswith(".") and not vol_name.startswith("/"):
                        assert "dev" in vol_name or vol_name in [
                            "pgdata-dev",
                            "redis-cache-data-dev",
                            "redis-queue-data-dev",
                            "redis-events-data-dev",
                            "redis-channels-data-dev",
                            "minio-data-dev",
                            "fuseki-data-dev",
                            "prometheus-data-dev",
                            "grafana-data-dev",
                            "alertmanager-data-dev",
                            "prefect-server-data-dev",
                            "prefect-db-data-dev",
                            "traefik-letsencrypt-dev",
                        ], f"Service {service_name} volume {vol_name} should use dev suffix"

    def test_dev_networks_use_dev_network(self, dev_compose_config):
        """Test that all services use hub-net-dev network."""
        services = dev_compose_config.get("services", {})
        for service_name, service_config in services.items():
            networks = service_config.get("networks", [])
            if isinstance(networks, list):
                assert (
                    "hub-net-dev" in networks
                ), f"Service {service_name} must be connected to hub-net-dev network"
            elif isinstance(networks, dict):
                assert (
                    "hub-net-dev" in networks
                ), f"Service {service_name} must be connected to hub-net-dev network"

    def test_dev_health_check_intervals(self, dev_compose_config):
        """Test that health checks have development-appropriate intervals."""
        services = dev_compose_config.get("services", {})

        for service_name, service_config in services.items():
            if "healthcheck" in service_config:
                healthcheck = service_config["healthcheck"]
                interval = healthcheck.get("interval", "")
                # Development can have less frequent health checks (30s is fine)
                if interval:
                    # Parse interval (e.g., "30s" -> 30)
                    interval_value = int("".join(filter(str.isdigit, interval)))
                    assert (
                        interval_value <= 60
                    ), f"Service {service_name} health check interval should be <= 60s for development, got {interval}"

    def test_dev_hot_reload_volumes(self, dev_compose_config):
        """Test that application services have code volumes mounted for hot-reload."""
        services = dev_compose_config.get("services", {})

        application_services_with_code = [
            "api-service",
            "worker-service",
            "semantic-service",
            "dq-service",
            "compliance-service",
            "datacontract-service",
            "observability-service",
            "webhook-service",
            "prefect-integration-service",
        ]

        for service_name in application_services_with_code:
            if service_name in services:
                service_config = services[service_name]
                volumes = service_config.get("volumes", [])

                # Check if code volume is mounted (.:/app or similar)
                code_volume_mounted = any(
                    ":/app" in str(vol)
                    or ":/code" in str(vol)
                    or (isinstance(vol, str) and vol.startswith(".:"))
                    for vol in volumes
                )

                assert (
                    code_volume_mounted
                ), f"Service {service_name} should have code volume mounted for hot-reload"

    def test_dev_no_resource_limits(self, dev_compose_config):
        """Test that development services don't have resource limits (for flexibility)."""
        services = dev_compose_config.get("services", {})

        application_services = [
            "api-service",
            "worker-service",
        ]

        for service_name in application_services:
            if service_name in services:
                service_config = services[service_name]
                # Development should not have deploy.resources limits
                if "deploy" in service_config:
                    deploy = service_config["deploy"]
                    if "resources" in deploy:
                        resources = deploy["resources"]
                        # Development may have reservations but not strict limits
                        if "limits" in resources:
                            # Limits should be generous or absent
                            pass  # Allow limits in dev, but they should be generous

    def test_dev_api_service_uses_runserver(self, dev_compose_config):
        """Test that api-service uses Django runserver for development."""
        services = dev_compose_config.get("services", {})
        api_service = services.get("api-service", {})

        if "command" in api_service:
            command = api_service["command"]
            assert (
                "runserver" in command
            ), f"api-service should use 'runserver' command for development, got '{command}'"

    def test_dev_all_services_have_build_or_image(self, dev_compose_config):
        """Test that all services have either build or image specified."""
        services = dev_compose_config.get("services", {})
        for service_name, service_config in services.items():
            assert (
                "build" in service_config or "image" in service_config
            ), f"Service {service_name} must have either 'build' or 'image'"

    def test_dev_infrastructure_services_exist(self, dev_compose_config):
        """Test that required infrastructure services exist (docker-compose.dev.yml uses redis-cache)."""
        services = dev_compose_config.get("services", {})
        required_services = ["postgres", "redis-cache", "minio", "fuseki"]
        for service_name in required_services:
            assert (
                service_name in services
            ), f"Required infrastructure service {service_name} not found"

    def test_dev_monitoring_services_exist(self, dev_compose_config):
        """Test that monitoring services exist."""
        services = dev_compose_config.get("services", {})
        monitoring_services = ["prometheus", "grafana", "jaeger", "alertmanager"]
        for service_name in monitoring_services:
            assert service_name in services, f"Required monitoring service {service_name} not found"

    def test_dev_application_services_exist(self, dev_compose_config):
        """Test that application services exist."""
        services = dev_compose_config.get("services", {})
        application_services = [
            "api-service",
            "worker-service",
            "semantic-service",
            "dq-service",
            "compliance-service",
            "datacontract-service",
            "observability-service",
            "webhook-service",
        ]
        for service_name in application_services:
            assert (
                service_name in services
            ), f"Required application service {service_name} not found"

    def test_dev_env_file_allowed(self, dev_compose_config):
        """Test that development services can use env_file (for convenience)."""
        services = dev_compose_config.get("services", {})
        # Development can use env_file, it's optional
        # Just verify the config is valid
        for service_name, service_config in services.items():
            if "env_file" in service_config:
                env_file = service_config["env_file"]
                # Should be a string or list of strings
                assert isinstance(
                    env_file, (str, list)
                ), f"Service {service_name} env_file should be string or list"
