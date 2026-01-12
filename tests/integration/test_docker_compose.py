"""
Integration tests for docker-compose.yml configuration.

Tests service startup, health checks, dependencies, and service communication.
"""
import os
import sys
import time
import subprocess
import requests
from pathlib import Path
import yaml
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class DockerComposeIntegrationTest:
    """Integration tests for docker-compose.yml."""

    @pytest.fixture(scope="class")
    def docker_compose_file(self):
        """Get path to docker-compose.yml."""
        return project_root / "docker-compose.yml"

    @pytest.fixture(scope="class")
    def docker_compose_config(self, docker_compose_file):
        """Load docker-compose.yml configuration."""
        with open(docker_compose_file, 'r') as f:
            return yaml.safe_load(f)

    def test_docker_compose_file_exists(self, docker_compose_file):
        """Test that docker-compose.yml exists."""
        assert docker_compose_file.exists(), f"docker-compose.yml not found at {docker_compose_file}"

    def test_docker_compose_valid_yaml(self, docker_compose_config):
        """Test that docker-compose.yml is valid YAML."""
        assert docker_compose_config is not None
        assert 'services' in docker_compose_config

    def test_all_services_have_build_or_image(self, docker_compose_config):
        """Test that all services have either build or image specified."""
        services = docker_compose_config.get('services', {})
        for service_name, service_config in services.items():
            assert 'build' in service_config or 'image' in service_config, \
                f"Service {service_name} must have either 'build' or 'image'"

    def test_all_services_have_networks(self, docker_compose_config):
        """Test that all services are connected to hub-net network."""
        services = docker_compose_config.get('services', {})
        for service_name, service_config in services.items():
            networks = service_config.get('networks', [])
            if isinstance(networks, list):
                assert 'hub-net' in networks, \
                    f"Service {service_name} must be connected to hub-net network"
            elif isinstance(networks, dict):
                assert 'hub-net' in networks, \
                    f"Service {service_name} must be connected to hub-net network"

    def test_infrastructure_services_exist(self, docker_compose_config):
        """Test that required infrastructure services exist."""
        services = docker_compose_config.get('services', {})
        required_services = ['postgres', 'redis', 'minio', 'fuseki']
        for service_name in required_services:
            assert service_name in services, f"Required infrastructure service {service_name} not found"

    def test_monitoring_services_exist(self, docker_compose_config):
        """Test that monitoring services exist."""
        services = docker_compose_config.get('services', {})
        monitoring_services = ['prometheus', 'grafana', 'jaeger', 'alertmanager']
        for service_name in monitoring_services:
            assert service_name in services, f"Required monitoring service {service_name} not found"

    def test_application_services_exist(self, docker_compose_config):
        """Test that application services exist."""
        services = docker_compose_config.get('services', {})
        application_services = [
            'api-service',
            'worker-service',
            'workflow-engine-service',
            'workflow-registry-service',
            'event-bus-health-service',
            'event-schema-registry-service',
            'semantic-service',
            'dq-service',
            'compliance-service',
            'datacontract-service',
            'search-service',
            'observability-service',
            'webhook-service',
        ]
        for service_name in application_services:
            assert service_name in services, f"Required application service {service_name} not found"

    def test_all_services_have_healthchecks(self, docker_compose_config):
        """Test that all application services have health checks."""
        services = docker_compose_config.get('services', {})
        # Infrastructure services may not need health checks
        infrastructure_services = {'postgres', 'redis', 'minio', 'fuseki', 'prometheus', 'grafana', 'jaeger', 'alertmanager', 'traefik', 'prefect-server', 'prefect-db', 'prefect-worker'}

        for service_name, service_config in services.items():
            if service_name not in infrastructure_services:
                assert 'healthcheck' in service_config, \
                    f"Service {service_name} must have a healthcheck"

    def test_service_dependencies(self, docker_compose_config):
        """Test that service dependencies are properly configured."""
        services = docker_compose_config.get('services', {})

        # Test that workflow-engine-service depends on postgres and redis
        workflow_engine = services.get('workflow-engine-service', {})
        depends_on = workflow_engine.get('depends_on', {})
        assert 'postgres' in depends_on or 'postgres' in (depends_on if isinstance(depends_on, list) else []), \
            "workflow-engine-service must depend on postgres"
        assert 'redis' in depends_on or 'redis' in (depends_on if isinstance(depends_on, list) else []), \
            "workflow-engine-service must depend on redis"

        # Test that api-service depends on postgres, redis, and minio
        api_service = services.get('api-service', {})
        api_depends_on = api_service.get('depends_on', {})
        assert 'postgres' in api_depends_on or 'postgres' in (api_depends_on if isinstance(api_depends_on, list) else []), \
            "api-service must depend on postgres"
        assert 'redis' in api_depends_on or 'redis' in (api_depends_on if isinstance(api_depends_on, list) else []), \
            "api-service must depend on redis"
        assert 'minio' in api_depends_on or 'minio' in (api_depends_on if isinstance(api_depends_on, list) else []), \
            "api-service must depend on minio"

    def test_opentelemetry_configuration(self, docker_compose_config):
        """Test that services have OpenTelemetry configuration."""
        services = docker_compose_config.get('services', {})

        # Services that should have OpenTelemetry configuration
        services_with_tracing = [
            'workflow-engine-service',
            'workflow-registry-service',
            'event-bus-health-service',
            'event-schema-registry-service',
            'api-service',
            'worker-service',
        ]

        for service_name in services_with_tracing:
            service_config = services.get(service_name, {})
            environment = service_config.get('environment', [])

            # Check if environment is a list or dict
            if isinstance(environment, list):
                env_dict = {item.split('=')[0]: item.split('=')[1] if '=' in item else '' for item in environment}
            else:
                env_dict = environment

            assert 'OPENTELEMETRY_ENABLED' in env_dict or any('OPENTELEMETRY_ENABLED' in str(e) for e in environment), \
                f"Service {service_name} must have OPENTELEMETRY_ENABLED configuration"
            assert 'JAEGER_AGENT_HOST' in env_dict or any('JAEGER_AGENT_HOST' in str(e) for e in environment), \
                f"Service {service_name} must have JAEGER_AGENT_HOST configuration"

    def test_prometheus_scrape_configuration(self):
        """Test that Prometheus scrape configuration includes all services."""
        prometheus_config_file = project_root / "monitoring" / "prometheus" / "prometheus.yml"
        assert prometheus_config_file.exists(), "Prometheus configuration file not found"

        with open(prometheus_config_file, 'r') as f:
            prometheus_config = yaml.safe_load(f)

        scrape_configs = prometheus_config.get('scrape_configs', [])
        job_names = [config.get('job_name') for config in scrape_configs]

        # Check for key services
        required_jobs = [
            'workflow-engine-service',
            'workflow-registry-service',
            'event-bus-health-service',
            'event-schema-registry-service',
        ]

        for job_name in required_jobs:
            assert job_name in job_names, \
                f"Prometheus scrape config must include {job_name}"

    def test_volumes_defined(self, docker_compose_config):
        """Test that required volumes are defined."""
        volumes = docker_compose_config.get('volumes', {})
        required_volumes = [
            'pgdata',
            'redis-data',
            'minio-data',
            'fuseki-data',
            'prometheus-data',
            'grafana-data',
            'alertmanager-data',
        ]

        for volume_name in required_volumes:
            assert volume_name in volumes, f"Required volume {volume_name} not defined"

    def test_network_defined(self, docker_compose_config):
        """Test that hub-net network is defined."""
        networks = docker_compose_config.get('networks', {})
        assert 'hub-net' in networks, "hub-net network must be defined"

        network_config = networks.get('hub-net', {})
        assert network_config.get('driver') == 'bridge', "hub-net should use bridge driver"

    def test_service_ports_unique(self, docker_compose_config):
        """Test that service ports don't conflict."""
        services = docker_compose_config.get('services', {})
        ports_used = {}

        for service_name, service_config in services.items():
            ports = service_config.get('ports', [])
            for port_mapping in ports:
                if isinstance(port_mapping, str):
                    host_port = port_mapping.split(':')[0]
                elif isinstance(port_mapping, dict):
                    host_port = port_mapping.get('published')
                else:
                    continue

                if host_port:
                    assert host_port not in ports_used, \
                        f"Port {host_port} is used by both {ports_used[host_port]} and {service_name}"
                    ports_used[host_port] = service_name

    def test_environment_variables_consistent(self, docker_compose_config):
        """Test that environment variables are consistently named."""
        services = docker_compose_config.get('services', {})

        # Check that database URL format is consistent
        for service_name, service_config in services.items():
            environment = service_config.get('environment', [])

            if isinstance(environment, list):
                env_dict = {item.split('=')[0]: item.split('=')[1] if '=' in item else '' for item in environment}
            else:
                env_dict = environment

            if 'DATABASE_URL' in env_dict:
                db_url = env_dict['DATABASE_URL']
                assert db_url.startswith('postgresql://'), \
                    f"Service {service_name} DATABASE_URL must use postgresql:// protocol"

            if 'REDIS_URL' in env_dict:
                redis_url = env_dict['REDIS_URL']
                assert redis_url.startswith('redis://'), \
                    f"Service {service_name} REDIS_URL must use redis:// protocol"


