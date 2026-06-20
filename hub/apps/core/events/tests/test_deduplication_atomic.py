"""Phase 88: Atomic deduplication tests -- verifies TOCTOU fix."""

import threading
from unittest.mock import patch

from django.test import TestCase

from hub.apps.core.events.deduplication import (
    check_and_store_event,
)


class TestAtomicDeduplication(TestCase):
    """Verify atomic SET NX prevents TOCTOU race."""

    def _get_redis(self):
        """Get a real Redis client or skip."""
        try:
            from hub.apps.core.events.deduplication import (
                get_redis_client,
            )

            client = get_redis_client()
            if client is None:
                self.skipTest("Redis not available")
            client.ping()
            return client
        except Exception:
            self.skipTest("Redis not available")

    def _redis_key(self, name):
        """Create a test key and register cleanup."""
        key = f"test:dedup:atomic:{name}"
        rc = self._get_redis()
        rc.delete(key)
        self.addCleanup(rc.delete, key)
        return key, rc

    def test_first_call_returns_new_event(self):
        key, rc = self._redis_key("new")

        is_dup, eid = check_and_store_event(
            key,
            "evt-001",
            ttl=60,
            redis_client=rc,
        )
        self.assertFalse(is_dup)
        self.assertEqual(eid, "evt-001")

    def test_second_call_returns_duplicate(self):
        key, rc = self._redis_key("dup")

        is_dup1, eid1 = check_and_store_event(
            key,
            "evt-001",
            ttl=60,
            redis_client=rc,
        )
        is_dup2, eid2 = check_and_store_event(
            key,
            "evt-002",
            ttl=60,
            redis_client=rc,
        )

        self.assertFalse(is_dup1)
        self.assertTrue(is_dup2)
        self.assertEqual(eid1, "evt-001")
        self.assertEqual(eid2, "evt-001")  # returns original, not new

    def test_concurrent_publishes_exactly_one_wins(self):
        """10 concurrent threads -> exactly 1 new, 9 duplicates."""
        key, rc = self._redis_key("concurrent")

        results = []
        barrier = threading.Barrier(10)
        results_lock = threading.Lock()

        def worker(thread_id):
            barrier.wait()
            is_dup, eid = check_and_store_event(
                key,
                f"evt-{thread_id}",
                ttl=60,
                redis_client=rc,
            )
            with results_lock:
                results.append((thread_id, is_dup, eid))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Verify all threads completed
        self.assertEqual(
            len(results),
            10,
            f"Only {len(results)}/10 threads completed",
        )

        new_events = [r for r in results if not r[1]]
        dup_events = [r for r in results if r[1]]

        self.assertEqual(
            len(new_events),
            1,
            f"Expected exactly 1 new, got {len(new_events)}",
        )
        self.assertEqual(
            len(dup_events),
            9,
            f"Expected 9 duplicates, got {len(dup_events)}",
        )

        # All duplicates reference the same event_id as the winner
        winner_eid = new_events[0][2]
        for _, _, eid in dup_events:
            self.assertEqual(eid, winner_eid)

    def test_redis_unavailable_fails_open(self):
        """When Redis is unavailable, allow event through."""
        with patch(
            "hub.apps.core.events.deduplication.get_redis_client",
            return_value=None,
        ):
            is_dup, eid = check_and_store_event(
                "test:key",
                "evt-001",
            )
        self.assertFalse(is_dup)
        self.assertEqual(eid, "evt-001")
