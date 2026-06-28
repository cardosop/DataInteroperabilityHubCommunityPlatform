"""
Standalone test runner for Redis service configuration tests.

Validates Docker Compose configurations, Kubernetes manifests, and Redis
connectivity.  These tests are designed for local development / CI
environments where the full Redis fleet is available.

When Redis instances are not reachable the tests skip rather than fail
so they do not block CI runs that lack the full fleet.
"""

import os
import sys
from pathlib import Path

import pytest
import redis
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Disable Django loading
os.environ.pop("DJANGO_SETTINGS_MODULE", None)
os.environ["SKIP_DJANGO_SETUP"] = "1"

# ── Redis fleet ports (must match docker-compose.test.yml) ──────────────────
REDIS_PORTS = {
    "cache": 6379,
    "queue": 6380,
    "events": 6381,
    "channels": 6382,
}

# Env vars that hold Redis URLs inside the Docker test stack.  When running
# inside the api-service-test container these point to Docker hostnames
# (e.g. redis-cache-test:6379); on the host they may be unset → fall back
# to localhost with the mapped port.
_REDIS_PORT_TO_ENV = {
    6379: "REDIS_CACHE_URL",
    6380: "REDIS_QUEUE_URL",
    6381: "REDIS_EVENTS_URL",
    6382: "REDIS_CHANNELS_URL",
}


def _parse_redis_host_port(url: str) -> tuple[str, int]:
    """Extract (host, port) from a ``redis://host:port/db`` URL."""
    if not url or not isinstance(url, str) or not url.startswith("redis://"):
        return ("localhost", 6379)
    try:
        # redis://host:port/db → host:port/db
        host_port_db = url.replace("redis://", "", 1)
        # host:port/db → host:port
        host_port = host_port_db.split("/")[0]
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            return (host, int(port_str))
        return (host_port, 6379)
    except (ValueError, IndexError):
        return ("localhost", 6379)


def _resolve_redis_host_port(port: int) -> tuple[str, int]:
    """Return (host, port) for a Redis fleet instance.

    When ``REDIS_*_URL`` env vars are set (inside the Docker test stack),
    parses the hostname and internal port from the URL.  Falls back to
    ``localhost`` with the caller-supplied *port* for host-side execution.
    """
    env_var = _REDIS_PORT_TO_ENV.get(port)
    if env_var:
        url = os.environ.get(env_var, "")
        if url:
            host, resolved_port = _parse_redis_host_port(url)
            return (host, resolved_port)
    return ("localhost", port)


def _redis_is_available(port: int) -> bool:
    """Check whether a Redis instance is reachable on its resolved host:port."""
    host, resolved_port = _resolve_redis_host_port(port)
    try:
        r = redis.Redis(
            host=host, port=resolved_port,
            decode_responses=True, socket_connect_timeout=2,
        )
        return r.ping()
    except (redis.ConnectionError, ConnectionError, OSError):
        return False


def _require_redis_fleet():
    """Skip the current test unless ALL Redis fleet instances are reachable.

    Detects container-side execution via ``/.dockerenv`` so that the tests
    work through ``docker compose exec`` WITHOUT requiring the heavy
    ``PYTEST_DOCKER_COMPOSE_RUNTIME=1`` env var (which disables Django
    setup for all tests in the session).
    """
    in_docker = os.path.exists("/.dockerenv")
    in_runtime = os.environ.get("PYTEST_DOCKER_COMPOSE_RUNTIME") == "1"
    if not (in_docker or in_runtime):
        pytest.skip(
            "Redis fleet not available; run inside docker compose or set "
            "PYTEST_DOCKER_COMPOSE_RUNTIME=1 and start docker compose services"
        )
    missing = [name for name, port in REDIS_PORTS.items()
               if not _redis_is_available(port)]
    if missing:
        pytest.skip(
            f"Redis instance(s) not reachable: {missing}. "
            f"Ensure the full Redis fleet is running on ports {list(REDIS_PORTS.values())}."
        )


