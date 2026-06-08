"""
Phase 233.4 — Real ``webhook.test`` event type tests.

Pins the contract that the operator-facing ``POST /webhooks/{id}/test/``
endpoint emits the dedicated ``webhook.test`` event type instead of
mis-emitting ``asset.created`` (the pre-233.4 behaviour). Three
load-bearing observables:

  1. The persisted ``WebhookDelivery`` row carries
     ``event_type='webhook.test'`` (NOT ``asset.created``).
  2. The synthetic payload matches the spec shape:
     ``{event, tenant_id, timestamp, message}``.
  3. The test endpoint delivers REGARDLESS of which event types the
     webhook subscribes to — operators don't need to add
     ``webhook.test`` to ``event_types`` for the Test button to work.

No business-logic mocks; tests run against the real DRF view, the
real ``WebhookDeliveryService._deliver_webhook`` path (with
``WEBHOOK_ASYNC_DELIVERY=False`` so the call returns synchronously),
and the real ``WebhookDelivery`` table.
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


@override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
@pytest.mark.integration
class TestWebhookTestEventType(TestCase):
    """Pins the 233.4 contract end-to-end via the API surface.

    SSRF is disabled in test settings because the webhook URL
    (``https://subscriber.example.com/...``) wouldn't resolve in CI;
    the SSRF check is exercised by separate tests at the validator
    layer. Async delivery is disabled so ``_deliver_webhook`` runs
    synchronously and the test can inspect the delivery row right
    after the API call returns.
    """

    def setUp(self) -> None:
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com",
            password="pass",
            tenant=self.tenant,
            status="ACTIVE",
        )
        # The webhook subscribes ONLY to contract.created — NOT to
        # webhook.test. This is the load-bearing setup: the test
        # endpoint MUST still deliver to this webhook even though it
        # doesn't have webhook.test in its subscriptions.
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name=f"WH {uid}",
            url="https://subscriber.example.com/hooks",
            secret="legacy-plaintext-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _hit_test_endpoint(self):
        return self.client.post(f"/api/v1/webhooks/webhooks/{self.webhook.id}/test/")

    @pytest.mark.integration
    def test_test_endpoint_emits_webhook_test_event_type(self) -> None:
        """REQ 233.4.2 — the persisted delivery row carries event_type='webhook.test'."""
        before = WebhookDelivery.objects.filter(webhook=self.webhook).count()

        resp = self._hit_test_endpoint()
        self.assertEqual(resp.status_code, 200, resp.content)

        deliveries = list(
            WebhookDelivery.objects.filter(webhook=self.webhook)
            .order_by("-created_at")
        )
        self.assertEqual(len(deliveries) - before, 1)

        delivery = deliveries[0]
        self.assertEqual(delivery.event_type, WebhookEventType.WEBHOOK_TEST.value)
        # CRITICAL: NOT the pre-233.4 mis-emission.
        self.assertNotEqual(delivery.event_type, "asset.created")

    @pytest.mark.integration
    def test_synthetic_payload_matches_spec_shape(self) -> None:
        """REQ 233.4.2 — payload data has ``{event, tenant_id, timestamp, message}``.

        The webhook envelope wraps the spec keys under ``data`` so the
        outer envelope can carry routing-level fields
        (``event_type``, ``resource_type``, ``resource_id``,
        envelope ``timestamp``). The spec keys live in
        ``payload["data"]``; the outer envelope itself is stable
        (asserted separately below).
        """
        resp = self._hit_test_endpoint()
        self.assertEqual(resp.status_code, 200)

        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        payload = delivery.payload or {}

        # Outer envelope shape — routing fields the dispatcher reads.
        self.assertEqual(payload.get("event_type"), "webhook.test")
        self.assertEqual(payload.get("resource_type"), "WEBHOOK")
        self.assertRegex(
            str(payload.get("timestamp", "")),
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        )

        # Inner ``data`` block — the REQ 233.4.2 spec keys.
        data = payload.get("data") or {}
        for key in ("event", "tenant_id", "timestamp", "message"):
            self.assertIn(key, data, f"missing key {key} in synthetic payload data")

        self.assertEqual(data["event"], "webhook.test")
        self.assertEqual(data["tenant_id"], str(self.tenant.id))
        self.assertEqual(data["message"], "Test webhook delivery")
        self.assertRegex(
            str(data.get("timestamp", "")),
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        )

    @pytest.mark.integration
    def test_test_endpoint_delivers_to_webhook_not_subscribed_to_webhook_test(
        self,
    ) -> None:
        """The webhook's ``event_types=[CONTRACT_CREATED]`` does NOT include
        ``webhook.test`` — the test endpoint MUST still deliver. This is the
        universal-subscription contract from
        ``Webhook.subscribes_to_event_type``."""
        # Sanity: precondition the test depends on.
        self.assertNotIn(
            WebhookEventType.WEBHOOK_TEST.value,
            [str(t) for t in self.webhook.event_types],
        )

        resp = self._hit_test_endpoint()
        self.assertEqual(resp.status_code, 200, resp.content)

        # Delivery row was created despite the missing subscription.
        self.assertEqual(
            WebhookDelivery.objects.filter(
                webhook=self.webhook,
                event_type=WebhookEventType.WEBHOOK_TEST.value,
            ).count(),
            1,
        )

    @pytest.mark.integration
    def test_test_endpoint_does_not_fan_out_to_other_webhooks(self) -> None:
        """The test endpoint targets THIS webhook only, not the tenant fan-out.

        Earlier ``trigger_webhook(...)`` would deliver to EVERY webhook
        in the tenant subscribed to the event type. With the 233.4 fix
        calling ``_deliver_webhook`` directly, a sibling webhook in the
        same tenant should NOT receive the test payload.
        """
        # Create a sibling webhook in the same tenant that DOES
        # subscribe to webhook.test (so the only thing preventing
        # delivery is the direct-target semantics, not a subscription
        # mismatch).
        sibling = Webhook.objects.create(
            tenant=self.tenant,
            name="Sibling",
            url="https://other.example.com/hooks",
            secret="sibling-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],  # universal subscribes anyway
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        resp = self._hit_test_endpoint()
        self.assertEqual(resp.status_code, 200)

        # The sibling has ZERO deliveries — the test endpoint did not
        # fan out.
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=sibling).count(),
            0,
        )
        # The targeted webhook has exactly ONE delivery.
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=self.webhook).count(),
            1,
        )


@pytest.mark.integration
class TestWebhookTestUniversalSubscription(TestCase):
    """Pins the universal-subscription contract on
    ``Webhook.subscribes_to_event_type`` for ``webhook.test``.

    Unit-level test that doesn't require the API surface — covers the
    contract that makes the 233.4 fix work."""

    def setUp(self) -> None:
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com",
            password="pass",
            tenant=self.tenant,
            status="ACTIVE",
        )

    def _make_webhook(self, event_types):
        return Webhook.objects.create(
            tenant=self.tenant,
            name=f"WH {uuid.uuid4().hex[:6]}",
            url="https://subscriber.example.com/hooks",
            secret="s",
            event_types=event_types,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_subscribes_to_webhook_test_returns_true_regardless_of_event_types(
        self,
    ) -> None:
        """A webhook with ZERO matching subscriptions still subscribes to webhook.test."""
        wh = self._make_webhook([WebhookEventType.CONTRACT_CREATED])
        # Sanity: the webhook does NOT have webhook.test in its list.
        self.assertNotIn("webhook.test", wh.event_types)
        # But subscribes_to_event_type returns True for webhook.test.
        self.assertTrue(wh.subscribes_to_event_type("webhook.test"))

    @pytest.mark.integration
    def test_universal_subscription_is_specific_to_webhook_test(self) -> None:
        """The universal-subscription is NOT a wildcard — only ``webhook.test``."""
        wh = self._make_webhook([WebhookEventType.CONTRACT_CREATED])
        # ``contract.created`` is in the list — subscribes returns True.
        self.assertTrue(wh.subscribes_to_event_type("contract.created"))
        # ``asset.created`` is NOT in the list — subscribes returns False.
        # If the universal-subscription were a wildcard, this would be
        # True. The test pins that the contract is narrow: only
        # webhook.test bypasses the list check.
        self.assertFalse(wh.subscribes_to_event_type("asset.created"))

    @pytest.mark.integration
    def test_subscribes_to_webhook_test_when_only_test_in_list(self) -> None:
        """A webhook that EXPLICITLY includes webhook.test still subscribes
        (no regression — explicit + universal both return True)."""
        wh = self._make_webhook([WebhookEventType.WEBHOOK_TEST])
        self.assertTrue(wh.subscribes_to_event_type("webhook.test"))


@override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
@pytest.mark.integration
class TestDeliverTestEventPublicMethod(TestCase):
    """Phase 233.4.R1 GAP-A — pin the PUBLIC entry-point contract.

    The view layer MUST NOT reach into ``_deliver_webhook`` directly
    (private dispatch primitive subject to refactor). The supported
    public API is ``WebhookDeliveryService.deliver_test_event(webhook)``;
    these tests pin that contract so a future refactor that breaks the
    public method's signature surfaces here rather than as an
    AttributeError in production.
    """

    def setUp(self) -> None:
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com",
            password="pass",
            tenant=self.tenant,
            status="ACTIVE",
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name=f"WH {uid}",
            url="https://subscriber.example.com/hooks",
            secret="legacy-plaintext-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_public_method_exists_with_one_arg_signature(self) -> None:
        """The public method exists and takes exactly one positional arg."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        # `deliver_test_event` is a static method on the service class.
        self.assertTrue(hasattr(WebhookDeliveryService, "deliver_test_event"))
        # It takes exactly one positional parameter (the webhook).
        # Use inspect.signature so the test catches any future signature
        # drift (e.g. someone adding a required `*, actor_user` arg
        # without a default would silently break the view).
        import inspect

        sig = inspect.signature(WebhookDeliveryService.deliver_test_event)
        # One required positional parameter (the webhook).
        required_params = [
            p
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        self.assertEqual(len(required_params), 1)

    @pytest.mark.integration
    def test_public_method_dispatches_a_test_delivery(self) -> None:
        """Calling the public method directly produces a webhook.test delivery row."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        WebhookDeliveryService.deliver_test_event(self.webhook)

        deliveries = list(
            WebhookDelivery.objects.filter(webhook=self.webhook)
        )
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].event_type, "webhook.test")
        # Payload shape matches the spec literal — see
        # ``test_synthetic_payload_matches_spec_shape`` for the
        # envelope/data split rationale.
        payload = deliveries[0].payload or {}
        data = payload.get("data") or {}
        for key in ("event", "tenant_id", "timestamp", "message"):
            self.assertIn(key, data)
