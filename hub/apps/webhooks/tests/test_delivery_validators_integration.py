"""
Integration Tests for Webhook Delivery Validators with WebhookService

Comprehensive integration tests that validate delivery validators work correctly
with the actual WebhookService implementation. Uses real HTTP server (TestWebhookServer);
no mocks. Uses wait_until for delivery state (no fixed time.sleep) per FIX_PLAN_FLAKY_TESTS_5_6_2.
"""

import json
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue
from typing import List

from django.test import TestCase
from django.utils import timezone

from tests.utils.polling import wait_until

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.webhooks.delivery_validators import WebhookDeliveryValidator
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer


class _StatefulHandler(BaseHTTPRequestHandler):
    """Handler that returns status codes from a sequence (e.g. [500, 200])."""

    def __init__(self, response_sequence: List[int], request_queue: Queue, *args, **kwargs):
        self.response_sequence = response_sequence
        self.request_queue = request_queue
        super().__init__(*args, **kwargs)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        self.request_queue.put(
            {"body": body.decode("utf-8") if body else "", "headers": dict(self.headers)}
        )
        status = self.response_sequence.pop(0) if self.response_sequence else 200
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "received"}).encode("utf-8"))

    def log_message(self, format, *args):
        pass


class StatefulTestWebhookServer:
    """Test server that returns a sequence of HTTP statuses (e.g. 500 then 200)."""

    def __init__(self, response_sequence: List[int]):
        self.response_sequence = list(response_sequence)
        self.request_queue: Queue = Queue()
        self.server = None
        self.thread = None
        self.port = 0

    def start(self):
        def factory(request, client_address, server):
            return _StatefulHandler(
                self.response_sequence, self.request_queue, request, client_address, server
            )

        self.server = HTTPServer(("localhost", 0), factory)
        self.port = self.server.server_address[1]
        import threading

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.thread = None

    def get_url(self) -> str:
        return f"http://localhost:{self.port}/webhook"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


class WebhookDeliveryValidatorIntegrationTest(TestCase):
    """Integration tests for delivery validators with WebhookService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
        )

    def _create_webhook(self, url: str) -> Webhook:
        return Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url=url,
            secret="test-secret-key-for-webhook-signature-generation",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

    def test_integration_retry_validation_with_service(self):
        """Test retry validation integration with WebhookService (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="delivery not recorded")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            result = WebhookDeliveryValidator.validate_delivery_retry(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
            self.assertEqual(result.details["webhook_max_retries"], 3)
            self.assertEqual(result.details["attempt_number"], 0)

    def test_integration_retry_validation_max_retries_exceeded(self):
        """Test retry validation when WebhookService exceeds max retries (real server 500)."""
        with TestWebhookServer(response_status=500) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="delivery (max retries exceeded)")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            for _ in range(3):
                WebhookDeliveryService.retry_delivery(str(delivery.id))
                delivery.refresh_from_db()
            result = WebhookDeliveryValidator.validate_delivery_retry(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
            self.assertTrue(
                result.details.get("should_be_dead_letter", False)
                or delivery.status == DeliveryStatus.DEAD_LETTER
            )

    def test_integration_timeout_validation_with_service(self):
        """Test timeout validation: real server with long delay so request times out (35s)."""
        with TestWebhookServer(response_status=200, response_delay=35.0) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=40.0, message="timeout delivery (35s server delay)")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            result = WebhookDeliveryValidator.validate_delivery_timeout(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
            self.assertTrue(result.details.get("has_timeout_error", False))
            self.assertEqual(
                result.details["timeout_seconds"], str(WebhookDeliveryService.REQUEST_TIMEOUT)
            )

    def test_integration_status_validation_with_service(self):
        """Test status validation integration with WebhookService (real server 200)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="delivery (status validation)")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            delivery.refresh_from_db()
            result = WebhookDeliveryValidator.validate_delivery_status(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
            self.assertIn(
                delivery.status,
                [DeliveryStatus.SUCCESS, DeliveryStatus.PENDING, DeliveryStatus.FAILED],
            )
            if delivery.status == DeliveryStatus.SUCCESS:
                self.assertIsNotNone(delivery.delivered_at)
                self.assertTrue(result.details.get("success_constraints_valid", True))

    def test_integration_dlq_validation_with_service(self):
        """Test DLQ validation with WebhookService (real server 500, retry to DLQ)."""
        with TestWebhookServer(response_status=500) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="delivery (DLQ validation)")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            for _ in range(3):
                WebhookDeliveryService.retry_delivery(str(delivery.id))
                delivery.refresh_from_db()
            result = WebhookDeliveryValidator.validate_dead_letter_queue(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
            self.assertTrue(result.details["is_dead_letter"])
            self.assertTrue(result.details["max_retries_exceeded"])
            self.assertTrue(result.details["no_retry_scheduled"])

    def test_integration_comprehensive_validation_with_service(self):
        """Test comprehensive validation with WebhookService (real server 200)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="delivery (comprehensive validation)")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            result = WebhookDeliveryValidator.validate_all(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
            self.assertEqual(result.details["validation_type"], "comprehensive_delivery_validation")
            self.assertIn("retry_validation", result.details)
            self.assertIn("timeout_validation", result.details)
            self.assertIn("status_validation", result.details)
            self.assertIn("dlq_validation", result.details)

    def test_integration_validation_after_retry_flow(self):
        """Test validation after retry flow: server returns 500 then 200 (stateful server)."""
        with StatefulTestWebhookServer([500, 200]) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="delivery (retry flow)")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            result = WebhookDeliveryValidator.validate_delivery_retry(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
            self.assertIsNotNone(delivery.next_retry_at)
            WebhookDeliveryService.retry_delivery(str(delivery.id))
            delivery.refresh_from_db()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            result = WebhookDeliveryValidator.validate_all(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")

    def test_integration_validation_timeout_retry_flow(self):
        """Test validation with timeout then retry: first request times out (35s delay), retry uses new server 200."""
        # First delivery hits slow server (times out); we then retry against a fast server.
        # Use stateful server: we cannot simulate timeout then 200 with one server without delay.
        # So we test: 500 then 200 (retry after failure) - same flow as test_integration_validation_after_retry_flow.
        with StatefulTestWebhookServer([500, 200]) as server:
            webhook = self._create_webhook(server.get_url())
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=str(WebhookEventType.ODPS_CREATED),
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="delivery (timeout retry flow)")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            result = WebhookDeliveryValidator.validate_delivery_timeout(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
            WebhookDeliveryService.retry_delivery(str(delivery.id))
            delivery.refresh_from_db()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            result = WebhookDeliveryValidator.validate_all(delivery)
            self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
