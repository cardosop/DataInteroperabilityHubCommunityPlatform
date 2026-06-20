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

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True)]

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
from hub.apps.webhooks.service import WebhookDeliveryService
from tests.utils.wait_helpers import wait_for_event_persistence

from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

User = get_user_model()


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
            payload = json.loads(requests[0]["body"])
            self.assertEqual(payload["event_type"], WebhookEventType.ODPS_CREATED)
            self.assertEqual(payload["data"], event_data)

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
            # Should be FAILED with retry scheduled (500 response triggers retry)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
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
