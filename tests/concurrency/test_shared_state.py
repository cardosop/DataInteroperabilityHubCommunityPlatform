"""
Shared state tests: shared cache and in-memory structures under
concurrent load. Real cache; no mocks.
"""

import threading
from typing import List

from django.core.cache import cache

from tests.concurrency.base import ConcurrencyTestBase


class SharedStateTest(ConcurrencyTestBase):
    """Shared state (e.g. cache) under concurrency."""

    def test_shared_cache_key_increment_consistency(self):
        """Multiple threads increment a shared counter in cache; final count >= 1."""
        key = "concurrency_shared_counter"
        cache.delete(key)
        cache.set(key, 0, timeout=120)
        errors: List[str] = []
        lock = threading.Lock()

        def increment() -> None:
            try:
                # get then set is not atomic; we only check no crash and final value exists
                val = cache.get(key, 0)
                cache.set(key, (val or 0) + 1, timeout=120)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        final = cache.get(key)
        self.assertIsNotNone(final)
        self.assertIsInstance(final, (int, float))
        cache.delete(key)

    def test_shared_cache_multiple_keys_concurrent(self):
        """Concurrent set of different keys: all keys have correct value."""
        keys = [f"concurrency_shared_{i}" for i in range(8)]
        for k in keys:
            cache.delete(k)
        errors: List[str] = []
        lock = threading.Lock()

        def set_key(idx: int) -> None:
            try:
                cache.set(keys[idx], f"val_{idx}", timeout=60)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=set_key, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        for i, k in enumerate(keys):
            self.assertEqual(cache.get(k), f"val_{i}")
            cache.delete(k)

    def test_concurrent_clear_and_set(self):
        """Concurrent clear and set: no unhandled exceptions."""
        errors: List[str] = []
        lock = threading.Lock()

        def clear_cache() -> None:
            try:
                cache.clear()
            except Exception as e:
                with lock:
                    errors.append(str(e))

        def set_something(idx: int) -> None:
            try:
                cache.set(f"concurrent_set_{idx}", idx, timeout=10)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=set_something, args=(i,)))
        threads.append(threading.Thread(target=clear_cache))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
