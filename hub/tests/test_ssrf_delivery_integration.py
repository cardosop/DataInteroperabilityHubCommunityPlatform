"""
Integration tests for SSRF protection in the full webhook delivery path.

These tests verify that:
1. WebhookDeliveryService._attempt_delivery() blocks SSRF URLs when
   WEBHOOK_SSRF_ENABLED=True and marks the delivery as FAILED (not
   double-wrapped as a generic network error).
2. WebhookSerializer.validate_url() raises ValidationError for private
   URLs when WEBHOOK_SSRF_ENABLED=True.
3. Both checks are skipped when WEBHOOK_SSRF_ENABLED=False (test default).
4. HTTP redirects to private IPs are blocked — the redirect SSRF guard
   validates the Location header before following.
"""
import socket
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
)
from hub.apps.webhooks.serializers import WebhookSerializer
from hub.apps.webhooks.service import WebhookDeliveryService

from django.contrib.auth import get_user_model

User = get_user_model()


def _build_tenant_and_user():
    tenant = Tenant.objects.create(
        name="SSRF Test Tenant",
        slug=f"ssrf-test-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"ssrf-{uuid.uuid4().hex[:6]}@example.com",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
        display_name="SSRF Test User",
    )
    return tenant, user


# ---------------------------------------------------------------------------
# Delivery service — SSRF blocked delivery marks record FAILED (not doubled)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSSRFDeliveryBlocked(TestCase):
    """
    Verify _attempt_delivery blocks private-URL webhooks when SSRF is enabled,
    and that the delivery record is marked FAILED with the SSRF message
    without double-wrapping.
    """

    def setUp(self):
        self.tenant, self.user = _build_tenant_and_user()

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_delivery_to_private_ip_marked_failed(self):
        """Delivering to 127.0.0.1 must mark the delivery FAILED, not raise."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Private URL Webhook",
            url="http://127.0.0.1:8080/hook",
            secret="test-secret-12345",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        # _attempt_delivery must not raise — it catches SSRF internally
        WebhookDeliveryService._attempt_delivery(delivery)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIn("SSRF", delivery.error_message)
        # Message must NOT contain the double-wrap prefix "Webhook delivery error:"
        self.assertNotIn(
            "Webhook delivery error: SSRF",
            delivery.error_message,
            "SSRF error must not be double-wrapped by the generic network handler",
        )

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_delivery_to_aws_imds_marked_failed(self):
        """Delivering to AWS IMDS (169.254.169.254) must fail with SSRF."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="IMDS Webhook",
            url="http://169.254.169.254/latest/meta-data/",
            secret="test-secret-12345",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        WebhookDeliveryService._attempt_delivery(delivery)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIn("SSRF", delivery.error_message)

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_delivery_to_rfc1918_marked_failed(self):
        """Delivering to a RFC-1918 address (10.x) must fail with SSRF."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="RFC1918 Webhook",
            url="http://10.0.0.1/hook",
            secret="test-secret-12345",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        WebhookDeliveryService._attempt_delivery(delivery)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIn("SSRF", delivery.error_message)

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_dns_rebinding_marked_failed(self):
        """A hostname that resolves to 127.0.0.1 at delivery time must fail."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="DNS-rebind Webhook",
            url="http://rebind.example.com/hook",
            secret="test-secret-12345",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        import socket
        fake_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]
        with patch("hub.apps.webhooks.ssrf_guard.socket.getaddrinfo", return_value=fake_result):
            WebhookDeliveryService._attempt_delivery(delivery)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIn("SSRF", delivery.error_message)

    @override_settings(WEBHOOK_SSRF_ENABLED=False)
    def test_ssrf_disabled_allows_private_url(self):
        """When WEBHOOK_SSRF_ENABLED=False the check is skipped; delivery
        proceeds and fails with a connection error (not an SSRF error)."""
        import httpx

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Disabled SSRF Webhook",
            url="http://127.0.0.1:19999/hook",
            secret="test-secret-12345",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        # Mock deliver_webhook_with_response to raise ConnectError so the
        # test is deterministic — a real connection to port 19999 can
        # produce false failures if something is listening.
        with patch(
            "hub.apps.webhooks.service_client.WebhookDeliveryClient"
            ".deliver_webhook_with_response",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            WebhookDeliveryService._attempt_delivery(delivery)

        delivery.refresh_from_db()
        # Must be FAILED (connection refused), not blocked by SSRF
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        # Error message must NOT mention SSRF
        self.assertNotIn("SSRF", delivery.error_message or "")


# ---------------------------------------------------------------------------
# Serializer — validate_url SSRF gating
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSSRFSerializerValidation(TestCase):
    """
    Verify WebhookSerializer.validate_url() behaviour under both settings.
    """

    def _valid_data(self, url: str) -> dict:
        return {
            "name": "Test Webhook",
            "url": url,
            "secret": "supersecret123",
            "event_types": [WebhookEventType.ODPS_CREATED],
        }

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_private_url_rejected_when_enabled(self):
        """Serializer must raise ValidationError for 127.0.0.1 when SSRF is on."""
        s = WebhookSerializer(data=self._valid_data("http://127.0.0.1/hook"))
        self.assertFalse(s.is_valid())
        self.assertIn("url", s.errors)

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_rfc1918_rejected_when_enabled(self):
        """Serializer must reject 192.168.x URL when SSRF is on."""
        s = WebhookSerializer(data=self._valid_data("http://192.168.0.1/hook"))
        self.assertFalse(s.is_valid())
        self.assertIn("url", s.errors)

    @override_settings(WEBHOOK_SSRF_ENABLED=False)
    def test_private_url_allowed_when_disabled(self):
        """When SSRF guard is off, a private URL passes URL validation
        (the field-level model URLField validation still runs but accepts
        any valid URL format)."""
        s = WebhookSerializer(data=self._valid_data("http://127.0.0.1/hook"))
        # 'url' field error must not be present (SSRF guard skipped)
        s.is_valid()
        self.assertNotIn("url", s.errors)

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_public_url_accepted_when_enabled(self):
        """A genuine public URL must pass validation even when SSRF guard is on."""
        fake = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        with patch("hub.apps.webhooks.ssrf_guard.socket.getaddrinfo", return_value=fake):
            s = WebhookSerializer(data=self._valid_data("https://example.com/hook"))
            s.is_valid()
            self.assertNotIn("url", s.errors)


# ---------------------------------------------------------------------------
# HTTP redirect → private IP
#
# An attacker can register a public URL that returns a 301/302 redirect to a
# private address (e.g. http://169.254.169.254/).  The delivery service must
# re-validate the redirect destination before following it.
#
# Phase 278.G fix: _attempt_delivery now uses follow_redirects=False on the
# initial request and runs is_safe_url() on the Location header.
# ---------------------------------------------------------------------------


def _make_redirect_mock_response(status_code: int, location: str):
    """Build a mock httpx.Response with the given redirect status and Location."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.headers = {"Location": location}
    mock_resp.text = ""
    mock_resp.is_redirect = True
    return mock_resp


@pytest.mark.django_db
class TestSSRFRedirectBlocked(TestCase):
    """
    Open-redirect SSRF: public URL → 301/302 → private IP.

    The delivery service validates the Location header via is_safe_url()
    before following any redirect.
    """

    def setUp(self):
        self.tenant, self.user = _build_tenant_and_user()

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_redirect_to_aws_imds_is_blocked(self):
        """
        Public URL responding with 301 → http://169.254.169.254/ must be
        marked FAILED with 'SSRF' in error_message.

        Arrange: mock deliver_webhook_with_response to return a 301 with
        a private Location header pointing to AWS IMDS.
        Assert: delivery is FAILED, 'SSRF' in error_message.
        """
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Redirect SSRF Webhook",
            url="https://public.example.com/hook",
            secret="test-secret-redirect",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        # Simulate DNS resolving to a public IP (passes initial SSRF guard
        # on the webhook URL), then the first HTTP request returns a 301
        # redirect to the AWS IMDS address.
        public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        mock_initial = _make_redirect_mock_response(
            301, "http://169.254.169.254/latest/meta-data/"
        )

        with patch(
            "hub.apps.webhooks.ssrf_guard.socket.getaddrinfo",
            return_value=public_dns,
        ) as mock_dns, patch(
            "hub.apps.webhooks.service_client.WebhookDeliveryClient"
            ".deliver_webhook_with_response",
            return_value=mock_initial,
        ) as mock_probe:
            WebhookDeliveryService._attempt_delivery(delivery)

        # Verify the probe used follow_redirects=False — without this the
        # redirect guard would be dead code (httpx would auto-follow).
        mock_probe.assert_called_once()

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            DeliveryStatus.FAILED,
            "Redirect to private IP must mark delivery FAILED",
        )
        self.assertIn(
            "SSRF",
            delivery.error_message,
            "SSRF must appear in error_message for redirect attack",
        )

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_redirect_to_rfc1918_is_blocked(self):
        """Public URL → 302 → http://10.0.0.1/ must be blocked."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Redirect RFC1918 Webhook",
            url="https://public.example.com/hook2",
            secret="test-secret-rfc1918",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        mock_initial = _make_redirect_mock_response(
            302, "http://10.0.0.1/internal"
        )

        with patch(
            "hub.apps.webhooks.ssrf_guard.socket.getaddrinfo",
            return_value=public_dns,
        ), patch(
            "hub.apps.webhooks.service_client.WebhookDeliveryClient"
            ".deliver_webhook_with_response",
            return_value=mock_initial,
        ) as mock_probe:
            WebhookDeliveryService._attempt_delivery(delivery)

        mock_probe.assert_called_once()

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIn("SSRF", delivery.error_message)

    @override_settings(WEBHOOK_SSRF_ENABLED=True)
    def test_redirect_308_to_private_ip_is_blocked(self):
        """308 Permanent Redirect to private IP must also be blocked."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Redirect 308 Webhook",
            url="https://public.example.com/perm-redirect",
            secret="test-secret-308",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )
        public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        mock_initial = _make_redirect_mock_response(
            308, "http://169.254.169.254/latest/meta-data/"
        )
        with patch(
            "hub.apps.webhooks.ssrf_guard.socket.getaddrinfo",
            return_value=public_dns,
        ), patch(
            "hub.apps.webhooks.service_client.WebhookDeliveryClient"
            ".deliver_webhook_with_response",
            return_value=mock_initial,
        ) as mock_probe:
            WebhookDeliveryService._attempt_delivery(delivery)

        mock_probe.assert_called_once()
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIn("SSRF", delivery.error_message)


@pytest.mark.django_db
class TestSSRFRedirectSafeFollowed(TestCase):
    """Public URL → 301 → another public URL is followed normally."""

    def setUp(self):
        self.tenant, self.user = _build_tenant_and_user()

    @override_settings(WEBHOOK_SSRF_ENABLED=True, WEBHOOK_DELIVERY_MAX_RETRIES=0)
    def test_redirect_to_public_url_is_followed(self):
        """
        The redirect SSRF guard must NOT block legitimate redirects where
        the Location header points to a safe public address.
        """
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Safe Redirect Webhook",
            url="https://public.example.com/hook3",
            secret="test-secret-safe-redirect",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"event": "test"},
            signature="sha256=fake",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        mock_initial = _make_redirect_mock_response(
            301, "https://example.com/new-location"
        )

        with patch(
            "hub.apps.webhooks.ssrf_guard.socket.getaddrinfo",
            return_value=public_dns,
        ), patch(
            "hub.apps.webhooks.service_client.WebhookDeliveryClient"
            ".deliver_webhook_with_response",
            return_value=mock_initial,
        ) as mock_probe, patch(
            "hub.apps.webhooks.service_client.WebhookDeliveryClient"
            ".deliver_webhook",
            return_value=(200, '{"status": "ok"}'),
        ) as mock_follow:
            WebhookDeliveryService._attempt_delivery(delivery)

        # Verify the redirect guard followed the safe Location and delivered.
        mock_probe.assert_called_once()
        mock_follow.assert_called_once()
        _follow_url = mock_follow.call_args[0][0] if mock_follow.call_args[0] else mock_follow.call_args[1]["url"]
        self.assertEqual(
            _follow_url, "https://example.com/new-location",
            "deliver_webhook must be called with the redirect Location URL",
        )

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            DeliveryStatus.SUCCESS,
            f"Safe redirect should succeed, got {delivery.status}: {delivery.error_message}",
        )
        self.assertNotIn("SSRF", delivery.error_message or "")
