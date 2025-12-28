"""
End-to-end tests for transformation webhook retry logic.

Tests complete webhook delivery flow with retry mechanisms in realistic scenarios.
"""

import json
import uuid
import time
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
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TransformationWebhookE2ETest(TestCase):
    """End-to-end tests for transformation webhook retry logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_e2e_webhook_retry_flow_success_after_retries(self, mock_post):
        """
        E2E test: Webhook delivery succeeds after multiple retries.

        Scenario:
        1. Pipeline created event triggers webhook
        2. First delivery attempt fails (500 error)
        3. Retry with exponential backoff
        4. Second attempt fails (timeout)
        5. Retry again
        6. Third attempt succeeds
        """
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="E2E Retry Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],  # 1s, 5s, 30s
            created_by=self.user,
        )

        import requests
        # Simulate failure, failure, then success
        mock_responses = [
            MagicMock(status_code=500, text="Internal Server Error"),
            requests.exceptions.Timeout("Request timed out"),
            MagicMock(status_code=200, text="OK"),
        ]
        mock_post.side_effect = mock_responses

        # Trigger webhook
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

        self.assertEqual(count, 1)

        # Get delivery
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertIsNotNone(delivery)
        # After first attempt fails, attempt_number is incremented to 1
        self.assertEqual(delivery.attempt_number, 1)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)

        # First retry (attempt_number is incremented when retry fails)
        WebhookDeliveryService.retry_delivery(str(delivery.id))
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempt_number, 2)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)

        # Second retry
        WebhookDeliveryService.retry_delivery(str(delivery.id))
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempt_number, 2)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertIsNotNone(delivery.delivered_at)

        # Verify all attempts were made
        self.assertEqual(mock_post.call_count, 3)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_e2e_webhook_retry_flow_max_retries_exceeded(self, mock_post):
        """
        E2E test: Webhook delivery stops after max retries.

        Scenario:
        1. Pipeline execution started event triggers webhook
        2. All delivery attempts fail (500 errors)
        3. After max retries (3), delivery moves to dead letter queue
        """
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="E2E Max Retries Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_EXECUTION_STARTED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        # All attempts fail
        mock_response = MagicMock(status_code=500, text="Internal Server Error")
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

        # Retry until max retries exceeded
        for i in range(3):
            WebhookDeliveryService.retry_delivery(str(delivery.id))
            delivery.refresh_from_db()

        # Should be in dead letter after max retries
        self.assertEqual(delivery.attempt_number, 3)
        self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
        self.assertIsNone(delivery.next_retry_at)

        # Verify all attempts were made
        self.assertEqual(mock_post.call_count, 4)  # Initial + 3 retries

    @patch('hub.apps.webhooks.service.requests.post')
    def test_e2e_webhook_retry_flow_multiple_events(self, mock_post):
        """
        E2E test: Multiple transformation events trigger webhooks with retry logic.

        Scenario:
        1. Pipeline created event triggers webhook (succeeds immediately)
        2. Pipeline execution started event triggers webhook (fails, retries, succeeds)
        3. Pipeline execution completed event triggers webhook (succeeds immediately)
        """
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="E2E Multiple Events Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[
                WebhookEventType.PIPELINE_CREATED,
                WebhookEventType.PIPELINE_EXECUTION_STARTED,
                WebhookEventType.PIPELINE_EXECUTION_COMPLETED,
            ],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        import requests
        call_count = 0

        def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call (pipeline.created) succeeds
            if call_count == 1:
                return MagicMock(status_code=200, text="OK")
            # Second call (execution.started) fails
            elif call_count == 2:
                return MagicMock(status_code=500, text="Internal Server Error")
            # Third call (execution.started retry) succeeds
            elif call_count == 3:
                return MagicMock(status_code=200, text="OK")
            # Fourth call (execution.completed) succeeds
            elif call_count == 4:
                return MagicMock(status_code=200, text="OK")
            else:
                return MagicMock(status_code=200, text="OK")

        mock_post.side_effect = mock_post_side_effect

        pipeline_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        # Event 1: Pipeline created (succeeds immediately)
        count1 = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_CREATED,
            resource_type="PIPELINE",
            resource_id=pipeline_id,
            event_data={"pipeline_id": pipeline_id, "name": "Test Pipeline"},
        )
        self.assertEqual(count1, 1)

        delivery1 = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type=WebhookEventType.PIPELINE_CREATED
        ).first()
        self.assertEqual(delivery1.status, DeliveryStatus.SUCCESS)

        # Event 2: Execution started (fails, needs retry)
        count2 = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_EXECUTION_STARTED,
            resource_type="EXECUTION",
            resource_id=execution_id,
            event_data={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "asset_id": str(uuid.uuid4()),
            },
        )
        self.assertEqual(count2, 1)

        delivery2 = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type=WebhookEventType.PIPELINE_EXECUTION_STARTED
        ).first()
        self.assertEqual(delivery2.status, DeliveryStatus.FAILED)

        # Retry execution started
        WebhookDeliveryService.retry_delivery(str(delivery2.id))
        delivery2.refresh_from_db()
        self.assertEqual(delivery2.status, DeliveryStatus.SUCCESS)

        # Event 3: Execution completed (succeeds immediately)
        count3 = WebhookDeliveryService.trigger_transformation_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.PIPELINE_EXECUTION_COMPLETED,
            resource_type="EXECUTION",
            resource_id=execution_id,
            event_data={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "duration_ms": 5000,
                "records_processed": 1000,
            },
        )
        self.assertEqual(count3, 1)

        delivery3 = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type=WebhookEventType.PIPELINE_EXECUTION_COMPLETED
        ).first()
        self.assertEqual(delivery3.status, DeliveryStatus.SUCCESS)

        # Verify all deliveries
        self.assertEqual(WebhookDelivery.objects.filter(webhook=webhook).count(), 3)
        self.assertEqual(mock_post.call_count, 4)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_e2e_webhook_retry_flow_payload_validation(self, mock_post):
        """
        E2E test: Webhook payload validation works correctly with retry logic.

        Scenario:
        1. Valid payload triggers webhook successfully
        2. Invalid payload fails validation before delivery
        """
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="E2E Validation Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.PIPELINE_EXECUTION_STARTED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[1, 5, 30],
            created_by=self.user,
        )

        mock_response = MagicMock(status_code=200, text="OK")
        mock_post.return_value = mock_response

        pipeline_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        # Valid payload should succeed
        event_data = {
            "pipeline_id": pipeline_id,
            "execution_id": execution_id,
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
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

        # Invalid payload should fail validation
        from hub.apps.webhooks.odps_webhook_errors import ODPSWebhookPayloadError

        with self.assertRaises(ODPSWebhookPayloadError):
            # Missing required fields
            WebhookDeliveryService.trigger_transformation_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.PIPELINE_EXECUTION_STARTED,
                resource_type="EXECUTION",
                resource_id=execution_id,
                event_data={},  # Missing pipeline_id and execution_id
            )

        # No new delivery should be created for invalid payload
        self.assertEqual(WebhookDelivery.objects.filter(webhook=webhook).count(), 1)

