"""
112.B.3 — Webhook idempotency tests for real payload shape.

Tests that the WebhookDeliveryService correctly deduplicates
deliveries using the event_id / id fields in the payload, and
validates behaviour against the real payload structure produced
by ``_deliver_webhook``.

Uses real database records (TransactionTestCase, no mocks on the
service layer).
"""

import hashlib
import hmac
import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import UserStatus
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class WebhookIdempotencyRealPayloadTest(TestCase):
    """
    End-to-end idempotency tests using the real payload shape
    produced by WebhookDeliveryService.trigger_webhook /
    _deliver_webhook.
    """

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Idempotency Tenant {uid}",
            slug=f"idemp-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"idemp-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Idempotency User",
        )

    def _create_webhook(self, event_types=None):
        """Helper to create a webhook subscription."""
        return Webhook.objects.create(
            tenant=self.tenant,
            name="Idempotency Webhook",
            url="http://localhost:19999/idemp",
            secret="test-secret-key",
            event_types=event_types
            or [
                WebhookEventType.ODPS_CREATED,
            ],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    # ------------------------------------------------------------------
    # 1. Real payload shape validation
    # ------------------------------------------------------------------

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_payload_has_required_top_level_keys(self):
        """
        The payload stored in WebhookDelivery must contain the
        canonical keys: event_type, resource_type, resource_id,
        timestamp, data.
        """
        webhook = self._create_webhook()
        resource_id = str(uuid.uuid4())
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "status": "ACTIVE",
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=resource_id,
            event_data=event_data,
        )

        delivery = WebhookDelivery.objects.filter(
            webhook=webhook,
        ).first()
        self.assertIsNotNone(delivery)

        payload = delivery.payload
        required_keys = {
            "event_type",
            "resource_type",
            "resource_id",
            "timestamp",
            "data",
        }
        missing = required_keys - payload.keys()
        self.assertEqual(
            len(missing), 0,
            f"Missing required payload keys: {missing}",
        )
        self.assertEqual(
            payload["event_type"],
            WebhookEventType.ODPS_CREATED,
        )
        self.assertEqual(payload["resource_type"], "ODPS")
        self.assertEqual(payload["resource_id"], resource_id)
        self.assertIsInstance(payload["data"], dict)
        self.assertEqual(
            payload["data"]["contract_id"],
            event_data["contract_id"],
        )

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_payload_data_matches_event_data_exactly(self):
        """
        The ``data`` field in the payload must be the exact
        event_data dict passed by the caller.
        """
        webhook = self._create_webhook()
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "asset_id": str(uuid.uuid4()),
            "changes": {"name": "new-name"},
            "status": "DRAFT",
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        delivery = WebhookDelivery.objects.filter(
            webhook=webhook,
        ).first()
        self.assertIsNotNone(delivery)
        assert delivery is not None
        self.assertEqual(delivery.payload["data"], event_data)

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_event_id_promoted_to_top_level(self):
        """
        When event_data contains ``event_id``, it must be
        promoted to the top-level payload so that the
        idempotency JSONField lookup (payload__event_id) works.
        """
        webhook = self._create_webhook()
        event_id = str(uuid.uuid4())
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "event_id": event_id,
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        delivery = WebhookDelivery.objects.filter(
            webhook=webhook,
        ).first()
        self.assertIsNotNone(delivery)
        assert delivery is not None
        self.assertEqual(
            delivery.payload.get("event_id"),
            event_id,
            "event_id must be promoted from event_data to top-level payload",
        )

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_id_normalised_to_event_id(self):
        """
        When event_data contains ``id`` but not ``event_id``,
        it must be normalised to ``event_id`` at the top-level
        payload so the idempotency query is consistent.
        """
        webhook = self._create_webhook()
        fallback_id = str(uuid.uuid4())
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "id": fallback_id,
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        delivery = WebhookDelivery.objects.filter(
            webhook=webhook,
        ).first()
        self.assertIsNotNone(delivery)
        assert delivery is not None
        self.assertEqual(
            delivery.payload.get("event_id"),
            fallback_id,
            "id must be normalised to event_id in the payload",
        )
        # Original 'id' key must NOT appear at top level
        self.assertNotIn(
            "id",
            delivery.payload,
            "Top-level 'id' key should not be set; use 'event_id' only",
        )

    # ------------------------------------------------------------------
    # 2. Idempotency via event_id
    # ------------------------------------------------------------------

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_duplicate_event_id_skipped(self):
        """
        When a payload contains ``event_id`` and a previous
        delivery with the same event_id already has SUCCESS
        status, the duplicate must be silently skipped.
        """
        webhook = self._create_webhook()
        event_id = str(uuid.uuid4())

        # First delivery — manually seed a SUCCESS record with
        # event_id at top level (as the service now creates).
        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={
                "event_type": WebhookEventType.ODPS_CREATED,
                "resource_type": "ODPS",
                "resource_id": str(uuid.uuid4()),
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "contract_id": str(uuid.uuid4()),
                    "event_id": event_id,
                },
                "event_id": event_id,
            },
            signature="sig-first",
            status=DeliveryStatus.SUCCESS,
            attempt_number=1,
        )

        # Second trigger with same event_id — must be skipped
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data={
                "contract_id": str(uuid.uuid4()),
                "event_id": event_id,
            },
        )

        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
        )
        self.assertEqual(
            deliveries.count(),
            1,
            "Duplicate event_id should not create a second delivery record",
        )

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_duplicate_id_field_skipped(self):
        """
        Idempotency also works via the ``id`` field when
        ``event_id`` is absent — ``id`` is normalised to
        ``event_id`` in the payload.
        """
        webhook = self._create_webhook()
        fallback_id = str(uuid.uuid4())

        # Pre-existing successful delivery — event_id was
        # normalised from ``id`` to ``event_id`` at creation time.
        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={
                "event_type": WebhookEventType.ODPS_CREATED,
                "resource_type": "ODPS",
                "resource_id": str(uuid.uuid4()),
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "contract_id": str(uuid.uuid4()),
                    "id": fallback_id,
                },
                "event_id": fallback_id,
            },
            signature="sig-first",
            status=DeliveryStatus.SUCCESS,
            attempt_number=1,
        )

        # Trigger again with id — should be skipped
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data={
                "contract_id": str(uuid.uuid4()),
                "id": fallback_id,
            },
        )

        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
        )
        self.assertEqual(deliveries.count(), 1)

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_failed_delivery_does_not_block_retry(self):
        """
        A previously FAILED delivery must NOT trigger the
        idempotency guard — the retry should be allowed.
        """
        webhook = self._create_webhook()
        event_id = str(uuid.uuid4())

        # Pre-existing FAILED delivery
        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={
                "event_type": WebhookEventType.ODPS_CREATED,
                "resource_type": "ODPS",
                "resource_id": str(uuid.uuid4()),
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "contract_id": str(uuid.uuid4()),
                    "event_id": event_id,
                },
                "event_id": event_id,
            },
            signature="sig-failed",
            status=DeliveryStatus.FAILED,
            attempt_number=1,
        )

        # Retry trigger — should NOT be skipped because the
        # prior delivery was FAILED, not SUCCESS
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data={
                "contract_id": str(uuid.uuid4()),
                "event_id": event_id,
            },
        )

        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
        )
        self.assertEqual(
            deliveries.count(),
            2,
            "FAILED delivery should not block retry — a new delivery record should be created",
        )

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_no_event_id_always_delivers(self):
        """
        When the payload has neither ``event_id`` nor ``id``,
        idempotency is bypassed and every trigger creates a
        new delivery.
        """
        webhook = self._create_webhook()
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "status": "ACTIVE",
        }

        # Trigger twice with no event_id
        for _ in range(2):
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
        )
        self.assertEqual(
            deliveries.count(),
            2,
            "Without event_id, each trigger must create a separate delivery",
        )

    # ------------------------------------------------------------------
    # 3. Cross-webhook isolation
    # ------------------------------------------------------------------

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_idempotency_scoped_to_webhook(self):
        """
        A successful delivery to webhook A must NOT prevent
        delivery of the same event_id to webhook B.
        """
        webhook_a = self._create_webhook()
        webhook_b = Webhook.objects.create(
            tenant=self.tenant,
            name="Second Webhook",
            url="http://localhost:19998/second",
            secret="secret-b",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        event_id = str(uuid.uuid4())
        resource_id = str(uuid.uuid4())

        # Successful delivery to webhook A
        WebhookDelivery.objects.create(
            webhook=webhook_a,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={
                "event_type": WebhookEventType.ODPS_CREATED,
                "resource_type": "ODPS",
                "resource_id": resource_id,
                "timestamp": timezone.now().isoformat(),
                "data": {"contract_id": str(uuid.uuid4())},
                "event_id": event_id,
            },
            signature="sig-a",
            status=DeliveryStatus.SUCCESS,
            attempt_number=1,
        )

        # Trigger for the same tenant — webhook B should still
        # get a delivery (idempotency is per-webhook)
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=resource_id,
            event_data={
                "contract_id": str(uuid.uuid4()),
                "event_id": event_id,
            },
        )

        # webhook_a: 1 (pre-existing) + 1 (skipped = still 1),
        # webhook_b: 1 (new)
        self.assertEqual(
            WebhookDelivery.objects.filter(
                webhook=webhook_a,
            ).count(),
            1,
        )
        self.assertEqual(
            WebhookDelivery.objects.filter(
                webhook=webhook_b,
            ).count(),
            1,
        )

    # ------------------------------------------------------------------
    # 4. Signature verification against real payload
    # ------------------------------------------------------------------

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_signature_matches_sorted_json_payload(self):
        """
        The stored signature must match HMAC-SHA256 of the
        payload serialised with ``json.dumps(sort_keys=True)``.
        """
        webhook = self._create_webhook()
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "status": "ACTIVE",
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        delivery = WebhookDelivery.objects.filter(
            webhook=webhook,
        ).first()
        self.assertIsNotNone(delivery)
        assert delivery is not None

        payload_json = json.dumps(
            delivery.payload,
            sort_keys=True,
        )
        expected_sig = hmac.new(
            webhook.decrypted_secret.encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        self.assertEqual(delivery.signature, expected_sig)

    # ------------------------------------------------------------------
    # 5. Payload query field correctness
    # ------------------------------------------------------------------

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_json_field_query_event_id_works(self):
        """
        The idempotency guard uses
        ``payload__event_id=event_id`` — verify this JSONField
        lookup actually matches the stored payload structure.
        """
        webhook = self._create_webhook()
        event_id = str(uuid.uuid4())

        # Create a delivery with event_id at top-level payload
        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={
                "event_type": WebhookEventType.ODPS_CREATED,
                "resource_type": "ODPS",
                "resource_id": str(uuid.uuid4()),
                "timestamp": timezone.now().isoformat(),
                "data": {"contract_id": str(uuid.uuid4())},
                "event_id": event_id,
            },
            signature="test-sig",
            status=DeliveryStatus.SUCCESS,
            attempt_number=1,
        )

        # The JSONField lookup must find it
        exists = WebhookDelivery.objects.filter(
            webhook=webhook,
            status=DeliveryStatus.SUCCESS,
            payload__event_id=event_id,
        ).exists()
        self.assertTrue(
            exists,
            "payload__event_id lookup must match top-level event_id in the JSON payload",
        )

        # Different event_id must NOT match
        exists_other = WebhookDelivery.objects.filter(
            webhook=webhook,
            status=DeliveryStatus.SUCCESS,
            payload__event_id=str(uuid.uuid4()),
        ).exists()
        self.assertFalse(exists_other)