def test_docker_compose_configs():
    """Test Docker Compose configurations."""
    docker_compose_files = {
        "main": project_root / "docker-compose.yml",
        "dev": project_root / "docker-compose.dev.yml",
        "staging": project_root / "docker-compose.staging.yml",
        "production": project_root / "docker-compose.production.yml",
        "test": project_root / "docker-compose.test.yml",
    }

    configs = {}
    for name, file_path in docker_compose_files.items():
        if file_path.exists():
            with open(file_path) as f:
                configs[name] = yaml.safe_load(f)

    assert len(configs) > 0, "At least one Docker Compose file should exist"

    errors = []

    # Test 1: Redis instances defined
    redis_services = ["redis-cache", "redis-queue", "redis-events", "redis-channels"]
    if "test" in configs and "main" in configs:
        main_services = configs.get("main", {}).get("services", {})
        services = configs.get("test", {}).get("services", {})

        for redis_name in redis_services:
            if redis_name not in main_services and redis_name not in services:
                errors.append(f"{redis_name} should be defined in docker-compose.yml")

    # Test 2: Port mapping (omitted: label check — labels are optional per project)
    redis_ports = {"redis-cache": 6379, "redis-queue": 6380, "redis-events": 6381, "redis-channels": 6382}
    if "main" in configs:
        services = configs.get("main", {}).get("services", {})
        for redis_name, expected_port in redis_ports.items():
            if redis_name in services:
                ports = services[redis_name].get("ports", [])
                has_correct_mapping = any(
                    str(expected_port) in str(p) for p in ports
                )
                if not has_correct_mapping:
                    errors.append(
                        f"{redis_name} should have port mapping {expected_port}:6379 (current: {ports})"
                    )

    # Test 4: Health checks
    if "main" in configs:
        services = configs.get("main", {}).get("services", {})
        for redis_name in redis_services:
            if redis_name in services:
                has_healthcheck = services[redis_name].get("healthcheck") is not None
                if not has_healthcheck:
                    errors.append(f"{redis_name} should have a health check defined")

    # Test 5: AOF persistence
    queue_configs = configs.get("main", {}).get("services", {}).get("redis-queue", {})
    if queue_configs:
        command = str(queue_configs.get("command", ""))
        if "--appendonly" not in command and "appendonly" not in command.lower():
            errors.append("redis-queue should have AOF persistence configured")

    events_configs = configs.get("main", {}).get("services", {}).get("redis-events", {})
    if events_configs:
        command = str(events_configs.get("command", ""))
        if "--appendonly" not in command and "appendonly" not in command.lower():
            errors.append("redis-events should have AOF persistence configured")

    # Test 6: Queue noeviction policy
    if queue_configs:
        command = str(queue_configs.get("command", ""))
        env = queue_configs.get("environment", {})
        if "noeviction" not in command.lower() and not any(
            "noeviction" in str(v).lower() for v in env.values()
        ):
            errors.append("redis-queue should have noeviction policy")

    assert len(errors) == 0, f"Docker Compose config errors: {errors}"


def test_kubernetes_manifests():
    """Test Kubernetes manifests."""
    errors = []
    redis_instances = ["redis-cache", "redis-queue", "redis-events", "redis-channels"]

    for instance in redis_instances:
        base_path = project_root / "k8s" / instance / "base"
        if not base_path.exists():
            errors.append(f"{instance} base directory should exist")
            continue

        required_files = ["statefulset.yaml", "service.yaml", "configmap.yaml", "pvc.yaml"]
        for file_name in required_files:
            file_path = base_path / file_name
            if not file_path.exists():
                errors.append(f"{instance} {file_name} should exist")
            else:
                # Validate YAML
                try:
                    with open(file_path) as f:
                        yaml.safe_load(f)
                except yaml.YAMLError as e:
                    errors.append(f"Invalid YAML in {file_path}: {e}")

    assert len(errors) == 0, f"Kubernetes manifest errors: {errors}"


def test_redis_connectivity():
    """Test Redis connectivity (requires running Redis fleet)."""
    _require_redis_fleet()

    errors = []
    for name, port in REDIS_PORTS.items():
        host, resolved_port = _resolve_redis_host_port(port)
        try:
            r = redis.Redis(
                host=host, port=resolved_port,
                decode_responses=True, socket_connect_timeout=3,
            )
            result = r.ping()
            if not result:
                errors.append(f"redis-{name} (port {port}) ping returned False")
        except redis.ConnectionError as e:
            errors.append(f"redis-{name} (port {port}) not accessible: {e}")
        except (ConnectionError, TimeoutError, OSError) as e:
            errors.append(f"redis-{name} (port {port}) error: {e}")

    assert len(errors) == 0, f"Redis connectivity errors: {errors}"


def test_redis_isolation():
    """Test Redis instance isolation (requires running Redis fleet)."""
    _require_redis_fleet()

    errors = []
    try:
        cache_host, cache_port = _resolve_redis_host_port(6379)
        queue_host, queue_port = _resolve_redis_host_port(6380)
        events_host, events_port = _resolve_redis_host_port(6381)
        channels_host, channels_port = _resolve_redis_host_port(6382)

        cache_client = redis.Redis(host=cache_host, port=cache_port, decode_responses=True, db=0)
        queue_client = redis.Redis(host=queue_host, port=queue_port, decode_responses=True, db=0)
        events_client = redis.Redis(host=events_host, port=events_port, decode_responses=True, db=0)
        channels_client = redis.Redis(host=channels_host, port=channels_port, decode_responses=True, db=0)

        # Set a test key in cache
        test_key = "test_isolation_key"
        cache_client.set(test_key, "cache_value")

        # Verify it doesn't exist in other instances
        if queue_client.get(test_key) is not None:
            errors.append("Keys should be isolated between instances (queue found cache key)")
        if events_client.get(test_key) is not None:
            errors.append("Keys should be isolated between instances (events found cache key)")
        if channels_client.get(test_key) is not None:
            errors.append("Keys should be isolated between instances (channels found cache key)")

        # Cleanup
        cache_client.delete(test_key)
    except (redis.ConnectionError, ConnectionError, OSError) as e:
        errors.append(f"Redis isolation test error: {e}")

    assert len(errors) == 0, f"Redis isolation errors: {errors}"


def main():
    """Run all tests."""
    print("=" * 80)
    print("Running Redis Service Configuration Tests")
    print("=" * 80)

    results = {
        "docker_compose_configs": test_docker_compose_configs(),
        "kubernetes_manifests": test_kubernetes_manifests(),
        "redis_connectivity": test_redis_connectivity(),
        "redis_isolation": test_redis_isolation(),
    }

    print("Results:")
    for test_name, result in results.items():
        status = "PASS" if result is None else f"FAIL: {len(result)} errors"
        print(f"  {test_name}: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
