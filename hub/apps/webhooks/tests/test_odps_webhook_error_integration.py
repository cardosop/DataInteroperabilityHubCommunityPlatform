"""
Integration tests for ODPS webhook error scenarios.

Tests end-to-end error handling using real HTTP servers only (no mocks/stubs):
- Timeout, retry success, max retries exceeded, rate limit, SSL error
- Multiple webhooks, connection error recovery
"""

import contextlib
import threading
import time
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.odps_webhook_errors import (
    ODPSWebhookValidationError,
)
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.tests.test_delivery_validators_integration import (
    StatefulTestWebhookServer,
)
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class _Always500Handler(BaseHTTPRequestHandler):
    """Handler that always returns HTTP 500."""

    def do_POST(self):
        self.send_response(500)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Internal Server Error")

    def log_message(self, format, *args):
        pass


class _RateLimitHandler(BaseHTTPRequestHandler):
    """Handler that returns 429 with Retry-After header."""

    def do_POST(self):
        self.send_response(429)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Retry-After", "60")
        self.end_headers()
        self.wfile.write(b"Rate Limited")

    def log_message(self, format, *args):
        pass


def _start_http_server(handler_class, port=0):
    """Start an HTTP server in a daemon thread; return (server, port, url)."""
    server = HTTPServer(("127.0.0.1", port), handler_class)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/webhook"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, url


