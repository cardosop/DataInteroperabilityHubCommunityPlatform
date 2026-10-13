"""
W4.1 (R2-B3/B4) — event-bus contract pins.

Pins the three W4.1 fixes against REAL Redis, REAL DB rows, and the REAL
bus/listener code (no mocks):

1. **Separate publisher/consumer dedup namespaces** (R2-B3).  The
   pre-fix bus shared ONE Redis namespace (``event:dedup:*``) between
   ``EventPublisher`` (stores the key after publishing) and the consumer
   (checks the key before handling) — every event published through
   ``EventPublisher`` was therefore skipped by every consumer as
   "already processed" (self-dedup), and consumer A's consumption state
   suppressed delivery to consumer B.  The contract now: publisher keys
   live under ``event:sent:*``, consumer keys under
   ``event:cons:{subscriber}:*`` — a publish must never trip a
   consumer's dedup check, and one subscriber's consumption must never
   suppress another's.

2. **on_commit publishing** (R2-B4).  Production-mode publishes inside
   a transaction defer delivery to ``transaction.on_commit`` — a
   rollback must deliver NO phantom event (no Redis message, no
   persisted row, no phantom publisher dedup key).

3. **Listener started in the worker** (R2-B3/B4).  The worker
   entrypoint starts one Redis pub/sub listener thread per active
   subscriber; the end-to-end pin proves publisher → bus → listener →
   consumer delivery through real Redis.
"""

from __future__ import annotations

import contextlib
import threading
import uuid

import redis
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings

from envpolicy import skip_or_fail
from hub.apps.core.events.bus import EventBus
from hub.apps.core.events.deduplication import (
    CONSUMER_DEDUP_NAMESPACE,
    PUBLISHER_DEDUP_NAMESPACE,
    check_event_duplicate,
    generate_deduplication_key,
)
from hub.apps.core.events.listener import (
    EventBusListener,
    start_event_listener,
    stop_event_listener,
    unregister_listener_subscriber,
)
from hub.apps.core.events.models import Event, EventSubscription
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.schema import EventSchema
from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


