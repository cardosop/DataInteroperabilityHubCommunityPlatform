"""
Integration tests for ODPS webhook error scenarios.

Tests end-to-end error handling scenarios including:
- Complete webhook delivery flow with errors
- Error recovery and retry logic
- Multiple error types in sequence
- Error context and logging
"""
import json
import uuid
import requests
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
    ODPSWebhookDeliveryError,
    ODPSWebhookValidationError,
    ODPSWebhookPayloadError,
)
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ODPSWebhookErrorIntegrationTest(TestCase):
    """Integration tests for ODPS webhook error scenarios"""

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

        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
            max_retries=3,
            retry_intervals=[1, 5, 30],  # Must match max_retries
        )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_complete_error_handling_flow_timeout(self, mock_post):
        """Test complete error handling flow for timeout error"""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        event_data = {
            "contract_id": str(uuid.uuid4()),
            "status": "ACTIVE",
        }

        # Trigger webhook
        count = WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        self.assertEqual(count, 1)

        # Check delivery was created
        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIsNotNone(delivery.error_message)
        # Error message should contain timeout-related text
        error_msg_lower = delivery.error_message.lower()
        self.assertTrue(
            "timeout" in error_msg_lower or "timed out" in error_msg_lower,
            f"Expected 'timeout' or 'timed out' in error message, got: {delivery.error_message}"
        )
        self.assertIsNotNone(delivery.next_retry_at)

        # Verify error context
        self.assertEqual(delivery.event_type, WebhookEventType.ODPS_CREATED)
        self.assertEqual(delivery.webhook, self.webhook)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_error_handling_with_retry_success(self, mock_post):
        """Test error handling with retry that eventually succeeds"""
        # First attempt fails, second succeeds
        mock_responses = [
            MagicMock(status_code=500, text="Internal Server Error"),
            MagicMock(status_code=200, text="OK"),
        ]
        mock_post.side_effect = mock_responses

        event_data = {"contract_id": str(uuid.uuid4())}

        # Trigger webhook
        WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        # First attempt fails
        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertEqual(delivery.http_status_code, 500)
        self.assertEqual(delivery.attempt_number, 1)

        # Manually retry (simulating retry job)
        WebhookDeliveryService.retry_delivery(str(delivery.id))

        # Check retry succeeded
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.http_status_code, 200)
        self.assertIsNotNone(delivery.delivered_at)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_error_handling_max_retries_exceeded(self, mock_post):
        """Test error handling when max retries are exceeded"""
        # Always return 500 error
        mock_response = MagicMock(status_code=500, text="Internal Server Error")
        mock_post.return_value = mock_response

        event_data = {"contract_id": str(uuid.uuid4())}

        # Trigger webhook
        WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)

        # Simulate multiple retry attempts until max retries exceeded
        for attempt in range(self.webhook.max_retries + 1):
            WebhookDeliveryService._attempt_delivery(delivery)
            delivery.refresh_from_db()

            if delivery.attempt_number >= self.webhook.max_retries:
                break

            # Schedule next retry
            WebhookDeliveryService._schedule_retry(delivery)
            delivery.refresh_from_db()

        # Should be marked as dead letter
        self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
        self.assertIsNone(delivery.next_retry_at)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_error_handling_rate_limit(self, mock_post):
        """Test error handling for rate limit errors"""
        mock_response = MagicMock(status_code=429, text="Rate Limited")
        mock_response.headers = {"Retry-After": "60"}
        mock_post.return_value = mock_response

        event_data = {"contract_id": str(uuid.uuid4())}

        # Trigger webhook
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
        self.assertIsNotNone(delivery.next_retry_at)  # Should be retryable

    @patch('hub.apps.webhooks.service.requests.post')
    def test_error_handling_ssl_error(self, mock_post):
        """Test error handling for SSL errors"""
        mock_post.side_effect = requests.exceptions.SSLError("SSL certificate verification failed")

        event_data = {"contract_id": str(uuid.uuid4())}

        # Trigger webhook
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
        self.assertIn("ssl", delivery.error_message.lower())

    def test_payload_validation_integration(self):
        """Test payload validation integration with webhook triggering"""
        # Invalid payload - wrong event type
        with self.assertRaises(ODPSWebhookValidationError):
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type="invalid.event.type",
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )

        # Invalid payload - non-ODPS event type
        with self.assertRaises(ODPSWebhookValidationError):
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.CONTRACT_CREATED,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_error_handling_multiple_webhooks(self, mock_post):
        """Test error handling when multiple webhooks are triggered"""
        # Create second webhook
        webhook2 = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook 2",
            url="https://example.com/webhook2",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
            max_retries=3,
            retry_intervals=[1, 5, 30],  # Must match max_retries
        )

        # Map URLs to responses - one succeeds, one fails
        url_responses = {
            self.webhook.url: MagicMock(status_code=200, text="OK"),
            webhook2.url: MagicMock(status_code=500, text="Internal Server Error"),
        }

        def mock_post_side_effect(url, *args, **kwargs):
            # Return appropriate response based on URL
            return url_responses.get(url, MagicMock(status_code=500, text="Unknown URL"))

        mock_post.side_effect = mock_post_side_effect

        event_data = {"contract_id": str(uuid.uuid4())}

        # Trigger webhook
        count = WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        self.assertEqual(count, 2)

        # Check both deliveries - verify one succeeded and one failed
        delivery1 = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        delivery2 = WebhookDelivery.objects.filter(webhook=webhook2).first()

        self.assertIsNotNone(delivery1)
        self.assertIsNotNone(delivery2)

        # One should succeed, one should fail (order-independent check)
        statuses = {delivery1.status, delivery2.status}
        self.assertIn(DeliveryStatus.SUCCESS, statuses)
        self.assertIn(DeliveryStatus.FAILED, statuses)

        # Verify the failed one has the correct HTTP status
        failed_delivery = delivery1 if delivery1.status == DeliveryStatus.FAILED else delivery2
        self.assertEqual(failed_delivery.http_status_code, 500)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_error_handling_connection_error_recovery(self, mock_post):
        """Test connection error recovery"""
        # First attempt fails with connection error, second succeeds
        mock_responses = [
            requests.exceptions.ConnectionError("Connection refused"),
            MagicMock(status_code=200, text="OK"),
        ]
        mock_post.side_effect = mock_responses

        event_data = {"contract_id": str(uuid.uuid4())}

        # Trigger webhook
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

        # Retry should succeed
        WebhookDeliveryService.retry_delivery(str(delivery.id))
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

    def test_error_context_preservation(self):
        """Test that error context is properly preserved"""
        # Create webhook with specific configuration
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/test",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Try to deliver with inactive webhook
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

