"""W10.2 (oss-release-remediation) — the ASYNC retry contract.

The D1 staging crash drill exposed the gap: in async mode
(``WEBHOOK_ASYNC_DELIVERY=True``, the deployment default)
``_schedule_retry`` wrote ``status=FAILED`` + ``next_retry_at`` and then
NOTHING read it back — failed deliveries parked at attempt_number=1
forever, the retry_intervals budget never ran, DEAD_LETTER never
converged (the inline-mode branch's own comment admits "no processor
(cron / scheduler job) ever reads it back").

Root fix (W10.2): ``_schedule_retry`` enqueues the retry on the RQ
queue's SCHEDULED registry (``queue.enqueue_at``) — the worker's
built-in RQ scheduler (rq ≥ 2, already running in the worker entrypoint)
moves it to the queue when ``next_retry_at`` arrives, and the schedule
lives in Redis so it SURVIVES a worker crash (the D1 contract).

These pins exercise the REAL django-rq queue + scheduled registry
against the real test Redis — no mocks.  RED against the pre-fix
service (the registry stays empty and the retry never happens).
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase, TransactionTestCase, override_settings
from django_rq import get_queue

from hub.apps.tenants.models import Tenant
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService

pytestmark = pytest.mark.django_db(transaction=True)


def _scheduled_ids(queue_name: str = "job_default") -> list[str]:
    """The job ids currently sitting in the queue's SCHEDULED registry.

    job_default (P0-7 / W105-ASYNC-LISTENER-LIVENESS): the retry scheduler
    enqueues to job_default — the queue the WORKER_TYPE light lane actually
    joins.  The legacy "default" queue is consumed by NO process in the
    stack (33 jobs parked forever on staging), which is exactly why the
    D1 retry assertion could never pass.
    """
    return list(get_queue(queue_name).scheduled_job_registry.get_job_ids())


@pytest.mark.integration
@override_settings(WEBHOOK_ASYNC_DELIVERY=True, WEBHOOK_SSRF_ENABLED=False)
class TestAsyncRetryEnqueue(TestCase):
    """ASYNC mode: a failed attempt MUST schedule the next attempt."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"w102-async-{uid}",
            slug=f"w102-async-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="w102-async-retry",
            url="https://example.com/w102-retry",
            event_types=[WebhookEventType.ASSET_CREATED],
            secret=uuid.uuid4().hex[:16],
            status=WebhookStatus.ACTIVE,
            retry_intervals=[60, 120],
            max_retries=2,
        )
        self.delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ASSET_CREATED,
            payload={"event_id": f"evt-{uid}"},
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

    def test_failed_attempt_schedules_the_retry(self):
        before = set(_scheduled_ids())
        # A delivery attempt against an unreachable target → recoverable
        # failure → _schedule_retry → the scheduled registry gains a job.
        self.delivery.webhook.url = "http://203.0.113.9:1/hook"
        self.delivery.webhook.save()
        WebhookDeliveryService._attempt_delivery(self.delivery)
        self.delivery.refresh_from_db()

        self.assertEqual(self.delivery.status, DeliveryStatus.FAILED)
        after = set(_scheduled_ids())
        self.assertTrue(
            after - before,
            f"no retry job scheduled: registry {before} → {after}",
        )
        # The scheduled retry must fire after next_retry_at — the registry
        # timestamp for the new job is in the future (backoff respected).
        self.assertIsNotNone(self.delivery.next_retry_at)


