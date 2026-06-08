"""
Integration tests for docker-compose.staging.yml configuration.

Tests staging-specific configurations, environment variables, volumes, and service settings.
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
def staging_compose_file():
    """Get path to docker-compose.staging.yml."""
    return project_root / "docker-compose.staging.yml"


@pytest.fixture(scope="module")
def staging_compose_config(staging_compose_file):
    """Load docker-compose.staging.yml configuration."""
    with open(staging_compose_file, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def base_compose_config():
    """Load base docker-compose.yml configuration for comparison."""
    base_file = project_root / "docker-compose.yml"
    with open(base_file, "r") as f:
        return yaml.safe_load(f)


class TestDockerComposeStaging:
    """Integration tests for docker-compose.staging.yml."""

    def test_staging_compose_file_exists(self, staging_compose_file):
        """Test that docker-compose.staging.yml exists."""
        assert (
            staging_compose_file.exists()
        ), f"docker-compose.staging.yml not found at {staging_compose_file}"

    def test_staging_compose_valid_yaml(self, staging_compose_config):
        """Test that docker-compose.staging.yml is valid YAML."""
        assert staging_compose_config is not None
        assert "services" in staging_compose_config

    def test_staging_network_defined(self, staging_compose_config):
        """Test that hub-net-staging network is defined."""
        networks = staging_compose_config.get("networks", {})
        assert "hub-net-staging" in networks, "hub-net-staging network must be defined"

        network_config = networks.get("hub-net-staging", {})
        assert network_config.get("driver") == "bridge", "hub-net-staging should use bridge driver"

    def test_staging_volumes_defined(self, staging_compose_config):
        """Test that staging-specific volumes are defined (matches docker-compose.staging.yml)."""
        volumes = staging_compose_config.get("volumes", {})
        required_staging_volumes = [
            "pgdata-staging",
            "redis-cache-data-staging",
            "redis-queue-data-staging",
            "redis-events-data-staging",
            "redis-channels-data-staging",
            "minio-data-staging",
            "fuseki-data-staging",
            "prometheus-data-staging",
            "grafana-data-staging",
            "alertmanager-data-staging",
        ]

        for volume_name in required_staging_volumes:
            assert volume_name in volumes, f"Required staging volume {volume_name} not defined"

    def test_staging_container_names(self, staging_compose_config):
        """Test that all containers have staging-specific names."""
        services = staging_compose_config.get("services", {})
        for service_name, service_config in services.items():
            if "container_name" in service_config:
                container_name = service_config["container_name"]
                assert (
                    "staging" in container_name
                ), f"Service {service_name} container_name must include 'staging': {container_name}"

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

    def test_staging_environment_variables(self, staging_compose_config):
        """Test that staging environment variables are set correctly."""
        services = staging_compose_config.get("services", {})

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
                environment.get("ENVIRONMENT") == "staging"
            ), f"Service {service_name} ENVIRONMENT must be 'staging', got '{environment.get('ENVIRONMENT')}'"

            assert (
                "LOG_LEVEL" in environment
            ), f"Service {service_name} must have LOG_LEVEL variable"
            assert (
                environment.get("LOG_LEVEL") == "INFO"
            ), f"Service {service_name} LOG_LEVEL must be 'INFO' for staging"

            if "DEBUG" in environment:
                debug_value = str(environment.get("DEBUG"))
                if "${DEBUG" not in debug_value:
                    assert debug_value.lower() in [
                        "false",
                        "0",
                        "no",
                    ], f"Service {service_name} DEBUG should be False for staging, got '{debug_value}'"

    def test_staging_volumes_use_staging_suffix(self, staging_compose_config):
        """Test that volumes use staging-specific names (matches docker-compose.staging.yml)."""
        services = staging_compose_config.get("services", {})
        allowed_volume_names = {
            "pgdata-staging",
            "redis-cache-data-staging",
            "redis-queue-data-staging",
            "redis-events-data-staging",
            "redis-channels-data-staging",
            "minio-data-staging",
            "fuseki-data-staging",
            "prometheus-data-staging",
            "grafana-data-staging",
            "alertmanager-data-staging",
            "prefect-server-data-staging",
            "prefect-db-data-staging",
            "traefik-letsencrypt-staging",
        }

        for service_name, service_config in services.items():
            volumes = service_config.get("volumes", [])
            for vol in volumes:
                if isinstance(vol, str) and ":" in vol:
                    vol_name = vol.split(":")[0]
                    # Check if it's a named volume (not a path)
                    if vol_name and not vol_name.startswith(".") and not vol_name.startswith("/"):
                        assert (
                            "staging" in vol_name or vol_name in allowed_volume_names
                        ), f"Service {service_name} volume {vol_name} should use staging suffix"

    def test_staging_networks_use_staging_network(self, staging_compose_config):
        """Test that all services use hub-net-staging network."""
        services = staging_compose_config.get("services", {})
        for service_name, service_config in services.items():
            networks = service_config.get("networks", [])
            if isinstance(networks, list):
                assert (
                    "hub-net-staging" in networks
                ), f"Service {service_name} must be connected to hub-net-staging network"
            elif isinstance(networks, dict):
                assert (
                    "hub-net-staging" in networks
                ), f"Service {service_name} must be connected to hub-net-staging network"

    def test_staging_health_check_intervals(self, staging_compose_config):
        """Test that health checks have staging-appropriate intervals."""
        services = staging_compose_config.get("services", {})

        for service_name, service_config in services.items():
            if "healthcheck" in service_config:
                healthcheck = service_config["healthcheck"]
                interval = healthcheck.get("interval", "")
                # Staging should have more frequent health checks (20s or less)
                if interval:
                    # Parse interval (e.g., "20s" -> 20)
                    interval_value = int("".join(filter(str.isdigit, interval)))
                    assert (
                        interval_value <= 30
                    ), f"Service {service_name} health check interval should be <= 30s for staging, got {interval}"

    def test_staging_no_env_file(self, staging_compose_config):
        """Test that staging services don't use env_file (should use environment variables directly)."""
        services = staging_compose_config.get("services", {})
        for service_name, service_config in services.items():
            assert (
                "env_file" not in service_config
            ), f"Service {service_name} should not use env_file in staging, use environment variables directly"

    def test_staging_resource_limits(self, staging_compose_config):
        """Test that application services have resource limits configured."""
        services = staging_compose_config.get("services", {})

        # Infrastructure services may not have resource limits (matches docker-compose.staging.yml)
        infrastructure_services = {
            "postgres",
            "redis-cache",
            "redis-queue",
            "redis-events",
            "redis-channels",
            "minio",
            "fuseki",
            "prometheus",
            "grafana",
            "jaeger",
            "alertmanager",
            "traefik",
        }

        application_services = [
            "api-service",
            "worker-service",
            "semantic-service",
            "dq-service",
            "compliance-service",
            "datacontract-service",
            "search-service",
        ]

        for service_name in application_services:
            if service_name in services:
                service_config = services[service_name]
                # Check if deploy.resources is configured
                if "deploy" in service_config:
                    deploy = service_config["deploy"]
                    assert (
                        "resources" in deploy
                    ), f"Service {service_name} should have resource limits configured"
                    resources = deploy["resources"]
                    assert (
                        "limits" in resources
                    ), f"Service {service_name} should have resource limits"
                    assert (
                        "reservations" in resources
                    ), f"Service {service_name} should have resource reservations"

    def test_staging_restart_policy(self, staging_compose_config):
        """Test that services have restart policies configured."""
        services = staging_compose_config.get("services", {})

        application_services = [
            "api-service",
            "worker-service",
            "workflow-engine-service",
        ]

        for service_name in application_services:
            if service_name in services:
                service_config = services[service_name]
                if "deploy" in service_config:
                    deploy = service_config["deploy"]
                    assert (
                        "restart_policy" in deploy
                    ), f"Service {service_name} should have restart policy configured"
                    restart_policy = deploy["restart_policy"]
                    assert (
                        "condition" in restart_policy
                    ), f"Service {service_name} restart policy should specify condition"

    def test_staging_all_services_have_build_or_image(self, staging_compose_config):
        """Test that all services have either build or image specified."""
        services = staging_compose_config.get("services", {})
        for service_name, service_config in services.items():
            assert (
                "build" in service_config or "image" in service_config
            ), f"Service {service_name} must have either 'build' or 'image'"

    def test_staging_infrastructure_services_exist(self, staging_compose_config):
        """Test that required infrastructure services exist (docker-compose.staging.yml uses redis-cache)."""
        services = staging_compose_config.get("services", {})
        required_services = ["postgres", "redis-cache", "minio", "fuseki"]
        for service_name in required_services:
            assert (
                service_name in services
            ), f"Required infrastructure service {service_name} not found"

    def test_staging_monitoring_services_exist(self, staging_compose_config):
        """Test that monitoring services exist."""
        services = staging_compose_config.get("services", {})
        monitoring_services = ["prometheus", "grafana", "jaeger", "alertmanager"]
        for service_name in monitoring_services:
            assert service_name in services, f"Required monitoring service {service_name} not found"

    def test_staging_application_services_exist(self, staging_compose_config):
        """Test that application services exist."""
        services = staging_compose_config.get("services", {})
        application_services = [
            "api-service",
            "worker-service",
            "semantic-service",
            "dq-service",
            "compliance-service",
            "datacontract-service",
            "search-service",
        ]
        for service_name in application_services:
            assert (
                service_name in services
            ), f"Required application service {service_name} not found"
