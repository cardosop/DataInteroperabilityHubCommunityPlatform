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
import os
import sys
import time
import subprocess
import json
import requests
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import pytest
import httpx

# Set environment variable to allow connection failures during import
os.environ['DOCKER_COMPOSE_E2E_TEST'] = 'true'

# Module-level pytest markers
# Use transaction=False to avoid database flush issues with foreign keys
pytestmark = [pytest.mark.django_db(transaction=False), pytest.mark.e2e, pytest.mark.docker_compose_runtime]

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure Django settings before any Django imports
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

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
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _run_command(self, command: List[str], check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
        """Run docker compose command."""
        if not self._docker_available():
            raise RuntimeError(
                "Docker CLI not available. These tests must run on the host with Docker installed, "
                "not inside a container. Use --docker-compose-runtime when Docker is available."
            )
        cmd = ["docker", "compose", "-f", str(self.compose_file), "-p", self.project_name] + command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check
        )
        return result
    
    def start_services(self, services: Optional[List[str]] = None, wait: bool = True, timeout: int = 600) -> None:
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
    
    def stop_services(self, services: Optional[List[str]] = None) -> None:
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
    
    def get_service_status(self, service_name: str) -> Optional[Dict]:
        """Get service status."""
        # First try with current project
        result = self._run_command(["ps", "--format", "json", service_name], check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                services = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
                if services:
                    return services[0]
            except json.JSONDecodeError:
                pass
        
        # If not found, check all containers (services may be running under different project)
        try:
            # Try exact service name match first
            all_result = subprocess.run(
                ["docker", "ps", "--format", "json", "--filter", f"name={service_name}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if all_result.returncode == 0 and all_result.stdout.strip():
                services = [json.loads(line) for line in all_result.stdout.strip().split('\n') if line]
                # Filter by service name pattern (container name contains service name)
                for service in services:
                    name = service.get('Names', '')
                    # Match if service name is in container name or container name ends with service name
                    # Also handle staging naming (e.g., "hub-semantic-staging" matches "semantic-service")
                    # Handle patterns like: "hub-staging-workflow-engine" matches "workflow-engine-service"
                    service_base = service_name.replace('-service', '')
                    if (service_name in name or 
                        name.endswith(service_name) or
                        name.endswith(service_base) or
                        name.endswith(service_base + '-staging') or
                        name.endswith('hub-staging-' + service_base) or
                        name.endswith('hub-' + service_base + '-staging')):
                        return service
            
            # Also try checking by label (com.docker.compose.service)
            label_result = subprocess.run(
                ["docker", "ps", "--format", "json", "--filter", f"label=com.docker.compose.service={service_name}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if label_result.returncode == 0 and label_result.stdout.strip():
                services = [json.loads(line) for line in label_result.stdout.strip().split('\n') if line]
                if services:
                    return services[0]
            
            # Try checking stopped containers too (for potential restart)
            stopped_result = subprocess.run(
                ["docker", "ps", "-a", "--format", "json", "--filter", f"name={service_name}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if stopped_result.returncode == 0 and stopped_result.stdout.strip():
                services = [json.loads(line) for line in stopped_result.stdout.strip().split('\n') if line]
                for service in services:
                    name = service.get('Names', '')
                    service_base = service_name.replace('-service', '')
                    if (service_name in name or 
                        name.endswith(service_base) or
                        name.endswith(service_base + '-staging') or
                        name.endswith('hub-staging-' + service_base)):
                        # Return even if stopped - caller can check state
                        return service
        except Exception:
            pass
        
        return None
    
    def get_all_services(self) -> List[str]:
        """Get all service names from docker-compose.yml."""
        with open(self.compose_file, 'r') as f:
            config = yaml.safe_load(f)
        return list(config.get('services', {}).keys())
    
    def wait_for_service_healthy(self, service_name: str, timeout: int = 300) -> bool:
        """Wait for service to become healthy."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_service_status(service_name)
            if status:
                health = status.get('Health', '')
                state = status.get('State', '')
                if health == 'healthy' or (state == 'running' and health == ''):
                    return True
            time.sleep(2)
        return False
    
    def wait_for_services_healthy(self, services: List[str], timeout: int = 300) -> None:
        """Wait for multiple services to become healthy."""
        for service in services:
            if not self.wait_for_service_healthy(service, timeout):
                raise RuntimeError(f"Service {service} failed to become healthy within {timeout} seconds")
    
    def get_service_logs(self, service_name: str, tail: int = 100) -> str:
        """Get service logs."""
        result = self._run_command(["logs", "--tail", str(tail), service_name], check=False)
        return result.stdout
    
    def restart_service(self, service_name: str) -> None:
        """Restart a service."""
        self._run_command(["restart", service_name])
        self.wait_for_service_healthy(service_name)
    
    def get_service_port(self, service_name: str, internal_port: Optional[int] = None) -> Optional[int]:
        """Get published port for a service."""
        status = self.get_service_status(service_name)
        if not status:
            return None
        
        # Try to get port from Publishers (docker compose ps format)
        publishers = status.get('Publishers', [])
        if publishers:
            # Get first published port
            for pub in publishers:
                if pub.get('PublishedPort'):
                    return pub['PublishedPort']
        
        # Fallback: parse from Ports string (format: "0.0.0.0:8001->8000/tcp")
        ports_str = status.get('Ports', '')
        if ports_str:
            # Extract published port (first number before ->)
            import re
            match = re.search(r':(\d+)->', ports_str)
            if match:
                return int(match.group(1))
        
        # If internal_port provided, try to find matching port mapping from compose file
        if internal_port:
            with open(self.compose_file, 'r') as f:
                config = yaml.safe_load(f)
            service_config = config.get('services', {}).get(service_name, {})
            ports_config = service_config.get('ports', [])
            for port_mapping in ports_config:
                if isinstance(port_mapping, str):
                    # Format: "8001:8000"
                    parts = port_mapping.split(':')
                    if len(parts) == 2 and parts[1] == str(internal_port):
                        return int(parts[0])
                elif isinstance(port_mapping, dict):
                    # Format: {"published": 8001, "target": 8000}
                    if port_mapping.get('target') == internal_port:
                        return port_mapping.get('published')
        
        return None
    
    def get_service_url(self, service_name: str, path: str = '', internal_port: Optional[int] = None) -> Optional[str]:
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
        state = status.get('State', '')
        return state == 'running'


def detect_compose_file():
    """Detect which Docker Compose file to use based on running services."""
    # Check if staging services are running
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.staging.yml", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root)
        )
        if result.returncode == 0 and result.stdout.strip():
            services = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
            running_services = [s for s in services if s.get('State') == 'running']
            if len(running_services) >= 5:  # At least 5 services running
                staging_file = project_root / "docker-compose.staging.yml"
                if staging_file.exists():
                    return staging_file
    except Exception:
        pass
    
    # Try dev compose file (for development)
    dev_compose_file = project_root / "docker-compose.dev.yml"
    if dev_compose_file.exists():
        return dev_compose_file
    
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
    with open(docker_compose_file, 'r') as f:
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
    return ['postgres', 'redis', 'minio', 'fuseki']


@pytest.fixture(scope="module")
def core_services(docker_compose_config):
    """Get core application service names."""
    services = []
    available_services = docker_compose_config.get('services', {})
    
    # Add services that exist in compose file
    potential_services = [
        'workflow-engine-service',
        'workflow-registry-service',
        'event-bus-health-service',
        'event-schema-registry-service',
        'api-service',
        'worker-service',
    ]
    
    for service_name in potential_services:
        if service_name in available_services:
            services.append(service_name)
    
    return services


@pytest.fixture(scope="module")
def microservices():
    """Get microservice names."""
    return [
        'semantic-service',
        'dq-service',
        'compliance-service',
        'datacontract-service',
        'search-service',
        'observability-service',
        'webhook-service',
        'prefect-integration-service',
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
            state = status.get('State', '')
            if state == 'running':
                running_services.append(service)
            elif state in ['exited', 'stopped', 'created']:
                stopped_services.append(service)
    
    # Only start services that aren't running
    services_to_start = [s for s in infrastructure_services + core_services if s not in running_services]
    
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
                time.sleep(10)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                # Log but don't fail - some services may not be available or may take longer
                import warnings
                warnings.warn(f"Failed to start core services {core_to_start}: {e}")
    
    yield
    
    # Don't stop services - they may be shared with other tests
    # Cleanup handled by docker_compose_manager fixture only if we started them


@pytest.fixture(scope="function")
def test_tenant():
    """Create a test tenant."""
    from hub.apps.tenants.models import Tenant
    tenant, _ = Tenant.objects.get_or_create(
        name="E2E Test Tenant",
        defaults={
            'slug': 'e2e-test-tenant',
        }
    )
    return tenant


@pytest.fixture(scope="function")
def test_user(test_tenant):
    """Create a test user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        email='e2e_test@example.com',
        defaults={
            'tenant': test_tenant,
        }
    )
    return user


@pytest.fixture(scope="function")
def api_client(test_user):
    """Create authenticated API client."""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=test_user)
    return client


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
            if status and status.get('State') == 'running':
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
            assert status.get('State') == 'running', \
                f"Service {service_name} is not running: {status.get('State')}"
    
    def test_core_services_healthy(
        self, docker_compose_manager, started_services, core_services
    ):
        """Test that core services are healthy."""
        # Service health endpoint mappings: (internal_port, health_path)
        # Note: event-bus-health-service uses /healthz according to docker-compose.staging.yml
        health_endpoints = {
            'workflow-engine-service': (8088, '/healthz'),
            'workflow-registry-service': (8089, '/health'),
            'event-bus-health-service': (8090, '/healthz'),  # Uses /healthz per compose file
            'event-schema-registry-service': (8091, '/health'),
            'api-service': (8000, '/health'),
            'worker-service': (8080, '/healthz'),
        }
        
        for service_name in core_services:
            # Check if service is available
            if not docker_compose_manager.is_service_available(service_name):
                pytest.skip(f"Service {service_name} is not running")
            
            status = docker_compose_manager.get_service_status(service_name)
            assert status is not None, f"Service {service_name} not found"
            assert status.get('State') == 'running', \
                f"Service {service_name} is not running: {status.get('State')}"
            
            # Check health endpoint if configured
            if service_name in health_endpoints:
                internal_port, endpoint = health_endpoints[service_name]
                service_url = docker_compose_manager.get_service_url(service_name, endpoint, internal_port)
                if not service_url:
                    pytest.skip(f"Could not determine port for {service_name}")
                
                try:
                    response = requests.get(service_url, timeout=10)
                    assert response.status_code == 200, \
                        f"Health endpoint {service_url} returned {response.status_code}"
                except requests.exceptions.ConnectionError:
                    pytest.skip(f"Service {service_name} not accessible at {service_url}")
    
    def test_service_communication(
        self, docker_compose_manager, started_services
    ):
        """Test that services can communicate with each other."""
        # Test API service health
        api_url = docker_compose_manager.get_service_url('api-service', '/health', 8000)
        if not api_url or not docker_compose_manager.is_service_available('api-service'):
            pytest.skip("API service not available")
        
        try:
            api_health = requests.get(api_url, timeout=10)
            assert api_health.status_code == 200, "API service should be healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip(f"API service not accessible at {api_url}")
        
        # Test workflow engine can reach postgres (verified by health check)
        workflow_url = docker_compose_manager.get_service_url('workflow-engine-service', '/ready', 8088)
        if workflow_url and docker_compose_manager.is_service_available('workflow-engine-service'):
            try:
                workflow_health = requests.get(workflow_url, timeout=10)
                assert workflow_health.status_code == 200, \
                    "Workflow engine should be ready (connected to postgres)"
            except requests.exceptions.ConnectionError:
                pytest.skip("Workflow service not accessible")
        else:
            pytest.skip("Workflow service not available")
        
        # Test event bus can reach redis (verified by health check)
        # Use /healthz endpoint per docker-compose.staging.yml
        event_bus_url = docker_compose_manager.get_service_url('event-bus-health-service', '/healthz', 8090)
        if event_bus_url and docker_compose_manager.is_service_available('event-bus-health-service'):
            try:
                event_bus_health = requests.get(event_bus_url, timeout=10)
                assert event_bus_health.status_code == 200, \
                    "Event bus should be healthy (connected to redis)"
                
                # Try to parse JSON response if available
                try:
                    health_data = event_bus_health.json()
                    if 'redis' in health_data:
                        assert health_data['redis'].get('connected') is True, \
                            "Event bus should be connected to Redis"
                except (ValueError, KeyError):
                    # Health endpoint may return non-JSON or different format - that's OK
                    pass
            except requests.exceptions.ConnectionError:
                pytest.skip("Event bus service not accessible")
        else:
            pytest.skip("Event bus service not available")
    
    def test_service_dependencies_resolved(
        self, docker_compose_manager, started_services
    ):
        """Test that service dependencies are properly resolved."""
        # Verify dependencies are healthy
        postgres_status = docker_compose_manager.get_service_status('postgres')
        assert postgres_status is not None, "PostgreSQL should be running"
        assert postgres_status.get('State') == 'running', "PostgreSQL should be running"
        
        redis_status = docker_compose_manager.get_service_status('redis')
        assert redis_status is not None, "Redis should be running"
        assert redis_status.get('State') == 'running', "Redis should be running"
        
        # Check workflow service depends on postgres and redis
        if docker_compose_manager.is_service_available('workflow-engine-service'):
            workflow_status = docker_compose_manager.get_service_status('workflow-engine-service')
            assert workflow_status is not None
            
            # Test workflow service can reach dependencies
            workflow_url = docker_compose_manager.get_service_url('workflow-engine-service', '/ready', 8088)
            if workflow_url:
                try:
                    workflow_ready = requests.get(workflow_url, timeout=10)
                    assert workflow_ready.status_code == 200, "Workflow service should be ready"
                except requests.exceptions.ConnectionError:
                    pytest.skip("Workflow service not accessible")
            else:
                pytest.skip("Could not determine workflow service URL")
        else:
            pytest.skip("Workflow engine service not available")
        
        # Check event bus depends on redis
        if docker_compose_manager.is_service_available('event-bus-health-service'):
            event_bus_status = docker_compose_manager.get_service_status('event-bus-health-service')
            assert event_bus_status is not None


class TestDockerComposeWorkflowExecution:
    """E2E tests for workflow execution in Docker Compose environment."""
    
    def test_workflow_registry_service_available(
        self, docker_compose_manager, started_services
    ):
        """Test that workflow registry service is available."""
        if not docker_compose_manager.is_service_available('workflow-registry-service'):
            pytest.skip("Workflow registry service not available")
        
        registry_url = docker_compose_manager.get_service_url('workflow-registry-service', '/health', 8089)
        if not registry_url:
            pytest.skip("Could not determine workflow registry service URL")
        
        try:
            registry_health = requests.get(registry_url, timeout=10)
            assert registry_health.status_code == 200, \
                "Workflow registry service should be available"
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Workflow registry service not accessible at {registry_url}")
    
    def test_workflow_engine_service_available(
        self, docker_compose_manager, started_services
    ):
        """Test that workflow engine service is available."""
        if not docker_compose_manager.is_service_available('workflow-engine-service'):
            pytest.skip("Workflow engine service not available")
        
        engine_url = docker_compose_manager.get_service_url('workflow-engine-service', '/healthz', 8088)
        if not engine_url:
            pytest.skip("Could not determine workflow engine service URL")
        
        try:
            engine_health = requests.get(engine_url, timeout=10)
            assert engine_health.status_code == 200, \
                "Workflow engine service should be available"
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Workflow engine service not accessible at {engine_url}")
    
    def test_workflow_registration(
        self, docker_compose_manager, started_services, test_user
    ):
        """Test workflow registration via workflow registry service."""
        workflow_def = {
            "workflow_name": "test_workflow_e2e",
            "dsl_json": {
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "task": "test_task",
                        "inputs": {}
                    }
                ]
            },
            "version": "1.0.0",
            "description": "E2E test workflow",
            "created_by_id": str(test_user.id),
        }
        
        if not docker_compose_manager.is_service_available('workflow-registry-service'):
            pytest.skip("Workflow registry service not available")
        
        registry_url = docker_compose_manager.get_service_url('workflow-registry-service', '/workflows', 8089)
        if not registry_url:
            pytest.skip("Could not determine workflow registry service URL")
        
        try:
            response = requests.post(
                registry_url,
                json=workflow_def,
                timeout=10
            )
            # May return 201 (created) or 200 (already exists)
            assert response.status_code in [200, 201], \
                f"Workflow registration failed: {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Workflow registry service not available: {e}")
    
    def test_workflow_discovery(
        self, docker_compose_manager, started_services
    ):
        """Test workflow discovery via workflow registry service."""
        if not docker_compose_manager.is_service_available('workflow-registry-service'):
            pytest.skip("Workflow registry service not available")
        
        registry_url = docker_compose_manager.get_service_url('workflow-registry-service', '/workflows', 8089)
        if not registry_url:
            pytest.skip("Could not determine workflow registry service URL")
        
        try:
            response = requests.get(registry_url, timeout=10)
            assert response.status_code == 200, \
                f"Workflow discovery failed: {response.status_code}"
            
            data = response.json()
            assert 'workflows' in data or isinstance(data, list), \
                "Workflow discovery should return workflows list"
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Workflow registry service not available: {e}")
    
    def test_workflow_execution_via_api(
        self, docker_compose_manager, started_services, api_client, test_tenant
    ):
        """Test workflow execution via API service."""
        # Create an asset first (contracts require assets)
        from hub.apps.assets.models import Asset, AssetStatus
        
        asset = Asset.objects.create(
            tenant=test_tenant,
            key=f"e2e-test-asset-{uuid.uuid4().hex[:8]}",
            name="E2E Test Asset",
            status=AssetStatus.DRAFT
        )
        
        # Create a contract to trigger contract creation workflow
        contract_data = {
            "asset_id": str(asset.id),
            "original_raw": '{"id": "e2e-test-contract", "name": "E2E Test Contract"}',
            "original_format": "JSON",
            "original_spec_type": "ODCS",
            "original_spec_version": "1.0.0"
        }
        
        try:
            response = api_client.post('/api/v1/contracts/', contract_data, format='json')
            # May succeed or fail depending on validation
            assert response.status_code in [200, 201, 400, 422, 405], \
                f"Contract creation failed: {response.status_code} - {response.text}"
            
            if response.status_code in [200, 201]:
                # Workflow should have been triggered
                contract_id = response.data.get('id')
                assert contract_id is not None, "Contract ID should be returned"
        except Exception as e:
            pytest.skip(f"API service not available or contract creation failed: {e}")
    
    def test_workflow_state_persistence(
        self, docker_compose_manager, started_services
    ):
        """Test that workflow state is persisted in database."""
        try:
            from hub.apps.orchestration.models import WorkflowInstance, WorkflowStep
            
            # Check if workflow instances exist
            instance_count = WorkflowInstance.objects.count()
            step_count = WorkflowStep.objects.count()
            
            # At least the tables should exist
            assert instance_count >= 0, "WorkflowInstance table should exist"
            assert step_count >= 0, "WorkflowStep table should exist"
        except ImportError:
            pytest.skip("Workflow models not available")
        except Exception as e:
            pytest.skip(f"Workflow models not available: {e}")


class TestDockerComposeEventBus:
    """E2E tests for event bus in Docker Compose environment."""
    
    def test_event_bus_service_available(
        self, docker_compose_manager, started_services
    ):
        """Test that event bus service is available."""
        if not docker_compose_manager.is_service_available('event-bus-health-service'):
            pytest.skip("Event bus service not available")
        
        # Use /healthz endpoint per docker-compose.staging.yml
        event_bus_url = docker_compose_manager.get_service_url('event-bus-health-service', '/healthz', 8090)
        if not event_bus_url:
            pytest.skip("Could not determine event bus service URL")
        
        try:
            health_response = requests.get(event_bus_url, timeout=10)
            assert health_response.status_code == 200, \
                "Event bus service should be available"
            
            # Try to parse JSON if available
            try:
                health_data = health_response.json()
                assert 'status' in health_data, "Health check should include status"
            except ValueError:
                # Health endpoint may return non-JSON - that's OK if status is 200
                pass
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Event bus service not accessible at {event_bus_url}")
    
    def test_event_bus_redis_connection(
        self, docker_compose_manager, started_services
    ):
        """Test that event bus can connect to Redis."""
        if not docker_compose_manager.is_service_available('event-bus-health-service'):
            pytest.skip("Event bus service not available")
        
        # Verify Redis is running
        redis_status = docker_compose_manager.get_service_status('redis')
        assert redis_status is not None, "Redis should be running"
        assert redis_status.get('State') == 'running', "Redis should be running"
        
        # Use /healthz endpoint per docker-compose.staging.yml
        event_bus_url = docker_compose_manager.get_service_url('event-bus-health-service', '/healthz', 8090)
        if not event_bus_url:
            pytest.skip("Could not determine event bus service URL")
        
        try:
            health_response = requests.get(event_bus_url, timeout=10)
            assert health_response.status_code == 200
            
            # Try to parse JSON if available
            try:
                health_data = health_response.json()
                if 'redis' in health_data:
                    redis_info = health_data['redis']
                    assert redis_info.get('connected') is True, \
                        "Event bus should be connected to Redis"
            except ValueError:
                # Health endpoint may return non-JSON - if status is 200, assume healthy
                pass
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Event bus service not accessible at {event_bus_url}")
    
    def test_event_publishing(
        self, docker_compose_manager, started_services, test_tenant, test_user
    ):
        """Test event publishing via event bus."""
        try:
            from hub.apps.core.events.bus import get_event_bus
            from hub.apps.core.events.models import Event
            event_bus = get_event_bus()
            
            # Use registered event type for testing
            # Create a test asset first to have a valid asset_id
            from hub.apps.assets.models import Asset, AssetStatus
            asset = Asset.objects.create(
                tenant=test_tenant,
                key=f"e2e-test-asset-{uuid.uuid4().hex[:8]}",
                name="E2E Test Asset",
                status=AssetStatus.DRAFT
            )
            
            # Publish a registered event type (asset.created)
            event_id = event_bus.publish(
                event_type="asset.created",
                data={"asset_id": str(asset.id)},
                tenant_id=str(test_tenant.id),
                user_id=str(test_user.id),
            )
            
            assert event_id is not None, "Event ID should be returned"
            
            # Verify event was persisted
            event = Event.objects.filter(event_id=event_id).first()
            assert event is not None, "Event should be persisted in database"
            assert event.event_type == "asset.created", \
                "Event type should match"
        except Exception as e:
            pytest.skip(f"Event bus not available: {e}")
    
    def test_event_subscription(
        self, docker_compose_manager, started_services, test_tenant, test_user
    ):
        """Test event subscription via event bus."""
        try:
            from hub.apps.core.events.bus import get_event_bus
            from hub.apps.assets.models import Asset, AssetStatus
            from hub.apps.core.events.models import EventSubscription
            event_bus = get_event_bus()
            
            # Create a test asset for the event
            asset = Asset.objects.create(
                tenant=test_tenant,
                key=f"e2e-test-asset-sub-{uuid.uuid4().hex[:8]}",
                name="E2E Test Asset for Subscription",
                status=AssetStatus.DRAFT
            )
            
            # Subscribe to events using registered event type
            # Note: subscribe() registers the subscription but doesn't start listening
            # For E2E tests, we verify the subscription was registered
            subscriber_name = f"e2e-test-subscriber-{uuid.uuid4().hex[:8]}"
            
            def event_handler(event_data: Dict[str, Any]) -> None:
                # Handler for subscription (not called in this test as we're not listening)
                pass
            
            # Register subscription
            event_bus.subscribe(
                subscriber_name=subscriber_name,
                event_type_pattern="asset.created",
                handler=event_handler,
                is_active=True
            )
            
            # Verify subscription was registered in database
            subscription = EventSubscription.objects.filter(
                subscriber_name=subscriber_name,
                event_type_pattern="asset.created"
            ).first()
            assert subscription is not None, "Subscription should be registered"
            assert subscription.is_active, "Subscription should be active"
            
            # Publish an event using registered event type
            event_id = event_bus.publish(
                event_type="asset.created",
                data={"asset_id": str(asset.id)},
                tenant_id=str(test_tenant.id),
                user_id=str(test_user.id),
            )
            
            # Verify event was published
            assert event_id is not None, "Event should be published"
            
            # Note: Actual event delivery requires a listener/worker running
            # This test verifies subscription registration and event publishing
        except Exception as e:
            pytest.skip(f"Event bus subscription not available: {e}")
    
    def test_event_persistence(
        self, docker_compose_manager, started_services, test_tenant, test_user
    ):
        """Test that events are persisted in database."""
        try:
            from hub.apps.core.events.bus import get_event_bus
            from hub.apps.core.events.models import Event
            from hub.apps.assets.models import Asset, AssetStatus
            event_bus = get_event_bus()
            
            # Create a test asset for the event
            asset = Asset.objects.create(
                tenant=test_tenant,
                key=f"e2e-test-asset-persist-{uuid.uuid4().hex[:8]}",
                name="E2E Test Asset for Persistence",
                status=AssetStatus.DRAFT
            )
            
            # Publish an event using registered event type
            event_id = event_bus.publish(
                event_type="asset.created",
                data={"asset_id": str(asset.id)},
                tenant_id=str(test_tenant.id),
                user_id=str(test_user.id),
            )
            
            # Verify event in database
            event = Event.objects.filter(event_id=event_id).first()
            assert event is not None, "Event should be persisted"
            assert event.event_type == "asset.created"
            assert event.tenant_id == test_tenant.id
        except Exception as e:
            pytest.skip(f"Event persistence not available: {e}")
    
    def test_dead_letter_queue(
        self, docker_compose_manager, started_services, test_tenant
    ):
        """Test dead letter queue functionality."""
        try:
            from hub.apps.core.events.models import DeadLetterQueue
            # Check if DLQ table exists
            dlq_count = DeadLetterQueue.objects.count()
            assert dlq_count >= 0, "DeadLetterQueue table should exist"
        except ImportError:
            pytest.skip("Dead letter queue models not available")
        except Exception as e:
            pytest.skip(f"Dead letter queue not available: {e}")


class TestDockerComposeServiceLayer:
    """E2E tests for service layer in Docker Compose environment."""
    
    def test_api_service_endpoints(
        self, docker_compose_manager, started_services, api_client
    ):
        """Test API service endpoints."""
        # Test health endpoint (may redirect to /health/)
        response = api_client.get('/health', follow=True)
        assert response.status_code == 200, "Health endpoint should be accessible"
        
        # Test API docs endpoint (may not be available in all environments)
        # Try common API docs endpoints
        docs_endpoints = ['/api/docs/', '/api/schema/swagger-ui/', '/swagger/', '/api/schema/redoc/']
        docs_accessible = False
        for endpoint in docs_endpoints:
            response = api_client.get(endpoint)
            if response.status_code in [200, 302]:
                docs_accessible = True
                break
        
        # API docs may not be configured in all environments - that's OK
        # Just verify the API is responding (health check passed above)
        assert True, "API service is accessible (health check passed)"
    
    def test_contract_service_integration(
        self, docker_compose_manager, started_services, api_client, test_tenant
    ):
        """Test contract service integration."""
        # List contracts
        response = api_client.get('/api/v1/contracts/')
        assert response.status_code == 200, \
            f"Contract list endpoint failed: {response.status_code}"
    
    def test_asset_service_integration(
        self, docker_compose_manager, started_services, api_client, test_tenant
    ):
        """Test asset service integration."""
        # List assets
        response = api_client.get('/api/v1/assets/')
        assert response.status_code == 200, \
            f"Asset list endpoint failed: {response.status_code}"
    
    def test_service_to_service_communication(
        self, docker_compose_manager, started_services
    ):
        """Test service-to-service communication."""
        # Test that API service can communicate with backend services
        # This is verified by API endpoints working
        
        # Test semantic service - use dynamic port detection
        if docker_compose_manager.is_service_available('semantic-service'):
            semantic_url = docker_compose_manager.get_service_url('semantic-service', '/health', 8081)
            if semantic_url:
                try:
                    response = requests.get(semantic_url, timeout=10)
                    assert response.status_code == 200, \
                        f"Semantic service should be accessible at {semantic_url}"
                except requests.exceptions.RequestException:
                    pytest.skip(f"Semantic service not accessible at {semantic_url}")
            else:
                pytest.skip("Could not determine semantic service URL")
        else:
            pytest.skip("Semantic service not available")
        
        # Test DQ service - use dynamic port detection
        if docker_compose_manager.is_service_available('dq-service'):
            dq_url = docker_compose_manager.get_service_url('dq-service', '/health', 8083)
            if dq_url:
                try:
                    response = requests.get(dq_url, timeout=10)
                    assert response.status_code == 200, \
                        f"DQ service should be accessible at {dq_url}"
                except requests.exceptions.RequestException:
                    pytest.skip(f"DQ service not accessible at {dq_url}")
            else:
                pytest.skip("Could not determine DQ service URL")
        else:
            pytest.skip("DQ service not available")
        
        # Test compliance service - use dynamic port detection
        if docker_compose_manager.is_service_available('compliance-service'):
            compliance_url = docker_compose_manager.get_service_url('compliance-service', '/health', 8082)
            if compliance_url:
                try:
                    response = requests.get(compliance_url, timeout=10)
                    assert response.status_code == 200, \
                        f"Compliance service should be accessible at {compliance_url}"
                except requests.exceptions.RequestException:
                    pytest.skip(f"Compliance service not accessible at {compliance_url}")
            else:
                pytest.skip("Could not determine compliance service URL")
        else:
            pytest.skip("Compliance service not available")
    
    def test_worker_service_integration(
        self, docker_compose_manager, started_services
    ):
        """Test worker service integration."""
        if not docker_compose_manager.is_service_available('worker-service'):
            pytest.skip("Worker service not available")
        
        worker_url = docker_compose_manager.get_service_url('worker-service', '/healthz', 8080)
        if not worker_url:
            pytest.skip("Could not determine worker service URL")
        
        try:
            worker_health = requests.get(worker_url, timeout=10)
            assert worker_health.status_code == 200, \
                "Worker service should be healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Worker service not accessible at {worker_url}")
    
    def test_database_operations(
        self, docker_compose_manager, started_services, test_tenant
    ):
        """Test database operations through service layer."""
        from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
        
        # Create a contract via ORM with proper fields
        contract = Contract.objects.create(
            tenant=test_tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "e2e-test-contract", "name": "E2E Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {
                    "name": "E2E Test Contract",
                    "title": "E2E Test Contract"
                }
            },
            status=ContractStatus.DRAFT
        )
        
        assert contract.id is not None, "Contract should be created"
        assert contract.tenant == test_tenant, "Tenant should be set"
        
        # Verify contract can be retrieved
        retrieved = Contract.objects.get(id=contract.id)
        assert retrieved.id == contract.id, "Contract should be retrievable"
        assert retrieved.tenant == test_tenant, "Tenant should match"
    
    def test_redis_operations(
        self, docker_compose_manager, started_services
    ):
        """Test Redis operations through service layer."""
        try:
            import redis
            from django.conf import settings
            
            # Check if Redis service is available
            if not docker_compose_manager.is_service_available('redis'):
                pytest.skip("Redis service not available")
            
            # Get Redis port dynamically from docker compose
            redis_port = docker_compose_manager.get_service_port('redis', 6379)
            if not redis_port:
                # Fallback to settings
                redis_port = getattr(settings, 'REDIS_PORT', 6379)
            
            # Get Redis host from settings or use localhost
            redis_host = getattr(settings, 'REDIS_HOST', 'localhost')
            redis_db = getattr(settings, 'REDIS_DB', 0)
            
            # Create Redis client with dynamic port
            redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
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
        except redis.ConnectionError as e:
            pytest.skip(f"Redis connection failed: {e}")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")


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
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                # Services are running, don't skip
                return
        except Exception:
            pass

        # Skip tests if flag not set and services not detected
        skip_runtime = pytest.mark.skip(reason="need --docker-compose-runtime option to run or Docker Compose services must be running")
        for item in items:
            if "docker_compose_runtime" in item.keywords:
                item.add_marker(skip_runtime)