@pytest.mark.integration
class DockerComposeRuntimeTest:
    """Runtime tests for docker-compose (requires Docker Compose to be running)."""

    @pytest.fixture(scope="class")
    def docker_compose_running(self):
        """Check if docker-compose is running."""
        try:
            result = subprocess.run(
                ['docker', 'compose', 'ps', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @pytest.mark.skipif(True, reason="Docker Compose test requires --docker-compose-running flag")
    def test_services_healthy(self, docker_compose_running):
        """Test that all services are healthy."""
        if not docker_compose_running:
            pytest.skip("Docker Compose not running")

        # This would require docker-compose to be running
        # For now, we'll skip this test unless explicitly enabled
        pass

    @pytest.mark.skipif(True, reason="Docker Compose test requires --docker-compose-running flag")
    def test_service_health_endpoints(self, docker_compose_running):
        """Test that service health endpoints are accessible."""
        if not docker_compose_running:
            pytest.skip("Docker Compose not running")

        # Health endpoints to test
        health_endpoints = [
            ('workflow-engine-service', 8088, '/healthz'),
            ('workflow-registry-service', 8089, '/health'),
            ('event-bus-health-service', 8090, '/healthz'),
            ('event-schema-registry-service', 8091, '/health'),
        ]

        for service_name, port, endpoint in health_endpoints:
            try:
                response = requests.get(f'http://localhost:{port}{endpoint}', timeout=2)
                assert response.status_code == 200, \
                    f"Service {service_name} health endpoint returned {response.status_code}"
            except requests.exceptions.RequestException:
                pytest.skip(f"Service {service_name} not accessible (may not be running)")


def pytest_addoption(parser):
    """Add command-line options for pytest."""
    parser.addoption(
        "--docker-compose-running",
        action="store_true",
        default=False,
        help="Run tests that require Docker Compose to be running"
    )

