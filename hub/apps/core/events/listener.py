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
from .metrics import event_queue_depth, get_tenant_id
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
            started += 1

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
        """Signal every listener thread and close their pubsub connections."""
        self._stop_event.set()
        for pubsub in list(self._pubsubs):
            with contextlib.suppress(Exception):
                pubsub.close()
        for thread in self._threads:
            thread.join(timeout=join_timeout)
        self._threads = []
        self._pubsubs = []

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
                pubsub = self.bus.redis_client.pubsub(ignore_subscribe_messages=True)
                self._pubsubs.append(pubsub)
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
            except (redis.RedisError, OSError) as exc:
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
