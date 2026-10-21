"""
Integration tests for asset webhook delivery via the asset event subscriber.

Pins the Phase 226 G11 bridge: ``asset.created`` / ``asset.updated`` /
``asset.activated`` events published on the event bus MUST reach
``WebhookDeliveryService`` through ``AssetEventSubscriber`` — without it
webhooks registered for ``asset.created`` receive zero delivery rows
(b7 #43/#44: webhook-delivery E2E timed out with "Last: null").

Uses the real HTTP server (TestWebhookServer); no mocks. Mirrors
test_mesh_webhook_delivery.py (wait_until polling, WEBHOOK_ASYNC_DELIVERY off).
"""

import contextlib
import http.server
import threading
import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.core.events.models import EventSubscription
from hub.apps.core.events.schema import EventSchema
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User
from hub.apps.webhooks import tasks
from hub.apps.webhooks.asset_event_subscriber import (
    ASSET_WEBHOOK_EVENT_TYPES,
    AssetEventSubscriber,
    get_asset_event_subscriber,
    trigger_asset_webhook_event,
)
from hub.apps.webhooks.models import DeliveryStatus, Webhook, WebhookDelivery, WebhookStatus
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer
from tests.utils.polling import wait_until

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(WEBHOOK_ASYNC_DELIVERY=False)
class AssetWebhookDeliveryTest(TestCase):
    """Test asset webhook delivery through the event subscriber."""

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        pass

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        # Registration test leaves subscription rows behind — clean them
        # so the handler tests below run against a clean subscription set.
        EventSubscription.objects.filter(subscriber_name="webhook_service_assets").delete()

    def _asset_event(self, event_type: str, asset_id: str) -> dict:
        """Build an event envelope in the bus's EventSchema shape."""
        return EventSchema.build_event(
            event_type=event_type,
            data={"asset_id": asset_id},
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            service_name="asset_service",
        )

    def test_subscriber_registers_all_asset_event_types(self):
        """The subscriber must cover every subscribable asset event type."""
        subscriber = get_asset_event_subscriber()
        self.assertIsInstance(subscriber, AssetEventSubscriber)
        registered = set(
            EventSubscription.objects.filter(
                subscriber_name="webhook_service_assets", is_active=True
            ).values_list("event_type_pattern", flat=True)
        )
        self.assertEqual(registered, set(ASSET_WEBHOOK_EVENT_TYPES))
        self.assertEqual(
            ASSET_WEBHOOK_EVENT_TYPES,
            ["asset.created", "asset.updated", "asset.activated"],
        )

    def test_asset_created_event_delivers_to_subscribed_webhook(self):
        """asset.created on the bus → delivery row + sink receipt via the subscriber."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Asset Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=["asset.created"],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            asset_id = str(uuid.uuid4())
            event = self._asset_event("asset.created", asset_id)

            # Route the event the same way the bus does: through the
            # subscriber handler (the missing bridge under test).
            AssetEventSubscriber()._handle_asset_event(event)

            wait_until(
                lambda: (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="asset.created"
                    ).count()
                    >= 1
                ),
                timeout=5.0,
                message="asset.created delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(webhook=webhook, event_type="asset.created")
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(
                delivery.status,
                DeliveryStatus.SUCCESS,
                msg=f"delivery did not succeed (attempts={delivery.attempt_number}, "
                f"http={delivery.http_status_code}): {delivery.error_message}",
            )
            self.assertEqual(delivery.payload["resource_id"], asset_id)
            self.assertEqual(delivery.payload["data"]["asset_id"], asset_id)
            self.assertIsNotNone(delivery.signature)
            received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received), 1)

    def test_asset_updated_event_delivers_to_subscribed_webhook(self):
        """asset.updated on the bus → delivery row via the subscriber."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Asset Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=["asset.updated"],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            asset_id = str(uuid.uuid4())
            event = self._asset_event("asset.updated", asset_id)
            # Include the schema's optional change fields to pin the payload shape.
            event["data"]["changes"] = {"status": {"old": "DRAFT", "new": "ACTIVE"}}

            AssetEventSubscriber()._handle_asset_event(event)

            wait_until(
                lambda: (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="asset.updated"
                    ).count()
                    >= 1
                ),
                timeout=5.0,
                message="asset.updated delivery not recorded",
            )
            delivery = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="asset.updated"
            ).first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["resource_id"], asset_id)

    def test_non_subscribed_webhook_receives_no_delivery(self):
        """A webhook not subscribed to the event type must stay silent."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Asset Events Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key",
            event_types=["asset.activated"],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        asset_id = str(uuid.uuid4())
        event = self._asset_event("asset.created", asset_id)

        AssetEventSubscriber()._handle_asset_event(event)

        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=webhook).count(),
            0,
        )

    def test_in_process_trigger_delivers_without_bus_listener(self):
        """The in-process helper must deliver an asset.* event WITHOUT any
        bus listener — the live-stack contract (no process runs
        EventBus.start_listening(), so the subscriber-only bridge left
        delivery rows at zero; webhook-delivery E2E "Last: null").
        """
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Asset Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=["asset.created"],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            asset_id = str(uuid.uuid4())

            triggered = trigger_asset_webhook_event(
                event_type="asset.created",
                asset_id=asset_id,
                tenant_id=str(self.tenant.id),
                data_extra={"name": "in-process asset"},
            )

            self.assertEqual(triggered, 1)
            wait_until(
                lambda: (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="asset.created"
                    ).count()
                    >= 1
                ),
                timeout=5.0,
                message="in-process asset.created delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(webhook=webhook, event_type="asset.created")
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["resource_id"], asset_id)
            self.assertEqual(delivery.payload["data"]["asset_id"], asset_id)
            received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received), 1)

    def test_in_process_trigger_is_fail_open(self):
        """A webhook-trigger failure must never raise into the asset
        operation that published the event."""
        with patch(
            "hub.apps.webhooks.asset_event_subscriber.WebhookDeliveryService.trigger_webhook",
            side_effect=RuntimeError("webhook infra down"),
        ):
            triggered = trigger_asset_webhook_event(
                event_type="asset.created",
                asset_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
            )
        self.assertEqual(triggered, 0)

    def test_deliver_webhook_task_delivers_with_tenant_context(self):
        """The RQ task must attempt delivery when called with the tenant id
        (worker connections have no request-scoped tenant context; the
        tenant_context wrap is what makes the RLS-scoped webhook join
        resolvable under a RLS-enforcing DB role)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Asset Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=["asset.created"],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type="asset.created",
                payload={"resource_id": str(uuid.uuid4())},
                status=DeliveryStatus.PENDING,
                attempt_number=0,
            )

            tasks.deliver_webhook(str(delivery.id), str(self.tenant.id))

            delivery.refresh_from_db()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertGreater(delivery.attempt_number, 0)

    def test_workflow_enqueue_triggers_in_process_delivery(self):
        """The asset-creation workflow must invoke the in-process trigger
        after publishing (the live-stack delivery path — no bus listener)."""
        from types import SimpleNamespace

        from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow

        fake_asset = SimpleNamespace(id=uuid.uuid4())
        # Patch the SOURCE module: asset_creation imports the trigger
        # lazily inside ``_enqueue_asset_event``
        # (``from hub.apps.webhooks.asset_event_subscriber import …``),
        # so the attribute never exists on the workflow module and
        # patching there raises AttributeError.
        with (
            patch(
                "hub.apps.core.events.publisher.EventPublisher.publish",
                return_value=str(uuid.uuid4()),
            ) as mock_publish,
            patch(
                "hub.apps.webhooks.asset_event_subscriber.trigger_asset_webhook_event"
            ) as mock_trigger,
        ):
            AssetCreationWorkflow._enqueue_asset_event(
                event="asset.created",
                asset=fake_asset,
                tenant=self.tenant,
                user_id=str(self.user.id),
                data_extra={"name": "workflow asset"},
            )

        mock_publish.assert_called_once()
        mock_trigger.assert_called_once()
        kwargs = mock_trigger.call_args.kwargs
        self.assertEqual(kwargs["event_type"], "asset.created")
        self.assertEqual(kwargs["asset_id"], str(fake_asset.id))
        self.assertEqual(kwargs["tenant_id"], str(self.tenant.id))
        self.assertEqual(kwargs["data_extra"]["name"], "workflow asset")

    def test_persistent_503_converges_to_dead_letter_inline(self):
        """Inline delivery (WEBHOOK_ASYNC_DELIVERY=False) must execute the
        per-webhook retry budget synchronously: FAILED → retries → DEAD_LETTER
        with attempt_number > 1 (the E2E forced-failure contract, b7 #44 —
        without the inline retry loop in _deliver_webhook the row parks at
        attempt_number=1 forever because no processor reads next_retry_at).
        """
        with TestWebhookServer(response_status=503) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Asset Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=["asset.created"],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
                max_retries=3,
                retry_intervals=[1, 1, 1],
            )
            asset_id = str(uuid.uuid4())
            event = self._asset_event("asset.created", asset_id)

            AssetEventSubscriber()._handle_asset_event(event)

            wait_until(
                lambda: (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="asset.created"
                    ).count()
                    >= 1
                ),
                timeout=5.0,
                message="asset.created delivery not recorded",
            )
            delivery = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="asset.created"
            ).first()
            self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
            self.assertGreater(delivery.attempt_number, 1)
            self.assertEqual(delivery.http_status_code, 503)
            # The sink must have recorded every retry attempt (503 each).
            received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received), 4)  # initial + 3 retries

    def test_missing_tenant_skips_delivery(self):
        """Events without a tenant in the source envelope are ignored."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Asset Events Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key",
            event_types=["asset.created"],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "asset.created",
            "data": {"asset_id": str(uuid.uuid4())},
            "source": {},
            "timestamp": timezone.now().isoformat(),
        }
        AssetEventSubscriber()._handle_asset_event(event)
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=webhook).count(),
            0,
        )


class _RedirectingHTTPServer(http.server.HTTPServer):
    """Scripted server that answers POSTs with a fixed status + optional
    Location header, counting the requests it received."""

    def __init__(self, location, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.location_target = location
        self.request_log: list[int] = []


class _RedirectHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.request_log.append(1)
        self.send_response(self.server.response_status)
        if self.server.location_target:
            self.send_header("Location", self.server.location_target)
        self.end_headers()

    # 302 rewrites POST→GET on the following hop; count both.
    do_GET = do_POST

    def log_message(self, format, *args):
        pass


class WebhookRedirectChainTest(TestCase):
    """W1.13 — a validated hop-2 redirect is followed; a FURTHER 3xx
    (hop-3+) is blocked outright (single-redirect policy), so an
    unvalidated target can never be reached."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant
        )

    @override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
    def test_hop3_redirect_chain_blocked(self):
        # hop3 returns 200; hop2 302→hop3; hop1 (the webhook URL) 302→hop2.
        # Pre-fix the follow auto-followed hop2→hop3 (follow_redirects=True
        # default) and the delivery landed on hop3 unvalidated.
        hop3 = _RedirectingHTTPServer(None, ("localhost", 0), _RedirectHandler)
        hop3.response_status = 200
        hop2 = _RedirectingHTTPServer(
            f"http://localhost:{hop3.server_address[1]}/x",
            ("localhost", 0),
            _RedirectHandler,
        )
        hop2.response_status = 302
        hop1 = _RedirectingHTTPServer(
            f"http://localhost:{hop2.server_address[1]}/x",
            ("localhost", 0),
            _RedirectHandler,
        )
        hop1.response_status = 302
        threads = [
            threading.Thread(target=server.serve_forever, daemon=True)
            for server in (hop1, hop2, hop3)
        ]
        for thread in threads:
            thread.start()
        try:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Redirect Chain Webhook",
                url=f"http://localhost:{hop1.server_address[1]}/hook",
                secret="test-secret-key",
                event_types=["asset.created"],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type="asset.created",
                payload={"resource_id": str(uuid.uuid4())},
                status=DeliveryStatus.PENDING,
                attempt_number=0,
            )

            tasks.deliver_webhook(str(delivery.id), str(self.tenant.id))

            delivery.refresh_from_db()
            self.assertIn("redirect chain", (delivery.error_message or ""))
            self.assertEqual(len(hop1.request_log), 1)
            self.assertEqual(len(hop2.request_log), 1)
            self.assertEqual(
                len(hop3.request_log),
                0,
                "hop-3 target must never receive a request",
            )
            # W1.19 — convention 8: the enforcement emits its audit event.
            from hub.apps.audit.models import AuditEvent

            self.assertTrue(
                AuditEvent.objects.filter(
                    action="WEBHOOK_DELIVERY_SSRF_BLOCKED",
                ).exists(),
                "hop-3 SSRF block must emit its audit event",
            )
        finally:
            for server in (hop1, hop2, hop3):
                with contextlib.suppress(Exception):
                    server.shutdown()
                    server.server_close()
