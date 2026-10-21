"""P0-7 (close-oss-release-conditions, ticket W105-ASYNC-LISTENER-LIVENESS)
— the async-listener heartbeat pins.

The W10.2 staging soak found the failure mode: the worker's RUNNING
listener threads stopped producing deliveries amid stack churn, and
nothing outside the process could tell — thread state and delivery were
unobservable (no liveness signal at all).  These pins hold the fix
contract against REAL Redis, REAL DB rows, and the REAL listener code
(no mocks):

1. While a listener thread listens, a watchdog emits a per-subscriber
   heartbeat every ``EVENT_BUS_LISTENER_HEARTBEAT_INTERVAL`` seconds —
   a timestamp gauge plus a healthy-labeled counter tick — visible
   through the WORKER-STYLE scrape (``prometheus_client.generate_latest()``,
   the exact channel the staging probe curls on the worker /metrics port).
2. Liveness ≠ delivery: the watchdog health-checks the listener thread
   AND its Redis pubsub connection (a PING roundtrip on the listen
   connection itself — ``pubsub.listen()`` is a blocking read, so the
   listen loop cannot emit anything while idle).  A dead thread or a
   dead connection flips the tick to healthy="0" while the timestamp
   keeps advancing (the watchdog itself is alive).
3. ``stop()`` silences the heartbeat — the gauge stops advancing, which
   is the staleness alert's kill signal.

RED against the pre-fix listener: no watchdog, no metrics — the scrape
shows no heartbeat family at all.
"""

from __future__ import annotations

import threading
import time
import uuid

from django.test import TransactionTestCase, override_settings
from prometheus_client import generate_latest

from hub.apps.core.events.bus import EventBus
from hub.apps.core.events.listener import (
    EventBusListener,
    unregister_listener_subscriber,
)
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.core.events.tests.test_w41_event_bus_contract import (
    _clear_namespaces,
    _real_redis,
)
from hub.apps.tenants.models import Tenant

# The heartbeat interval the pins run with — short enough to observe
# several ticks inside a test, long enough to stay far above the
# watchdog's scheduling granularity.
_HEARTBEAT = override_settings(EVENT_BUS_LISTENER_HEARTBEAT_INTERVAL=0.2)

TIMESTAMP_METRIC = "event_listener_heartbeat_timestamp_seconds"
TICKS_METRIC = "event_listener_heartbeat_total"


def _metric_value(scrape: str, metric_name: str, labels: dict[str, str]) -> float | None:
    """Parse one metric family's sample for *labels* out of a Prometheus
    text-format scrape (the exact text the worker /metrics serves)."""
    prefix = metric_name + "{"
    for line in scrape.splitlines():
        if not line.startswith(prefix):
            continue
        label_part, _, value = line.rpartition("} ")
        actual = {}
        for pair in label_part[len(metric_name) + 1 :].split(","):
            if "=" not in pair:
                continue
            key, _, raw = pair.partition("=")
            actual[key.strip()] = raw.strip().strip('"')
        if all(actual.get(k) == v for k, v in labels.items()):
            return float(value)
    return None