def _real_redis():
    """Real events Redis client or W16 skip/fail."""
    from django.conf import settings

    try:
        redis_url = getattr(settings, "REDIS_EVENTS_URL", None) or getattr(
            settings, "REDIS_URL", "redis://redis-events-test:6379/0"
        )
        client = redis.from_url(
            redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
    except (ValueError, redis.RedisError) as exc:
        skip_or_fail(f"events Redis unavailable for W4.1 contract pins: {exc}")
        raise
    else:
        return client


def _clear_namespaces(redis_client) -> None:
    """Drop all dedup keys (legacy + sent + cons) before/after each test."""
    for prefix in ("event:dedup:*", "event:sent:*", "event:cons:*"):
        try:
            keys = redis_client.keys(prefix)
            if keys:
                redis_client.delete(*keys)
        except redis.RedisError:
            pass


class TestDedupNamespaceSeparation(TestCase):
    """R2-B3 — publisher and consumer dedup live in separate namespaces."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.uid = uid
        self.redis_client = _real_redis()
        self.bus = EventBus(redis_client=self.redis_client)
        self.tenant = Tenant.objects.create(name=f"W41 {uid}", slug=f"w41-{uid}")
        _clear_namespaces(self.redis_client)

    def tearDown(self):
        _clear_namespaces(self.redis_client)

    def _event(self, event_type: str, data: dict) -> dict:
        return EventSchema.build_event(
            event_type=event_type,
            data=data,
            tenant_id=str(self.tenant.id),
            service_name="w41_test",
        )

    def test_publisher_uses_sent_namespace(self):
        """EventPublisher must dedup under ``event:sent:*``, never the
        shared legacy namespace."""
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}
        publisher = EventPublisher(service_name="w41_test", tenant_id=str(self.tenant.id))

        publisher.publish(event_type=event_type, data=data)

        sent_key = generate_deduplication_key(event_type, data, namespace=PUBLISHER_DEDUP_NAMESPACE)
        is_dup, stored_id = check_event_duplicate(sent_key, redis_client=self.redis_client)
        self.assertTrue(is_dup, "publisher must store its dedup key under event:sent:*")
        self.assertIsNotNone(stored_id)

        # The legacy shared namespace must NOT be written anymore.
        legacy_key = generate_deduplication_key(event_type, data)
        is_dup, _ = check_event_duplicate(legacy_key, redis_client=self.redis_client)
        self.assertFalse(is_dup, "publisher must not write the shared event:dedup:* namespace")

    def test_publisher_dedup_key_does_not_block_consumer(self):
        """The self-dedup root cause: a publish through EventPublisher must
        NOT trip the consumer's dedup check."""
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}
        publisher = EventPublisher(service_name="w41_test", tenant_id=str(self.tenant.id))
        event_id = publisher.publish(event_type=event_type, data=data)

        # The consumer receives the SAME envelope the publisher delivered
        # (the persisted row carries the published event_id).
        event_row = Event.objects.get(event_type=event_type, tenant_id=self.tenant.id)
        self.assertEqual(str(event_row.event_id), event_id)

        handler_called = []
        self.bus._handle_event(
            subscriber_name=f"w41_sub_{self.uid}",
            event=self._event(event_type, data),
            handler=handler_called.append,
        )

        self.assertEqual(len(handler_called), 1)

    def test_consumer_dedup_is_scoped_per_subscriber(self):
        """Consumer dedup must be per-subscriber: subscriber A's consumption
        must not suppress delivery to subscriber B."""
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}
        event = self._event(event_type, data)

        handler_a = []
        handler_b = []
        self.bus._handle_event(
            subscriber_name=f"w41_subA_{self.uid}", event=event, handler=handler_a.append
        )
        self.bus._handle_event(
            subscriber_name=f"w41_subB_{self.uid}", event=event, handler=handler_b.append
        )
        self.assertEqual(len(handler_a), 1)
        self.assertEqual(
            len(handler_b),
            1,
            "subscriber B must process the event subscriber A already consumed "
            "(pre-fix: the shared dedup namespace suppressed cross-subscriber delivery)",
        )

        # Same subscriber twice — still deduplicated.
        handler_a.clear()
        self.bus._handle_event(
            subscriber_name=f"w41_subA_{self.uid}", event=event, handler=handler_a.append
        )
        self.assertEqual(len(handler_a), 0)

    def test_consumer_stores_key_under_cons_namespace(self):
        """After handling, the consumer key must live under
        ``event:cons:{subscriber}:*``."""
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}
        subscriber_name = f"w41_sub_{self.uid}"
        self.bus._handle_event(
            subscriber_name=subscriber_name,
            event=self._event(event_type, data),
            handler=lambda event: None,
        )

        cons_key = generate_deduplication_key(
            event_type, data, namespace=CONSUMER_DEDUP_NAMESPACE, subscriber=subscriber_name
        )
        is_dup, _ = check_event_duplicate(cons_key, redis_client=self.redis_client)
        self.assertTrue(is_dup, "consumer must store its key under event:cons:{subscriber}:*")


