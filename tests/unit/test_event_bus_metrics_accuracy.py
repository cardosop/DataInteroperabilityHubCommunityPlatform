"""
Unit tests for event bus metrics accuracy.

Tests that metrics accurately reflect event bus operations by calling
real EventBus methods and reading back metric values via _value.get()
(for Counters) or mock_labels.called (for Histograms / publish path).
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

# Use a well-known valid UUID so tenant_id validation passes
_TENANT_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def bus():
    """Create an EventBus with a mock Redis transport."""
    from hub.apps.core.events.bus import EventBus

    with patch("hub.apps.core.events.bus.EventBus._create_redis_client") as mock_redis:
        mock_redis_client = Mock()
        mock_redis_client.publish.return_value = 1
        mock_redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_client

        b = EventBus()
        b.redis_client = mock_redis_client
        yield b


class TestEventBusMetricsAccuracy:
    """Event bus metrics accurately reflect publish / consume / retry counts."""

    # ------------------------------------------------------------------
    # publish-path metrics
    # ------------------------------------------------------------------

    def test_event_publish_rate_accuracy(self, bus):
        """Publishing N events increments event_published_total by N."""
        from hub.apps.core.events.metrics import event_published_total

        labeled = event_published_total.labels(
            event_type="contract.created", status="success", tenant_id=_TENANT_ID
        )
        before = labeled._value.get()

        with patch.object(bus, "_persist_event", return_value=Mock(id="ev-1")):
            for _ in range(5):
                bus.publish("contract.created", {"contract_id": str(uuid.uuid4()), "info": {"name": "test"}},
                            tenant_id=_TENANT_ID)

        assert labeled._value.get() - before == 5

    def test_failed_events_accuracy(self, bus):
        """Publish failure increments event_publish_failed_total via outer except.

        Uses force_sync_persistence=True so _persist_event is called and
        its Exception propagates through the inner except (line 371) to the
        outer except (line 564) which records the failure metric.
        """
        from hub.apps.core.events.metrics import event_publish_failed_total

        bus.force_sync_persistence = True
        with (
            patch.object(event_publish_failed_total, "labels") as mock_labels,
            patch.object(bus, "_persist_event", side_effect=Exception("db down")),
        ):
            mock_counter = Mock()
            mock_labels.return_value = mock_counter
            try:
                bus.publish("contract.created",
                            {"contract_id": str(uuid.uuid4()), "info": {"name": "test"}},
                            tenant_id=_TENANT_ID)
            except Exception:
                pass

        assert mock_labels.called, "event_publish_failed_total.labels must be called"
        mock_counter.inc.assert_called_once()

    def test_metrics_labels_accuracy(self, bus):
        """Published events carry correct label key/value pairs."""
        from hub.apps.core.events.metrics import event_published_total

        captured = {}

        def capture(**kwargs):
            captured.update(kwargs)
            return Mock()

        with (
            patch.object(event_published_total, "labels", side_effect=capture),
            patch.object(bus, "_persist_event", return_value=Mock(id="ev-lbl")),
        ):
            bus.publish("contract.created", {"contract_id": str(uuid.uuid4()), "info": {"name": "test"}},
                        tenant_id=_TENANT_ID, user_id=_TENANT_ID)

        assert captured.get("event_type") == "contract.created"
        assert captured.get("tenant_id") == _TENANT_ID

    # ------------------------------------------------------------------
    # consume-path metrics (verified via _value.get())
    # ------------------------------------------------------------------

    def test_event_consume_rate_accuracy(self, bus):
        """Handling N events increments the consumer counter by N."""
        from hub.apps.core.events.metrics import event_consumed_total

        labeled = event_consumed_total.labels(
            event_type="contract.created", subscriber_name="acc-sub",
            status="success", tenant_id=_TENANT_ID
        )
        before = labeled._value.get()

        event = {
            "event_id": "ev-1", "event_type": "contract.created",
            "timestamp": datetime.now().isoformat(),
            "source": {"tenant_id": _TENANT_ID}, "data": {},
        }
        handler = Mock()
        with (
            patch("hub.apps.core.events.bus.check_event_duplicate", return_value=(False, None)),
            patch("hub.apps.core.events.bus.store_event_id"),
            patch("hub.apps.core.events.bus.mark_event_processing"),
        ):
            for _ in range(3):
                bus._handle_event("acc-sub", event, handler)

        assert labeled._value.get() - before == 3

    def test_event_latency_accuracy(self, bus):
        """Latency metric is called with a non-negative value."""
        from hub.apps.core.events.metrics import event_latency_seconds

        event = {
            "event_id": "ev-lat", "event_type": "contract.created",
            "timestamp": (datetime.now() - timedelta(seconds=2)).isoformat(),
            "source": {"tenant_id": _TENANT_ID}, "data": {},
        }
        handler = Mock()
        with (
            patch("hub.apps.core.events.bus.check_event_duplicate", return_value=(False, None)),
            patch("hub.apps.core.events.bus.store_event_id"),
            patch("hub.apps.core.events.bus.mark_event_processing"),
            patch.object(event_latency_seconds, "labels") as mock_labels,
        ):
            mock_histogram = Mock()
            mock_labels.return_value = mock_histogram
            bus._handle_event("acc-sub", event, handler)

        assert mock_labels.called, "Latency metric labels must be called"
        mock_histogram.observe.assert_called_once()
        observed = mock_histogram.observe.call_args[0][0]
        assert observed >= 0, f"Latency must be non-negative, got {observed}"

    def test_retry_attempts_accuracy(self, bus):
        """Retry counter increments once per retry attempt."""
        from hub.apps.core.events.metrics import event_retry_attempts_total

        labeled = event_retry_attempts_total.labels(
            event_type="contract.created", subscriber_name="acc-sub",
            tenant_id=_TENANT_ID
        )
        before = labeled._value.get()

        event = {
            "event_id": "ev-retry", "event_type": "contract.created",
            "timestamp": datetime.now().isoformat(),
            "source": {"tenant_id": _TENANT_ID}, "data": {},
        }
        handler = Mock(side_effect=Exception("fail"))

        with (
            patch("hub.apps.core.events.bus.check_event_duplicate", return_value=(False, None)),
            patch("hub.apps.core.events.bus.get_retry_policy") as mock_policy,
            patch("hub.apps.core.events.bus._run_with_timeout") as mock_run,
            patch("hub.apps.core.events.bus.mark_event_processing"),
            patch("hub.apps.core.events.bus.store_event_id"),
        ):
            mock_policy.return_value = Mock(
                should_retry=Mock(return_value=True),
                calculate_delay=Mock(return_value=0.0),
                max_retries=3,
            )
            mock_run.side_effect = lambda func, args=(), timeout_seconds=30: func(*args)

            bus._handle_event("acc-sub", event, handler, retry_count=0)

        # Called once per retry attempt: range(0, 3+1) = 4 calls
        assert labeled._value.get() - before == 4

    # ------------------------------------------------------------------
    # DLQ path (needs Django DB for DeadLetterQueue.objects.create)
    # ------------------------------------------------------------------

    @pytest.mark.django_db(transaction=True)
    def test_dlq_size_accuracy(self, bus):
        """DLQ size increments when an event is sent to the dead-letter queue."""
        from hub.apps.core.events.metrics import event_dlq_size

        labeled = event_dlq_size.labels(
            event_type="contract.created", subscriber_name="acc-sub",
            tenant_id=_TENANT_ID
        )
        before = labeled._value.get()

        event = {
            "event_id": "ev-dlq", "event_type": "contract.created",
            "timestamp": datetime.now().isoformat(),
            "source": {"tenant_id": _TENANT_ID}, "data": {},
        }
        handler = Mock(side_effect=Exception("fail"))

        with (
            patch("hub.apps.core.events.bus.check_event_duplicate", return_value=(False, None)),
            patch("hub.apps.core.events.bus.get_retry_policy") as mock_policy,
            patch("hub.apps.core.events.bus._run_with_timeout") as mock_run,
            patch("hub.apps.core.events.bus.mark_event_processing"),
            patch("hub.apps.core.events.bus.store_event_id"),
        ):
            mock_policy.return_value = Mock(
                should_retry=Mock(return_value=False),  # → DLQ path
                max_retries=3,
            )
            mock_run.side_effect = lambda func, args=(), timeout_seconds=30: func(*args)
            bus._handle_event("acc-sub", event, handler, retry_count=0)

        assert labeled._value.get() - before == 1

    # ------------------------------------------------------------------
    # Queue depth (requires _listen loop — value-based assertion works)
    # ------------------------------------------------------------------

    @pytest.mark.django_db(transaction=True)
    def test_queue_depth_accuracy(self, bus):
        """Queue depth is touched via _handle_event (pending → inc, ack → dec).

        Uses patch.object to verify the metric labels are called, avoiding
        gauge-state contamination from other tests in the class.
        """
        from hub.apps.core.events.metrics import event_queue_depth

        event = {
            "event_id": "ev-q3", "event_type": "contract.created",
            "timestamp": datetime.now().isoformat(),
            "source": {"tenant_id": _TENANT_ID}, "data": {},
        }
        handler = Mock()
        with (
            patch.object(event_queue_depth, "labels") as mock_labels,
            patch("hub.apps.core.events.bus.check_event_duplicate", return_value=(False, None)),
            patch("hub.apps.core.events.bus.store_event_id"),
            patch("hub.apps.core.events.bus.mark_event_processing"),
            patch("hub.apps.core.events.bus.acknowledge_event"),
        ):
            mock_gauge = Mock()
            mock_labels.return_value = mock_gauge
            bus._handle_event("acc-sub-qdepth-3", event, handler)

        assert mock_labels.called, "event_queue_depth.labels must be called"
        # inc() on pending + dec() on acknowledge
        assert mock_gauge.inc.call_count + mock_gauge.dec.call_count >= 1
