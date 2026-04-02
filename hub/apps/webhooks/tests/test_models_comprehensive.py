"""Comprehensive webhook model tests — Phase 100.5"""
import uuid
import hmac
import hashlib
import json
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.webhooks.models import Webhook, WebhookDelivery, WebhookStatus, WebhookEventType, DeliveryStatus
from hub.apps.webhooks.encryption import encrypt_secret, decrypt_secret
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class WebhookModelTest(TestCase):
    """Test Webhook model lifecycle and methods."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE")

    def test_webhook_status_active(self):
        wh = Webhook.objects.create(tenant=self.tenant, name="Active", url="https://example.com", secret="mysecret", event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.ACTIVE, created_by=self.user)
        self.assertEqual(wh.status, WebhookStatus.ACTIVE)

    def test_webhook_status_paused(self):
        wh = Webhook.objects.create(tenant=self.tenant, name="Paused", url="https://example.com", secret="s", event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.PAUSED, created_by=self.user)
        self.assertEqual(wh.status, WebhookStatus.PAUSED)

    def test_webhook_status_disabled(self):
        wh = Webhook.objects.create(tenant=self.tenant, name="Disabled", url="https://example.com", secret="s", event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.DISABLED, created_by=self.user)
        self.assertEqual(wh.status, WebhookStatus.DISABLED)

    def test_secret_encryption_on_save(self):
        """Secret is encrypted when saved to DB — plaintext never stored."""
        plaintext = "plaintext-secret-abc"
        wh = Webhook.objects.create(tenant=self.tenant, name="Enc", url="https://example.com", secret=plaintext, event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.ACTIVE, created_by=self.user)
        wh.refresh_from_db()
        self.assertTrue(wh.secret.startswith("v1:"), f"Secret not encrypted: {wh.secret[:20]}")
        # Plaintext must NOT be stored in the secret field
        self.assertNotEqual(wh.secret, plaintext)
        self.assertNotIn(plaintext, wh.secret)

    def test_decrypted_secret_returns_original(self):
        """decrypted_secret property returns original plaintext."""
        wh = Webhook.objects.create(tenant=self.tenant, name="Dec", url="https://example.com", secret="my-secret-123", event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.ACTIVE, created_by=self.user)
        wh.refresh_from_db()
        self.assertEqual(wh.decrypted_secret, "my-secret-123")

    def test_generate_signature_hmac_sha256(self):
        """generate_signature produces valid HMAC-SHA256."""
        wh = Webhook.objects.create(tenant=self.tenant, name="Sig", url="https://example.com", secret="secret-key", event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.ACTIVE, created_by=self.user)
        payload = json.dumps({"event": "test"}, sort_keys=True)
        sig = wh.generate_signature(payload)
        expected = hmac.new("secret-key".encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        self.assertEqual(sig, expected)

    def test_event_type_subscription_check(self):
        wh = Webhook.objects.create(tenant=self.tenant, name="Sub", url="https://example.com", secret="s", event_types=[WebhookEventType.CONTRACT_CREATED, WebhookEventType.ASSET_CREATED], status=WebhookStatus.ACTIVE, created_by=self.user)
        self.assertTrue(wh.subscribes_to_event_type("contract.created"))
        self.assertFalse(wh.subscribes_to_event_type("ingestion.completed"))

    def test_default_retry_intervals(self):
        wh = Webhook.objects.create(tenant=self.tenant, name="Retry", url="https://example.com", secret="s", event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.ACTIVE, created_by=self.user)
        self.assertEqual(wh.retry_intervals, [1, 5, 30, 300, 1800])


class WebhookDeliveryModelTest(TestCase):
    """Test WebhookDelivery model."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE")
        self.webhook = Webhook.objects.create(tenant=self.tenant, name="WH", url="https://example.com", secret="s", event_types=[WebhookEventType.CONTRACT_CREATED], status=WebhookStatus.ACTIVE, created_by=self.user)

    def test_delivery_status_pending(self):
        d = WebhookDelivery.objects.create(webhook=self.webhook, event_type="contract.created", payload={"t": 1}, signature="sig", status=DeliveryStatus.PENDING)
        self.assertEqual(d.status, DeliveryStatus.PENDING)

    def test_delivery_status_success(self):
        d = WebhookDelivery.objects.create(webhook=self.webhook, event_type="contract.created", payload={"t": 1}, signature="sig", status=DeliveryStatus.SUCCESS, http_status_code=200)
        self.assertEqual(d.status, DeliveryStatus.SUCCESS)
        self.assertEqual(d.http_status_code, 200)

    def test_delivery_status_failed_with_error(self):
        d = WebhookDelivery.objects.create(webhook=self.webhook, event_type="contract.created", payload={"t": 1}, signature="sig", status=DeliveryStatus.FAILED, error_message="timeout", attempt_number=3)
        self.assertEqual(d.status, DeliveryStatus.FAILED)
        self.assertEqual(d.attempt_number, 3)

    def test_delivery_dead_letter_status(self):
        d = WebhookDelivery.objects.create(webhook=self.webhook, event_type="contract.created", payload={"t": 1}, signature="sig", status=DeliveryStatus.DEAD_LETTER, attempt_number=5)
        self.assertEqual(d.status, DeliveryStatus.DEAD_LETTER)

    def test_delivery_tracks_response_body(self):
        d = WebhookDelivery.objects.create(webhook=self.webhook, event_type="contract.created", payload={"t": 1}, signature="sig", status=DeliveryStatus.FAILED, response_body='{"error": "internal"}', http_status_code=500)
        self.assertEqual(d.response_body, '{"error": "internal"}')
        self.assertEqual(d.http_status_code, 500)


class EncryptionTest(TestCase):
    """Test encryption utility functions."""

    def test_encrypt_and_decrypt_roundtrip(self):
        plaintext = "my-webhook-secret-abc123"
        encrypted = encrypt_secret(plaintext)
        self.assertTrue(encrypted.startswith("v1:"))
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