class TestEndToEndPublishSubscribe(TransactionTestCase):
    """R2-B3/B4 evidence pin — end-to-end publisher → bus → listener → consumer.

    TransactionTestCase (not TestCase): the listener threads run on their
    OWN DB connections and must SEE the EventSubscription rows the test
    registers — TestCase's outer transaction hides them from sibling
    threads (the repo's known cross-thread visibility trap).
    """

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.uid = uid
        self.redis_client = _real_redis()
        self.bus = EventBus(redis_client=self.redis_client)
        self.tenant = Tenant.objects.create(name=f"W41E2E {uid}", slug=f"w41e2e-{uid}")
        _clear_namespaces(self.redis_client)

    def tearDown(self):
        _clear_namespaces(self.redis_client)

    def test_publish_subscribe_end_to_end_no_self_dedup(self):
        """Publish via EventPublisher (publisher dedup ON) → the worker-style
        listener thread must deliver the event to the consumer exactly once."""
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}

        received = []
        received_event = threading.Event()

        subscriber = EventSubscriber(f"w41_e2e_{self.uid}", event_bus=self.bus)
        subscriber.subscribe(
            event_type, lambda event: (received.append(event["event_id"]), received_event.set())
        )
        self.addCleanup(lambda: unregister_listener_subscriber(f"w41_e2e_{self.uid}"))

        listener = EventBusListener(bus=self.bus)
        try:
            started = listener.start()
            self.assertGreaterEqual(started, 1)
            self.assertTrue(
                listener.wait_until_subscribed(expected=started, timeout=10.0),
                "listener threads never subscribed to Redis",
            )

            publisher = EventPublisher(service_name="w41_test", tenant_id=str(self.tenant.id))
            event_id = publisher.publish(event_type=event_type, data=data)
            self.assertIsNotNone(event_id)

            self.assertTrue(
                received_event.wait(timeout=10.0),
                "consumer never received the published event",
            )
            self.assertEqual(received, [event_id])
        finally:
            listener.stop()

    def test_two_subscribers_both_receive(self):
        """Cross-subscriber delivery through the listener: two subscribers on
        the same pattern must BOTH receive the published event."""
        event_type = "asset.updated"
        data = {"asset_id": str(uuid.uuid4())}

        received_a = []
        received_b = []
        done = threading.Event()

        def _mark(list_: list) -> None:
            list_.append(True)
            if received_a and received_b:
                done.set()

        subscriber_a = EventSubscriber(f"w41_e2e2a_{self.uid}", event_bus=self.bus)
        subscriber_b = EventSubscriber(f"w41_e2e2b_{self.uid}", event_bus=self.bus)
        subscriber_a.subscribe(event_type, lambda event: _mark(received_a))
        subscriber_b.subscribe(event_type, lambda event: _mark(received_b))
        for name in (f"w41_e2e2a_{self.uid}", f"w41_e2e2b_{self.uid}"):
            self.addCleanup(lambda name=name: unregister_listener_subscriber(name))

        listener = EventBusListener(bus=self.bus)
        try:
            started = listener.start()
            self.assertGreaterEqual(started, 2)
            self.assertTrue(
                listener.wait_until_subscribed(expected=started, timeout=10.0),
                "listener threads never subscribed to Redis",
            )

            publisher = EventPublisher(service_name="w41_test", tenant_id=str(self.tenant.id))
            publisher.publish(event_type=event_type, data=data)

            self.assertTrue(
                done.wait(timeout=10.0),
                "not every subscriber received the event",
            )
        finally:
            listener.stop()


# Production-mode overrides: force_sync OFF so the bus/publisher take the
# REAL transaction.on_commit path; async persistence OFF so a committed
# deferred delivery persists the row synchronously inside the callback.
_PROD_MODE = override_settings(
    EVENT_BUS_FORCE_SYNC_PERSISTENCE=False,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)


def _drain_pubsub(pubsub, seconds: float = 1.0) -> list[dict]:
    """Collect any messages that arrive on *pubsub* within *seconds*."""
    import time

    messages = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        message = pubsub.get_message(timeout=0.2)
        if message is not None:
            messages.append(message)
    return messages


def _delivered_for_tenant(messages, tenant_id):
    """Redis message payloads whose source tenant matches *tenant_id*."""
    import json as _json

    matching = []
    for message in messages:
        if message.get("type") not in ("message", "pmessage"):
            continue
        try:
            payload = _json.loads(message["data"])
        except (TypeError, ValueError):
            continue
        if payload.get("source", {}).get("tenant_id") == str(tenant_id):
            matching.append(payload)
    return matching


