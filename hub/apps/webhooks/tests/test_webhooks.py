"""
Unit tests for Webhook Models and Service

Tests for webhook subscriptions and delivery.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, Mock

from hub.apps.webhooks.models import Webhook, WebhookDelivery, WebhookStatus, DeliveryStatus, WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class WebhookModelTest(TestCase):
    """Test Webhook model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_create_webhook(self):
        """Test webhook creation"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user
        )
        
        self.assertEqual(webhook.status, WebhookStatus.ACTIVE)
        self.assertIn(WebhookEventType.ASSET_CREATED, webhook.event_types)
    
    def test_webhook_signature(self):
        """Test webhook signature generation"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user
        )
        
        payload = '{"test": "data"}'
        signature = webhook.generate_signature(payload)
        
        self.assertIsNotNone(signature)
        self.assertEqual(len(signature), 64)  # SHA256 hex length


class WebhookDeliveryServiceTest(TestCase):
    """Test WebhookDeliveryService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user
        )
    
    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_webhook_success(self, mock_post):
        """Test successful webhook delivery"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response
        
        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ASSET_CREATED,
            resource_type="ASSET",
            resource_id="test-id",
            event_data={"test": "data"}
        )
        
        self.assertEqual(count, 1)
        
        # Verify delivery was created
        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
    
    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_webhook_retry(self, mock_post):
        """Test webhook delivery with retry"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ASSET_CREATED,
            resource_type="ASSET",
            resource_id="test-id",
            event_data={"test": "data"}
        )
        
        self.assertEqual(count, 1)
        
        # Verify delivery was created with retry scheduled
        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertIsNotNone(delivery.next_retry_at)

