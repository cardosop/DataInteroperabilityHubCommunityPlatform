"""
Comprehensive tests for ODPS webhook events.

Tests cover:
- All ODPS webhook events (created, updated, deleted, normalized, linked, unlinked, export.*)
- Event filtering and subscription
- Event delivery verification
- Event payload validation
- Event retry logic
- Dead letter queue handling

Uses REAL services (no mocks/stubs) - always fixing root causes and following
development best practices.
"""

import json
import uuid
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Optional
from queue import Queue

import pytest

pytestmark = pytest.mark.slow
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
)
from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.odps_event_subscriber import ODPSEventSubscriber, get_odps_event_subscriber
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.bus import get_event_bus
from tests.utils.wait_helpers import wait_for_event_persistence

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class WebhookReceiverHandler(BaseHTTPRequestHandler):
    """HTTP request handler for receiving webhook deliveries."""

    def __init__(self, request_queue: Queue, response_status: int = 200,
                 response_delay: float = 0.0, *args, **kwargs):
        self.request_queue = request_queue
        self.response_status = response_status
        self.response_delay = response_delay
        super().__init__(*args, **kwargs)

    def do_POST(self):
        """Handle POST requests (webhook deliveries)."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''
        headers = dict(self.headers)

        request_data = {
            'path': self.path,
            'method': 'POST',
            'headers': headers,
            'body': body.decode('utf-8') if body else '',
            'timestamp': timezone.now().isoformat(),
        }
        self.request_queue.put(request_data)

        if self.response_delay > 0:
            remaining = self.response_delay
            while remaining > 0:
                time.sleep(min(remaining, 0.5))  # INTENTIONAL: simulates slow webhook receiver
                remaining -= 0.5

        self.send_response(self.response_status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response_body = json.dumps({'status': 'received'})
        self.wfile.write(response_body.encode('utf-8'))

    def log_message(self, format, *args):
        """Suppress server logs during tests."""
        pass


class TestWebhookServer:
    """Test HTTP server for receiving webhook deliveries."""

    __test__ = False  # Not a test class — prevent pytest collection warning

    def __init__(self, port: int = 0, response_status: int = 200,
                 response_delay: float = 0.0):
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
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the HTTP server without blocking on in-flight requests."""
        if self.server:
            shutdown_thread = threading.Thread(target=self.server.shutdown, daemon=True)
            shutdown_thread.start()
            shutdown_thread.join(timeout=5)
            try:
                self.server.server_close()
            except Exception:
                pass
            self.server = None
            self.thread = None

    def get_url(self) -> str:
        """Get the server URL."""
        return f"http://localhost:{self.port}/webhook"

    def get_received_requests(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Get all received requests."""
        requests = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                request = self.request_queue.get(timeout=0.1)
                requests.append(request)
            except:
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
class ODPSWebhookEventsComprehensiveTest(TransactionTestCase):
    """Comprehensive tests for ODPS webhook events"""

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        pass

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        reset_circuit_breaker_by_name("webhook-delivery")
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

    def test_all_odps_webhook_events_created(self):
        """Test webhook delivery for odps.created event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Created Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "asset_id": str(uuid.uuid4()),
                "status": "DRAFT",
                "odps_version": "4.1",
                "original_format": "JSON",
                "normalization_status": "PENDING",
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            # Verify delivery
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_CREATED)
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

            # Verify HTTP request
            requests = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests), 1)
            payload = json.loads(requests[0]['body'])
            self.assertEqual(payload['event_type'], WebhookEventType.ODPS_CREATED)
            self.assertEqual(payload['data'], event_data)

    def test_all_odps_webhook_events_updated(self):
        """Test webhook delivery for odps.updated event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Updated Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_UPDATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "changes": {
                    "status": {"old": "DRAFT", "new": "ACTIVE"},
                    "odps_version": {"old": "4.0", "new": "4.1"},
                },
                "updated_fields": ["status", "odps_version"],
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_UPDATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_UPDATED)

    def test_all_odps_webhook_events_deleted(self):
        """Test webhook delivery for odps.deleted event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Deleted Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_DELETED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "deleted_at": timezone.now().isoformat(),
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_DELETED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_DELETED)

    def test_all_odps_webhook_events_normalized(self):
        """Test webhook delivery for odps.normalized event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Normalized Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_NORMALIZED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "normalization_status": "NORMALIZED_OK",
                "odps_version": "4.1",
                "validation_status": "VALID",
                "normalized_at": timezone.now().isoformat(),
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_NORMALIZED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_NORMALIZED)

    def test_all_odps_webhook_events_linked(self):
        """Test webhook delivery for odps.linked event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Linked Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_LINKED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "source_id": contract_id,
                "target_id": str(uuid.uuid4()),
                "link_type": "ODPS_TO_ODCS",
                "linked_at": timezone.now().isoformat(),
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_LINKED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_LINKED)

    def test_all_odps_webhook_events_unlinked(self):
        """Test webhook delivery for odps.unlinked event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Unlinked Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_UNLINKED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "source_id": contract_id,
                "target_id": str(uuid.uuid4()),
                "link_type": "ODPS_TO_ODCS",
                "unlinked_at": timezone.now().isoformat(),
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_UNLINKED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_UNLINKED)

    def test_all_odps_webhook_events_export_started(self):
        """Test webhook delivery for odps.export.started event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Export Started Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_EXPORT_STARTED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "export_format": "JSON",
                "export_target": "FILE",
                "started_at": timezone.now().isoformat(),
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_EXPORT_STARTED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_EXPORT_STARTED)

    def test_all_odps_webhook_events_export_completed(self):
        """Test webhook delivery for odps.export.completed event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Export Completed Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_EXPORT_COMPLETED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "export_format": "JSON",
                "export_url": "https://example.com/export.json",
                "completed_at": timezone.now().isoformat(),
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_EXPORT_COMPLETED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_EXPORT_COMPLETED)

    def test_all_odps_webhook_events_export_failed(self):
        """Test webhook delivery for odps.export.failed event"""
        with TestWebhookServer() as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Export Failed Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_EXPORT_FAILED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {
                "contract_id": contract_id,
                "export_format": "JSON",
                "error": "Export failed: Invalid contract",
                "failed_at": timezone.now().isoformat(),
            }

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_EXPORT_FAILED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence()

            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_EXPORT_FAILED)

    def test_odps_webhook_event_filtering_multiple_events(self):
        """Test webhook event filtering with multiple event subscriptions"""
        with TestWebhookServer() as server1, TestWebhookServer() as server2:
            # Webhook subscribed to multiple events
            webhook1 = Webhook.objects.create(
                tenant=self.tenant,
                name="Multi Event Webhook",
                url=server1.get_url(),
                secret="test-secret",
                event_types=[
                    WebhookEventType.ODPS_CREATED,
                    WebhookEventType.ODPS_UPDATED,
                    WebhookEventType.ODPS_DELETED,
                ],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            # Webhook subscribed to single event
            webhook2 = Webhook.objects.create(
                tenant=self.tenant,
                name="Single Event Webhook",
                url=server2.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())

            # Trigger ODPS_CREATED - both webhooks should receive
            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data={"contract_id": contract_id},
            )
            self.assertEqual(count, 2)
            wait_for_event_persistence()

            # Trigger ODPS_UPDATED - only webhook1 should receive
            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_UPDATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data={"contract_id": contract_id},
            )
            self.assertEqual(count, 1)
            wait_for_event_persistence()

            # Verify deliveries
            deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
            self.assertEqual(deliveries1.count(), 2)

            deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
            self.assertEqual(deliveries2.count(), 1)

    def test_odps_webhook_event_retry_logic(self):
        """Test webhook event retry logic with exponential backoff"""
        # Start server that returns 500 error (recoverable)
        with TestWebhookServer(response_status=500) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Retry Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                max_retries=3,
                retry_intervals=[1, 5, 30],  # 1s, 5s, 30s
                created_by=self.user,
            )

            contract_id = str(uuid.uuid4())
            event_data = {"contract_id": contract_id}

            count = WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=contract_id,
                event_data=event_data,
            )

            self.assertEqual(count, 1)
            wait_for_event_persistence(timeout=2.0)

            # Verify delivery was created
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertIsNotNone(delivery.error_message)
            # Should be scheduled for retry or failed
            self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])

            # Verify retry is scheduled
            if delivery.status == DeliveryStatus.FAILED:
                self.assertIsNotNone(delivery.next_retry_at)
                self.assertGreater(delivery.attempt_number, 0)

    def test_odps_webhook_event_dead_letter_queue(self):
        """Test webhook event dead letter queue after max retries"""
        # Use invalid URL to simulate persistent failure
        invalid_url = "http://localhost:99999/webhook"

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS DLQ Webhook",
            url=invalid_url,
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=2,
            retry_intervals=[1, 5],
            created_by=self.user,
        )

        contract_id = str(uuid.uuid4())
        event_data = {"contract_id": contract_id}

        count = WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=contract_id,
            event_data=event_data,
        )

        self.assertEqual(count, 1)
        wait_for_event_persistence(timeout=2.0)

        # Run _attempt_delivery and _schedule_retry until DEAD_LETTER (same pattern as
        # test_error_handling_max_retries_exceeded)
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertIsNotNone(delivery)
        for _ in range(webhook.max_retries + 1):
            WebhookDeliveryService._attempt_delivery(delivery)
            delivery.refresh_from_db()

            if delivery.attempt_number >= webhook.max_retries:
                WebhookDeliveryService._schedule_retry(delivery)
                delivery.refresh_from_db()
                break

            WebhookDeliveryService._schedule_retry(delivery)
            delivery.refresh_from_db()

        self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
        self.assertIsNone(delivery.next_retry_at)
