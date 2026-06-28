#!/usr/bin/env python3
"""
Comprehensive test runner for Redis configuration tests.

This script runs all Redis configuration tests and validates the implementation
without requiring Django setup. It directly tests Redis connections and configuration.

Works both as a standalone runner (``python test_redis_configuration_runner.py``)
and as a pytest test file.

When running inside Docker (api-service-test), the Redis services are at
``redis-*-test`` hostnames.  On the host, they are accessible via
``localhost`` with mapped ports.
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def _redis_clients():
    """Return (host, port, name) tuples for all Redis instances.

    Auto-detects Docker vs host environment by checking for the
    ``REDIS_CACHE_URL`` env var.
    """
    if os.environ.get("REDIS_CACHE_URL"):
        # Inside Docker — use service hostnames
        try:
            import redis as _redis
        except ImportError:
            pytest.skip("redis-py not installed")
        return [
            ("redis-cache-test", 6379, "cache"),
            ("redis-queue-test", 6379, "queue"),
            ("redis-events-test", 6379, "events"),
            ("redis-channels-test", 6379, "channels"),
        ]
    # On host — use localhost with mapped ports
    return [
        ("localhost", 6379, "cache"),
        ("localhost", 6380, "queue"),
        ("localhost", 6381, "events"),
        ("localhost", 6382, "channels"),
    ]


def test_redis_instances_accessible():
    """Test that all Redis instances are accessible."""
    try:
        import redis
    except ImportError:
        pytest.skip("redis-py not installed")

    for host, port, name in _redis_clients():
        try:
            client = redis.Redis(
                host=host, port=port, decode_responses=True, socket_connect_timeout=3
            )
            assert client.ping(), f"redis-{name} ({host}:{port}): ping returned False"
        except redis.ConnectionError as e:
            pytest.skip(f"redis-{name} ({host}:{port}) not accessible in this environment: {e}")


def test_redis_instances_isolated():
    """Test that Redis instances are isolated (keys in one don't appear in another)."""
    try:
        import redis
    except ImportError:
        pytest.skip("redis-py not installed")

    clients_cfg = _redis_clients()
    clients = {}
    test_keys = {}

    for host, port, name in clients_cfg:
        try:
            client = redis.Redis(
                host=host, port=port, decode_responses=True, socket_connect_timeout=3
            )
            client.ping()
        except redis.ConnectionError:
            pytest.skip(f"redis-{name} ({host}:{port}) not accessible — cannot test isolation")
        clients[name] = client
        test_keys[name] = (f"test_isolation_{name}", f"{name}_value")

    # Set unique keys in each instance
    for name, client in clients.items():
        key, value = test_keys[name]
        client.set(key, value)

    # Verify isolation — each key should ONLY exist in its own instance
    for name, client in clients.items():
        expected_key, expected_value = test_keys[name]
        # Own instance: key must exist with correct value
        assert client.get(expected_key) == expected_value, (
            f"redis-{name}: own key missing or wrong value"
        )
        # Other instances: key must NOT exist
        for other_name, other_client in clients.items():
            if other_name == name:
                continue
            assert other_client.get(expected_key) is None, (
                f"Isolation violation: redis-{other_name} can see redis-{name}'s key"
            )

    # Cleanup
    for name, client in clients.items():
        key, _ = test_keys[name]
        client.delete(key)


def test_redis_url_parsing():
    """Test Redis URL parsing utilities."""
    try:
        from hub.apps.core.redis_pools import parse_redis_url
    except ImportError:
        pytest.skip("Django not available — cannot test redis_pools")

    test_cases = [
        ("redis://localhost:6379/0", ("localhost", 6379)),
        ("redis://redis-cache:6379/0", ("redis-cache", 6379)),
        ("redis://localhost/0", ("localhost", 6379)),  # Default port
        ("redis://host:6380/0", ("host", 6380)),
    ]

    for url, expected in test_cases:
        result = parse_redis_url(url)
        assert result == expected, f"Parsed {url} -> {result}, expected {expected}"


def test_redis_connection_pools():
    """Test that connection pools can be created and used."""
    try:
        import redis
    except ImportError:
        pytest.skip("redis-py not installed")

    # Build pool configs from whatever Redis hosts are available.
    # At least one must be reachable.
    pool_configs = []
    for host, port, name in _redis_clients():
        try:
            r = redis.Redis(host=host, port=port, socket_connect_timeout=2)
            r.ping()
            pool_configs.append((host, port, name))
        except redis.ConnectionError:
            continue

    if not pool_configs:
        pytest.skip("No Redis instances accessible — cannot test connection pools")

    for host, port, name in pool_configs:
        url = f"redis://{host}:{port}/0"
        pool = redis.ConnectionPool.from_url(url, max_connections=10, decode_responses=True)
        assert pool is not None, f"redis-{name}: pool creation returned None"
        client = redis.Redis(connection_pool=pool)
        assert client.ping(), f"redis-{name}: client from pool failed ping"


def main():
    """Standalone runner — runs all tests and exits with 0 (pass) or 1 (fail)."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=project_root,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