@_PROD_MODE
class TestRollbackNoPhantomEvent(TransactionTestCase):
    """R2-B4 — a rolled-back transaction must deliver NO phantom event.

    TransactionTestCase (real commits) + the production-mode overrides:
    ``EVENT_BUS_FORCE_SYNC_PERSISTENCE=False`` makes the bus/publisher
    take the REAL ``transaction.on_commit`` path, so an inner
    ``transaction.atomic()`` that rolls back truly discards the deferred
    delivery while a committing atomic delivers it.
    """

    def _setup(self):
        uid = uuid.uuid4().hex[:8]
        self.uid = uid
        self.redis_client = _real_redis()
        self.bus = EventBus(redis_client=self.redis_client)
        self.tenant = Tenant.objects.create(name=f"W41RB {uid}", slug=f"w41rb-{uid}")
        _clear_namespaces(self.redis_client)

    def _teardown(self):
        _clear_namespaces(self.redis_client)

    def test_rollback_delivers_no_phantom_event_direct_bus(self):
        """EventBus.publish inside a rolled-back transaction: no Redis
        message, no persisted row."""
        self._setup()
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}

        pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe("events:asset:created")
        self.addCleanup(pubsub.close)
        try:
            with contextlib.suppress(RuntimeError), transaction.atomic():
                self.bus.publish(
                    event_type=event_type,
                    data=data,
                    tenant_id=str(self.tenant.id),
                )
                raise RuntimeError("intentional rollback")

            # Deferred delivery must never have happened.
            assert not Event.objects.filter(
                event_type=event_type, tenant_id=self.tenant.id
            ).exists(), "phantom Event row persisted for a rolled-back transaction"
            delivered = _delivered_for_tenant(_drain_pubsub(pubsub), self.tenant.id)
            assert delivered == [], (
                f"phantom Redis delivery for a rolled-back transaction: {delivered}"
            )
        finally:
            self._teardown()

    def test_commit_delivers_event_direct_bus(self):
        """Control: the SAME publish must deliver (row + Redis message) once
        the transaction commits — deferral is not loss."""
        self._setup()
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}

        pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe("events:asset:created")
        self.addCleanup(pubsub.close)
        try:
            event_id = None
            with transaction.atomic():
                event_id = self.bus.publish(
                    event_type=event_type,
                    data=data,
                    tenant_id=str(self.tenant.id),
                )
            assert event_id is not None
            assert Event.objects.filter(event_type=event_type).exists(), (
                "committed publish must persist the event row"
            )
            delivered = _delivered_for_tenant(_drain_pubsub(pubsub, seconds=5.0), self.tenant.id)
            assert delivered, "committed publish must deliver the Redis message"
            assert delivered[0]["event_id"] == event_id
        finally:
            self._teardown()

    def test_rollback_discards_publisher_event_and_dedup_key(self):
        """EventPublisher.publish inside a rolled-back transaction: no
        delivery, no phantom publisher dedup key (which would otherwise
        suppress the next legitimate publish of the same logical event)."""
        self._setup()
        event_type = "asset.created"
        data = {"asset_id": str(uuid.uuid4())}
        publisher = EventPublisher(service_name="w41_test", tenant_id=str(self.tenant.id))

        pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe("events:asset:created")
        self.addCleanup(pubsub.close)
        try:
            with contextlib.suppress(RuntimeError), transaction.atomic():
                deferred_id = publisher.publish(event_type=event_type, data=data)
                assert deferred_id is None, (
                    "deferred publisher publish must not fabricate an event id pre-commit"
                )
                raise RuntimeError("intentional rollback")

            delivered = _delivered_for_tenant(_drain_pubsub(pubsub), self.tenant.id)
            assert delivered == [], (
                f"phantom Redis delivery from rolled-back publisher publish: {delivered}"
            )
            sent_key = generate_deduplication_key(
                event_type, data, namespace=PUBLISHER_DEDUP_NAMESPACE
            )
            is_dup, _ = check_event_duplicate(sent_key, redis_client=self.redis_client)
            assert not is_dup, (
                "rolled-back publisher publish stored a phantom dedup key — "
                "the next legitimate publish would be suppressed"
            )

            # The same logical publish now (autocommit, no atomic) must
            # deliver normally — the phantom never suppressed it.
            event_id = publisher.publish(event_type=event_type, data=data)
            assert event_id is not None
            delivered = _delivered_for_tenant(_drain_pubsub(pubsub, seconds=5.0), self.tenant.id)
            assert delivered, "legitimate post-rollback publish was suppressed or lost"
            assert delivered[0]["event_id"] == event_id
        finally:
            self._teardown()


