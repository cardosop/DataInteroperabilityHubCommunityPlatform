"""Comprehensive webhook model tests — Phase 100.5"""

import hashlib
import hmac
import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.webhooks.encryption import decrypt_secret, encrypt_secret
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class WebhookModelTest(TestCase):
    """Test Webhook model lifecycle and methods."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE"
        )

    def test_webhook_default_status_is_active(self):
        """A webhook created without explicit status defaults to ACTIVE."""
        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="Default",
            url="https://example.com",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            created_by=self.user,
        )
        self.assertEqual(wh.status, WebhookStatus.ACTIVE)

    def test_webhook_invalid_status_raises_validation_error(self):
        """Saving a webhook with an invalid status string raises ValidationError."""
        from django.core.exceptions import ValidationError

        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="BadStatus",
            url="https://example.com",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        wh.status = "INVALID_STATUS"
        with self.assertRaises(ValidationError):
            wh.full_clean()

    def test_secret_encryption_on_save(self):
        """Secret is encrypted when saved to DB — plaintext never stored."""
        plaintext = "plaintext-secret-abc"
        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="Enc",
            url="https://example.com",
            secret=plaintext,
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        wh.refresh_from_db()
        # Verify the stored value is encrypted (always differs from plaintext)
        self.assertNotEqual(wh.secret, plaintext)
        self.assertNotIn(plaintext, wh.secret)
        # Verify round-trip: decrypted_secret returns the original plaintext
        self.assertEqual(wh.decrypted_secret, plaintext)

    def test_decrypted_secret_returns_original(self):
        """decrypted_secret property returns original plaintext."""
        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="Dec",
            url="https://example.com",
            secret="my-secret-123",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        wh.refresh_from_db()
        self.assertEqual(wh.decrypted_secret, "my-secret-123")

    def test_generate_signature_hmac_sha256(self):
        """generate_signature produces valid HMAC-SHA256."""
        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="Sig",
            url="https://example.com",
            secret="secret-key",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        payload = json.dumps({"event": "test"}, sort_keys=True)
        sig = wh.generate_signature(payload)
        expected = hmac.new(b"secret-key", payload.encode("utf-8"), hashlib.sha256).hexdigest()
        self.assertEqual(sig, expected)

    def test_event_type_subscription_check(self):
        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="Sub",
            url="https://example.com",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED, WebhookEventType.ASSET_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.assertTrue(wh.subscribes_to_event_type("contract.created"))
        self.assertFalse(wh.subscribes_to_event_type("ingestion.completed"))

    def test_default_retry_intervals(self):
        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="Retry",
            url="https://example.com",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.assertEqual(wh.retry_intervals, [1, 5, 30, 300, 1800])


class WebhookDeliveryModelTest(TestCase):
    """Test WebhookDelivery model."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE"
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="WH",
            url="https://example.com",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    def test_delivery_default_status_is_pending(self):
        """A WebhookDelivery created without explicit status defaults to PENDING."""
        d = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="contract.created",
            payload={"t": 1},
            signature="sig",
        )
        self.assertEqual(d.status, DeliveryStatus.PENDING)

    def test_delivery_status_cannot_be_null(self):
        """Attempting to set status=None raises IntegrityError (DB-enforced)."""
        from django.db import IntegrityError, transaction

        d = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="contract.created",
            payload={"t": 1},
            signature="sig",
            status=DeliveryStatus.PENDING,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            WebhookDelivery.objects.filter(pk=d.pk).update(status=None)

    def test_delivery_dead_letter_is_terminal(self):
        """When attempt_number reaches max_retries, _schedule_retry sets DEAD_LETTER."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        d = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="contract.created",
            payload={"t": 1},
            signature="sig",
            status=DeliveryStatus.FAILED,
            attempt_number=self.webhook.max_retries,
        )
        WebhookDeliveryService._schedule_retry(d)
        d.refresh_from_db()
        self.assertEqual(d.status, DeliveryStatus.DEAD_LETTER)
        self.assertIsNone(d.next_retry_at)

    def test_delivery_tracks_response_body(self):
        d = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="contract.created",
            payload={"t": 1},
            signature="sig",
            status=DeliveryStatus.FAILED,
            response_body='{"error": "internal"}',
            http_status_code=500,
        )
        self.assertEqual(d.response_body, '{"error": "internal"}')
        self.assertEqual(d.http_status_code, 500)


class EncryptionTest(TestCase):
    """Test encryption utility functions."""

    def test_encrypt_and_decrypt_roundtrip(self):
        plaintext = "my-webhook-secret-abc123"
        encrypted = encrypt_secret(plaintext)
        # encrypted value differs from plaintext regardless of backend (Fernet or KMS)
        self.assertNotEqual(encrypted, plaintext)
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_idempotent(self):
        """Encrypting already encrypted value returns it unchanged."""
        plaintext = "test"
        encrypted = encrypt_secret(plaintext)
        double_encrypted = encrypt_secret(encrypted)
        self.assertEqual(encrypted, double_encrypted)

    def test_decrypt_legacy_plaintext(self):
        """Values without v1: prefix are treated as legacy plaintext."""
        self.assertEqual(decrypt_secret("legacy-secret"), "legacy-secret")
