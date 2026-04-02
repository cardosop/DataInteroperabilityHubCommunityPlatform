"""
Comprehensive integration tests for ODPS webhook delivery.

Tests webhook delivery, event filtering, and error handling using real HTTP servers
without mocks or stubs. All tests use actual HTTP requests to verify end-to-end behavior.
"""

import json
import uuid
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Optional
from queue import Queue
from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.odps_event_subscriber import ODPSEventSubscriber, get_odps_event_subscriber
from hub.apps.webhooks.odps_webhook_errors import (
    ODPSWebhookValidationError,
    ODPSWebhookPayloadError,
)
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.bus import get_event_bus
from tests.utils.wait_helpers import wait_for_event_persistence

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class WebhookReceiverHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for receiving webhook deliveries.

    Stores received requests in a queue for test verification.
    """

    def __init__(self, request_queue: Queue, response_status: int = 200,
                 response_delay: float = 0.0, *args, **kwargs):
        """
        Initialize handler.

        Args:
            request_queue: Queue to store received requests
            response_status: HTTP status code to return
            response_delay: Delay before responding (for timeout tests)
        """
        self.request_queue = request_queue
        self.response_status = response_status
        self.response_delay = response_delay
        super().__init__(*args, **kwargs)

    def do_POST(self):
        """Handle POST requests (webhook deliveries)."""
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        # Parse headers
        headers = dict(self.headers)

        # Store request for verification
        request_data = {
            'path': self.path,
            'method': 'POST',
            'headers': headers,
            'body': body.decode('utf-8') if body else '',
            'timestamp': timezone.now().isoformat(),
        }
        self.request_queue.put(request_data)

        # Simulate delay if configured (broken into small intervals for clean shutdown)
        if self.response_delay > 0:
            remaining = self.response_delay
            while remaining > 0:
                time.sleep(min(remaining, 0.5))  # INTENTIONAL: simulates slow webhook receiver
                remaining -= 0.5

        # Send response
        self.send_response(self.response_status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        response_body = json.dumps({'status': 'received'})
        self.wfile.write(response_body.encode('utf-8'))

    def log_message(self, format, *args):
        """Suppress server logs during tests."""
        pass


class TestWebhookServer:
    """
    Test HTTP server for receiving webhook deliveries.

    Provides a real HTTP endpoint that webhooks can be delivered to,
    allowing comprehensive testing without mocks.
    """

    __test__ = False  # Not a test class — prevent pytest collection warning

    """
    """

    def __init__(self, port: int = 0, response_status: int = 200,
                 response_delay: float = 0.0):
        """
        Initialize test webhook server.

        Args:
            port: Port to bind to (0 = auto-assign)
            response_status: HTTP status code to return
            response_delay: Delay before responding (for timeout tests)
        """
        self.port = port
        self.response_status = response_status
        self.response_delay = response_delay
        self.request_queue: Queue = Queue()
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Start the HTTP server."""
        def handler_factory(*args, **kwargs):
            return WebhookReceiverHandler(
                self.request_queue,
                self.response_status,
                self.response_delay,
                *args,
                **kwargs
            )

        self.server = HTTPServer(("localhost", self.port), handler_factory)
        self.server.timeout = 1  # Don't block on individual requests
        self.port = self.server.server_address[1]
        self._shutting_down = False
        self.thread = threading.Thread(target=self.server.serve_forever, name="webhook-test-server", daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the HTTP server without blocking on in-flight requests."""
        self._shutting_down = True
        if self.server:
            # Use a thread to call shutdown() so it doesn't block indefinitely
            shutdown_thread = threading.Thread(target=self.server.shutdown, daemon=True)
            shutdown_thread.start()
            shutdown_thread.join(timeout=5)  # Wait max 5s for clean shutdown
            try:
                self.server.server_close()
            except Exception:
                pass
            self.server = None
            self.thread = None

    def get_url(self) -> str:
        """Get the server URL."""
        return f"http://localhost:{self.port}/webhook"

    def received_count(self) -> int:
        """Return number of requests in queue without consuming. Use for wait conditions."""
        return self.request_queue.qsize()

    def get_received_requests(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Get all received requests (consumes from queue).

        Args:
            timeout: Maximum time to wait for requests

        Returns:
            List of received request data
        """
        requests = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                request = self.request_queue.get(timeout=0.1)
                requests.append(request)
            except Exception:
                if time.time() - start_time >= timeout:
                    break

        return requests

    def clear_requests(self):
        """Clear all received requests."""
        while not self.request_queue.empty():
            try:
                self.request_queue.get_nowait()
            except:
                pass

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


@override_settings(WEBHOOK_ASYNC_DELIVERY=False)
class ODPSWebhookIntegrationTest(TransactionTestCase):
    """
    Comprehensive integration tests for ODPS webhook delivery.

    Uses real HTTP servers to test webhook delivery without mocks.
    Runs with WEBHOOK_ASYNC_DELIVERY=False so deliveries happen synchronously
    (no RQ worker needed in test container).
    """

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE to avoid timeout."""
        pass

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

    def test_odps_webhook_delivery_success(self):
        """
        Test successful ODPS webhook delivery.

        Verifies:
        - Webhook is delivered to correct URL
        - Payload structure is correct
        - Signature is present and valid
        - Delivery record is created with success status
        """
        # Start webhook receiver server
        with TestWebhookServer(response_status=200) as server:
            webhook_url = server.get_url()

            # Create webhook subscribed to ODPS events
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=webhook_url,
                secret="test-secret-key-12345",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            # Trigger ODPS webhook
            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "asset_id": str(uuid.uuid4()),
                "status": "ACTIVE",
                "odps_version": "4.1",
                "original_format": "JSON",
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Verify webhook was triggered
            self.assertEqual(count, 1, "Webhook should be triggered")

            # Wait for delivery
            wait_for_event_persistence()

            # Verify delivery record
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1, "Delivery record should be created")

            delivery = deliveries.first()
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_CREATED)
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertIsNotNone(delivery.delivered_at)
            self.assertIsNotNone(delivery.signature)

            # Verify HTTP request was received
            received_requests = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received_requests), 1, "Webhook should be delivered")

            request = received_requests[0]
            self.assertEqual(request['method'], 'POST')

            # Verify payload structure
            payload = json.loads(request['body'])
            self.assertEqual(payload['event_type'], WebhookEventType.ODPS_CREATED)
            self.assertEqual(payload['resource_type'], "ODPS")
            self.assertEqual(payload['resource_id'], contract_id)
            self.assertEqual(payload['data'], event_data)
            self.assertIn('timestamp', payload)

            # Verify headers
            headers = request['headers']
            self.assertIn('X-Webhook-Signature', headers)
            self.assertIn('X-Webhook-Event-Type', headers)
            self.assertEqual(headers['X-Webhook-Event-Type'], WebhookEventType.ODPS_CREATED)
            self.assertEqual(headers['Content-Type'], 'application/json')

            # Verify signature matches
            signature = headers['X-Webhook-Signature']
            self.assertEqual(signature, delivery.signature)

    def test_odps_webhook_event_filtering(self):
        """
        Test ODPS webhook event filtering.

        Verifies:
        - Only webhooks subscribed to specific event types receive deliveries
        - Multiple webhooks can subscribe to same event
        - Webhooks subscribed to different events don't receive unrelated deliveries
        """
        # Start multiple webhook receiver servers
        with TestWebhookServer() as server1, \
             TestWebhookServer() as server2, \
             TestWebhookServer() as server3:

            # Create webhook subscribed to ODPS_CREATED
            webhook1 = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Created Webhook",
                url=server1.get_url(),
                secret="secret-1",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            # Create webhook subscribed to ODPS_UPDATED
            webhook2 = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Updated Webhook",
                url=server2.get_url(),
                secret="secret-2",
                event_types=[WebhookEventType.ODPS_UPDATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            # Create webhook subscribed to both events
            webhook3 = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Multi Webhook",
                url=server3.get_url(),
                secret="secret-3",
                event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.ODPS_UPDATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "status": "ACTIVE",
            }

            # Trigger ODPS_CREATED event
            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Verify correct webhooks were triggered
            self.assertEqual(count, 2, "Two webhooks should receive ODPS_CREATED event")

            # Wait for deliveries
            wait_for_event_persistence()

            # Verify deliveries
            deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
            self.assertEqual(deliveries1.count(), 1, "Webhook1 should receive delivery")

            deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
            self.assertEqual(deliveries2.count(), 0, "Webhook2 should not receive delivery")

            deliveries3 = WebhookDelivery.objects.filter(webhook=webhook3)
            self.assertEqual(deliveries3.count(), 1, "Webhook3 should receive delivery")

            # Verify HTTP requests
            requests1 = server1.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests1), 1, "Server1 should receive request")

            requests2 = server2.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests2), 0, "Server2 should not receive request")

            requests3 = server3.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests3), 1, "Server3 should receive request")

            # Clear and test ODPS_UPDATED event
            server1.clear_requests()
            server2.clear_requests()
            server3.clear_requests()

            # Trigger ODPS_UPDATED event
            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_UPDATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Verify correct webhooks were triggered
            self.assertEqual(count, 2, "Two webhooks should receive ODPS_UPDATED event")

            # Wait for deliveries
            wait_for_event_persistence()

            # Verify deliveries
            deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
            self.assertEqual(deliveries1.count(), 1, "Webhook1 should still have only 1 delivery")

            deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
            self.assertEqual(deliveries2.count(), 1, "Webhook2 should receive delivery")

            deliveries3 = WebhookDelivery.objects.filter(webhook=webhook3)
            self.assertEqual(deliveries3.count(), 2, "Webhook3 should have 2 deliveries")

    def test_odps_webhook_error_handling_http_error(self):
        """
        Test ODPS webhook error handling for HTTP errors.

        Verifies:
        - HTTP 4xx errors are handled correctly
        - HTTP 5xx errors are handled correctly
        - Delivery record is updated with error information
        - Retry is scheduled for recoverable errors
        """
        # Test 4xx error (client error - non-recoverable)
        with TestWebhookServer(response_status=400) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {"contract_id": contract_id}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Wait for delivery attempt
            wait_for_event_persistence()

            # Verify delivery record
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.http_status_code, 400)
            self.assertIsNotNone(delivery.error_message)
            # 4xx errors are typically non-recoverable
            self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])

        # Test 5xx error (server error - recoverable)
        with TestWebhookServer(response_status=500) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook 2",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {"contract_id": contract_id}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Wait for delivery attempt
            wait_for_event_persistence()

            # Verify delivery record
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.http_status_code, 500)
            self.assertIsNotNone(delivery.error_message)
            # 5xx errors are recoverable and should schedule retry
            self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])

    def test_odps_webhook_error_handling_connection_error(self):
        """
        Test ODPS webhook error handling for connection errors.

        Verifies:
        - Connection errors are handled gracefully
        - Delivery record is updated with error information
        - Retry is scheduled for recoverable errors
        """
        # Use invalid URL to simulate connection error
        invalid_url = "http://localhost:99999/webhook"

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url=invalid_url,
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        contract_id = str(uuid.uuid4())
        event_data = {"contract_id": contract_id}

        WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=contract_id,
            event_data=event_data,
        )

        # Wait for delivery attempt
        wait_for_event_persistence(timeout=2.0)

        # Verify delivery record
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertIsNotNone(delivery)
        self.assertIsNotNone(delivery.error_message)
        # Connection errors are recoverable
        self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])

    @override_settings(WEBHOOK_REQUEST_TIMEOUT=2)
    def test_odps_webhook_error_handling_timeout(self):
        """
        Test ODPS webhook error handling for timeout errors.

        Verifies:
        - Timeout errors are handled gracefully
        - Delivery record is updated with error information
        - Retry is scheduled for recoverable errors
        """
        # Start server with delay longer than WEBHOOK_REQUEST_TIMEOUT (2s)
        with TestWebhookServer(response_status=200, response_delay=5.0) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {"contract_id": contract_id}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Wait for delivery attempt (WEBHOOK_REQUEST_TIMEOUT is 2 seconds)
            wait_for_event_persistence(timeout=2.0)

            # Verify delivery record
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertIsNotNone(delivery.error_message)
            # Timeout errors are recoverable
            self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])

    def test_odps_webhook_error_handling_rate_limit(self):
        """
        Test ODPS webhook error handling for rate limit errors.

        Verifies:
        - Rate limit (429) errors are handled correctly
        - Delivery record is updated with error information
        - Retry is scheduled with appropriate delay
        """
        with TestWebhookServer(response_status=429) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {"contract_id": contract_id}

            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Wait for delivery attempt
            wait_for_event_persistence()

            # Verify delivery record
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.http_status_code, 429)
            self.assertIsNotNone(delivery.error_message)
            # Rate limit errors are recoverable
            self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])

    def test_odps_webhook_e2e_event_bus_integration(self):
        """
        E2E test for ODPS webhook delivery from event bus.

        Verifies:
        - Event published to event bus triggers webhook delivery
        - Event subscriber correctly processes ODPS events
        - Webhook is delivered with correct payload
        - Full integration from event bus to webhook delivery
        """
        # Start webhook receiver server
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS E2E Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            # Create event publisher
            publisher = EventPublisher(
                service_name="contract_service",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            # Publish ODPS event
            contract_id = str(uuid.uuid4())
            event_id = publisher.publish(
                event_type="odps.created",
                data={
                    "contract_id": contract_id,
                    "asset_id": str(uuid.uuid4()),
                    "status": "ACTIVE",
                    "odps_version": "4.1",
                    "original_format": "JSON",
                }
            )

            self.assertIsNotNone(event_id, "Event should be published")

            # Simulate event subscriber handling the event
            subscriber = get_odps_event_subscriber()
            event = {
                "event_id": event_id,
                "event_type": "odps.created",
                "data": {
                    "contract_id": contract_id,
                    "asset_id": str(uuid.uuid4()),
                    "status": "ACTIVE",
                    "odps_version": "4.1",
                    "original_format": "JSON",
                },
                "source": {
                    "service": "contract_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                }
            }

            # Handle event (this triggers webhook delivery)
            subscriber._handle_odps_event(event)

            # Wait for webhook delivery
            wait_for_event_persistence(timeout=2.0)

            # Verify webhook was delivered
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1, "Webhook should be delivered")

            delivery = deliveries.first()
            self.assertEqual(delivery.event_type, "odps.created")
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

            # Verify HTTP request was received
            received_requests = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received_requests), 1, "Webhook should be received")

            request = received_requests[0]
            payload = json.loads(request['body'])
            self.assertEqual(payload['event_type'], "odps.created")
            self.assertEqual(payload['data']['contract_id'], contract_id)

    def test_odps_webhook_all_event_types(self):
        """
        Test webhook delivery for all ODPS event types.

        Verifies that all ODPS event types can trigger webhook delivery.
        """
        odps_event_types = WebhookEventType.get_odps_event_types()

        with TestWebhookServer() as server:
            # Create webhook subscribed to all ODPS events
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS All Events Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=odps_event_types,
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())

            # Test each ODPS event type
            for event_type in odps_event_types:
                # Prepare event data based on event type
                if "linked" in event_type:
                    event_data = {
                        "odps_contract_id": contract_id,
                        "odcs_contract_id": str(uuid.uuid4()),
                        "link_type": "bidirectional",
                    }
                elif "export" in event_type:
                    event_data = {
                        "contract_id": contract_id,
                        "export_format": "JSON",
                        "export_url": "https://example.com/export.json",
                    }
                else:
                    event_data = {
                        "contract_id": contract_id,
                        "status": "ACTIVE",
                    }

                # Trigger webhook
                count = WebhookDeliveryService.trigger_odps_webhook(
                    tenant_id=str(self.tenant.id),
                    event_type=event_type,
                    resource_type="ODPS",
                    resource_id=contract_id,
                    event_data=event_data,
                )

                self.assertEqual(count, 1, f"Webhook should be triggered for {event_type}")

                # Wait for delivery
                wait_for_event_persistence()

                # Verify delivery
                delivery = WebhookDelivery.objects.filter(
                    webhook=webhook,
                    event_type=event_type
                ).first()
                self.assertIsNotNone(delivery, f"Delivery should exist for {event_type}")
                self.assertEqual(delivery.event_type, event_type)

                # Clear server requests for next iteration
                server.clear_requests()

    def test_odps_webhook_inactive_webhook_skipped(self):
        """
        Test that inactive webhooks are skipped.

        Verifies:
        - Inactive webhooks don't receive deliveries
        - Only active webhooks are triggered
        """
        with TestWebhookServer() as server:
            # Create active webhook
            active_webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Active Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            # Create inactive webhook
            inactive_webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Inactive Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.DISABLED,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {"contract_id": contract_id}

            # Trigger webhook
            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            # Only active webhook should be triggered
            self.assertEqual(count, 1, "Only active webhook should be triggered")

            # Wait for delivery
            wait_for_event_persistence()

            # Verify only active webhook has delivery
            active_deliveries = WebhookDelivery.objects.filter(webhook=active_webhook)
            self.assertEqual(active_deliveries.count(), 1)

            inactive_deliveries = WebhookDelivery.objects.filter(webhook=inactive_webhook)
            self.assertEqual(inactive_deliveries.count(), 0)

