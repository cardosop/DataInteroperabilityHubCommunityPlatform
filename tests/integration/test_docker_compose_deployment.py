"""
Comprehensive integration tests for Docker Compose deployment.

Tests service startup, health checks, dependencies, and service communication.
These tests actually start Docker Compose services and verify they work correctly.

NOTE: These tests require Docker Compose services to be started BEFORE running.
Use the test runner script: ./scripts/run_docker_compose_integration_tests.sh

For runtime tests, set PYTEST_DOCKER_COMPOSE_RUNTIME=1 and ensure services are running.

IMPORTANT: Runtime tests don't require Django - they test Docker Compose directly.
Set PYTEST_DOCKER_COMPOSE_RUNTIME=1 and unset DJANGO_SETTINGS_MODULE before running.

REQUIREMENT: Docker CLI must be available (e.g. on host). Tests skip when run inside
a container that does not have Docker (e.g. api-service-test container).
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

import pytest
import requests
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# For runtime tests, prevent pytest-django from loading Django
# This must be done before pytest-django plugin loads
_RUNTIME_TESTS_ENABLED = os.getenv("PYTEST_DOCKER_COMPOSE_RUNTIME") == "1"
if _RUNTIME_TESTS_ENABLED:
    # Unset DJANGO_SETTINGS_MODULE to prevent pytest-django from loading Django
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)
    os.environ["SKIP_DJANGO_SETUP"] = "1"

_HOST_ONLY_REASON = (
    "Docker Compose runtime test — requires PYTEST_DOCKER_COMPOSE_RUNTIME=1. "
    "Run on the host via: ./scripts/run_docker_compose_integration_tests.sh"
)


class DockerComposeManager:
    """Manages Docker Compose lifecycle for tests."""

    def __init__(self, compose_file: Path, project_name: str = "hub-test"):
        self.compose_file = compose_file
        self.project_name = project_name
        self.services_started = False

    def _run_command(
        self, command: list[str], check: bool = True, timeout: int = 300
    ) -> subprocess.CompletedProcess:
        """Run docker compose command."""
        cmd = ["docker", "compose", "-f", str(self.compose_file), "-p", self.project_name] + command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)
        if result.returncode != 0 and check:
            # Print error for debugging
            print(f"Docker Compose command failed: {' '.join(cmd)}")
            print(f"Return code: {result.returncode}")
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")
        return result

    def start_services(
        self,
        services: list[str] | None = None,
        wait: bool = True,
        no_deps: bool = False,
        force: bool = False,
    ) -> None:
        """Start Docker Compose services.

        When no_deps=True, start only the given services without their dependencies
        (docker compose up -d --no-deps). Does not touch services_started flag.
        When force=True, run up even if services_started (e.g. to restore a stopped service).
        """
        if no_deps:
            if not services:
                raise ValueError("services required when no_deps=True")
            cmd = ["up", "-d", "--no-deps", "--remove-orphans"] + services
            result = self._run_command(cmd, check=False)
            if result.returncode != 0:
                print(f"Docker Compose command failed: {' '.join(cmd)}")
                print(f"Return code: {result.returncode}")
                print(f"Stderr: {result.stderr}")
            result.check_returncode()
            if wait:
                self.wait_for_services_healthy(services)
            return

        if self.services_started and not force:
            return

        if not force:
            # First, try to stop any existing containers with conflicting names
            try:
                self._run_command(["down", "-v"], check=False)
            except Exception as e:
                logger.warning(
                    "Docker Compose down before start failed (continuing): %s", e, exc_info=True
                )

        # Start services
        cmd = ["up", "-d", "--remove-orphans"]
        if services:
            cmd.extend(services)

        result = self._run_command(cmd, check=False)
        if result.returncode != 0:
            # If there are container name conflicts, try to remove them first
            if "already in use" in result.stderr or "Conflict" in result.stderr:
                # Extract container names from error
                import re

                container_names = re.findall(r'container name "([^"]+)"', result.stderr)
                for container_name in container_names:
                    # Remove the leading slash if present
                    container_name = container_name.lstrip("/")
                    try:
                        subprocess.run(
                            ["docker", "rm", "-f", container_name],
                            capture_output=True,
                            check=False,
                            timeout=30,
                        )
                    except Exception as e:
                        logger.warning(
                            "docker rm -f %s failed (continuing): %s",
                            container_name,
                            e,
                            exc_info=True,
                        )

                # Retry starting services
                result = self._run_command(cmd, check=False)
                if result.returncode != 0:
                    print(f"Docker Compose retry failed: {' '.join(cmd)}")
                    print(f"Return code: {result.returncode}")
                    print(f"Stdout: {result.stdout}")
                    print(f"Stderr: {result.stderr}")
                    result.check_returncode()
            else:
                # Print error details before re-raising
                print(f"Docker Compose command failed: {' '.join(cmd)}")
                print(f"Return code: {result.returncode}")
                print(f"Stdout: {result.stdout}")
                print(f"Stderr: {result.stderr}")
                result.check_returncode()

        if not force:
            self.services_started = True

        if wait:
            self.wait_for_services_healthy(services or self.get_all_services())

    def stop_services(self, services: list[str] | None = None) -> None:
        """Stop Docker Compose services."""
        cmd = ["stop"]
        if services:
            cmd.extend(services)
        else:
            cmd = ["down", "-v", "--remove-orphans"]

        try:
            self._run_command(cmd, check=False, timeout=60)
        except subprocess.TimeoutExpired:
            # Force stop if timeout
            try:
                self._run_command(
                    ["down", "-v", "--timeout", "10", "--remove-orphans"], check=False, timeout=30
                )
            except Exception as e:
                logger.warning(
                    "Docker Compose force down after stop timeout failed: %s", e, exc_info=True
                )

        self.services_started = False

    def get_service_status(self, service_name: str) -> dict | None:
        """Get service status."""
        result = self._run_command(["ps", "--format", "json", service_name], check=False)
        if result.returncode != 0 or not result.stdout.strip():
            return None

        try:
            services = [json.loads(line) for line in result.stdout.strip().split("\n") if line]
            return services[0] if services else None
        except json.JSONDecodeError:
            return None

    def get_all_services(self) -> list[str]:
        """Get all service names from docker-compose.yml."""
        with open(self.compose_file) as f:
            config = yaml.safe_load(f)
        return list(config.get("services", {}).keys())

    def wait_for_service_healthy(self, service_name: str, timeout: int = 300) -> bool:
        """Wait for service to become healthy."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_service_status(service_name)
            if status:
                health = status.get("Health", "")
                state = status.get("State", "")
                if health == "healthy" or (state == "running" and health == ""):
                    return True
            time.sleep(2)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services
        return False

    def wait_for_services_healthy(self, services: list[str], timeout: int = 300) -> None:
        """Wait for multiple services to become healthy."""
        for service in services:
            if not self.wait_for_service_healthy(service, timeout):
                raise RuntimeError(
                    f"Service {service} failed to become healthy within {timeout} seconds"
                )

    def get_service_logs(self, service_name: str, tail: int = 100) -> str:
        """Get service logs."""
        result = self._run_command(["logs", "--tail", str(tail), service_name], check=False)
        return result.stdout

    def restart_service(self, service_name: str) -> None:
        """Restart a service."""
        self._run_command(["restart", service_name])
        self.wait_for_service_healthy(service_name)