class TestListenerHeartbeat(TransactionTestCase):
    """P0-7 heartbeat pins — real listener threads, real Redis, real DB rows.

    TransactionTestCase (not TestCase): the listener + watchdog threads
    run on their OWN DB connections and must SEE the EventSubscription
    rows the test registers (the repo's known cross-thread visibility
    trap).
    """

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.uid = uid
        self.redis_client = _real_redis()
        self.bus = EventBus(redis_client=self.redis_client)
        self.tenant = Tenant.objects.create(name=f"HB {uid}", slug=f"hb-{uid}")
        self.subscriber_name = f"hb_{uid}"
        self.received: list[str] = []
        self.received_event = threading.Event()

        def _handle(event: dict) -> None:
            self.received.append(event["event_id"])
            self.received_event.set()

        subscriber = EventSubscriber(self.subscriber_name, event_bus=self.bus)
        # asset.created is a registered event type — the schema registry
        # rejects unknown types, so the pin rides a real one.
        subscriber.subscribe("asset.created", _handle)
        self.addCleanup(lambda: unregister_listener_subscriber(self.subscriber_name))
        _clear_namespaces(self.redis_client)

    def tearDown(self):
        _clear_namespaces(self.redis_client)

    def _scrape(self) -> str:
        """The worker-style scrape: prometheus_client's default registry,
        the same generate_latest() the worker's /metrics handler serves."""
        return generate_latest().decode()

    def _wait_for(self, predicate, timeout: float = 15.0, description: str = "") -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)  # noqa: sleep-needed — poll interval for a bounded deadline loop
        self.fail(f"timed out waiting for: {description}")

    def test_heartbeat_ticks_while_listening_and_delivery_still_works(self):
        """The watchdog ticks (timestamp advances, healthy=1) while the
        listener is live, visible through the worker-style scrape — and
        the delivery path is untouched (liveness AND delivery)."""
        listener = EventBusListener(bus=self.bus)
        try:
            with _HEARTBEAT:
                started = listener.start()
                self.assertGreaterEqual(started, 1)
                self.assertTrue(
                    listener.wait_until_subscribed(expected=started, timeout=10.0),
                    "listener threads never subscribed to Redis",
                )

                # Two advancing timestamp samples prove the watchdog TICKS
                # (a one-shot value would be a boot stamp, not a heartbeat).
                seen: list[float] = []

                def _sample() -> bool:
                    value = _metric_value(
                        self._scrape(), TIMESTAMP_METRIC, {"subscriber_name": self.subscriber_name}
                    )
                    if value is None:
                        return False
                    if not seen or value > seen[-1]:
                        seen.append(value)
                    return len(seen) >= 2

                self._wait_for(_sample, description="two advancing heartbeat timestamps")

                healthy_ticks = _metric_value(
                    self._scrape(), TICKS_METRIC, {"subscriber_name": self.subscriber_name, "healthy": "1"}
                )
                self.assertIsNotNone(
                    healthy_ticks,
                    f"no healthy heartbeat ticks in scrape: {self._scrape()[:400]}",
                )
                assert healthy_ticks is not None  # narrowing for the static checker
                self.assertGreaterEqual(healthy_ticks, 1)

                # Delivery through the SAME listener stays intact.
                publisher = EventPublisher(service_name="hb_test", tenant_id=str(self.tenant.id))
                event_id = publisher.publish(
                    event_type="asset.created", data={"asset_id": self.uid}
                )
                self.assertIsNotNone(event_id)
                self.assertTrue(
                    self.received_event.wait(timeout=10.0),
                    "consumer never received the published event",
                )
                self.assertEqual(self.received, [event_id])
        finally:
            listener.stop()

    def test_dead_pubsub_connection_flips_ticks_to_unhealthy_then_recovers(self):
        """The W10.2 failure mode: a listener thread that is alive but whose
        pubsub connection died.  The watchdog must report healthy="0" while
        the connection is down and healthy="1" again after the listen loop
        reconnects (the loop's own reconnect backoff)."""
        listener = EventBusListener(bus=self.bus)
        try:
            with _HEARTBEAT:
                started = listener.start()
                self.assertGreaterEqual(started, 1)
                self.assertTrue(
                    listener.wait_until_subscribed(expected=started, timeout=10.0),
                    "listener threads never subscribed to Redis",
                )

                def _healthy_tick(healthy: str) -> bool:
                    return (
                        _metric_value(
                            self._scrape(), TICKS_METRIC,
                            {"subscriber_name": self.subscriber_name, "healthy": healthy},
                        )
                        or 0
                    ) >= 1

                self._wait_for(lambda: _healthy_tick("1"), description="initial healthy tick")

                # Kill the live pubsub connection underneath the listen loop
                # (the churn shape the soak saw).  The loop's finally-branch
                # drops the pubsub from the watchdog's view and backs off
                # before reconnecting — during that window the thread is
                # alive but has NO live connection: the unhealthy tick must
                # appear, and the reconnect must restore healthy=1.
                pubsub = listener._active_pubsubs.get(self.subscriber_name)
                self.assertIsNotNone(pubsub, "no live pubsub to kill")
                pubsub.close()

                self._wait_for(
                    lambda: _healthy_tick("0"),
                    timeout=20.0,
                    description="an unhealthy (healthy=0) tick while the connection is down",
                )
                self._wait_for(
                    lambda: _healthy_tick("1"),
                    timeout=20.0,
                    description="healthy=1 restored after the listen loop reconnects",
                )
        finally:
            listener.stop()

    def test_listener_pubsub_reads_are_blocking_not_reconnect_storm(self):
        """P0-7 finding: the listener's pubsub connection inherited the
        pool's ``socket_timeout`` (5s production / 2s under the test
        client) — ``parse_response(block=True)`` DISCONNECTS + raises
        TimeoutError on every timeout, so a quiet listener re-subscribed
        in a perpetual reconnect storm (the churn amplifier behind the
        W10.2 delivery gaps).  The listen connection must block
        indefinitely: the SAME pubsub stays subscribed across a window
        longer than the old timeout — no reconnect, no re-subscribe."""
        listener = EventBusListener(bus=self.bus)
        try:
            with _HEARTBEAT:
                started = listener.start()
                self.assertGreaterEqual(started, 1)
                self.assertTrue(
                    listener.wait_until_subscribed(expected=started, timeout=10.0),
                    "listener threads never subscribed to Redis",
                )
                pubsub = listener._active_pubsubs.get(self.subscriber_name)
                self.assertIsNotNone(pubsub, "no live pubsub to observe")
                # The old socket_timeout was 2s under the test client — a
                # quiet window of 4s crosses TWO old timeout boundaries.
                deadline = time.monotonic() + 4.0
                while time.monotonic() < deadline:
                    time.sleep(0.1)  # noqa: sleep-needed — quiet-window stride in a bounded loop
                self.assertIs(
                    listener._active_pubsubs.get(self.subscriber_name),
                    pubsub,
                    "the pubsub connection was replaced — the listener is "
                    "re-subscribing in a reconnect storm (socket_timeout "
                    "leaked onto the listen connection)",
                )
                self.assertTrue(
                    pubsub.subscribed,
                    "the original pubsub is no longer subscribed",
                )
        finally:
            listener.stop()

    def test_stop_silences_the_heartbeat(self):
        """stop() must silence the watchdog: the timestamp gauge stops
        advancing — the staleness alert's kill signal."""
        listener = EventBusListener(bus=self.bus)
        with _HEARTBEAT:
            started = listener.start()
            self.assertGreaterEqual(started, 1)
            self.assertTrue(
                listener.wait_until_subscribed(expected=started, timeout=10.0),
                "listener threads never subscribed to Redis",
            )
            self._wait_for(
                lambda: _metric_value(
                    self._scrape(), TIMESTAMP_METRIC, {"subscriber_name": self.subscriber_name}
                )
                is not None,
                description="at least one heartbeat tick",
            )
            listener.stop()

        stopped_value = _metric_value(
            self._scrape(), TIMESTAMP_METRIC, {"subscriber_name": self.subscriber_name}
        )
        self.assertIsNotNone(stopped_value)
        # Observe a window far longer than several heartbeat intervals: a
        # live watchdog would have advanced the gauge many times.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            current = _metric_value(
                self._scrape(), TIMESTAMP_METRIC, {"subscriber_name": self.subscriber_name}
            )
            self.assertEqual(
                current,
                stopped_value,
                "heartbeat advanced after listener.stop() — the watchdog survived the stop",
            )
            time.sleep(0.2)  # noqa: sleep-needed — observation-window stride inside a bounded loop
