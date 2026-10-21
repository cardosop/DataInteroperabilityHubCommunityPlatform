"""
Event Bus Listener (W4.1, R2-B3/B4)

Starts the Redis pub/sub listener threads in the WORKER process.

The stack historically had NO process running ``EventBus.start_listening()``
— bus-subscribed consumers (webhooks, mesh, virtualization, notifications)
were structurally dead and the asset workflow worked around it with
in-process delivery (Phase 226 G11).  This module closes that gap: the
worker boots one listener thread per active subscriber and routes every
message through ``EventBus._handle_event``, so the consumer-side machinery
(dedup in the ``event:cons:{subscriber}:*`` namespace, ack tracking,
retries, DLQ) applies unchanged.

Deployment contract: ``EVENT_BUS_LISTENER_ENABLED`` must be set in BOTH
the worker and api services of a deployment — the API reads the same flag
to disarm its in-process webhook delivery fallbacks (Phase 226 G11) so a
deployment with the worker listener never double-delivers.

Heartbeat (P0-7, W105-ASYNC-LISTENER-LIVENESS): every started listener
is watched by a heartbeat watchdog — one tick per subscriber every
``EVENT_BUS_LISTENER_HEARTBEAT_INTERVAL`` seconds (default 30s) stamping
``event_listener_heartbeat_timestamp_seconds`` + the healthy-labeled
``event_listener_heartbeat_total`` counter on the worker /metrics
endpoint.  Liveness ≠ delivery: the watchdog health-checks the thread
AND its pubsub connection; staleness of the gauge is the kill signal
(alert: ``EventBusListenerHeartbeatStale``).  The W10.2 soak's failure
mode — RUNNING listener threads that stopped producing deliveries —
is observable through it.

Delivery semantics: Redis pub/sub is at-least-once.  Per-subscriber
consumer dedup narrows duplicates, but a concurrent check-then-store race
across listener replicas can still deliver twice — the ack machinery
(``mark_event_pending``/``acknowledge_event``) records that.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from typing import TYPE_CHECKING, Any

import redis
import structlog
from django.conf import settings
from django.db.utils import DatabaseError, InterfaceError, ProgrammingError

from .acknowledgment import mark_event_pending
from .bus import EventBus, get_event_bus
from .metrics import (
    event_listener_heartbeat_timestamp_seconds,
    event_listener_heartbeat_total,
    event_queue_depth,
    get_tenant_id,
)
from .models import EventSubscription

if TYPE_CHECKING:
    from .subscriber import EventSubscriber

logger = structlog.get_logger(__name__)

# subscriber_name -> EventSubscriber instance (registered at construction).
_listener_subscribers: dict[str, EventSubscriber] = {}


def register_listener_subscriber(subscriber: EventSubscriber) -> None:
    """Register a subscriber instance for worker-listener dispatch.

    Idempotent per subscriber name (last instance wins — the worker boots
    one instance per app ``ready()`` hook).
    """
    _listener_subscribers[subscriber.subscriber_name] = subscriber


def unregister_listener_subscriber(subscriber_name: str) -> None:
    """Remove a subscriber from the listener registry (test cleanup)."""
    _listener_subscribers.pop(subscriber_name, None)


def get_listener_subscribers() -> dict[str, EventSubscriber]:
    """Snapshot of the registered subscribers."""
    return dict(_listener_subscribers)


class EventBusListener:
    """
    Starts one daemon thread per active, handler-bearing subscriber.

    Each thread subscribes to the subscriber's active Redis channels,
    routes matching messages to the subscriber's registered handler
    through ``EventBus._handle_event``, and reconnects with exponential
    backoff when the Redis connection drops.
    """

    def __init__(self, bus: EventBus | None = None):
        self.bus = bus or get_event_bus()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._pubsubs: list[redis.client.PubSub] = []
        # P0-7 heartbeat watchdog state: the LIVE pubsub per subscriber
        # (the reconnect loop replaces it), guarded so the watchdog can
        # snapshot it while listen threads churn.
        self._active_pubsubs: dict[str, redis.client.PubSub] = {}
        self._pubsubs_lock = threading.Lock()
        self._thread_subscribers: dict[str, threading.Thread] = {}
        self._heartbeat_thread: threading.Thread | None = None

    @property
    def threads(self) -> list[threading.Thread]:
        """The live listener threads (populated by :meth:`start`)."""
        return self._threads

    def start(self) -> int:
        """Start one listener thread per active subscriber.  Returns the
        number of threads started (0 when nothing is registered)."""
        # Subscriptions deferred during AppConfig.ready() must be flushed
        # first — the listener reads the persisted EventSubscription rows.
        self.bus._flush_deferred_subscriptions()

        started = 0
        for subscriber_name, subscriber in list(_listener_subscribers.items()):
            if not subscriber.handlers:
                logger.debug(
                    "event_listener_skipped_no_handlers",
                    subscriber_name=subscriber_name,
                )
                continue
            active_patterns = self._active_patterns(subscriber_name)
            if not active_patterns:
                logger.debug(
                    "event_listener_skipped_no_active_subscriptions",
                    subscriber_name=subscriber_name,
                )
                continue
            thread = threading.Thread(
                target=self._listen,
                args=(subscriber_name, subscriber),
                daemon=True,
                name=f"event-listener-{subscriber_name}",
            )
            thread.start()
            self._threads.append(thread)
            self._thread_subscribers[subscriber_name] = thread
            started += 1

        if started:
            # P0-7 (W105-ASYNC-LISTENER-LIVENESS): the watchdog stamps
            # liveness for every started subscriber (see _heartbeat_loop).
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True,
                name="event-listener-heartbeat",
            )
            self._heartbeat_thread.start()

        logger.info("event_listener_started", subscribers=started)
        return started

    def wait_until_subscribed(self, expected: int = 1, timeout: float = 10.0) -> bool:
        """Block until at least *expected* pubsubs have subscribed to Redis.

        redis-py 7.1 exposes ONE ``subscribed`` flag covering both
        ``subscribe`` and ``psubscribe`` (there is no separate
        ``psubscribed`` property).
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            subscribed = sum(1 for ps in self._pubsubs if ps.subscribed)
            if subscribed >= expected:
                return True
            time.sleep(0.05)
        return False

    def stop(self, join_timeout: float = 10.0) -> None:
        """Signal every listener thread, stop the heartbeat watchdog, and
        close the pubsub connections."""
        self._stop_event.set()
        # Join the watchdog first — it only reads state and its next
        # wait() wakes on the stop event, so it exits promptly.
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=join_timeout)
            self._heartbeat_thread = None
        for pubsub in list(self._pubsubs):
            with contextlib.suppress(Exception):
                pubsub.close()
        for thread in self._threads:
            thread.join(timeout=join_timeout)
        self._threads = []
        self._pubsubs = []
        self._thread_subscribers = {}
        self._active_pubsubs = {}

    def _active_patterns(self, subscriber_name: str) -> list[str]:
        """Active event-type patterns for *subscriber_name* (DB-backed)."""
        try:
            return list(
                EventSubscription.objects.filter(
                    subscriber_name=subscriber_name, is_active=True
                ).values_list("event_type_pattern", flat=True)
            )
        except (DatabaseError, InterfaceError, ProgrammingError) as exc:
            # DB unavailable — nothing to listen for.
            logger.warning(
                "event_listener_subscription_lookup_failed",
                subscriber_name=subscriber_name,
                error=str(exc),
            )
            return []

    def _listen(self, subscriber_name: str, subscriber: EventSubscriber) -> None:
        """Blocking listen loop for one subscriber, with reconnect backoff."""
        backoff = 1.0
        while not self._stop_event.is_set():
            pubsub = None
            try:
                patterns = self._active_patterns(subscriber_name)
                if not patterns:
                    return
                pubsub = self._create_pubsub()
                with self._pubsubs_lock:
                    self._pubsubs.append(pubsub)
                    self._active_pubsubs[subscriber_name] = pubsub
                for pattern in patterns:
                    channel = self.bus._get_channel(pattern)
                    if "*" in pattern:
                        pubsub.psubscribe(channel)
                    else:
                        pubsub.subscribe(channel)

                backoff = 1.0  # connected — reset the reconnect backoff
                for message in pubsub.listen():
                    if self._stop_event.is_set():
                        break
                    if message.get("type") not in ("message", "pmessage"):
                        continue
                    self._handle_message(subscriber_name, subscriber, message)
            except (redis.RedisError, OSError, ValueError) as exc:
                # ValueError included (P0-7): redis-py's socket reader
                # raises ValueError ("I/O operation on closed file") when
                # the connection is closed concurrently (stop(), a peer
                # closing the socket) — a transport failure, not a
                # programming error: reconnect.
                if self._stop_event.is_set():
                    break
                logger.warning(
                    "event_listener_reconnecting",
                    subscriber_name=subscriber_name,
                    error=str(exc),
                    backoff_seconds=backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            finally:
                if pubsub is not None:
                    with contextlib.suppress(Exception):
                        pubsub.close()
                    with contextlib.suppress(ValueError):
                        self._pubsubs.remove(pubsub)
                    with self._pubsubs_lock:
                        if self._active_pubsubs.get(subscriber_name) is pubsub:
                            self._active_pubsubs.pop(subscriber_name, None)

    def _create_pubsub(self) -> redis.client.PubSub:
        """A PubSub whose read connection BLOCKS indefinitely.

        P0-7 (W105-ASYNC-LISTENER-LIVENESS): the pool's ``socket_timeout``
        (5s production) leaked onto the listen connection —
        ``parse_response(block=True)`` disconnects + raises TimeoutError
        on every timeout, so a quiet listener re-subscribed in a
        perpetual reconnect storm (the churn amplifier behind the W10.2
        delivery gaps; the heartbeat pins caught it live).  Pub/sub reads
        must block; connection liveness is the health-check machinery's
        job (``health_check_interval`` rides along in the copied kwargs).
        """
        pool = self.bus.redis_client.connection_pool
        kwargs = dict(pool.connection_kwargs)
        kwargs["socket_timeout"] = None
        pubsub_pool = redis.ConnectionPool(**kwargs)
        return redis.client.PubSub(
            connection_pool=pubsub_pool, ignore_subscribe_messages=True
        )

    def _heartbeat_loop(self) -> None:
        """P0-7 watchdog: one liveness tick per subscriber per interval.

        The listen loop itself can emit nothing while idle (a blocking
        read) — this watchdog is the liveness signal.  Staleness of the
        timestamp gauge is the kill signal: a wedged loop, a dead thread,
        or a dead watchdog process all stop the ticks.
        """
        while not self._stop_event.is_set():
            interval = getattr(settings, "EVENT_BUS_LISTENER_HEARTBEAT_INTERVAL", 30.0)
            if self._stop_event.wait(max(interval, 0.1)):
                break
            self._heartbeat_tick()

    def _heartbeat_tick(self) -> None:
        """One tick: health-check every subscriber, stamp the metrics.

        healthy = thread alive AND its live pubsub accepts the
        health-check PING (``pubsub.check_health()`` writes the PING on
        the listen connection — the listener consumes the PONG and the
        health-check machinery ignores it).  No live pubsub (the
        reconnect backoff window) is unhealthy — exactly the W10.2
        failure mode.  The timestamp ticks REGARDLESS of health: a fresh
        gauge with healthy=0 rate means the connection died; a STALE
        gauge means the watchdog itself died.  Metric emission must never
        break the watchdog, so each operation is exception-guarded.
        """
        now = time.time()
        with self._pubsubs_lock:
            snapshot = dict(self._active_pubsubs)
        for subscriber_name, thread in self._thread_subscribers.items():
            healthy = thread.is_alive()
            pubsub = snapshot.get(subscriber_name)
            if pubsub is None:
                healthy = False
            elif healthy:
                try:
                    pubsub.check_health()
                except (RuntimeError, redis.RedisError, OSError):
                    # RuntimeError = the pubsub connection is unset (never
                    # subscribed); RedisError/OSError = the health-check
                    # PING could not be written — either way: unhealthy.
                    healthy = False
            with contextlib.suppress(Exception):
                event_listener_heartbeat_timestamp_seconds.labels(
                    subscriber_name=subscriber_name
                ).set(now)
            with contextlib.suppress(Exception):
                event_listener_heartbeat_total.labels(
                    subscriber_name=subscriber_name,
                    healthy="1" if healthy else "0",
                ).inc()

    def _handle_message(
        self,
        subscriber_name: str,
        subscriber: EventSubscriber,
        message: dict[str, Any],
    ) -> None:
        """Route one Redis message to the subscriber's matching handler."""
        raw = message.get("data", "")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            # Mirror bus._listen: unparseable messages go to the DLQ so
            # they are not silently lost.
            logger.exception(
                "event_decode_error",
                subscriber_name=subscriber_name,
                error=str(exc),
            )
            self.bus._send_to_dlq(
                subscriber_name,
                {"event_type": "UNPARSEABLE", "raw_data": raw[:4096]},
                f"JSON decode error: {exc}",
            )
            return

        event_type = event.get("event_type", "")
        for pattern, handler in subscriber.handlers.items():
            if self._pattern_matches(pattern, event_type):
                event_id = event.get("event_id")
                if event_id:
                    mark_event_pending(
                        event_id,
                        subscriber_name,
                        event_type,
                        redis_client=self.bus.redis_client,
                    )
                    tenant_label = get_tenant_id(event.get("source", {}).get("tenant_id"))
                    with contextlib.suppress(
                        Exception
                    ):  # metric update must never break event handling
                        event_queue_depth.labels(
                            event_type=event_type,
                            subscriber_name=subscriber_name,
                            tenant_id=tenant_label,
                        ).inc()
                self.bus._handle_event(subscriber_name, event, handler)
                return

        logger.debug(
            "event_listener_no_handler_match",
            subscriber_name=subscriber_name,
            event_type=event_type,
        )

    @staticmethod
    def _pattern_matches(pattern: str, event_type: str) -> bool:
        """Simple wildcard matching (``*`` at the end), same as the bus."""
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type


# The process-wide listener instance (started by the worker entrypoint).
_event_listener: EventBusListener | None = None


def start_event_listener() -> EventBusListener | None:
    """Start the worker listener when ``EVENT_BUS_LISTENER_ENABLED`` is on.

    Idempotent: returns the existing listener when already started.
    Returns ``None`` when the kill switch disarms it.
    """
    global _event_listener  # noqa: PLW0603 — module-singleton lazy init (repo idiom)
    if _event_listener is not None:
        return _event_listener
    if not getattr(settings, "EVENT_BUS_LISTENER_ENABLED", False):
        logger.debug("event_listener_disabled", reason="EVENT_BUS_LISTENER_ENABLED unset")
        return None
    _event_listener = EventBusListener()
    _event_listener.start()
    return _event_listener


def stop_event_listener() -> None:
    """Stop the listener threads (worker shutdown / test cleanup)."""
    global _event_listener  # noqa: PLW0603 — module-singleton teardown (repo idiom)
    if _event_listener is not None:
        _event_listener.stop()
        _event_listener = None
