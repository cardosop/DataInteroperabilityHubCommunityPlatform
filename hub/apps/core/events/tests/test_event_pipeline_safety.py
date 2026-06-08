"""
112.C.2 — Event pipeline safety tests.

Proves:
1. Slow handler → TimeoutError after EVENT_HANDLER_TIMEOUT_SECONDS
2. Handler timeout → event sent to DLQ (not lost, no infinite retry)
3. Handler exception → bounded retries then DLQ
4. Non-retryable error → immediate DLQ (no retry)
5. JSON decode error → DLQ (not silently dropped)
6. _run_with_timeout uses structlog logger (no NameError crash)
"""
import time
import uuid

import pytest
from django.test import TestCase, override_settings
from unittest.mock import Mock, MagicMock, patch

from hub.apps.core.events.bus import EventBus, _run_with_timeout
from hub.apps.core.events.models import DeadLetterQueue
from hub.apps.core.events.retry_policy import RetryPolicy, RetryStrategy


pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class SlowHandlerTimeoutTest(TestCase):
    """Proves that slow handlers are timed out — not left running
    indefinitely."""

    def test_run_with_timeout_raises_on_slow_handler(self):
        """
        _run_with_timeout must raise TimeoutError when the
        handler exceeds the configured timeout.
        """
        def slow_handler(*args):
            time.sleep(10)

        with self.assertRaises(TimeoutError) as ctx:
            _run_with_timeout(
                slow_handler, args=(), timeout_seconds=0.3,
            )
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_run_with_timeout_returns_on_fast_handler(self):
        """Fast handlers complete normally."""
        def fast_handler(*args):
            return "ok"

        result = _run_with_timeout(
            fast_handler, args=(), timeout_seconds=5,
        )
        self.assertEqual(result, "ok")

    def test_run_with_timeout_propagates_handler_exception(self):
        """Handler exceptions propagate to the caller."""
        def bad_handler(*args):
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            _run_with_timeout(
                bad_handler, args=(), timeout_seconds=5,
            )

    def test_run_with_timeout_no_nameerror_on_timeout(self):
        """
        The timeout path formerly crashed with ``NameError`` on ``logging``
        (a missing import in the ``_run_with_timeout`` module).  This
        regression test proves the timeout raises the expected
        ``TimeoutError``, not ``NameError``.
        """
        def slow(*args):
            time.sleep(10)

        with self.assertRaises(TimeoutError):
            _run_with_timeout(slow, args=(), timeout_seconds=0.3)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    EVENT_HANDLER_TIMEOUT_SECONDS=0.3,
    EVENT_BUS_MAX_RETRIES=2,
)
class HandlerTimeoutDLQTest(TestCase):
    """Proves that timed-out handlers send the event to the DLQ."""

    def setUp(self):
        self.redis_client = Mock()
        self.redis_client.get.return_value = None
        self.redis_client.set.return_value = True
        self.redis_client.setex.return_value = True
        self.redis_client.setnx.return_value = True
        self.redis_client.pipeline.return_value = MagicMock(
            __enter__=MagicMock(
                return_value=MagicMock(
                    execute=MagicMock(return_value=[True, True]),
                    get=MagicMock(return_value=None),
                    set=MagicMock(return_value=True),
                    setex=MagicMock(return_value=True),
                )
            ),
            __exit__=MagicMock(return_value=False),
        )
        self.bus = EventBus(redis_client=self.redis_client)

    @patch("hub.apps.core.events.bus._run_with_timeout")
    def test_slow_handler_event_lands_in_dlq(self, mock_run):
        """
        When the handler exceeds EVENT_HANDLER_TIMEOUT_SECONDS,
        after exhausting retries the event must land in the DLQ.

        Patches ``_run_with_timeout`` to raise ``TimeoutError`` without
        relying on real threading timing (which is non-deterministic in
        test environments and can mask timeout paths when the daemon
        thread completes early).
        """
        mock_run.side_effect = TimeoutError("Event handler timed out after 0.3s")

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "timestamp": "2026-03-20T00:00:00+00:00",
            "data": {"contract_id": str(uuid.uuid4())},
            "source": {"tenant_id": str(uuid.uuid4())},
        }

        dlq_before = DeadLetterQueue.objects.count()

        self.bus._handle_event(
            "test-subscriber", event, lambda e: None,
        )

        dlq_after = DeadLetterQueue.objects.count()
        self.assertEqual(
            dlq_after, dlq_before + 1,
            "Timed-out event must land in the DLQ",
        )
        entry = DeadLetterQueue.objects.order_by("-created_at").first()
        self.assertIn("timed out", entry.error_message.lower())
        self.assertEqual(entry.subscriber, "test-subscriber")
        self.assertEqual(
            entry.event["event_id"], event["event_id"],
        )


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    EVENT_HANDLER_TIMEOUT_SECONDS=5,
)
class BoundedRetryTest(TestCase):
    """Proves retries are bounded — no infinite retry loop."""

    def setUp(self):
        self.redis_client = Mock()
        self.redis_client.get.return_value = None
        self.redis_client.set.return_value = True
        self.redis_client.setex.return_value = True
        self.redis_client.setnx.return_value = True
        self.redis_client.pipeline.return_value = MagicMock(
            __enter__=MagicMock(
                return_value=MagicMock(
                    execute=MagicMock(return_value=[True, True]),
                    get=MagicMock(return_value=None),
                    set=MagicMock(return_value=True),
                    setex=MagicMock(return_value=True),
                )
            ),
            __exit__=MagicMock(return_value=False),
        )
        self.bus = EventBus(redis_client=self.redis_client)

    def test_retryable_error_retries_then_dlq(self):
        """
        A retryable error retries up to max_retries then sends
        to DLQ — never loops infinitely.

        DEFAULT_RETRY_POLICY.max_retries = 3 (module-level
        constant, not affected by override_settings), so the
        handler runs 1 initial + 3 retries = 4 total calls.
        """
        call_count = 0

        def failing_handler(event):
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"transient failure #{call_count}")

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "timestamp": "2026-03-20T00:00:00+00:00",
            "data": {"contract_id": str(uuid.uuid4())},
            "source": {"tenant_id": str(uuid.uuid4())},
        }

        # Patch retry delay to zero for test speed
        with patch(
            "hub.apps.core.events.retry_policy.RetryPolicy"
            ".calculate_delay",
            return_value=0,
        ):
            self.bus._handle_event(
                "test-subscriber", event, failing_handler,
            )

        # DEFAULT max_retries=3 → attempts 0,1,2,3 = 4 calls
        self.assertEqual(call_count, 4)

        # Crucially: call_count is bounded (not infinite)
        self.assertLessEqual(call_count, 10)

        # Event must be in DLQ
        entry = DeadLetterQueue.objects.order_by(
            "-created_at"
        ).first()
        self.assertIsNotNone(entry)
        self.assertIn("transient failure", entry.error_message)
        self.assertEqual(entry.retry_count, 3)

    def test_non_retryable_error_immediate_dlq(self):
        """
        Non-retryable errors (ValidationError) go straight to
        DLQ without any retry.
        """
        call_count = 0

        def validation_handler(event):
            nonlocal call_count
            call_count += 1
            from rest_framework.exceptions import ValidationError
            raise ValidationError("bad data")

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "timestamp": "2026-03-20T00:00:00+00:00",
            "data": {"contract_id": str(uuid.uuid4())},
            "source": {"tenant_id": str(uuid.uuid4())},
        }

        self.bus._handle_event(
            "test-subscriber", event, validation_handler,
        )

        # Only 1 call — no retries for non-retryable errors
        self.assertEqual(call_count, 1)

        entry = DeadLetterQueue.objects.order_by(
            "-created_at"
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.subscriber, "test-subscriber")


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class JSONDecodeErrorDLQTest(TestCase):
    """Proves that unparseable messages go to DLQ instead of
    being silently dropped."""

    def setUp(self):
        self.redis_client = Mock()
        self.redis_client.get.return_value = None
        self.redis_client.set.return_value = True
        self.redis_client.setex.return_value = True
        self.redis_client.setnx.return_value = True
        self.bus = EventBus(redis_client=self.redis_client)

    def test_corrupt_json_sent_to_dlq(self):
        """
        When _listen receives a message with invalid JSON, it
        must send a synthetic event to the DLQ.
        """
        subscriber_name = "test-sub"

        corrupt_data = b"NOT VALID JSON {"

        # Build the message dict that Redis pubsub would deliver
        message = {
            "type": "message",
            "data": corrupt_data,
            "channel": b"events:contract.created",
            "pattern": None,
        }

        # Create a mock pubsub that yields one message then stops
        mock_pubsub = MagicMock()
        mock_pubsub.listen.return_value = iter([message])

        handler = Mock()

        dlq_before = DeadLetterQueue.objects.count()

        self.bus._listen(mock_pubsub, subscriber_name, handler)

        dlq_after = DeadLetterQueue.objects.count()
        self.assertEqual(
            dlq_after, dlq_before + 1,
            "Corrupt JSON must be sent to DLQ, not silently "
            "dropped",
        )

        entry = DeadLetterQueue.objects.order_by(
            "-created_at"
        ).first()
        self.assertEqual(entry.event_type, "UNPARSEABLE")
        self.assertIn(
            "JSON decode error", entry.error_message,
        )
        self.assertEqual(entry.subscriber, subscriber_name)

        # Handler should NOT have been called
        handler.assert_not_called()


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class RetryPolicySafetyTest(TestCase):
    """Proves retry policy boundaries are respected."""

    def test_should_retry_false_after_max_retries(self):
        """
        RetryPolicy.should_retry returns False once attempt
        reaches max_retries.
        """
        policy = RetryPolicy(
            max_retries=3,
            strategy=RetryStrategy.FIXED,
            base_delay=0,
        )
        self.assertTrue(policy.should_retry(0))
        self.assertTrue(policy.should_retry(1))
        self.assertTrue(policy.should_retry(2))
        self.assertFalse(policy.should_retry(3))
        self.assertFalse(policy.should_retry(100))

    def test_calculate_delay_capped_at_max_delay(self):
        """
        Exponential backoff must be capped at max_delay — no
        unbounded growth.
        """
        policy = RetryPolicy(
            max_retries=50,
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=60.0,
            multiplier=2.0,
            jitter=False,
        )
        # 2^30 would be huge, but must be capped at 60
        delay = policy.calculate_delay(30)
        self.assertLessEqual(delay, 60.0)

    def test_non_retryable_error_types(self):
        """
        ValidationError, PermissionDenied, AuthenticationFailed,
        NotFound — all must return should_retry=False.
        """
        policy = RetryPolicy(max_retries=10)

        from rest_framework.exceptions import (
            ValidationError,
            PermissionDenied,
            AuthenticationFailed,
            NotFound,
        )
        for exc_cls in (
            ValidationError, PermissionDenied,
            AuthenticationFailed, NotFound,
        ):
            exc = exc_cls("test")
            self.assertFalse(
                policy.should_retry(0, exc),
                f"{exc_cls.__name__} must NOT be retried",
            )
