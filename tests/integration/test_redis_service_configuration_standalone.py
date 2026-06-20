"""
Standalone test runner for Redis service configuration tests.
This version avoids Django dependencies by running tests directly.
"""

import os
import sys
from pathlib import Path

import redis
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Disable Django loading
os.environ.pop("DJANGO_SETTINGS_MODULE", None)
os.environ["SKIP_DJANGO_SETUP"] = "1"


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

    redis_services = ["redis-cache", "redis-queue", "redis-events", "redis-channels"]
    errors = []

    # Test 1: All Redis services defined
    for name, config in configs.items():
        services = config.get("services", {})
        # For test environment, services are named with -test suffix
        if name == "test":
            test_services = [s + "-test" for s in redis_services]
            for service_name in test_services:
                if service_name not in services:
                    errors.append(f"Service {service_name} not found in {name}")
        else:
            for service_name in redis_services:
                if service_name not in services:
                    errors.append(f"Service {service_name} not found in {name}")

    # Test 2: Health checks configured
    for name, config in configs.items():
        services = config.get("services", {})
        # For test environment, services are named with -test suffix
        if name == "test":
            test_services = [s + "-test" for s in redis_services]
            for service_name in test_services:
                if service_name in services:
                    service_config = services[service_name]
                    if "healthcheck" not in service_config:
                        errors.append(f"{service_name} must have healthcheck in {name}")
        else:
            for service_name in redis_services:
                if service_name in services:
                    service_config = services[service_name]
                    if "healthcheck" not in service_config:
                        errors.append(f"{service_name} must have healthcheck in {name}")

    # Test 3: Ports configured
    for name, config in configs.items():
        services = config.get("services", {})
        # For test environment, services are named with -test suffix
        if name == "test":
            test_services = [s + "-test" for s in redis_services]
            for service_name in test_services:
                if service_name in services:
                    service_config = services[service_name]
                    if "ports" not in service_config:
                        errors.append(f"{service_name} must have ports configured in {name}")
        else:
            for service_name in redis_services:
                if service_name in services:
                    service_config = services[service_name]
                    if "ports" not in service_config:
                        errors.append(f"{service_name} must have ports configured in {name}")

    # Test 4: Memory limits configured
    for name, config in configs.items():
        services = config.get("services", {})
        # For test environment, services are named with -test suffix
        if name == "test":
            test_services = [s + "-test" for s in redis_services]
            for service_name in test_services:
                if service_name in services:
                    service_config = services[service_name]
                    command = str(service_config.get("command", ""))
                    env = service_config.get("environment", {})
                    if "--maxmemory" not in command and not any(
                        "MAX_MEMORY" in str(k).upper() for k in env.keys()
                    ):
                        errors.append(
                            f"{service_name} should have memory limit configured in {name}"
                        )
        else:
            for service_name in redis_services:
                if service_name in services:
                    service_config = services[service_name]
                    command = str(service_config.get("command", ""))
                    env = service_config.get("environment", {})
                    if "--maxmemory" not in command and not any(
                        "MAX_MEMORY" in str(k).upper() for k in env.keys()
                    ):
                        errors.append(
                            f"{service_name} should have memory limit configured in {name}"
                        )

    # Test 5: Persistence configuration
    cache_configs = configs.get("main", {}).get("services", {}).get("redis-cache", {})
    if cache_configs:
        command = str(cache_configs.get("command", ""))
        if "--save" not in command and "save" not in command.lower():
            errors.append("redis-cache should have RDB persistence configured")

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

    return errors


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

    return errors


def test_redis_connectivity():
    """Test Redis connectivity."""
    errors = []
    clients_config = [
        (6379, "cache"),
        (6380, "queue"),
        (6381, "events"),
        (6382, "channels"),
    ]

    for port, name in clients_config:
        try:
            r = redis.Redis(
                host="localhost", port=port, decode_responses=True, socket_connect_timeout=3
            )
            result = r.ping()
            if not result:
                errors.append(f"redis-{name} (port {port}) ping returned False")
        except redis.ConnectionError as e:
            errors.append(f"redis-{name} (port {port}) not accessible: {e}")
        except Exception as e:
            errors.append(f"redis-{name} (port {port}) error: {e}")

    return errors


def test_redis_isolation():
    """Test Redis instance isolation."""
    errors = []
    try:
        cache_client = redis.Redis(host="localhost", port=6379, decode_responses=True, db=0)
        queue_client = redis.Redis(host="localhost", port=6380, decode_responses=True, db=0)
        events_client = redis.Redis(host="localhost", port=6381, decode_responses=True, db=0)
        channels_client = redis.Redis(host="localhost", port=6382, decode_responses=True, db=0)

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
    except Exception as e:
        errors.append(f"Redis isolation test error: {e}")

    return errors


def main():
    """Run all tests."""
    print("=" * 80)
    print("Running Redis Service Configuration Tests")
    print("=" * 80)

    all_errors = []

    print("\n1. Testing Docker Compose configurations...")
    errors = test_docker_compose_configs()
    if errors:
        all_errors.extend(errors)
        for error in errors:
            print(f"  ✗ {error}")
    else:
        print("  ✓ All Docker Compose configurations valid")

    print("\n2. Testing Kubernetes manifests...")
    errors = test_kubernetes_manifests()
    if errors:
        all_errors.extend(errors)
        for error in errors:
            print(f"  ✗ {error}")
    else:
        print("  ✓ All Kubernetes manifests valid")

    print("\n3. Testing Redis connectivity...")
    errors = test_redis_connectivity()
    if errors:
        all_errors.extend(errors)
        for error in errors:
            print(f"  ✗ {error}")
    else:
        print("  ✓ All Redis instances accessible")

    print("\n4. Testing Redis isolation...")
    errors = test_redis_isolation()
    if errors:
        all_errors.extend(errors)
        for error in errors:
            print(f"  ✗ {error}")
    else:
        print("  ✓ Redis instances are isolated")

    print("\n" + "=" * 80)
    if all_errors:
        print(f"FAILED: {len(all_errors)} error(s) found")
        return 1
    else:
        print("SUCCESS: All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
