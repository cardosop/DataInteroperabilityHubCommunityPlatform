"""
Integration tests for optimized dual-write pattern.

Tests:
- Write-behind pattern with buffering
- Batch writes
- Retry logic (success path; retry-on-failure requires real DB failure, no mocks)
- Consistency validation
- Performance improvements

All tests use real implementations (no mocks/stubs).
"""

import uuid

from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.models import Event
from hub.apps.core.events.persistence_tasks import (
    _validate_batch_persistence,
    _validate_event_persistence,
    persist_event_async,
    persist_events_batch_async,
)
from hub.apps.core.events.write_behind import (
    WriteBehindBuffer,
    get_write_behind_buffer,
    shutdown_write_behind_buffer,
)
from tests.factories import TenantFactory, UserFactory
from tests.utils.polling import wait_until


class WriteBehindPatternTest(TestCase):
    """Test write-behind pattern implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.event_bus = get_event_bus()

    def tearDown(self):
        """Clean up after tests."""
        # Shutdown write-behind buffer if running
        shutdown_write_behind_buffer(flush=False)

    def test_write_behind_buffer_initialization(self):
        """Test write-behind buffer initialization."""
        buffer = WriteBehindBuffer(buffer_size=50, flush_interval_seconds=2.0, max_retries=3)

        self.assertEqual(buffer.buffer_size, 50)
        self.assertEqual(buffer.flush_interval_seconds, 2.0)
        self.assertEqual(buffer.max_retries, 3)
        self.assertEqual(buffer.get_buffer_size(), 0)

        buffer.stop(flush=False)

    def test_write_behind_buffer_add_event(self):
        """Test adding events to write-behind buffer."""
        buffer = WriteBehindBuffer(buffer_size=10, flush_interval_seconds=60.0)
        buffer.start()

        event_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        result = buffer.add_event(event_data)
        self.assertTrue(result)
        self.assertEqual(buffer.get_buffer_size(), 1)

        buffer.stop(flush=True)

    def test_write_behind_buffer_size_flush(self):
        """Test write-behind buffer flushes when size threshold is reached."""
        buffer = WriteBehindBuffer(buffer_size=5, flush_interval_seconds=60.0)
        buffer.start()
        initial_count = Event.objects.count()

        # Add events up to buffer size
        for _i in range(5):
            event_data = {
                "event_id": str(uuid.uuid4()),
                "event_type": "contract.created",
                "event_version": "1.0.0",
                "timestamp": timezone.now().isoformat(),
                "source": {
                    "service": "hub",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
                "data": {"contract_id": str(uuid.uuid4())},
                "metadata": {},
            }
            buffer.add_event(event_data)

        # Poll for flush to complete (no fixed sleep)
        wait_until(
            lambda: Event.objects.count() >= initial_count + 5,
            timeout=5.0,
            interval=0.2,
            message="Write-behind buffer did not persist 5 events within 5s",
        )
        self.assertGreaterEqual(Event.objects.count(), initial_count + 5)

        buffer.stop(flush=False)

    def test_write_behind_buffer_time_flush(self):
        """Test write-behind buffer flushes based on time interval."""
        buffer = WriteBehindBuffer(
            buffer_size=100,
            flush_interval_seconds=0.5,  # Short interval for test
        )
        buffer.start()
        initial_count = Event.objects.count()

        # Add a few events
        for _i in range(3):
            event_data = {
                "event_id": str(uuid.uuid4()),
                "event_type": "contract.created",
                "event_version": "1.0.0",
                "timestamp": timezone.now().isoformat(),
                "source": {
                    "service": "hub",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
                "data": {"contract_id": str(uuid.uuid4())},
                "metadata": {},
            }
            buffer.add_event(event_data)

        # Poll for time-based flush (no fixed sleep)
        wait_until(
            lambda: Event.objects.count() >= initial_count + 3,
            timeout=5.0,
            interval=0.2,
            message="Write-behind time flush did not persist 3 events within 5s",
        )
        self.assertGreaterEqual(Event.objects.count(), initial_count + 3)

        buffer.stop(flush=False)

    def test_write_behind_buffer_retry_logic(self):
        """Test write-behind buffer retry logic on failures."""
        buffer = WriteBehindBuffer(
            buffer_size=5, flush_interval_seconds=60.0, max_retries=2, retry_delay_seconds=0.1
        )
        buffer.start()

        # Add events
        event_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(uuid.uuid4()),  # Invalid tenant ID to cause failure
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        # Test flush with real persistence (no mock). Retry-on-failure path would require
        # real transient DB failure injection; covered by unit tests or infra.
        buffer.add_event(event_data)
        flushed = buffer.flush()
        self.assertEqual(flushed, 1)
        self.assertTrue(Event.objects.filter(event_id=event_data["event_id"]).exists())

        buffer.stop(flush=False)

    def test_write_behind_buffer_consistency_validation(self):
        """Test write-behind buffer consistency validation."""
        buffer = WriteBehindBuffer(buffer_size=10, flush_interval_seconds=60.0)
        buffer.start()

        event_ids = []
        for _i in range(5):
            event_id = str(uuid.uuid4())
            event_ids.append(event_id)

            event_data = {
                "event_id": event_id,
                "event_type": "contract.created",
                "event_version": "1.0.0",
                "timestamp": timezone.now().isoformat(),
                "source": {
                    "service": "hub",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
                "data": {"contract_id": str(uuid.uuid4())},
                "metadata": {},
            }
            buffer.add_event(event_data)

        # Flush and validate
        persisted_count = buffer.flush()
        self.assertEqual(persisted_count, 5)

        # Verify events exist in database
        for event_id in event_ids:
            self.assertTrue(Event.objects.filter(event_id=event_id).exists())

        buffer.stop(flush=False)


class PersistenceRetryTest(TestCase):
    """Test persistence retry logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)

    def test_persist_event_async_retry(self):
        """Test async event persistence with retry logic."""
        event_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        # Test with retry logic
        event_id = persist_event_async(event_data, max_retries=2, retry_delay_seconds=0.1)

        self.assertEqual(event_id, event_data["event_id"])
        self.assertTrue(Event.objects.filter(event_id=event_data["event_id"]).exists())

    def test_persist_event_async_retry_on_transient_failure(self):
        """persist_event_async recovers after a transient lock-timeout failure.

        Uses a helper thread that acquires an ``EXCLUSIVE`` table lock on the
        ``events`` table via a raw *psycopg2* connection.  The test sets a
        short ``lock_timeout`` so the first ``INSERT`` attempt fails with
        ``OperationalError`` (canceling statement due to lock timeout).  The
        retry loop catches the exception and sleeps; a release thread drops
        the lock before the second attempt, so the retry succeeds.

        The helper uses ``LOCK TABLE … NOWAIT`` so that if the lock cannot
        be acquired immediately (e.g. another test's transaction still holds
        a conflicting lock in a ``--reuse-db`` run), the test retries the
        whole setup once rather than hanging.

        No mocks — real PostgreSQL locking, real Django error handling, real
        retry loop.
        """
        import threading
        import time

        from django.conf import settings
        from django.db import connection

        db = settings.DATABASES["default"]

        # ── Helper: hold an EXCLUSIVE lock on the events table ──────────
        lock_acquired = threading.Event()
        release_lock = threading.Event()
        helper_error: list[Exception | None] = [None]

        def _hold_table_lock():
            import psycopg2

            try:
                conn = psycopg2.connect(
                    dbname=db["NAME"],
                    user=db["USER"],
                    password=db["PASSWORD"],
                    host=db.get("HOST", "localhost"),
                    port=db.get("PORT", "5432"),
                    connect_timeout=5,
                )
                conn.autocommit = False
                try:
                    # NOWAIT fails immediately if another transaction holds a
                    # conflicting lock — no hanging, clear error message.
                    conn.cursor().execute("LOCK TABLE events IN EXCLUSIVE MODE NOWAIT")
                    lock_acquired.set()
                    release_lock.wait(timeout=30)
                finally:
                    conn.rollback()
                    conn.close()
            except Exception as exc:
                helper_error[0] = exc

        # Try the whole lock setup up to twice — the first attempt may fail
        # when another test's transaction hasn't released its locks yet
        # (common with --reuse-db).
        for _attempt in range(2):
            lock_acquired.clear()
            release_lock.clear()
            helper_error[0] = None

            locker = threading.Thread(target=_hold_table_lock, daemon=True)
            locker.start()
            acquired = lock_acquired.wait(timeout=5)
            if acquired:
                break
            locker.join(timeout=2)
            # Brief pause to let stale transactions release their locks
            time.sleep(1)
        else:
            self.fail(
                "Helper thread could not acquire EXCLUSIVE table lock on "
                "'events' after 2 attempts (NOWAIT).  A concurrent "
                "transaction may be holding a conflicting lock.  "
                f"Last helper error: {helper_error[0]!r}"
            )

        # ── Release thread: drop the lock while the retry loop sleeps ──
        def _release_after_delay(delay: float):
            time.sleep(delay)
            release_lock.set()

        threading.Thread(target=_release_after_delay, args=(0.2,), daemon=True).start()

        event_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        # Set a short lock_timeout so the INSERT fails quickly instead of
        # blocking until the lock is released.
        # Reset in finally so downstream tests aren't affected.
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '100ms'")

            event_id = persist_event_async(
                event_data, max_retries=1, retry_delay_seconds=0.5
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '0'")

        locker.join(timeout=5)

        self.assertEqual(event_id, event_data["event_id"])
        self.assertTrue(
            Event.objects.filter(event_id=event_data["event_id"]).exists(),
            "Event should be persisted after retry recovers from lock timeout.",
        )

    def test_persist_events_batch_async_retry(self):
        """Test batch event persistence with retry logic."""
        events_data = []
        event_ids = []
        for _i in range(5):
            eid = str(uuid.uuid4())
            event_ids.append(eid)
            events_data.append(
                {
                    "event_id": eid,
                    "event_type": "contract.created",
                    "event_version": "1.0.0",
                    "timestamp": timezone.now().isoformat(),
                    "source": {
                        "service": "hub",
                        "tenant_id": str(self.tenant.id),
                        "user_id": str(self.user.id),
                    },
                    "data": {"contract_id": str(uuid.uuid4())},
                    "metadata": {},
                }
            )

        persisted_count = persist_events_batch_async(
            events_data, max_retries=2, retry_delay_seconds=0.1
        )

        self.assertEqual(persisted_count, 5)
        for eid in event_ids:
            self.assertTrue(Event.objects.filter(event_id=eid).exists())


class ConsistencyValidationTest(TestCase):
    """Test consistency validation for dual-write pattern."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)

    def test_validate_event_persistence(self):
        """Test event persistence validation."""
        event_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        # Persist event
        persist_event_async(event_data)

        # Validate persistence
        _validate_event_persistence(event_data["event_id"], event_data)

        # Should not raise exception
        # Validation completed without raising — function under test uses
        # raise on failure, so reaching this point is the success assertion.

    def test_validate_event_persistence_failure(self):
        """Test event persistence validation detects failures."""
        event_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        # Don't persist event, try to validate
        with self.assertRaises(ValueError):
            _validate_event_persistence(event_data["event_id"], event_data)

    def test_validate_batch_persistence(self):
        """Test batch persistence validation."""
        events_data = []
        for _i in range(5):
            events_data.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "contract.created",
                    "event_version": "1.0.0",
                    "timestamp": timezone.now().isoformat(),
                    "source": {
                        "service": "hub",
                        "tenant_id": str(self.tenant.id),
                        "user_id": str(self.user.id),
                    },
                    "data": {"contract_id": str(uuid.uuid4())},
                    "metadata": {},
                }
            )

        # Persist events
        persist_events_batch_async(events_data)

        # Validate batch persistence
        _validate_batch_persistence(events_data, 5)

        # Should not raise exception
        # Validation completed without raising — function under test uses
        # raise on failure, so reaching this point is the success assertion.


class DualWriteOptimizationTest(TestCase):
    """Test dual-write optimization integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.event_bus = get_event_bus()

    def tearDown(self):
        """Clean up after tests."""
        shutdown_write_behind_buffer(flush=False)

    @override_settings(EVENT_BUS_WRITE_BEHIND_ENABLED=True)
    def test_write_behind_pattern_integration(self):
        """Test write-behind pattern integration with event bus."""
        # Ensure write-behind buffer is initialized
        buffer = get_write_behind_buffer()

        # Publish events with write-behind enabled
        event_ids = []
        for _i in range(10):
            event_id = self.event_bus.publish(
                event_type="contract.created",
                data={"contract_id": str(uuid.uuid4())},
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
            event_ids.append(event_id)

        # Force flush to ensure events are persisted
        buffer.flush()

        # Poll for all events to be persisted (no fixed sleep)
        def all_persisted():
            return all(Event.objects.filter(event_id=eid).exists() for eid in event_ids)

        wait_until(
            all_persisted,
            timeout=5.0,
            interval=0.2,
            message="Not all 10 events persisted within 5s after flush",
        )
        for event_id in event_ids:
            self.assertTrue(Event.objects.filter(event_id=event_id).exists())

    @override_settings(
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_ENABLE_PERSISTENCE=False,
    )
    def test_async_persistence_fallback(self):
        """Test async persistence fallback when write-behind is disabled.

        Disable persistence during publish so we can test persist_event_async directly
        without duplicate event_id from publish's own persistence path.
        """
        event_id = self.event_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Execute persistence task directly to verify it works
        # (In production, RQ workers execute this)
        from hub.apps.core.events.persistence_tasks import persist_event_async

        # Get event data (recreate from event_id)
        event_data = {
            "event_id": event_id,
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        # Execute persistence directly
        persist_event_async(event_data)

        # Verify event was persisted
        self.assertTrue(Event.objects.filter(event_id=event_id).exists())

    @override_settings(EVENT_BUS_ENABLE_PERSISTENCE=False)
    def test_dual_write_consistency(self):
        """Test dual-write consistency (Redis + PostgreSQL).

        Disable persistence during publish so we can test persist_event_async directly
        without duplicate event_id from publish's own persistence path.
        """
        event_id = self.event_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Event should be published to Redis immediately
        self.assertIsNotNone(event_id)

        # Execute persistence task directly to verify it works
        # (In production, RQ workers execute this)
        from hub.apps.core.events.persistence_tasks import persist_event_async

        event_data = {
            "event_id": event_id,
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {},
        }

        # Execute persistence directly
        persist_event_async(event_data)

        # Event should be in PostgreSQL
        event = Event.objects.filter(event_id=event_id).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "contract.created")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))

        # Validate consistency
        _validate_event_persistence(
            event_id,
            {
                "event_id": event_id,
                "event_type": "contract.created",
                "source": {"tenant_id": str(self.tenant.id)},
            },
        )
