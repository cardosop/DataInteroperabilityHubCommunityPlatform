"""
Thread safety tests: multi-threaded access to services/cache,
shared state protection. Real cache and DB; no mocks.
"""

import threading
from typing import List

from django.core.cache import cache
from django.db import connection

from hub.apps.contracts.models import Contract
from tests.concurrency.base import ConcurrencyTestBase


class ThreadSafetyTest(ConcurrencyTestBase):
    """Thread-safe behavior of cache and DB access."""

    def test_cache_concurrent_set_get(self):
        """Concurrent set and get on Django cache: no errors, correct final value."""
        key = "concurrency_thread_safety_key"
        cache.delete(key)
        errors: List[str] = []
        lock = threading.Lock()

        def set_value(idx: int) -> None:
            try:
                cache.set(key, f"value_{idx}", timeout=60)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        def get_value() -> None:
            try:
                cache.get(key)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        # Mix of setters and getters
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=set_value, args=(i,)))
        for _ in range(5):
            threads.append(threading.Thread(target=get_value))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        val = cache.get(key)
        self.assertIsNotNone(val)
        self.assertTrue(val.startswith("value_"))
        cache.delete(key)

    def test_concurrent_cache_delete(self):
        """Concurrent delete of same key: no errors."""
        key = "concurrency_delete_key"
        cache.set(key, "x", timeout=60)
        errors: List[str] = []
        lock = threading.Lock()

        def delete_key() -> None:
            try:
                cache.delete(key)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=delete_key) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)

    def test_db_query_concurrent_same_connection_pattern(self):
        """Each thread uses ensure_connection/close; no cross-thread connection leak."""
        results: List[bool] = []
        lock = threading.Lock()

        def query() -> None:
            try:
                connection.ensure_connection()
                list(Contract.objects.filter(tenant=self.tenant).values_list("id", flat=True)[:1])
                with lock:
                    results.append(True)
            except Exception:
                with lock:
                    results.append(False)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=query) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 6)
        self.assertTrue(all(results))
