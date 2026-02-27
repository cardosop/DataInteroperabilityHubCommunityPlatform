"""
Comprehensive integration tests for test environment setup.

Tests validate:
- Test Docker Compose configuration
- Test environment services startup
- Test API server accessibility
- SDK test environment configuration
- CLI test environment configuration
- Service health checks
- Service connectivity
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestTestEnvironmentDockerCompose:
    """Tests for test Docker Compose configuration."""

    @pytest.fixture(scope="class")
    def docker_compose_file(self):
        """Get path to docker-compose.test.yml."""
        return project_root / "docker-compose.test.yml"

    @pytest.fixture(scope="class")
    def docker_compose_config(self, docker_compose_file):
        """Load docker-compose.test.yml configuration."""
        with open(docker_compose_file, "r") as f:
            return yaml.safe_load(f)

    def test_docker_compose_file_exists(self, docker_compose_file):
        """Test that docker-compose.test.yml exists."""
        assert (
            docker_compose_file.exists()
        ), f"docker-compose.test.yml not found at {docker_compose_file}"

    def test_docker_compose_valid_yaml(self, docker_compose_config):
        """Test that docker-compose.test.yml is valid YAML."""
        assert docker_compose_config is not None
        assert "services" in docker_compose_config

    def test_all_services_have_build_or_image(self, docker_compose_config):
        """Test that all services have either build or image specified."""
        services = docker_compose_config.get("services", {})
        for service_name, service_config in services.items():
            assert (
                "build" in service_config or "image" in service_config
            ), f"Service {service_name} must have either 'build' or 'image'"

    def test_infrastructure_services_defined(self, docker_compose_config):
        """Test that infrastructure services are defined."""
        services = docker_compose_config.get("services", {})
        required_services = [
            "postgres-test",
            "redis-cache-test",  # docker-compose.test uses redis-cache-test, redis-queue-test, etc.
            "minio-test",
            "fuseki-test",
        ]
        for service in required_services:
            assert service in services, f"Required infrastructure service {service} not found"

    def test_microservices_defined(self, docker_compose_config):
        """Test that microservices are defined."""
        services = docker_compose_config.get("services", {})
        required_services = [
            "datacontract-service-test",
            "dq-service-test",
            "compliance-service-test",
            "semantic-service-test",
        ]
        for service in required_services:
            assert service in services, f"Required microservice {service} not found"

    def test_application_services_defined(self, docker_compose_config):
        """Test that application services are defined."""
        services = docker_compose_config.get("services", {})
        required_services = [
            "api-service-test",
            "worker-service-test",
        ]
        for service in required_services:
            assert service in services, f"Required application service {service} not found"

    def test_services_have_healthchecks(self, docker_compose_config):
        """Test that all services have health checks configured."""
        services = docker_compose_config.get("services", {})
        skip_healthcheck = {
            "prefect-worker-test",
            "ensure-test-db",
            "redis-exporter-cache-test",
            "redis-exporter-queue-test",
            "redis-exporter-events-test",
            "redis-exporter-channels-test",
            "mock-server-test",
            "mailhog-test",
        }
        for service_name, service_config in services.items():
            if service_name in skip_healthcheck:
                continue
            # Skip volume-only entries (docker-compose may list volumes under services in some configs)
            if "build" not in service_config and "image" not in service_config:
                continue
            assert (
                "healthcheck" in service_config
            ), f"Service {service_name} must have healthcheck configured"

    def test_services_use_test_ports(self, docker_compose_config):
        """Test that services use isolated test ports."""
        services = docker_compose_config.get("services", {})
        port_mappings = {
            "postgres-test": "5434",
            "redis-cache-test": "6379",
            "redis-queue-test": "6380",
            "minio-test": "9010",
            "fuseki-test": "3031",
            "api-service-test": "8001",
            "datacontract-service-test": "8093",
            "dq-service-test": "8084",
            "compliance-service-test": "8085",
            "semantic-service-test": "8086",
            "worker-service-test": "8087",
        }
        for service_name, expected_port in port_mappings.items():
            if service_name in services:
                ports = services[service_name].get("ports", [])
                # Check if expected port is in any port mapping
                # Handle both direct port numbers and environment variable substitution
                port_found = False
                for port_mapping in ports:
                    port_str = str(port_mapping)
                    # Check for direct port number
                    if f":{expected_port}:" in port_str or port_str.startswith(f"{expected_port}:"):
                        port_found = True
                        break
                    # Check for environment variable with default value
                    if f"${expected_port}" in port_str or f":-{expected_port}" in port_str:
                        port_found = True
                        break
                    # Check for dict format
                    if isinstance(port_mapping, dict):
                        published = str(port_mapping.get("published", ""))
                        if expected_port in published or f":-{expected_port}" in published:
                            port_found = True
                            break
                assert port_found, (
                    f"Service {service_name} should use port {expected_port}, "
                    f"but found ports: {ports}"
                )

    def test_services_use_test_network(self, docker_compose_config):
        """Test that services use test network."""
        services = docker_compose_config.get("services", {})
        for service_name, service_config in services.items():
            networks = service_config.get("networks", [])
            # Check if hub-test-net is in networks
            if isinstance(networks, list):
                network_names = networks
            elif isinstance(networks, dict):
                network_names = list(networks.keys())
            else:
                network_names = []
            assert "hub-test-net" in network_names or "hub-test-net" in str(
                networks
            ), f"Service {service_name} should use hub-test-net network"

    def test_services_have_test_environment(self, docker_compose_config):
        """Test that services have test environment variables."""
        services = docker_compose_config.get("services", {})
        for service_name, service_config in services.items():
            env = service_config.get("environment", {})
            if isinstance(env, dict):
                # Check if ENVIRONMENT is set to test
                if "ENVIRONMENT" in env:
                    assert env["ENVIRONMENT"] == "test" or "${ENVIRONMENT:-test}" in str(
                        env["ENVIRONMENT"]
                    ), f"Service {service_name} should have ENVIRONMENT=test"


class TestTestEnvironmentServices:
    """Tests for test environment services (requires services to be running)."""

    @pytest.fixture(scope="class")
    def test_services_running(self):
        """Check if test services are running."""
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", "docker-compose.test.yml", "ps", "--format", "json"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                services = [line for line in result.stdout.strip().split("\n") if line]
                running_services = [
                    s for s in services if '"State":"running"' in s or '"State":"healthy"' in s
                ]
                return len(running_services) > 0
        except Exception:
            pass
        return False

    @pytest.mark.skipif(
        not globals().get("PSYCOPG2_AVAILABLE", False),
        reason="psycopg2 not available",
    )
    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running. Start with: ./scripts/setup-test-environment.sh start",
    )
    def test_postgres_test_service_accessible(self):
        """Test that PostgreSQL test service is accessible."""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5434,
                user="hub_test",
                password="hub_test",
                database="hub_test",
                connect_timeout=5,
            )
            conn.close()
            assert True
        except Exception as e:
            pytest.fail(f"PostgreSQL test service not accessible: {e}")

    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running",
    )
    def test_redis_test_service_accessible(self):
        """Test that Redis test service is accessible."""
        import redis

        try:
            r = redis.Redis(host="localhost", port=6380, db=0, socket_connect_timeout=5)
            r.ping()
            assert True
        except Exception as e:
            pytest.fail(f"Redis test service not accessible: {e}")

    @pytest.mark.skipif(
        not globals().get("REQUESTS_AVAILABLE", False),
        reason="requests not available",
    )
    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running",
    )
    def test_minio_test_service_accessible(self):
        """Test that MinIO test service is accessible."""
        try:
            response = requests.get("http://localhost:9010/minio/health/live", timeout=5)
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(f"MinIO test service not accessible: {e}")

    @pytest.mark.skipif(
        not globals().get("REQUESTS_AVAILABLE", False),
        reason="requests not available",
    )
    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running",
    )
    def test_api_test_service_accessible(self):
        """Test that API test service is accessible."""
        try:
            response = requests.get("http://localhost:8001/health", timeout=10)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
        except Exception as e:
            pytest.fail(f"API test service not accessible: {e}")

    @pytest.mark.skipif(
        not globals().get("REQUESTS_AVAILABLE", False),
        reason="requests not available",
    )
    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running",
    )
    def test_datacontract_service_test_accessible(self):
        """Test that DataContract test service is accessible."""
        try:
            response = requests.get("http://localhost:8093/health", timeout=5)
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(f"DataContract test service not accessible: {e}")

    @pytest.mark.skipif(
        not globals().get("REQUESTS_AVAILABLE", False),
        reason="requests not available",
    )
    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running",
    )
    def test_dq_service_test_accessible(self):
        """Test that DQ test service is accessible."""
        try:
            response = requests.get("http://localhost:8084/health", timeout=5)
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(f"DQ test service not accessible: {e}")

    @pytest.mark.skipif(
        not globals().get("REQUESTS_AVAILABLE", False),
        reason="requests not available",
    )
    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running",
    )
    def test_compliance_service_test_accessible(self):
        """Test that Compliance test service is accessible."""
        try:
            response = requests.get("http://localhost:8085/health", timeout=5)
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(f"Compliance test service not accessible: {e}")

    @pytest.mark.skipif(
        not globals().get("REQUESTS_AVAILABLE", False),
        reason="requests not available",
    )
    @pytest.mark.skipif(
        not os.getenv("TEST_ENV_SERVICES_RUNNING", "").lower() == "true",
        reason="Test services not running",
    )
    def test_semantic_service_test_accessible(self):
        """Test that Semantic test service is accessible."""
        try:
            response = requests.get("http://localhost:8086/health", timeout=5)
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(f"Semantic test service not accessible: {e}")


class TestTestEnvironmentConfiguration:
    """Tests for test environment configuration modules."""

    def test_python_sdk_test_env_config_exists(self):
        """Test that Python SDK test environment config exists."""
        config_file = project_root / "tests" / "sdk_python" / "test_env_config.py"
        assert config_file.exists(), f"Python SDK test env config not found at {config_file}"

    def test_python_sdk_test_env_config_importable(self):
        """Test that Python SDK test environment config is importable."""
        try:
            from tests.sdk_python.test_env_config import (
                get_test_api_base_url,
                get_test_api_url,
                get_test_service_urls,
                is_test_environment,
            )

            assert callable(get_test_api_url)
            assert callable(get_test_api_base_url)
            assert callable(is_test_environment)
            assert callable(get_test_service_urls)
        except ImportError as e:
            pytest.fail(f"Failed to import Python SDK test env config: {e}")

    def test_python_sdk_test_env_config_functions(self):
        """Test that Python SDK test environment config functions work."""
        from tests.sdk_python.test_env_config import (
            get_test_api_base_url,
            get_test_api_url,
            get_test_service_urls,
        )

        # Test API URL
        api_url = get_test_api_url()
        assert api_url.startswith("http://")
        assert "localhost" in api_url or "8001" in api_url

        # Test API base URL
        api_base_url = get_test_api_base_url()
        assert api_base_url.endswith("/api/v1")

        # Test service URLs
        service_urls = get_test_service_urls()
        assert "datacontract" in service_urls
        assert "dq" in service_urls
        assert "compliance" in service_urls
        assert "semantic" in service_urls

    def test_javascript_sdk_test_env_config_exists(self):
        """Test that JavaScript SDK test environment config exists."""
        config_file = project_root / "sdk" / "js" / "src" / "__tests__" / "test-env-config.ts"
        assert config_file.exists(), f"JavaScript SDK test env config not found at {config_file}"

    def test_cli_test_env_config_exists(self):
        """Test that CLI test environment config exists."""
        config_file = project_root / "cli" / "tests" / "test_env_config.py"
        assert config_file.exists(), f"CLI test env config not found at {config_file}"

    def test_cli_test_env_config_importable(self):
        """Test that CLI test environment config is importable."""
        try:
            from cli.tests.test_env_config import (
                get_test_api_base_url,
                get_test_api_url,
                get_test_service_urls,
                is_test_environment,
            )

            assert callable(get_test_api_url)
            assert callable(get_test_api_base_url)
            assert callable(is_test_environment)
            assert callable(get_test_service_urls)
        except ImportError as e:
            pytest.fail(f"Failed to import CLI test env config: {e}")

    def test_cli_test_env_config_functions(self):
        """Test that CLI test environment config functions work."""
        from cli.tests.test_env_config import (
            get_test_api_base_url,
            get_test_api_url,
            get_test_service_urls,
        )

        # Test API URL
        api_url = get_test_api_url()
        assert api_url.startswith("http://")
        assert "localhost" in api_url or "8001" in api_url

        # Test API base URL
        api_base_url = get_test_api_base_url()
        assert api_base_url.endswith("/api/v1")

        # Test service URLs
        service_urls = get_test_service_urls()
        assert "datacontract" in service_urls
        assert "dq" in service_urls
        assert "compliance" in service_urls
        assert "semantic" in service_urls


class TestTestEnvironmentScripts:
    """Tests for test environment management scripts."""

    def test_setup_script_exists(self):
        """Test that setup-test-environment.sh exists."""
        script_file = project_root / "scripts" / "setup-test-environment.sh"
        assert script_file.exists(), f"Setup script not found at {script_file}"

    def test_setup_script_executable(self):
        """Test that setup-test-environment.sh is executable."""
        script_file = project_root / "scripts" / "setup-test-environment.sh"
        if script_file.exists():
            assert os.access(script_file, os.X_OK), f"Setup script {script_file} is not executable"

    def test_env_test_example_exists(self):
        """Test that .env.test.example exists."""
        env_file = project_root / ".env.test.example"
        assert env_file.exists(), f".env.test.example not found at {env_file}"

    def test_env_test_example_has_required_vars(self):
        """Test that .env.test.example has required variables."""
        env_file = project_root / ".env.test.example"
        if env_file.exists():
            content = env_file.read_text()
            # docker-compose.test uses POSTGRES_TEST_* to avoid .env override
            required_vars = [
                "POSTGRES_TEST_USER",
                "POSTGRES_TEST_PASSWORD",
                "POSTGRES_TEST_DB",
                "API_TEST_PORT",
                "DATACONTRACT_SERVICE_URL",
                "DQ_SERVICE_URL",
                "COMPLIANCE_SERVICE_URL",
                "SEMANTIC_SERVICE_URL",
            ]
            for var in required_vars:
                assert var in content, f"Required variable {var} not found in .env.test.example"