class ODPSWebhookErrorIntegrationTest(TransactionTestCase):
    """Integration tests for ODPS webhook error scenarios using real HTTP servers."""

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE to avoid timeout."""

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        reset_circuit_breaker_by_name("webhook-delivery")
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
            max_retries=3,
            retry_intervals=[1, 5, 30],
        )

    @override_settings(WEBHOOK_REQUEST_TIMEOUT=2)
    def test_complete_error_handling_flow_timeout(self):
        """Test complete error handling flow for timeout via real server that delays response."""
        # Server responds after 3s; client timeout is 2s
        server = TestWebhookServer(response_status=200, response_delay=3.0)
        server.start()
        try:
            self.webhook.url = server.get_url()
            self.webhook.save(update_fields=["url"])

            event_data = {"contract_id": str(uuid.uuid4()), "status": "ACTIVE"}

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            self.assertEqual(count, 1)

            delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertIsNotNone(delivery.error_message)
            error_msg_lower = delivery.error_message.lower()
            self.assertTrue(
                "timeout" in error_msg_lower or "timed out" in error_msg_lower,
                f"Expected 'timeout' or 'timed out' in error message, got: {delivery.error_message}",
            )
            self.assertIsNotNone(delivery.next_retry_at)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_CREATED)
            self.assertEqual(delivery.webhook, self.webhook)
        finally:
            server.stop()

    @override_settings(WEBHOOK_DELIVERY_MAX_RETRIES=2)
    def test_error_handling_with_retry_success(self):
        """Test error handling with retry that eventually succeeds via real server (500 then 200)."""
        # Client retries on 5xx (max_retries=2 → 3 attempts). Need 3×500 so first _attempt_delivery
        # fails with FAILED, then retry_delivery gets 200.
        # Override WEBHOOK_DELIVERY_MAX_RETRIES because the test-mode default is 0.
        with StatefulTestWebhookServer([500, 500, 500, 200]) as server:
            self.webhook.url = server.get_url()
            self.webhook.save(update_fields=["url"])

            event_data = {"contract_id": str(uuid.uuid4())}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertEqual(delivery.http_status_code, 500)
            self.assertEqual(delivery.attempt_number, 1)

            WebhookDeliveryService.retry_delivery(str(delivery.id))

            delivery.refresh_from_db()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.http_status_code, 200)
            self.assertIsNotNone(delivery.delivered_at)

    def test_error_handling_max_retries_exceeded(self):
        """Test error handling when max retries are exceeded via real server always returning 500."""
        httpd, _port, url = _start_http_server(_Always500Handler)
        try:
            self.webhook.url = url
            self.webhook.save(update_fields=["url"])

            event_data = {"contract_id": str(uuid.uuid4())}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
            self.assertIsNotNone(delivery)

            # Run attempts until we have exhausted retries; then _schedule_retry marks DEAD_LETTER
            for _ in range(self.webhook.max_retries + 1):
                WebhookDeliveryService._attempt_delivery(delivery)
                delivery.refresh_from_db()

                if delivery.attempt_number >= self.webhook.max_retries:
                    # One more _schedule_retry so service marks DEAD_LETTER (attempt_number >= max_retries)
                    WebhookDeliveryService._schedule_retry(delivery)
                    delivery.refresh_from_db()
                    break

                WebhookDeliveryService._schedule_retry(delivery)
                delivery.refresh_from_db()

            self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
            self.assertIsNone(delivery.next_retry_at)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_error_handling_rate_limit(self):
        """Test error handling for rate limit (429) via real server."""
        httpd, _port, url = _start_http_server(_RateLimitHandler)
        try:
            self.webhook.url = url
            self.webhook.save(update_fields=["url"])

            event_data = {"contract_id": str(uuid.uuid4())}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertEqual(delivery.http_status_code, 429)
            self.assertIsNotNone(delivery.next_retry_at)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_error_handling_ssl_error(self):
        """Test error handling for SSL errors via real HTTPS server with self-signed cert."""
        import ssl
        import tempfile

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        # Generate self-signed cert and key in temp files
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(timezone.now())
            .not_valid_after(timezone.now() + timedelta(days=1))
            .sign(key, hashes.SHA256())
        )

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=False) as cert_file:
            cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
            cert_path = cert_file.name
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=False) as key_file:
            key_file.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            key_path = key_file.name

        try:

            class _OkHandler(BaseHTTPRequestHandler):
                def do_POST(self):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')

                def log_message(self, format, *args):
                    pass

            server = HTTPServer(("127.0.0.1", 0), _OkHandler)
            port = server.server_address[1]
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert_path, key_path)
            server.socket = context.wrap_socket(server.socket, server_side=True)

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            time.sleep(  # noqa: sleep-needed — test timing requirement
                0.2
            )  # INTENTIONAL: wait for HTTPS server thread to start accepting connections

            self.webhook.url = f"https://127.0.0.1:{port}/webhook"
            self.webhook.save(update_fields=["url"])

            event_data = {"contract_id": str(uuid.uuid4())}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertIsNotNone(delivery.error_message)
            err_lower = delivery.error_message.lower()
            self.assertTrue(
                "ssl" in err_lower or "certificate" in err_lower or "verify" in err_lower,
                f"Expected ssl/certificate/verify in error message, got: {delivery.error_message}",
            )

            server.shutdown()
            server.server_close()
        finally:
            import os

            for p in (cert_path, key_path):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(p)

    def test_error_handling_multiple_webhooks(self):
        """Test error handling when multiple webhooks are triggered via two real servers."""
        server_ok = TestWebhookServer(response_status=200)
        server_ok.start()
        httpd_fail, _port_fail, url_fail = _start_http_server(_Always500Handler)
        try:
            self.webhook.url = server_ok.get_url()
            self.webhook.save(update_fields=["url"])

            webhook2 = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook 2",
                url=url_fail,
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
                max_retries=3,
                retry_intervals=[1, 5, 30],
            )

            event_data = {"contract_id": str(uuid.uuid4())}

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            self.assertEqual(count, 2)

            delivery1 = WebhookDelivery.objects.filter(webhook=self.webhook).first()
            delivery2 = WebhookDelivery.objects.filter(webhook=webhook2).first()

            self.assertIsNotNone(delivery1)
            self.assertIsNotNone(delivery2)

            statuses = {delivery1.status, delivery2.status}
            self.assertIn(DeliveryStatus.SUCCESS, statuses)
            self.assertIn(DeliveryStatus.FAILED, statuses)

            failed = delivery1 if delivery1.status == DeliveryStatus.FAILED else delivery2
            self.assertEqual(failed.http_status_code, 500)
        finally:
            server_ok.stop()
            httpd_fail.shutdown()
            httpd_fail.server_close()

    def test_error_handling_connection_error_recovery(self):
        """Test connection error recovery: first attempt fails (no server), retry succeeds (server up)."""
        import socket

        # Reserve a port by binding then closing; use SO_REUSEADDR so we can rebind immediately
        httpd_reserve = HTTPServer(("127.0.0.1", 0), _Always500Handler)
        port = httpd_reserve.server_address[1]
        httpd_reserve.server_close()

        self.webhook.url = f"http://127.0.0.1:{port}/webhook"
        self.webhook.save(update_fields=["url"])

        event_data = {"contract_id": str(uuid.uuid4())}

        WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)

        # Start server on same port returning 200 so retry succeeds (SO_REUSEADDR for immediate rebind)
        class _OkHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')

            def log_message(self, format, *args):
                pass

        class ReuseAddrHTTPServer(HTTPServer):
            def server_bind(self):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                super().server_bind()

        httpd = ReuseAddrHTTPServer(("127.0.0.1", port), _OkHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)  # noqa: sleep-needed  # INTENTIONAL: wait for HTTP server thread to start accepting connections

        try:
            WebhookDeliveryService.retry_delivery(str(delivery.id))
            delivery.refresh_from_db()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_payload_validation_integration(self):
        """Test payload validation integration with webhook triggering."""
        with self.assertRaises(ODPSWebhookValidationError):
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type="invalid.event.type",
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )

        with self.assertRaises(ODPSWebhookValidationError):
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.CONTRACT_CREATED,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )

    def test_error_context_preservation(self):
        """Test that error context is properly preserved."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/test",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        webhook.status = WebhookStatus.PAUSED
        webhook.save()

        with self.assertRaises(ODPSWebhookValidationError) as cm:
            WebhookDeliveryService._deliver_webhook(
                webhook=webhook,
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data={"contract_id": str(uuid.uuid4())},
            )

        error = cm.exception
        self.assertEqual(error.webhook_id, str(webhook.id))
        self.assertEqual(error.tenant_id, str(self.tenant.id))
        self.assertEqual(error.event_type, WebhookEventType.ODPS_CREATED)
        self.assertIn("webhook_id", error.context)
        self.assertIn("event_type", error.context)

    def test_trigger_odps_webhook_returns_zero_when_no_active_webhooks(self):
        """Failure path: tenant has no active webhooks; trigger_odps_webhook returns 0 (no mocks)."""
        self.webhook.status = WebhookStatus.PAUSED
        self.webhook.save()
        count = WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data={"contract_id": str(uuid.uuid4())},
        )
        self.assertEqual(count, 0)
        self.assertEqual(WebhookDelivery.objects.filter(webhook=self.webhook).count(), 0)

    def test_trigger_odps_webhook_returns_zero_for_tenant_with_no_webhooks(self):
        """Failure path: tenant with no webhooks at all; trigger_odps_webhook returns 0 (no mocks)."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        count = WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(other_tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data={"contract_id": str(uuid.uuid4())},
        )
        self.assertEqual(count, 0)

    def test_trigger_odps_webhook_invalid_event_type_raises_with_context(self):
        """Failure path: invalid event type raises ODPSWebhookValidationError (no mocks)."""
        with self.assertRaises(ODPSWebhookValidationError) as cm:
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.CONTRACT_CREATED,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )
        self.assertIn("not an ODPS event type", str(cm.exception))
        self.assertEqual(WebhookDelivery.objects.filter(webhook=self.webhook).count(), 0)

    def test_delivery_failure_via_real_http_server_500(self):
        """Integration: real HTTP server returning 500 causes FAILED and http_status_code 500 (no mocks)."""

        class Handler500(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Internal Server Error")

            def log_message(self, format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler500)
        port = server.server_address[1]
        url = f"http://127.0.0.1:{port}/webhook"

        # Client retries on 5xx (max_retries=2 → 3 attempts). Server must handle all 3.
        def serve_until_done():
            for _ in range(3):
                server.handle_request()

        thread = threading.Thread(target=serve_until_done, daemon=True)
        thread.start()
        time.sleep(0.15)  # noqa: sleep-needed  # INTENTIONAL: wait for HTTP server thread to start accepting connections

        webhook_real = Webhook.objects.create(
            tenant=self.tenant,
            name="Real Server Webhook",
            url=url,
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
            max_retries=2,
            retry_intervals=[1, 2],
        )
        try:
            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data={"contract_id": str(uuid.uuid4())},
            )
            self.assertGreaterEqual(count, 1)
            delivery = WebhookDelivery.objects.filter(webhook=webhook_real).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertEqual(delivery.http_status_code, 500)
        finally:
            thread.join(timeout=2.0)
            server.server_close()
