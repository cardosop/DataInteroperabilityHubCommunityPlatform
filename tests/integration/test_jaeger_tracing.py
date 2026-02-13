"""
Integration tests for Jaeger tracing configuration.

Validates docker-compose includes Jaeger and that services that should
export traces have JAEGER_AGENT_HOST or OTEL config. No mocks; uses real YAML.
Optional: Jaeger UI HTTP health when JAEGER_URL set (skip if unavailable).
"""

from pathlib import Path

import pytest
import yaml

project_root = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def compose_path():
    """Path to docker-compose.yml."""
    return project_root / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose_config(compose_path):
    """Loaded docker-compose.yml."""
    if not compose_path.exists():
        return None
    with open(compose_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.integration
class TestJaegerTracing:
    """Jaeger and tracing configuration tests."""

    def test_docker_compose_has_jaeger_service(self, compose_config):
        """Docker Compose must define jaeger service."""
        assert compose_config is not None
        services = compose_config.get("services", {})
        assert "jaeger" in services, "docker-compose.yml must define jaeger service"

    def test_jaeger_service_has_image_or_build(self, compose_config):
        """Jaeger service must have image or build."""
        if not compose_config:
            pytest.skip("Compose not loaded")
        jaeger = compose_config.get("services", {}).get("jaeger", {})
        assert "image" in jaeger or "build" in jaeger

    def test_jaeger_ports_exposed(self, compose_config):
        """Jaeger should expose UI and collector ports."""
        if not compose_config:
            pytest.skip("Compose not loaded")
        jaeger = compose_config.get("services", {}).get("jaeger", {})
        ports = jaeger.get("ports", [])
        port_str = str(ports)
        assert "16686" in port_str or "6831" in port_str or "14268" in port_str

    def test_services_have_jaeger_env(self, compose_config):
        """Key application services must have JAEGER_AGENT_HOST or OTEL config."""
        if not compose_config:
            pytest.skip("Compose not loaded")
        services = compose_config.get("services", {})
        services_with_tracing = [
            "api-service",
            "worker-service",
            "workflow-engine-service",
            "workflow-registry-service",
            "event-bus-health-service",
            "event-schema-registry-service",
        ]
        for name in services_with_tracing:
            if name not in services:
                continue
            env = services[name].get("environment", {})
            if isinstance(env, list):
                env_str = " ".join(str(e) for e in env)
            else:
                env_str = str(env)
            assert (
                "JAEGER_AGENT_HOST" in env_str
                or "OTEL" in env_str
                or "opentelemetry" in env_str.lower()
            ), (f"Service {name} should have JAEGER_AGENT_HOST or " "OTEL config for tracing")
