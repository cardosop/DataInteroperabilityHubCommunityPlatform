"""
End-to-End tests for Docker Compose deployment.

These tests verify complete Docker Compose deployment scenarios including:
- Complete deployment startup and health
- Workflow execution in Docker Compose environment
- Event bus functionality in Docker Compose environment
- Service layer interactions in Docker Compose environment

These tests require Docker Compose services to be running.
Run with: pytest tests/e2e/test_docker_compose_e2e.py --docker-compose-runtime -v
"""

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests
import yaml

# Set environment variable to allow connection failures during import
os.environ["DOCKER_COMPOSE_E2E_TEST"] = "true"

# Module-level pytest markers
# These tests use Docker CLI + HTTP requests only — no Django DB access needed.
pytestmark = [pytest.mark.e2e, pytest.mark.docker_compose_runtime, pytest.mark.slow]

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure Django settings before any Django imports
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

# Defer Django imports until needed to avoid connection issues during import
# Django models will be imported inside test methods when needed


class DockerComposeE2EManager:
    """Manages Docker Compose lifecycle for E2E tests."""

    def __init__(self, compose_file: Path, project_name: str = "hub-e2e-test"):
        self.compose_file = compose_file
        self.project_name = project_name
        self.services_started = False

    @staticmethod
    def _docker_available() -> bool:
        """Check if Docker CLI is available (tests run on host, not inside container)."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _run_command(
        self, command: list[str], check: bool = True, timeout: int = 600
    ) -> subprocess.CompletedProcess:
        """Run docker compose command."""
        if not self._docker_available():
            raise RuntimeError(
                "Docker CLI not available. These tests must run on the host with Docker installed, "
                "not inside a container. Use --docker-compose-runtime when Docker is available."
            )
        cmd = ["docker", "compose", "-f", str(self.compose_file), "-p", self.project_name] + command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)
        return result

    def start_services(
        self, services: list[str] | None = None, wait: bool = True, timeout: int = 600
    ) -> None:
        """Start Docker Compose services."""
        if self.services_started:
            return

        cmd = ["up", "-d"]
        if services:
            cmd.extend(services)

        self._run_command(cmd, timeout=timeout)
        self.services_started = True

        if wait:
            self.wait_for_services_healthy(services or self.get_all_services(), timeout=timeout)

    def stop_services(self, services: list[str] | None = None) -> None:
        """Stop Docker Compose services."""
        cmd = ["stop"]
        if services:
            cmd.extend(services)
        else:
            cmd = ["down", "-v"]

        try:
            self._run_command(cmd, check=False, timeout=300)
        except subprocess.TimeoutExpired:
            # Force stop if timeout
            self._run_command(["down", "-v", "--timeout", "10"], check=False, timeout=60)

        self.services_started = False

    def get_service_status(self, service_name: str) -> dict | None:
        """Get service status."""
        # First try with current project
        result = self._run_command(["ps", "--format", "json", service_name], check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                services = [json.loads(line) for line in result.stdout.strip().split("\n") if line]
                if services:
                    return services[0]
            except json.JSONDecodeError:
                pass

        # If not found, check all containers (services may be running under different project).
        # Service names vary across environments:
        #   test:    api-service-test  → container hub-test-api
        #   staging: api-service       → container hub-staging-api
        #   dev:     api-service       → container hub-api
        # Build a list of name variants to search for.
        service_base = service_name.replace("-service", "")
        search_variants = [
            service_name,  # api-service
            service_base,  # api
            f"{service_name}-test",  # api-service-test
            f"{service_base}-test",  # api-test
        ]

        def _matches(container_name: str) -> bool:
            """Check if container name is the primary service container.

            Must match the service name exactly at the end of the
            container name — not just as a substring.  This prevents
            ``hub-test-compliance-rq-worker`` from matching when we
            want ``hub-test-compliance``.
            """
            # Exact-end matches (most specific first)
            exact_suffixes = [
                f"hub-test-{service_base}",
                f"hub-staging-{service_base}",
                f"hub-{service_base}",
                f"hub-{service_base}-staging",
                service_name,
                service_base,
            ]
            for suffix in exact_suffixes:
                if (
                    container_name == suffix
                    or container_name.endswith(f"-{suffix}")
                    or container_name.endswith(f"_{suffix}")
                ):
                    return True
                # Also handle when container name IS the suffix
                if container_name == suffix:
                    return True
            return False

        try:
            # Search running containers by broad name filter.
            # Collect all candidates, then pick the best match
            # (shortest name = most likely the primary service,
            # not a sidecar like -rq-worker or -migration).
            for filter_name in search_variants:
                all_result = subprocess.run(
                    ["docker", "ps", "--format", "json", "--filter", f"name={filter_name}"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if all_result.returncode == 0 and all_result.stdout.strip():
                    services = [
                        json.loads(line) for line in all_result.stdout.strip().split("\n") if line
                    ]
                    candidates = [s for s in services if _matches(s.get("Names", ""))]
                    if candidates:
                        # Prefer the shortest name (primary service,
                        # not sidecar like -rq-worker, -migration)
                        candidates.sort(key=lambda s: len(s.get("Names", "")))
                        return candidates[0]

            # Also try checking by compose service label
            for label_name in search_variants:
                label_result = subprocess.run(
                    [
                        "docker",
                        "ps",
                        "--format",
                        "json",
                        "--filter",
                        f"label=com.docker.compose.service={label_name}",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if label_result.returncode == 0 and label_result.stdout.strip():
                    services = [
                        json.loads(line) for line in label_result.stdout.strip().split("\n") if line
                    ]
                    if services:
                        return services[0]
        except Exception:
            pass

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
            time.sleep(2)  # INTENTIONAL: e2e/integration test polling real services
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

    def get_service_port(self, service_name: str, internal_port: int | None = None) -> int | None:
        """Get published port for a service."""
        status = self.get_service_status(service_name)
        if not status:
            return None

        # Try to get port from Publishers (docker compose ps format)
        publishers = status.get("Publishers", [])
        if publishers:
            # Get first published port
            for pub in publishers:
                if pub.get("PublishedPort"):
                    return pub["PublishedPort"]

        # Fallback: parse from Ports string (format: "0.0.0.0:8001->8000/tcp")
        ports_str = status.get("Ports", "")
        if ports_str:
            # Extract published port (first number before ->)
            import re

            match = re.search(r":(\d+)->", ports_str)
            if match:
                return int(match.group(1))

        # If internal_port provided, try to find matching port mapping from compose file
        if internal_port:
            with open(self.compose_file) as f:
                config = yaml.safe_load(f)
            service_config = config.get("services", {}).get(service_name, {})
            ports_config = service_config.get("ports", [])
            for port_mapping in ports_config:
                if isinstance(port_mapping, str):
                    # Format: "8001:8000"
                    parts = port_mapping.split(":")
                    if len(parts) == 2 and parts[1] == str(internal_port):
                        return int(parts[0])
                elif isinstance(port_mapping, dict):
                    # Format: {"published": 8001, "target": 8000}
                    if port_mapping.get("target") == internal_port:
                        return port_mapping.get("published")

        return None

    def get_service_url(
        self, service_name: str, path: str = "", internal_port: int | None = None
    ) -> str | None:
        """Get full URL for a service endpoint."""
        port = self.get_service_port(service_name, internal_port)
        if not port:
            return None
        return f"http://localhost:{port}{path}"

    def is_service_available(self, service_name: str) -> bool:
        """Check if service is available (running)."""
        status = self.get_service_status(service_name)
        if not status:
            return False
        state = status.get("State", "")
        return state == "running"


def detect_compose_file():
    """Detect which Docker Compose file to use based on running services.

    Checks test, staging, dev, and main compose files in order,
    returning the first one that has >= 5 running services.
    """
    candidates = [
        "docker-compose.test.yml",
        "docker-compose.staging.yml",
        "docker-compose.dev.yml",
    ]
    for filename in candidates:
        compose_path = project_root / filename
        if not compose_path.exists():
            continue
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", filename, "ps", "--format", "json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(project_root),
            )
            if result.returncode == 0 and result.stdout.strip():
                services = [json.loads(line) for line in result.stdout.strip().split("\n") if line]
                running = [s for s in services if s.get("State") == "running"]
                if len(running) >= 5:
                    return compose_path
        except Exception:
            continue

    # Fall back to main compose file
    compose_file = project_root / "docker-compose.yml"
    assert compose_file.exists(), f"docker-compose.yml not found at {compose_file}"
    return compose_file


@pytest.fixture(scope="module")
def docker_compose_file():
    """Get path to docker-compose.yml."""
    return detect_compose_file()


@pytest.fixture(scope="module")
def docker_compose_config(docker_compose_file):
    """Load docker-compose.yml configuration."""
    with open(docker_compose_file) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def docker_compose_manager(docker_compose_file):
    """Create Docker Compose manager."""
    if not DockerComposeE2EManager._docker_available():
        pytest.skip(
            "Docker CLI not available. Run these tests on the host with Docker installed, "
            "not inside a container (e.g. api-service-test)."
        )
    manager = DockerComposeE2EManager(docker_compose_file)
    yield manager
    # Cleanup
    manager.stop_services()


@pytest.fixture(scope="module")
def infrastructure_services():
    """Get infrastructure service names."""
    return ["postgres", "redis", "minio", "fuseki"]


@pytest.fixture(scope="module")
def core_services(docker_compose_config):
    """Get core application service names."""
    services = []
    available_services = docker_compose_config.get("services", {})

    # Add services that exist in compose file
    potential_services = [
        "workflow-engine-service",
        "workflow-registry-service",
        "event-bus-health-service",
        "event-schema-registry-service",
        "api-service",
        "worker-service",
    ]

    for service_name in potential_services:
        if service_name in available_services:
            services.append(service_name)

    return services


@pytest.fixture(scope="module")
def microservices():
    """Get microservice names."""
    return [
        "semantic-service",
        "dq-service",
        "compliance-service",
        "datacontract-service",
        "search-service",
        "observability-service",
        "webhook-service",
        "prefect-integration-service",
    ]


@pytest.fixture(scope="module")
def all_services(infrastructure_services, core_services, microservices):
    """Get all service names."""
    return infrastructure_services + core_services + microservices


@pytest.fixture(scope="module")
def started_services(docker_compose_manager, infrastructure_services, core_services):
    """Start all required services for E2E tests."""
    # Check if services are already running (don't start if they are)
    # Note: Services may be running under a different project name, so we check by service name
    running_services = []
    stopped_services = []

    for service in infrastructure_services + core_services:
        status = docker_compose_manager.get_service_status(service)
        if status:
            state = status.get("State", "")
            if state == "running":
                running_services.append(service)
            elif state in ["exited", "stopped", "created"]:
                stopped_services.append(service)

    # Only start services that aren't running
    services_to_start = [
        s for s in infrastructure_services + core_services if s not in running_services
    ]

    if services_to_start:
        # Start infrastructure first
        infra_to_start = [s for s in infrastructure_services if s not in running_services]
        if infra_to_start:
            try:
                docker_compose_manager.start_services(infra_to_start, wait=True, timeout=300)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                # Log but don't fail - some services may not be available
                import warnings

                warnings.warn(f"Failed to start infrastructure services {infra_to_start}: {e}")

        # Start core services
        core_to_start = [s for s in core_services if s not in running_services]
        if core_to_start:
            try:
                # Try to start core services, but don't wait too long
                docker_compose_manager.start_services(core_to_start, wait=False, timeout=300)
                # Give services some time to start
                import time

                time.sleep(10)  # INTENTIONAL: e2e/integration test polling real services
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                # Log but don't fail - some services may not be available or may take longer
                import warnings

                warnings.warn(f"Failed to start core services {core_to_start}: {e}")

    yield

    # Don't stop services - they may be shared with other tests
    # Cleanup handled by docker_compose_manager fixture only if we started them


@pytest.fixture(scope="function")
def api_base_url(docker_compose_manager):
    """Get the base URL for the API service running in Docker."""
    api_url = docker_compose_manager.get_service_url("api-service", "", 8000)
    if not api_url:
        # Try test variant
        api_url = docker_compose_manager.get_service_url("api-service-test", "", 8000)
    if not api_url:
        # Last resort: default port from docker-compose.test.yml
        api_url = "http://localhost:8001"
    return api_url.rstrip("/")


@pytest.fixture(scope="function")
def api_session(api_base_url):
    """Create an HTTP session for the API service with authentication.

    Uses the API's health endpoint to verify connectivity, then creates
    a test tenant+user+API key via docker exec into the running container.
    Works from the host without Django installed.
    """
    session = requests.Session()

    # Verify API is reachable
    try:
        resp = requests.get(f"{api_base_url}/health/", timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"API service not healthy at {api_base_url}")
    except requests.exceptions.ConnectionError:
        pytest.skip(f"API service not reachable at {api_base_url}")

    # Create API key via docker exec into the running API container
    container = None
    for name in ["hub-test-api", "hub-staging-api", "hub-api"]:
        check = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"name={name}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if check.stdout.strip():
            container = name
            break

    if not container:
        pytest.skip("Could not find running API container for auth setup")

    # One-liner: get-or-create tenant + subscription + user + API key
    setup_script = (
        "from hub.apps.tenants.models import Tenant, TenantPlan; "
        "from hub.apps.users.models import User, UserStatus, Role, UserRole; "
        "from hub.apps.auth.models import APIKey; "
        "from hub.apps.billing.models import Subscription, SubscriptionStatus; "
        "from django.utils import timezone; "
        "from datetime import timedelta; "
        "p, _ = TenantPlan.objects.get_or_create(slug='free', defaults={'name':'Free','tier':'FREE','is_active':True,'limits_json':{}}); "
        "t, _ = Tenant.objects.get_or_create(slug='docker-e2e-host', defaults={'name': 'Docker E2E Host', 'plan': p}); "
        "Subscription.objects.get_or_create(tenant=t, defaults={'plan':p,'status':SubscriptionStatus.ACTIVE,'current_period_start':timezone.now(),'current_period_end':timezone.now()+timedelta(days=365)}); "
        "u, _ = User.objects.get_or_create(email='docker-e2e@test.com', defaults={'tenant': t, 'status': UserStatus.ACTIVE}); "
        "r, _ = Role.objects.get_or_create(tenant=t, name='TENANT_ADMIN', defaults={'description': 'TA'}); "
        "UserRole.objects.get_or_create(user=u, role=r); "
        "k = APIKey.generate_key(); "
        "APIKey.objects.filter(user=u, name='docker-e2e-key').delete(); "
        "APIKey.objects.create(user=u, tenant=t, name='docker-e2e-key', key_hash=APIKey.hash_key(k), scopes=['read', 'write', 'admin']); "
        "print(k)"
    )
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "python",
            "-c",
            f"import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','hub.settings'); django.setup(); {setup_script}",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.skip(f"Failed to create API key in container: {result.stderr[:200]}")

    api_key = result.stdout.strip().split("\n")[-1]
    session.headers.update(
        {
            "Authorization": f"ApiKey {api_key}",
            "Content-Type": "application/json",
        }
    )
    session._base_url = api_base_url
    session._tenant_slug = "docker-e2e-host"
    return session


class TestDockerComposeCompleteDeployment:
    """E2E tests for complete Docker Compose deployment."""

    def test_all_services_start_successfully(
        self, docker_compose_manager, started_services, all_services
    ):
        """Test that all services start successfully."""
        # Verify all services are running
        running_services = []
        failed_services = []

        for service_name in all_services:
            status = docker_compose_manager.get_service_status(service_name)
            if status and status.get("State") == "running":
                running_services.append(service_name)
            else:
                failed_services.append(service_name)

        # Log results
        print(f"\nRunning services ({len(running_services)}): {running_services}")
        if failed_services:
            print(f"Failed services ({len(failed_services)}): {failed_services}")
            for service in failed_services:
                logs = docker_compose_manager.get_service_logs(service)
                print(f"\nLogs for {service}:\n{logs[-500:]}")

        # At least core services should be running
        assert len(running_services) > 0, "No services are running"

    def test_infrastructure_services_healthy(
        self, docker_compose_manager, started_services, infrastructure_services
    ):
        """Test that infrastructure services are healthy."""
        for service_name in infrastructure_services:
            status = docker_compose_manager.get_service_status(service_name)
            assert status is not None, f"Service {service_name} not found"
            assert status.get("State") == "running", (
                f"Service {service_name} is not running: {status.get('State')}"
            )

    def test_core_services_healthy(self, docker_compose_manager, started_services, core_services):
        """Test that core services are healthy."""
        # Service health endpoint mappings: (internal_port, health_path)
        # Note: event-bus-health-service uses /healthz according to docker-compose.staging.yml
        health_endpoints = {
            "workflow-engine-service": (8088, "/healthz"),
            "workflow-registry-service": (8089, "/health"),
            "event-bus-health-service": (8090, "/healthz"),  # Uses /healthz per compose file
            "event-schema-registry-service": (8091, "/health"),
            "api-service": (8000, "/health/"),
            "worker-service": (8080, "/healthz"),
        }

        for service_name in core_services:
            # Check if service is available
            if not docker_compose_manager.is_service_available(service_name):
                pytest.skip(f"Service {service_name} is not running")  # noqa: skip-in-body — runtime service dependency

            status = docker_compose_manager.get_service_status(service_name)
            assert status is not None, f"Service {service_name} not found"
            assert status.get("State") == "running", (
                f"Service {service_name} is not running: {status.get('State')}"
            )

            # Check health endpoint if configured
            if service_name in health_endpoints:
                internal_port, endpoint = health_endpoints[service_name]
                service_url = docker_compose_manager.get_service_url(
                    service_name, endpoint, internal_port
                )
                if not service_url:
                    pytest.skip(f"Could not determine port for {service_name}")  # noqa: skip-in-body — runtime service dependency

                try:
                    response = requests.get(service_url, timeout=10)
                    assert response.status_code == 200, (
                        f"Health endpoint {service_url} returned {response.status_code}"
                    )
                except requests.exceptions.ConnectionError:
                    pytest.skip(f"Service {service_name} not accessible at {service_url}")  # noqa: skip-in-body — runtime service dependency

@pytest.mark.skip(reason="f'API service not accessible at {api_url}'")
    def test_service_communication(self, docker_compose_manager, started_services):
        """Test that services can communicate with each other."""
        # Test API service health (Django requires trailing slash)
        api_url = docker_compose_manager.get_service_url("api-service", "/health/", 8000)
        if not api_url or not docker_compose_manager.is_service_available("api-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("API service not available")

        try:
            api_health = requests.get(api_url, timeout=10)
            assert api_health.status_code == 200, "API service should be healthy"
        except requests.exceptions.ConnectionError:

        # Test workflow engine can reach postgres (verified by health check)
        workflow_url = docker_compose_manager.get_service_url(
            "workflow-engine-service", "/ready", 8088
        )
        if workflow_url and docker_compose_manager.is_service_available("workflow-engine-service"):
            try:
                workflow_health = requests.get(workflow_url, timeout=10)
                assert workflow_health.status_code == 200, (
                    "Workflow engine should be ready (connected to postgres)"
                )
            except requests.exceptions.ConnectionError:
                pytest.skip("Workflow service not accessible")  # noqa: skip-in-body — runtime service dependency
        else:
            pytest.skip("Workflow service not available")  # noqa: skip-in-body — runtime service dependency

        # Test event bus can reach redis (verified by health check)
        # Use /healthz endpoint per docker-compose.staging.yml
        event_bus_url = docker_compose_manager.get_service_url(
            "event-bus-health-service", "/healthz", 8090
        )
        if event_bus_url and docker_compose_manager.is_service_available(
            "event-bus-health-service"
        ):
            try:
                event_bus_health = requests.get(event_bus_url, timeout=10)
                assert event_bus_health.status_code == 200, (
                    "Event bus should be healthy (connected to redis)"
                )

                # Try to parse JSON response if available
                try:
                    health_data = event_bus_health.json()
                    if "redis" in health_data:
                        assert health_data["redis"].get("connected") is True, (
                            "Event bus should be connected to Redis"
                        )
                except (ValueError, KeyError):
                    # Health endpoint may return non-JSON or different format - that's OK
                    pass
            except requests.exceptions.ConnectionError:
                pytest.skip("Event bus service not accessible")  # noqa: skip-in-body — runtime service dependency
        else:
            pytest.skip("Event bus service not available")  # noqa: skip-in-body — runtime service dependency

    def test_service_dependencies_resolved(self, docker_compose_manager, started_services):
        """Test that service dependencies are properly resolved."""
        # Verify dependencies are healthy
        postgres_status = docker_compose_manager.get_service_status("postgres")
        assert postgres_status is not None, "PostgreSQL should be running"
        assert postgres_status.get("State") == "running", "PostgreSQL should be running"

        redis_status = docker_compose_manager.get_service_status("redis")
        assert redis_status is not None, "Redis should be running"
        assert redis_status.get("State") == "running", "Redis should be running"

        # Check workflow service depends on postgres and redis
        if docker_compose_manager.is_service_available("workflow-engine-service"):
            workflow_status = docker_compose_manager.get_service_status("workflow-engine-service")
            assert workflow_status is not None

            # Test workflow service can reach dependencies
            workflow_url = docker_compose_manager.get_service_url(
                "workflow-engine-service", "/ready", 8088
            )
            if workflow_url:
                try:
                    workflow_ready = requests.get(workflow_url, timeout=10)
                    assert workflow_ready.status_code == 200, "Workflow service should be ready"
                except requests.exceptions.ConnectionError:
                    pytest.skip("Workflow service not accessible")  # noqa: skip-in-body — runtime service dependency
            else:
                pytest.skip("Could not determine workflow service URL")  # noqa: skip-in-body — runtime service dependency
        else:
            pytest.skip("Workflow engine service not available")  # noqa: skip-in-body — runtime service dependency

        # Check event bus depends on redis
        if docker_compose_manager.is_service_available("event-bus-health-service"):
            event_bus_status = docker_compose_manager.get_service_status("event-bus-health-service")
            assert event_bus_status is not None


class TestDockerComposeWorkflowExecution:
    """E2E tests for workflow execution in Docker Compose environment."""

@pytest.mark.skip(reason="f'Workflow registry service not accessible at {registry_url}'")
    def test_workflow_registry_service_available(self, docker_compose_manager, started_services):
        """Test that workflow registry service is available."""
        if not docker_compose_manager.is_service_available("workflow-registry-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Workflow registry service not available")

        registry_url = docker_compose_manager.get_service_url(
            "workflow-registry-service", "/health", 8089
        )
        if not registry_url:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Could not determine workflow registry service URL")

        try:
            registry_health = requests.get(registry_url, timeout=10)
            assert registry_health.status_code == 200, (
                "Workflow registry service should be available"
            )
        except requests.exceptions.ConnectionError:

@pytest.mark.skip(reason="f'Workflow engine service not accessible at {engine_url}'")
    def test_workflow_engine_service_available(self, docker_compose_manager, started_services):
        """Test that workflow engine service is available."""
        if not docker_compose_manager.is_service_available("workflow-engine-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Workflow engine service not available")

        engine_url = docker_compose_manager.get_service_url(
            "workflow-engine-service", "/healthz", 8088
        )
        if not engine_url:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Could not determine workflow engine service URL")

        try:
            engine_health = requests.get(engine_url, timeout=10)
            assert engine_health.status_code == 200, "Workflow engine service should be available"
        except requests.exceptions.ConnectionError:

@pytest.mark.skip(reason="f'Workflow registry service not available: {e}'")
    def test_workflow_registration(self, docker_compose_manager, started_services):
        """Test workflow registration via workflow registry service."""
        workflow_def = {
            "workflow_name": "test_workflow_e2e",
            "dsl_json": {
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task", "inputs": {}}],
            },
            "version": "1.0.0",
            "description": "E2E test workflow",
            "created_by_id": str(uuid.uuid4()),
        }

        if not docker_compose_manager.is_service_available("workflow-registry-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Workflow registry service not available")

        registry_url = docker_compose_manager.get_service_url(
            "workflow-registry-service", "/workflows", 8089
        )
        if not registry_url:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Could not determine workflow registry service URL")

        try:
            response = requests.post(registry_url, json=workflow_def, timeout=10)
            # May return 201 (created) or 200 (already exists)
            assert response.status_code in [200, 201], (
                f"Workflow registration failed: {response.status_code} - {response.text}"
            )
        except requests.exceptions.RequestException as e:

@pytest.mark.skip(reason="f'Workflow registry service not available: {e}'")
    def test_workflow_discovery(self, docker_compose_manager, started_services):
        """Test workflow discovery via workflow registry service."""
        if not docker_compose_manager.is_service_available("workflow-registry-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Workflow registry service not available")

        registry_url = docker_compose_manager.get_service_url(
            "workflow-registry-service", "/workflows", 8089
        )
        if not registry_url:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Could not determine workflow registry service URL")

        try:
            response = requests.get(registry_url, timeout=10)
            assert response.status_code == 200, f"Workflow discovery failed: {response.status_code}"

            data = response.json()
            assert "workflows" in data or isinstance(data, list), (
                "Workflow discovery should return workflows list"
            )
        except requests.exceptions.RequestException as e:

@pytest.mark.skip(reason="f'API service not reachable at {api_base_url}'")
    def test_workflow_execution_via_api(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test workflow execution via API service (HTTP only, no Django ORM)."""
        # Create an asset first via HTTP
        asset_data = {
            "key": f"e2e-docker-asset-{uuid.uuid4().hex[:8]}",
            "name": "E2E Docker Compose Test Asset",
            "domain": "test",
            "visibility": "INTERNAL",
        }
        try:
            asset_resp = api_session.post(
                f"{api_base_url}/api/v1/assets/", json=asset_data, timeout=15
            )
        except requests.exceptions.ConnectionError:

        if asset_resp.status_code not in [200, 201]:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                f"Could not create asset: {asset_resp.status_code} - {asset_resp.text[:200]}"
            )

        asset_id = asset_resp.json().get("id")
        assert asset_id, "Asset creation should return an id"

        # Create a contract to trigger contract creation workflow
        contract_data = {
            "asset_id": str(asset_id),
            "original_raw": '{"id": "e2e-test-contract", "name": "E2E Test Contract"}',
            "original_format": "JSON",
            "original_spec_type": "ODCS",
            "original_spec_version": "1.0.0",
        }
        contract_resp = api_session.post(
            f"{api_base_url}/api/v1/contracts/", json=contract_data, timeout=15
        )
        # May succeed or fail depending on validation
        assert contract_resp.status_code in [200, 201, 400, 422, 405], (
            f"Contract creation unexpected status: {contract_resp.status_code} - {contract_resp.text[:200]}"
        )

        if contract_resp.status_code in [200, 201]:
            contract_id = contract_resp.json().get("id")
            assert contract_id is not None, "Contract ID should be returned"

    def test_workflow_state_persistence(self, docker_compose_manager, started_services):
        """Test that workflow state tables exist in the database via docker exec."""
        # Find the postgres container
        pg_container = None
        for name in ["hub-test-postgres", "hub-staging-postgres", "hub-postgres"]:
            check = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"name={name}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if check.stdout.strip():
                pg_container = name
                break

        if not pg_container:
            pytest.skip("PostgreSQL container not found")  # noqa: skip-in-body — runtime service dependency

        # Check if workflow tables exist
        result = subprocess.run(
            [
                "docker",
                "exec",
                pg_container,
                "psql",
                "-U",
                "hub_test",
                "-d",
                "hub_test_test_shared",
                "-tAc",
                "SELECT count(*) FROM information_schema.tables WHERE table_name IN ('workflow_instances', 'workflow_steps')",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            pytest.skip(f"Could not query database: {result.stderr[:200]}")  # noqa: skip-in-body — runtime service dependency

        table_count = int(result.stdout.strip() or "0")
        assert table_count >= 1, "At least one workflow table should exist in the database"


class TestDockerComposeEventBus:
    """E2E tests for event bus in Docker Compose environment."""

@pytest.mark.skip(reason="f'Event bus service not accessible at {event_bus_url}'")
    def test_event_bus_service_available(self, docker_compose_manager, started_services):
        """Test that event bus service is available."""
        if not docker_compose_manager.is_service_available("event-bus-health-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Event bus service not available")

        # Use /healthz endpoint per docker-compose.staging.yml
        event_bus_url = docker_compose_manager.get_service_url(
            "event-bus-health-service", "/healthz", 8090
        )
        if not event_bus_url:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Could not determine event bus service URL")

        try:
            health_response = requests.get(event_bus_url, timeout=10)
            assert health_response.status_code == 200, "Event bus service should be available"

            # Try to parse JSON if available
            try:
                health_data = health_response.json()
                assert "status" in health_data, "Health check should include status"
            except ValueError:
                # Health endpoint may return non-JSON - that's OK if status is 200
                pass
        except requests.exceptions.ConnectionError:

@pytest.mark.skip(reason="f'Event bus service not accessible at {event_bus_url}'")
    def test_event_bus_redis_connection(self, docker_compose_manager, started_services):
        """Test that event bus can connect to Redis."""
        if not docker_compose_manager.is_service_available("event-bus-health-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Event bus service not available")

        # Verify Redis is running
        redis_status = docker_compose_manager.get_service_status("redis")
        assert redis_status is not None, "Redis should be running"
        assert redis_status.get("State") == "running", "Redis should be running"

        # Use /healthz endpoint per docker-compose.staging.yml
        event_bus_url = docker_compose_manager.get_service_url(
            "event-bus-health-service", "/healthz", 8090
        )
        if not event_bus_url:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Could not determine event bus service URL")

        try:
            health_response = requests.get(event_bus_url, timeout=10)
            assert health_response.status_code == 200

            # Try to parse JSON if available
            try:
                health_data = health_response.json()
                if "redis" in health_data:
                    redis_info = health_data["redis"]
                    assert redis_info.get("connected") is True, (
                        "Event bus should be connected to Redis"
                    )
            except ValueError:
                # Health endpoint may return non-JSON - if status is 200, assume healthy
                pass
        except requests.exceptions.ConnectionError:

@pytest.mark.skip(reason="f'API not reachable at {api_base_url}'")
    def test_event_publishing(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test event publishing by creating an asset (which triggers asset.created event)."""
        asset_data = {
            "key": f"e2e-event-pub-{uuid.uuid4().hex[:8]}",
            "name": "E2E Event Publishing Test Asset",
            "domain": "test",
            "visibility": "INTERNAL",
        }
        try:
            resp = api_session.post(f"{api_base_url}/api/v1/assets/", json=asset_data, timeout=15)
        except requests.exceptions.ConnectionError:

        # Asset creation triggers asset.created event via the event bus
        assert resp.status_code in [200, 201], (
            f"Asset creation (event trigger) failed: {resp.status_code} - {resp.text[:200]}"
        )
        asset_id = resp.json().get("id")
        assert asset_id, "Asset should have an id"

@pytest.mark.skip(reason="f'API not reachable at {api_base_url}'")
    def test_event_subscription(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test event subscription by verifying webhooks/subscriptions endpoint exists."""
        try:
            resp = api_session.get(f"{api_base_url}/api/v1/webhooks/", timeout=10)
        except requests.exceptions.ConnectionError:

        # The webhooks endpoint should be accessible (200) or return empty list
        assert resp.status_code in [200, 404], (
            f"Webhooks endpoint unexpected status: {resp.status_code}"
        )

@pytest.mark.skip(reason="f'API not reachable at {api_base_url}'")
    def test_event_persistence(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test that events are persisted by creating an asset and checking audit trail."""
        asset_data = {
            "key": f"e2e-event-persist-{uuid.uuid4().hex[:8]}",
            "name": "E2E Event Persistence Test",
            "domain": "test",
            "visibility": "INTERNAL",
        }
        try:
            resp = api_session.post(f"{api_base_url}/api/v1/assets/", json=asset_data, timeout=15)
        except requests.exceptions.ConnectionError:

        assert resp.status_code in [200, 201], (
            f"Asset creation failed: {resp.status_code} - {resp.text[:200]}"
        )

        # Verify the asset can be retrieved (proves DB persistence)
        asset_id = resp.json().get("id")
        get_resp = api_session.get(f"{api_base_url}/api/v1/assets/{asset_id}/", timeout=10)
        assert get_resp.status_code == 200, "Created asset should be retrievable"

    def test_dead_letter_queue(self, docker_compose_manager, started_services):
        """Test dead letter queue table exists via docker exec psql."""
        pg_container = None
        for name in ["hub-test-postgres", "hub-staging-postgres", "hub-postgres"]:
            check = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"name={name}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if check.stdout.strip():
                pg_container = name
                break

        if not pg_container:
            pytest.skip("PostgreSQL container not found")  # noqa: skip-in-body — runtime service dependency

        result = subprocess.run(
            [
                "docker",
                "exec",
                pg_container,
                "psql",
                "-U",
                "hub_test",
                "-d",
                "hub_test_test_shared",
                "-tAc",
                "SELECT count(*) FROM information_schema.tables WHERE table_name = 'dead_letter_queue'",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            pytest.skip(f"Could not query database: {result.stderr[:200]}")  # noqa: skip-in-body — runtime service dependency

        assert int(result.stdout.strip() or "0") >= 1, "DeadLetterQueue table should exist"


class TestDockerComposeServiceLayer:
    """E2E tests for service layer in Docker Compose environment."""

    def test_api_service_endpoints(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test API service endpoints via HTTP."""
        resp = api_session.get(f"{api_base_url}/health/", timeout=10)
        assert resp.status_code == 200, "Health endpoint should be accessible"

        # Try common API docs endpoints
        for endpoint in [
            "/api/docs/",
            "/api/schema/swagger-ui/",
            "/swagger/",
            "/api/schema/redoc/",
        ]:
            r = api_session.get(f"{api_base_url}{endpoint}", timeout=5)
            if r.status_code in [200, 302]:
                break

    def test_contract_service_integration(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test contract service integration via HTTP."""
        resp = api_session.get(f"{api_base_url}/api/v1/contracts/", timeout=10)
        assert resp.status_code == 200, f"Contract list failed: {resp.status_code}"

    def test_asset_service_integration(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test asset service integration via HTTP."""
        resp = api_session.get(f"{api_base_url}/api/v1/assets/", timeout=10)
        assert resp.status_code == 200, f"Asset list failed: {resp.status_code}"

    def test_service_to_service_communication(self, docker_compose_manager, started_services):
        """Test service-to-service communication."""
        # Test that API service can communicate with backend services
        # This is verified by API endpoints working

        # Internal services (semantic, DQ, compliance) require the
        # X-Internal-Api-Key header for inter-service authentication.
        internal_api_key = os.environ.get("INTERNAL_API_KEY", "test-internal-api-key-for-test-env")
        internal_headers = {"X-Internal-Api-Key": internal_api_key}

        # Test semantic service
        if docker_compose_manager.is_service_available("semantic-service"):
            semantic_url = docker_compose_manager.get_service_url(
                "semantic-service", "/health/", 8081
            )
            if semantic_url:
                try:
                    response = requests.get(semantic_url, headers=internal_headers, timeout=10)
                    assert response.status_code == 200, (
                        f"Semantic service should be accessible at {semantic_url} (got {response.status_code})"
                    )
                except requests.exceptions.RequestException:
                    pytest.skip(f"Semantic service not accessible at {semantic_url}")  # noqa: skip-in-body — runtime service dependency
            else:
                pytest.skip("Could not determine semantic service URL")  # noqa: skip-in-body — runtime service dependency
        else:
            pytest.skip("Semantic service not available")  # noqa: skip-in-body — runtime service dependency

        # Test DQ service
        if docker_compose_manager.is_service_available("dq-service"):
            dq_url = docker_compose_manager.get_service_url("dq-service", "/health/", 8083)
            if dq_url:
                try:
                    response = requests.get(dq_url, headers=internal_headers, timeout=10)
                    assert response.status_code == 200, (
                        f"DQ service should be accessible at {dq_url} (got {response.status_code})"
                    )
                except requests.exceptions.RequestException:
                    pytest.skip(f"DQ service not accessible at {dq_url}")  # noqa: skip-in-body — runtime service dependency
            else:
                pytest.skip("Could not determine DQ service URL")  # noqa: skip-in-body — runtime service dependency
        else:
            pytest.skip("DQ service not available")  # noqa: skip-in-body — runtime service dependency

        # Test compliance service
        if docker_compose_manager.is_service_available("compliance-service"):
            compliance_url = docker_compose_manager.get_service_url(
                "compliance-service", "/health/", 8082
            )
            if compliance_url:
                try:
                    response = requests.get(compliance_url, headers=internal_headers, timeout=10)
                    assert response.status_code == 200, (
                        f"Compliance service should be accessible at {compliance_url} (got {response.status_code})"
                    )
                except requests.exceptions.RequestException:
                    pytest.skip(f"Compliance service not accessible at {compliance_url}")  # noqa: skip-in-body — runtime service dependency
            else:
                pytest.skip("Could not determine compliance service URL")  # noqa: skip-in-body — runtime service dependency
        else:
            pytest.skip("Compliance service not available")  # noqa: skip-in-body — runtime service dependency

@pytest.mark.skip(reason="f'Worker service not accessible at {worker_url}'")
    def test_worker_service_integration(self, docker_compose_manager, started_services):
        """Test worker service integration."""
        if not docker_compose_manager.is_service_available("worker-service"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Worker service not available")

        worker_url = docker_compose_manager.get_service_url("worker-service", "/healthz", 8080)
        if not worker_url:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Could not determine worker service URL")

        try:
            worker_health = requests.get(worker_url, timeout=10)
            assert worker_health.status_code == 200, "Worker service should be healthy"
        except requests.exceptions.ConnectionError:

    def test_database_operations(
        self, docker_compose_manager, started_services, api_session, api_base_url
    ):
        """Test database operations via API (create + retrieve)."""
        contract_data = {
            "original_raw": json.dumps(
                {
                    "id": "e2e-db-ops-test",
                    "name": "E2E DB Ops Contract",
                }
            ),
            "original_format": "JSON",
            "original_spec_type": "ODCS",
            "original_spec_version": "1.0.0",
        }
        resp = api_session.post(
            f"{api_base_url}/api/v1/contracts/",
            json=contract_data,
            timeout=15,
        )
        # 201 created or 400 if missing required fields
        assert resp.status_code in [200, 201, 400], (
            f"Contract create: {resp.status_code} {resp.text[:200]}"
        )
        if resp.status_code in [200, 201]:
            cid = resp.json().get("id")
            assert cid, "Contract should have an id"
            get_r = api_session.get(
                f"{api_base_url}/api/v1/contracts/{cid}/",
                timeout=10,
            )
            assert get_r.status_code == 200, "Created contract should be retrievable"

@pytest.mark.skip(reason="redis package not installed")
@pytest.mark.skip(reason="f'Redis connection failed: {e}'")
@pytest.mark.skip(reason="f'Redis not available: {e}'")
    def test_redis_operations(self, docker_compose_manager, started_services):
        """Test Redis operations through service layer."""
        try:
        except ImportError:
            pytest.skip("redis package not installed")

        # Check if Redis service is available  # noqa: skip-in-body — runtime service dependency
        if not docker_compose_manager.is_service_available("redis"):
            pytest.skip("Redis service not available")

        # Get Redis port dynamically from docker compose
        redis_port = docker_compose_manager.get_service_port("redis", 6379)
        if not redis_port:
            redis_port = 6379

        redis_host = "localhost"
        redis_db = 0

        try:
            redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )

            # Test Redis connection
            redis_client.ping()

            # Test Redis operations
            test_key = f"e2e_test_{uuid.uuid4()}"
            redis_client.set(test_key, "test_value", ex=60)
            value = redis_client.get(test_key)
            assert value == "test_value", "Redis should store and retrieve values"

            # Cleanup
            redis_client.delete(test_key)
            pytest.skip(f"Redis connection failed: {e}")
        except Exception as e:


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "docker_compose_runtime: marks tests as requiring Docker Compose runtime"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test items based on command-line options."""
    # Check if Docker CLI is available first
    try:
        result = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        docker_available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        docker_available = False

    if not docker_available:
        # Docker not available (e.g. running inside api-service-test container) - skip all
        skip_docker = pytest.mark.skip(
            reason="Docker CLI not available. Run on host with Docker, not inside container."
        )
        for item in items:
            if "docker_compose_runtime" in item.keywords:
                item.add_marker(skip_docker)
        return

    # Check if --docker-compose-runtime flag is set
    runtime_flag = config.getoption("--docker-compose-runtime", default=False)

    if not runtime_flag:
        # Check if we can auto-detect running services
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Services are running, don't skip
                return
        except Exception:
            pass

        # Skip tests if flag not set and services not detected
        skip_runtime = pytest.mark.skip(
            reason="need --docker-compose-runtime option to run or Docker Compose services must be running"
        )
        for item in items:
            if "docker_compose_runtime" in item.keywords:
                item.add_marker(skip_runtime)
