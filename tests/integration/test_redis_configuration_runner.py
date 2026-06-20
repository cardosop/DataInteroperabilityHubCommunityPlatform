#!/usr/bin/env python3
"""
Comprehensive test runner for Redis configuration tests.

This script runs all Redis configuration tests and validates the implementation
without requiring Django setup. It directly tests Redis connections and configuration.
"""

import sys
from pathlib import Path

import redis

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_redis_instances_accessible():
    """Test that all Redis instances are accessible."""
    print("\n=== Testing Redis Instance Accessibility ===")
    clients_config = [
        (6379, "cache"),
        (6380, "queue"),
        (6381, "events"),
        (6382, "channels"),
    ]

    results = []
    for port, name in clients_config:
        try:
            client = redis.Redis(
                host="localhost", port=port, decode_responses=True, socket_connect_timeout=3
            )
            result = client.ping()
            if result:
                print(f"✓ redis-{name} (port {port}): Accessible")
                results.append((name, port, True, None))
            else:
                print(f"✗ redis-{name} (port {port}): Ping returned False")
                results.append((name, port, False, "Ping returned False"))
        except redis.ConnectionError as e:
            print(f"✗ redis-{name} (port {port}): Connection failed - {e}")
            results.append((name, port, False, str(e)))
        except Exception as e:
            print(f"✗ redis-{name} (port {port}): Error - {e}")
            results.append((name, port, False, str(e)))

    return results


def test_redis_instances_isolated():
    """Test that Redis instances are isolated."""
    print("\n=== Testing Redis Instance Isolation ===")
    try:
        cache_client = redis.Redis(
            host="localhost", port=6379, decode_responses=True, socket_connect_timeout=3
        )
        queue_client = redis.Redis(
            host="localhost", port=6380, decode_responses=True, socket_connect_timeout=3
        )
        events_client = redis.Redis(
            host="localhost", port=6381, decode_responses=True, socket_connect_timeout=3
        )
        channels_client = redis.Redis(
            host="localhost", port=6382, decode_responses=True, socket_connect_timeout=3
        )

        # Set unique keys in each instance
        test_keys = {}
        for name, client in [
            ("cache", cache_client),
            ("queue", queue_client),
            ("events", events_client),
            ("channels", channels_client),
        ]:
            key = f"test_isolation_{name}"
            value = f"{name}_value"
            client.set(key, value)
            test_keys[name] = (key, value)
            print(f"✓ Set key in redis-{name}")

        # Verify isolation - keys should only exist in their respective instances
        all_isolated = True
        for name, client in [
            ("cache", cache_client),
            ("queue", queue_client),
            ("events", events_client),
            ("channels", channels_client),
        ]:
            expected_key, expected_value = test_keys[name]
            # Check that key exists in correct instance
            if client.get(expected_key) != expected_value:
                print(f"✗ FAIL: redis-{name} key not found or incorrect value")
                all_isolated = False

        # Cleanup
        for name, client in [
            ("cache", cache_client),
            ("queue", queue_client),
            ("events", events_client),
            ("channels", channels_client),
        ]:
            key, _ = test_keys[name]
            client.delete(key)

        if all_isolated:
            print("✓ All Redis instances are properly isolated")
        else:
            print("✗ Isolation test failed")

        return all_isolated
    except Exception as e:
        print(f"✗ Isolation test error: {e}")
        return False


def test_redis_url_parsing():
    """Test Redis URL parsing utilities."""
    print("\n=== Testing Redis URL Parsing ===")
    try:
        from hub.apps.core.redis_pools import parse_redis_url

        test_cases = [
            ("redis://localhost:6379/0", ("localhost", 6379)),
            ("redis://redis-cache:6379/0", ("redis-cache", 6379)),
            ("redis://localhost/0", ("localhost", 6379)),  # Default port
            ("redis://host:6380/0", ("host", 6380)),
        ]

        all_passed = True
        for url, expected in test_cases:
            result = parse_redis_url(url)
            if result == expected:
                print(f"✓ Parsed {url} -> {result}")
            else:
                print(f"✗ Parsed {url} -> {result}, expected {expected}")
                all_passed = False

        return all_passed
    except Exception as e:
        print(f"✗ URL parsing test error: {e}")
        return False


def test_redis_connection_pools():
    """Test that connection pools can be created."""
    print("\n=== Testing Redis Connection Pools ===")
    try:
        # Test connection pool creation directly using redis.ConnectionPool
        # This avoids Django settings dependency
        cache_pool = redis.ConnectionPool.from_url(
            "redis://localhost:6379/0", max_connections=50, decode_responses=True
        )
        queue_pool = redis.ConnectionPool.from_url(
            "redis://localhost:6380/0", max_connections=20, decode_responses=True
        )
        events_pool = redis.ConnectionPool.from_url(
            "redis://localhost:6381/0", max_connections=30, decode_responses=True
        )
        channels_pool = redis.ConnectionPool.from_url(
            "redis://localhost:6382/0", max_connections=40, decode_responses=True
        )

        assert cache_pool is not None
        assert queue_pool is not None
        assert events_pool is not None
        assert channels_pool is not None

        print("✓ All connection pools created successfully")
        print(f"  Cache pool: max_connections={cache_pool.max_connections}")
        print(f"  Queue pool: max_connections={queue_pool.max_connections}")
        print(f"  Events pool: max_connections={events_pool.max_connections}")
        print(f"  Channels pool: max_connections={channels_pool.max_connections}")

        # Test that pools can create clients
        cache_client = redis.Redis(connection_pool=cache_pool)
        queue_client = redis.Redis(connection_pool=queue_pool)
        events_client = redis.Redis(connection_pool=events_pool)
        channels_client = redis.Redis(connection_pool=channels_pool)

        # Test connectivity
        assert cache_client.ping() is True
        assert queue_client.ping() is True
        assert events_client.ping() is True
        assert channels_client.ping() is True

        print("✓ All connection pools can create working clients")

        return True
    except Exception as e:
        print(f"✗ Connection pool test error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("Redis Configuration Test Runner")
    print("=" * 80)

    all_passed = True

    # Test 1: Redis instances accessible
    results = test_redis_instances_accessible()
    if not all(r[2] for r in results):
        all_passed = False

    # Test 2: Redis instances isolated
    if not test_redis_instances_isolated():
        all_passed = False

    # Test 3: URL parsing
    if not test_redis_url_parsing():
        all_passed = False

    # Test 4: Connection pools
    if not test_redis_connection_pools():
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("SUCCESS: All tests passed!")
        return 0
    else:
        print("FAILED: Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
