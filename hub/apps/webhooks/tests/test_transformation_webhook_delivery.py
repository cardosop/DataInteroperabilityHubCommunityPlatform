"""
Unit and integration tests for transformation webhook delivery.

Tests that transformation events properly trigger webhook delivery with correct filtering,
validation, and retry logic.
"""

import json
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.odps_webhook_errors import (
    ODPSWebhookValidationError,
    ODPSWebhookPayloadError,
)
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TransformationWebhookDeliveryTest(TestCase):
    """Unit and integration tests for transformation webhook delivery"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_pipeline_created(self, mock_post):
        """Test that pipeline.created events trigger webhook delivery"""
        # Create webhook subscribed to transformation events
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Transformation Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger transformation webhook
        pipeline_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": pipeline_id,
            "name": "Test Pipeline",
            "version": "1.0.0",
            "status": "DRAFT",
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_CREATED,
            resource_type="PIPELINE",
            resource_id=pipeline_id,
            event_data=event_data,
        )

        # Verify webhook was triggered
        self.assertEqual(count, 1)

        # Verify delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, WebhookEventType.PIPELINE_CREATED)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertIsNotNone(delivery.delivered_at)

        # Verify payload structure
        payload = delivery.payload
        self.assertEqual(payload["event_type"], WebhookEventType.PIPELINE_CREATED)
        self.assertEqual(payload["resource_type"], "PIPELINE")
        self.assertEqual(payload["resource_id"], pipeline_id)
        self.assertIn("timestamp", payload)
        self.assertIn("data", payload)
        self.assertEqual(payload["data"]["pipeline_id"], pipeline_id)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_pipeline_execution_started(self, mock_post):
        """Test that pipeline.execution.started events trigger webhook delivery"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Execution Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_EXECUTION_STARTED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        pipeline_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": pipeline_id,
            "execution_id": execution_id,
            "asset_id": str(uuid.uuid4()),
            "execution_mode": "SYNC",
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_EXECUTION_STARTED,
            resource_type="EXECUTION",
            resource_id=execution_id,
            event_data=event_data,
        )

        self.assertEqual(count, 1)
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertEqual(delivery.event_type, WebhookEventType.PIPELINE_EXECUTION_STARTED)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_pipeline_execution_completed(self, mock_post):
        """Test that pipeline.execution.completed events trigger webhook delivery"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Execution Completed Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_EXECUTION_COMPLETED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        pipeline_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": pipeline_id,
            "execution_id": execution_id,
            "result_asset_id": str(uuid.uuid4()),
            "duration_ms": 5000,
            "records_processed": 1000,
            "quality_metrics": {"score": 0.95},
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_EXECUTION_COMPLETED,
            resource_type="EXECUTION",
            resource_id=execution_id,
            event_data=event_data,
        )

        self.assertEqual(count, 1)
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertEqual(delivery.event_type, WebhookEventType.PIPELINE_EXECUTION_COMPLETED)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_pipeline_execution_failed(self, mock_post):
        """Test that pipeline.execution.failed events trigger webhook delivery"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Execution Failed Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_EXECUTION_FAILED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        pipeline_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": pipeline_id,
            "execution_id": execution_id,
            "error_message": "Execution failed",
            "error_code": "EXECUTION_ERROR",
            "error_details": {"step": "transform"},
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_EXECUTION_FAILED,
            resource_type="EXECUTION",
            resource_id=execution_id,
            event_data=event_data,
        )

        self.assertEqual(count, 1)
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertEqual(delivery.event_type, WebhookEventType.PIPELINE_EXECUTION_FAILED)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_preview_generated(self, mock_post):
        """Test that preview.generated events trigger webhook delivery"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Preview Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PREVIEW_GENERATED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        pipeline_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        preview_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": pipeline_id,
            "asset_id": asset_id,
            "preview_id": preview_id,
            "row_count_changes": {"before": 100, "after": 95},
            "schema_changes": {"added": ["new_column"]},
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PREVIEW_GENERATED,
            resource_type="PREVIEW",
            resource_id=preview_id,
            event_data=event_data,
        )

        self.assertEqual(count, 1)
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertEqual(delivery.event_type, WebhookEventType.PREVIEW_GENERATED)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_wrangling_completed(self, mock_post):
        """Test that wrangling.completed events trigger webhook delivery"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Wrangling Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.WRANGLING_COMPLETED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        session_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        event_data = {
            "session_id": session_id,
            "operation_id": operation_id,
            "asset_id": asset_id,
            "operation_type": "filter",
            "rows_processed": 1000,
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.WRANGLING_COMPLETED,
            resource_type="WRANGLING",
            resource_id=operation_id,
            event_data=event_data,
        )

        self.assertEqual(count, 1)
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertEqual(delivery.event_type, WebhookEventType.WRANGLING_COMPLETED)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

    def test_trigger_transformation_webhook_invalid_event_type(self):
        """Test that invalid event types raise validation error"""
        with self.assertRaises(ODPSWebhookValidationError) as cm:
            WebhookDeliveryService.trigger_transformation_webhook(
                tenant_id=str(self.tenant.id),
                event_type="invalid.event.type",
                resource_type="PIPELINE",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )

        self.assertIn("is not a transformation event type", str(cm.exception))

    def test_trigger_transformation_webhook_payload_validation(self):
        """Test that payload validation works correctly"""
        # Missing required fields should fail validation
        with self.assertRaises(ODPSWebhookPayloadError):
            WebhookDeliveryService.trigger_transformation_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.PIPELINE_EXECUTION_STARTED,
                resource_type="EXECUTION",
                resource_id=str(uuid.uuid4()),
                event_data={},  # Missing pipeline_id and execution_id
            )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_multiple_webhooks(self, mock_post):
        """Test that multiple webhooks can subscribe to the same event"""
        # Create multiple webhooks
        webhook1 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 1",
            url="https://example.com/webhook1",
            secret="test-secret-1",
            event_types=[WebhookEventType.PIPELINE_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 2",
            url="https://example.com/webhook2",
            secret="test-secret-2",
            event_types=[WebhookEventType.PIPELINE_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        pipeline_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": pipeline_id,
            "name": "Test Pipeline",
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_CREATED,
            resource_type="PIPELINE",
            resource_id=pipeline_id,
            event_data=event_data,
        )

        # Both webhooks should be triggered
        self.assertEqual(count, 2)

        # Verify both deliveries were created
        deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
        deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
        self.assertEqual(deliveries1.count(), 1)
        self.assertEqual(deliveries2.count(), 1)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_transformation_webhook_inactive_webhook(self, mock_post):
        """Test that inactive webhooks are not triggered"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Inactive Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_CREATED],
            status=WebhookStatus.PAUSED,  # Inactive
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        pipeline_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": pipeline_id,
            "name": "Test Pipeline",
        }

        count = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_CREATED,
            resource_type="PIPELINE",
            resource_id=pipeline_id,
            event_data=event_data,
        )

        # No webhooks should be triggered
        self.assertEqual(count, 0)

        # No deliveries should be created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 0)