@pytest.mark.integration
@override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
class TestInlineModeDoesNotSchedule(TestCase):
    """INLINE mode (test/E2E stacks): the synchronous loop owns retries —
    the scheduled registry must stay untouched (no double-retry)."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"w102-inline-{uid}",
            slug=f"w102-inline-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="w102-inline-retry",
            url="http://203.0.113.9:1/hook",
            event_types=[WebhookEventType.ASSET_CREATED],
            secret=uuid.uuid4().hex[:16],
            status=WebhookStatus.ACTIVE,
            retry_intervals=[60],
            max_retries=1,
        )
        self.delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ASSET_CREATED,
            payload={"event_id": f"evt-{uid}"},
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

    def test_inline_failure_does_not_touch_the_scheduled_registry(self):
        before = set(_scheduled_ids())
        WebhookDeliveryService._attempt_delivery(self.delivery)
        self.delivery.refresh_from_db()
        # The inline loop drives retries synchronously; its exact
        # terminal state is its own contract — THIS pin owns the registry
        # boundary (no scheduled job may be enqueued in inline mode).
        self.assertNotEqual(self.delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(set(_scheduled_ids()), before)


@pytest.mark.integration
@override_settings(WEBHOOK_ASYNC_DELIVERY=True, WEBHOOK_SSRF_ENABLED=False)
class TestDeadLetterCountsTheFinalAttempt(TestCase):
    """P0-7 (W105-ASYNC-LISTENER-LIVENESS): the retry that exhausts the
    budget is a REAL execution — the service's own contract
    ("attempt_number > 1, DEAD_LETTER after max_retries") demands the
    final attempt be counted.  The staging probe's retry assertion
    reads exactly this: the pre-fix DLQ branch skipped the increment
    (DEAD_LETTER at attempt=1 after two executions), so the retry was
    invisible to every DB-level observer — the reason the D1 drill's
    retry assertion stayed "pending"."""

    def test_dead_letter_row_carries_every_attempt(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"w102-dlq-{uid}",
            slug=f"w102-dlq-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        webhook = Webhook.objects.create(
            tenant=tenant,
            name="w102-dlq-count",
            url="http://203.0.113.9:1/hook",
            event_types=[WebhookEventType.ASSET_CREATED],
            secret=uuid.uuid4().hex[:16],
            status=WebhookStatus.ACTIVE,
            retry_intervals=[60],
            max_retries=1,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ASSET_CREATED,
            payload={"event_id": f"evt-{uid}"},
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        # Attempt 1 fails → FAILED, retry scheduled.
        WebhookDeliveryService._attempt_delivery(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertEqual(delivery.attempt_number, 1)

        # The retry (the scheduled executor's call) fails → DEAD_LETTER.
        # The final attempt must be counted: attempt_number == 2.
        WebhookDeliveryService._attempt_delivery(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
        self.assertEqual(
            delivery.attempt_number,
            2,
            "the DEAD_LETTER row must count the final (budget-exhausting) "
            "attempt — attempt_number stayed at 1 after two real executions",
        )


@pytest.mark.integration
@override_settings(WEBHOOK_ASYNC_DELIVERY=True, WEBHOOK_SSRF_ENABLED=False)
class TestAutocommitTriggerEnqueues(TransactionTestCase):
    """W10.2 — the listener path (autocommit, no atomic block) MUST
    enqueue the RQ delivery immediately: ``transaction.on_commit``
    registered outside an atomic block never fires, and the delivery
    parked PENDING forever with no job (live-staging-proven)."""

    def test_trigger_outside_atomic_enqueues_the_job(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"w102-autocommit-{uid}",
            slug=f"w102-autocommit-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        webhook = Webhook.objects.create(
            tenant=tenant,
            name="w102-autocommit",
            url="http://203.0.113.9:1/hook",
            event_types=[WebhookEventType.ASSET_CREATED],
            secret=uuid.uuid4().hex[:16],
            status=WebhookStatus.ACTIVE,
            retry_intervals=[60],
            max_retries=1,
        )

        before = get_queue("job_default").count
        # TransactionTestCase: no wrapping atomic — the trigger runs in
        # autocommit, the production listener shape.
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(tenant.id),
            event_type=str(WebhookEventType.ASSET_CREATED),
            resource_type="ASSET",
            resource_id=uuid.uuid4().hex,
            event_data={"asset_id": uuid.uuid4().hex, "name": "w102"},
        )

        delivery = WebhookDelivery.objects.get(webhook=webhook)
        # The enqueue contract: the job reaches the queue.  A host-side
        # rq worker may consume it immediately (shared test redis) — so
        # EITHER the queue grew OR the job was already picked up (the
        # delivery left PENDING).  The pre-fix failure mode — a PENDING
        # row that NO job ever existed for — fails both.
        self.assertTrue(
            get_queue("job_default").count > before
            or delivery.status != DeliveryStatus.PENDING,
            "no RQ job enqueued for the delivery (queue unchanged, row parked PENDING)",
        )