def _docker_available() -> bool:
    """Check if Docker CLI and daemon are available (required for these tests)."""
    if shutil.which("docker") is None:
        return False
    # Verify the daemon is actually running and accessible
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


@pytest.fixture(scope="module")
def compose_file_path():
    """Get path to docker-compose.yml — no Docker check (for YAML-only tests)."""
    compose_file = project_root / "docker-compose.yml"
    assert compose_file.exists(), f"docker-compose.yml not found at {compose_file}"
    return compose_file


@pytest.fixture(scope="module")
def docker_compose_file(compose_file_path):
    """Get path to docker-compose.yml (requires Docker for runtime tests)."""
    if not _docker_available():
        pytest.skip("Docker CLI not available (run these tests on host with Docker)")
    return compose_file_path


@pytest.fixture(scope="module")
def docker_compose_config(compose_file_path):
    """Load docker-compose.yml configuration."""
    with open(compose_file_path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def docker_compose_manager(docker_compose_file):
    """Create Docker Compose manager.

    Skips when PYTEST_DOCKER_COMPOSE_RUNTIME is not set — these runtime tests
    are host-only and should be executed via:
        ./scripts/run_docker_compose_integration_tests.sh
    """
    if not _RUNTIME_TESTS_ENABLED:
        pytest.skip(_HOST_ONLY_REASON)
    manager = DockerComposeManager(docker_compose_file)
    yield manager
    # Cleanup
    manager.stop_services()


@pytest.fixture(scope="module")
def infrastructure_services(docker_compose_config):
    """Get infrastructure service names (matches docker-compose.yml: redis-cache, not redis)."""
    return ["postgres", "redis-cache", "minio", "fuseki"]


@pytest.fixture(scope="module")
def application_services(docker_compose_config):
    """Get application service names that must be present in docker-compose.yml."""
    return [
        "api-service",
        "worker-service",
        "compliance-service",
        "dq-service",
        "datacontract-service",
        "semantic-service",
        "prefect-server",
        "prefect-worker",
        "prefect-integration-service",
    ]


@pytest.mark.integration
class TestDockerComposeDeployment:
    """Integration tests for Docker Compose deployment."""

    def test_docker_compose_file_exists(self, compose_file_path):
        """Test that docker-compose.yml exists."""
        assert compose_file_path.exists(), (
            f"docker-compose.yml not found at {compose_file_path}"
        )

    def test_docker_compose_valid_yaml(self, docker_compose_config):
        """Test that docker-compose.yml is valid YAML."""
        assert docker_compose_config is not None
        assert "services" in docker_compose_config

    def test_infrastructure_services_defined(self, docker_compose_config, infrastructure_services):
        """Test that infrastructure services are defined."""
        services = docker_compose_config.get("services", {})
        for service_name in infrastructure_services:
            assert service_name in services, f"Infrastructure service {service_name} not found"

    def test_application_services_defined(self, docker_compose_config, application_services):
        """Test that application services are defined."""
        services = docker_compose_config.get("services", {})
        for service_name in application_services:
            assert service_name in services, f"Application service {service_name} not found"

    def test_services_have_healthchecks(self, docker_compose_config, application_services):
        """Test that application services have health checks."""
        services = docker_compose_config.get("services", {})
        for service_name in application_services:
            if service_name in services:
                service_config = services[service_name]
                assert "healthcheck" in service_config, (
                    f"Service {service_name} must have a healthcheck"
                )


@pytest.mark.integration
@pytest.mark.requires_db
class TestDockerComposeServiceStartup:
    """Integration tests for service startup.

    These tests require Docker Compose services to be available.
    They will start services if not already running.
    """

    def test_infrastructure_services_start(self, docker_compose_manager, infrastructure_services):
        """Test that infrastructure services start successfully."""
        docker_compose_manager.start_services(infrastructure_services, wait=True)

        for service_name in infrastructure_services:
            status = docker_compose_manager.get_service_status(service_name)
            assert status is not None, f"Service {service_name} not found after start"
            assert status.get("State") == "running", (
                f"Service {service_name} is not running: {status.get('State')}"
            )

    def test_application_services_start_after_infrastructure(
        self, docker_compose_manager, infrastructure_services, application_services
    ):
        """Test that application services start after infrastructure."""
        # Start infrastructure first
        docker_compose_manager.start_services(infrastructure_services, wait=True)

        # Start application services
        docker_compose_manager.start_services(application_services, wait=True)

        for service_name in application_services:
            status = docker_compose_manager.get_service_status(service_name)
            assert status is not None, f"Service {service_name} not found after start"
            assert status.get("State") == "running", (
                f"Service {service_name} is not running: {status.get('State')}"
            )

    def test_service_startup_order_respects_dependencies(
        self, docker_compose_manager, docker_compose_config
    ):
        """Test that service startup order respects dependencies."""
        # Start all services
        all_services = docker_compose_manager.get_all_services()
        docker_compose_manager.start_services(all_services, wait=True)

        # Check that services with dependencies wait for their dependencies
        services = docker_compose_config.get("services", {})

        # Check workflow-engine-service depends on postgres and redis
        workflow_engine = services.get("workflow-engine-service", {})
        depends_on = workflow_engine.get("depends_on", {})

        if isinstance(depends_on, dict):
            # Check condition: service_healthy
            if "postgres" in depends_on:
                postgres_dep = depends_on["postgres"]
                if isinstance(postgres_dep, dict):
                    assert postgres_dep.get("condition") == "service_healthy", (
                        "workflow-engine-service should wait for postgres to be healthy"
                    )

        # Verify postgres is healthy before workflow-engine starts
        postgres_status = docker_compose_manager.get_service_status("postgres")
        workflow_status = docker_compose_manager.get_service_status("workflow-engine-service")

        if postgres_status and workflow_status:
            # Both should be running
            assert postgres_status.get("State") == "running"
            assert workflow_status.get("State") == "running"

    def test_service_restart(self, docker_compose_manager, application_services):
        """Test that services can be restarted."""
        # Start services first
        docker_compose_manager.start_services(application_services[:2], wait=True)

        # Restart a service
        service_to_restart = application_services[0]
        docker_compose_manager.restart_service(service_to_restart)

        # Verify service is still running
        status = docker_compose_manager.get_service_status(service_to_restart)
        assert status is not None
        assert status.get("State") == "running"


@pytest.mark.integration
@pytest.mark.requires_db
class TestDockerComposeHealthChecks:
    """Integration tests for service health checks."""

    # Health endpoint mappings: (service_name, host_port, endpoint_path)
    # Host ports from docker-compose.yml: workflow-engine 8098, workflow-registry 8089, api 8000
    HEALTH_ENDPOINTS = [
        ("workflow-engine-service", 8098, "/healthz"),
        ("workflow-engine-service", 8098, "/ready"),
        ("workflow-registry-service", 8089, "/health"),
        ("api-service", 8000, "/health"),
    ]

    @pytest.fixture(scope="class")
    def started_services(
        self, docker_compose_manager, infrastructure_services, application_services
    ):
        """Start all services for health check tests."""
        docker_compose_manager.start_services(infrastructure_services, wait=True)
        docker_compose_manager.start_services(application_services, wait=True)
        yield
        # Cleanup handled by docker_compose_manager fixture

    def test_health_endpoints_accessible(self, docker_compose_manager, started_services):
        """Test that health endpoints are accessible."""
        for service_name, port, endpoint in self.HEALTH_ENDPOINTS:
            # Check if service is running
            status = docker_compose_manager.get_service_status(service_name)
            if not status or status.get("State") != "running":
                pytest.skip(f"Service {service_name} is not running")  # noqa: skip-in-body — runtime service dependency

            # Try to access health endpoint
            url = f"http://localhost:{port}{endpoint}"
            try:
                response = requests.get(url, timeout=5)
                assert response.status_code == 200, (
                    f"Health endpoint {url} returned {response.status_code}"
                )
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Failed to access health endpoint {url}: {e}")

    def test_liveness_probes_respond(self, docker_compose_manager, started_services):
        """Test that liveness probes respond correctly."""
        liveness_endpoints = [
            ("workflow-engine-service", 8098, "/healthz"),
        ]

        for service_name, port, endpoint in liveness_endpoints:
            status = docker_compose_manager.get_service_status(service_name)
            if not status or status.get("State") != "running":
                pytest.skip(f"Service {service_name} is not running")  # noqa: skip-in-body — runtime service dependency

            url = f"http://localhost:{port}{endpoint}"
            response = requests.get(url, timeout=5)
            assert response.status_code == 200, (
                f"Liveness probe {url} returned {response.status_code}"
            )

            # Check response format — validate the JSON structure, not just substring presence
            try:
                data = response.json()
                status_val = data.get("status", "")
                self.assertIn(
                    status_val.lower(),
                    ["ok", "healthy", "pass"],
                    f"Unexpected liveness probe response: {data}",
                )
            except (json.JSONDecodeError, ValueError):
                assert response.text.lower().strip() in ["ok", "healthy", "true"]

    def test_readiness_probes_respond(self, docker_compose_manager, started_services):
        """Test that readiness probes respond correctly."""
        readiness_endpoints = [
            ("workflow-engine-service", 8098, "/ready"),
        ]

        for service_name, port, endpoint in readiness_endpoints:
            status = docker_compose_manager.get_service_status(service_name)
            if not status or status.get("State") != "running":
                pytest.skip(f"Service {service_name} is not running")  # noqa: skip-in-body — runtime service dependency

            url = f"http://localhost:{port}{endpoint}"
            response = requests.get(url, timeout=5)
            assert response.status_code == 200, (
                f"Readiness probe {url} returned {response.status_code}"
            )

            # Check response includes dependency status
            try:
                data = response.json()
                status_val = data.get("status", data.get("ready", ""))
                self.assertIn(
                    status_val.lower(),
                    ["ok", "ready"],
                    f"Unexpected readiness probe response: {data}",
                )
            except (json.JSONDecodeError, ValueError):
                assert response.text.lower().strip() in ["ready", "ok", "true"]

    def test_metrics_endpoints_accessible(self, docker_compose_manager, started_services):
        """Test that Prometheus metrics endpoints are accessible."""
        metrics_endpoints = [
            ("workflow-engine-service", 8098, "/metrics"),
        ]

        for service_name, port, endpoint in metrics_endpoints:
            status = docker_compose_manager.get_service_status(service_name)
            if not status or status.get("State") != "running":
                pytest.skip(f"Service {service_name} is not running")  # noqa: skip-in-body — runtime service dependency

            url = f"http://localhost:{port}{endpoint}"
            response = requests.get(url, timeout=5)
            assert response.status_code == 200, (
                f"Metrics endpoint {url} returned {response.status_code}"
            )

            # Check that response contains Prometheus format
            assert "# HELP" in response.text or "# TYPE" in response.text, (
                f"Metrics endpoint {url} should return Prometheus format"
            )


@pytest.mark.integration
@pytest.mark.requires_db
class TestDockerComposeServiceCommunication:
    """Integration tests for service-to-service communication."""

    @pytest.fixture(scope="class")
    def started_services(
        self, docker_compose_manager, infrastructure_services, application_services
    ):
        """Start all services for communication tests."""
        docker_compose_manager.start_services(infrastructure_services, wait=True)
        docker_compose_manager.start_services(application_services, wait=True)
        yield
        # Cleanup handled by docker_compose_manager fixture

    def test_services_can_reach_each_other(
        self, docker_compose_manager, started_services, application_services
    ):
        """Test that services can reach each other via Docker network."""
        # Test that workflow-engine-service can reach postgres
        workflow_status = docker_compose_manager.get_service_status("workflow-engine-service")
        postgres_status = docker_compose_manager.get_service_status("postgres")

        if not workflow_status or not postgres_status:
            pytest.fail(
                f"Required services not found: "
                f"workflow={workflow_status is not None}, "
                f"postgres={postgres_status is not None}"
            )
        assert workflow_status.get("State") == "running"
        assert postgres_status.get("State") == "running"

        # Test network connectivity by checking if workflow-engine can connect to postgres
        workflow_health = requests.get("http://localhost:8098/ready", timeout=5)
        assert workflow_health.status_code == 200, (
            "workflow-engine-service should be able to connect to postgres"
        )

    def test_service_discovery_works(self, docker_compose_manager, started_services):
        """Test that service discovery works within Docker network.

        Services should be able to resolve each other by name — verified
        indirectly via health checks that require service discovery.
        """
        registry_status = docker_compose_manager.get_service_status("workflow-registry-service")
        engine_status = docker_compose_manager.get_service_status("workflow-engine-service")

        if not registry_status or not engine_status:
            pytest.fail(
                f"Required services not found: "
                f"registry={registry_status is not None}, "
                f"engine={engine_status is not None}"
            )
        assert registry_status.get("State") == "running"
        assert engine_status.get("State") == "running"

        registry_health = requests.get("http://localhost:8089/health", timeout=5)
        engine_health = requests.get("http://localhost:8098/healthz", timeout=5)
        assert registry_health.status_code == 200
        assert engine_health.status_code == 200

    def test_api_service_can_reach_backend_services(self, docker_compose_manager, started_services):
        """Test that API service can reach backend services."""
        api_status = docker_compose_manager.get_service_status("api-service")

        if not api_status or api_status.get("State") != "running":
            pytest.fail(
                f"API service not running: status={'found' if api_status else 'missing'}"
            )
        api_health = requests.get("http://localhost:8000/health", timeout=5)
        assert api_health.status_code == 200, (
            "API service should be healthy and able to reach backend services"
        )


@pytest.mark.integration
@pytest.mark.requires_db
class TestDockerComposeServiceDependencies:
    """Integration tests for service dependencies."""

    @pytest.fixture(scope="class")
    def started_services(self, docker_compose_manager, infrastructure_services):
        """Start infrastructure services for dependency tests."""
        docker_compose_manager.start_services(infrastructure_services, wait=True)
        yield
        # Cleanup handled by docker_compose_manager fixture

    def test_workflow_engine_depends_on_postgres(
        self, docker_compose_manager, started_services, docker_compose_config
    ):
        """Test that workflow-engine-service depends on postgres."""
        workflow_config = docker_compose_config.get("services", {}).get(
            "workflow-engine-service", {}
        )
        depends_on = workflow_config.get("depends_on", {})
        dep_list = list(depends_on.keys()) if isinstance(depends_on, dict) else (depends_on or [])

        assert "postgres" in dep_list, "workflow-engine-service must depend on postgres"

        # Verify postgres is healthy before starting workflow-engine
        postgres_status = docker_compose_manager.get_service_status("postgres")
        assert postgres_status is not None
        assert postgres_status.get("State") == "running"

        # Start workflow-engine and verify it waits for postgres
        docker_compose_manager.start_services(["workflow-engine-service"], wait=True)
        workflow_status = docker_compose_manager.get_service_status("workflow-engine-service")
        assert workflow_status is not None
        assert workflow_status.get("State") == "running"

    def test_workflow_engine_depends_on_redis(
        self, docker_compose_manager, started_services, docker_compose_config
    ):
        """Test that workflow-engine-service depends on redis-cache (and other redis instances)."""
        workflow_config = docker_compose_config.get("services", {}).get(
            "workflow-engine-service", {}
        )
        depends_on = workflow_config.get("depends_on", {})
        dep_list = list(depends_on.keys()) if isinstance(depends_on, dict) else (depends_on or [])

        assert "redis-cache" in dep_list, "workflow-engine-service must depend on redis-cache"

        # Verify redis-cache is healthy
        redis_cache_status = docker_compose_manager.get_service_status("redis-cache")
        assert redis_cache_status is not None
        assert redis_cache_status.get("State") == "running"

    def test_api_service_depends_on_infrastructure(
        self, docker_compose_manager, started_services, docker_compose_config
    ):
        """Test that api-service depends on infrastructure services."""
        api_config = docker_compose_config.get("services", {}).get("api-service", {})
        depends_on = api_config.get("depends_on", {})
        dep_list = list(depends_on.keys()) if isinstance(depends_on, dict) else (depends_on or [])

        required_deps = ["postgres", "redis-cache", "minio"]
        for dep in required_deps:
            assert dep in dep_list, f"api-service must depend on {dep}"

    def test_dependency_health_conditions(
        self, docker_compose_manager, started_services, docker_compose_config
    ):
        """Test that dependencies use health conditions."""
        services = docker_compose_config.get("services", {})

        # Check that critical services wait for dependencies to be healthy
        workflow_config = services.get("workflow-engine-service", {})
        depends_on = workflow_config.get("depends_on", {})

        if isinstance(depends_on, dict) and "postgres" in depends_on:
            postgres_dep = depends_on["postgres"]
            if isinstance(postgres_dep, dict):
                assert postgres_dep.get("condition") == "service_healthy", (
                    "workflow-engine-service should wait for postgres to be healthy"
                )

    def test_services_fail_without_dependencies(
        self, docker_compose_manager, docker_compose_config
    ):
        """Test that services fail gracefully when dependencies are unavailable.

        Root cause (validation): (1) Asserting on log content was flaky. (2) start_services
        without --no-deps would bring postgres back up. (3) services_started guard caused
        start_services to no-op. Fix: use start_services(..., no_deps=True) so we start only
        workflow-engine without postgres; assert on health/state; always restore postgres.
        """
        try:
            docker_compose_manager.stop_services(["postgres"])
            # Start only workflow-engine without dependencies (--no-deps)
            docker_compose_manager.start_services(
                ["workflow-engine-service"], wait=False, no_deps=True
            )
            time.sleep(15)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services
            status = docker_compose_manager.get_service_status("workflow-engine-service")
            if status:
                health = status.get("Health", "")
                state = status.get("State", "")
                assert not (state == "running" and health == "healthy"), (
                    "workflow-engine-service should not be healthy when postgres is down"
                )
        except AssertionError:
            raise
        except Exception as e:
            raise AssertionError(
                f"Test failed with unexpected error (root cause must be fixed, not masked): {e!r}"
            ) from e
        finally:
            docker_compose_manager.start_services(["postgres"], wait=True, force=True)