class TestWorkerListenerWiring(TransactionTestCase):
    """The worker entrypoint starts the listener; the kill switch disarms it.

    TransactionTestCase for the same reason as the e2e class: the
    listener threads must see the registered EventSubscription rows.
    """

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.uid = uid
        self.redis_client = _real_redis()
        self.bus = EventBus(redis_client=self.redis_client)
        self.tenant = Tenant.objects.create(name=f"W41W {uid}", slug=f"w41w-{uid}")
        _clear_namespaces(self.redis_client)

    def tearDown(self):
        _clear_namespaces(self.redis_client)

    def test_kill_switch_disables_listener(self):
        from services.worker import main as worker_main

        with override_settings(EVENT_BUS_LISTENER_ENABLED=False):
            self.assertEqual(worker_main.start_event_listener(), 0)

    def test_worker_starts_listener_when_enabled(self):
        from services.worker import main as worker_main

        subscriber_name = f"w41_worker_{self.uid}"
        subscriber = EventSubscriber(subscriber_name, event_bus=self.bus)
        subscriber.subscribe(f"w41.worker.{self.uid}", lambda event: None)
        self.addCleanup(lambda: unregister_listener_subscriber(subscriber_name))
        self.addCleanup(
            lambda: EventSubscription.objects.filter(subscriber_name=subscriber_name).delete()
        )

        with override_settings(EVENT_BUS_LISTENER_ENABLED=True):
            started = worker_main.start_event_listener()
            try:
                self.assertEqual(started, 1)
                listener = start_event_listener()  # idempotent — same instance
                self.assertGreaterEqual(len(listener.threads), 1)
                self.assertTrue(
                    listener.wait_until_subscribed(expected=1, timeout=10.0),
                    "worker-started listener never subscribed to Redis",
                )
            finally:
                stop_event_listener()


class TestInProcessWebhookFallbackGate(TestCase):
    """W4.1 anti-regression: with the worker listener deployed
    (EVENT_BUS_LISTENER_ENABLED), the Phase-226 in-process webhook
    fallbacks must DISARM — delivery is the bus listener's job, and
    firing both paths would double-deliver."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.uid = uid
        self.tenant = Tenant.objects.create(name=f"W41G {uid}", slug=f"w41g-{uid}")
        self.user = User.objects.create_user(
            email=f"w41g-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def _webhook(self, event_type):
        from hub.apps.webhooks.models import Webhook, WebhookStatus

        return Webhook.objects.create(
            tenant=self.tenant,
            name=f"W41G webhook {self.uid}",
            url="http://127.0.0.1:1/hook",
            secret="w41-test-secret",
            event_types=[event_type],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    def test_asset_in_process_trigger_disarms_when_listener_enabled(self):
        """The armed off-path is pinned in test_asset_webhook_delivery
        (triggered == 1 + a delivery row); with the flag ON the helper
        must return 0 and create NOTHING."""
        from hub.apps.webhooks.asset_event_subscriber import trigger_asset_webhook_event
        from hub.apps.webhooks.models import WebhookDelivery

        webhook = self._webhook("asset.created")
        with override_settings(EVENT_BUS_LISTENER_ENABLED=True):
            triggered = trigger_asset_webhook_event(
                event_type="asset.created",
                asset_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
                data_extra={"name": "gated asset"},
            )
        self.assertEqual(triggered, 0)
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=webhook, event_type="asset.created").count(),
            0,
        )

    def test_mesh_in_process_trigger_disarms_when_listener_enabled(self):
        from hub.apps.core.events.service_publishers import DataMeshEventPublisher
        from hub.apps.webhooks.models import WebhookDelivery

        webhook = self._webhook("mesh.domain.created")
        with override_settings(EVENT_BUS_LISTENER_ENABLED=True):
            DataMeshEventPublisher()._trigger_webhook_for_event(
                internal_event_type="mesh.domain.created",
                resource_type="DATA_MESH_DOMAIN",
                resource_id=str(uuid.uuid4()),
                event_data={"domain_id": str(uuid.uuid4())},
                tenant_id=str(self.tenant.id),
            )
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=webhook).count(),
            0,
        )

    def test_virtualization_in_process_trigger_disarms_when_listener_enabled(self):
        from hub.apps.core.events.service_publishers import VirtualizationEventPublisher
        from hub.apps.webhooks.models import WebhookDelivery

        webhook = self._webhook("virtualization.dataset.created")
        with override_settings(EVENT_BUS_LISTENER_ENABLED=True):
            VirtualizationEventPublisher()._trigger_webhook_for_event(
                internal_event_type="virtualization.dataset.created",
                resource_type="VIRTUAL_DATASET",
                resource_id=str(uuid.uuid4()),
                event_data={"virtual_dataset_id": str(uuid.uuid4())},
                tenant_id=str(self.tenant.id),
            )
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=webhook).count(),
            0,
        )
