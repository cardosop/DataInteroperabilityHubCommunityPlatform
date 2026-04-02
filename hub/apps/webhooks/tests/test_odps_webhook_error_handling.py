"""
Unit tests for ODPS webhook error handling and validation.

Tests comprehensive error handling for ODPS webhook operations including:
- Error class hierarchy and structure
- Payload validation
- Delivery error handling (via real server or unreachable URL; no mocks)
- Error recovery strategies
"""

import time
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.contracts.odps_errors import RecoveryStrategy
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
    ODPSWebhookDeliveryError,
    ODPSWebhookError,
    ODPSWebhookPayloadError,
    ODPSWebhookValidationError,
)
from hub.apps.webhooks.odps_webhook_validators import (
    MAX_PAYLOAD_SIZE,
    validate_odps_event_data,
    validate_odps_webhook_payload,
)
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer
from tests.utils.wait_helpers import wait_for_event_persistence

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ODPSWebhookErrorTest(TestCase):
    """Test ODPS webhook error classes"""

    def test_odps_webhook_error_basic(self):
        """Test basic ODPS webhook error creation"""
        error = ODPSWebhookError(
            message="Test error",
            tenant_id="tenant-123",
            webhook_id="webhook-456",
            event_type="odps.created",
        )

        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.tenant_id, "tenant-123")
        self.assertEqual(error.webhook_id, "webhook-456")
        self.assertEqual(error.event_type, "odps.created")
        self.assertIn("webhook_id", error.context)
        self.assertIn("event_type", error.context)

    def test_odps_webhook_delivery_error_http(self):
        """Test ODPS webhook delivery error with HTTP status"""
        error = ODPSWebhookDeliveryError(
            message="HTTP 500 error",
            error_code=ODPSWebhookDeliveryError.ERROR_CODE_HTTP_ERROR,
            http_status_code=500,
            url="https://example.com/webhook",
            tenant_id="tenant-123",
            webhook_id="webhook-456",
        )

        self.assertEqual(error.http_status_code, 500)
        self.assertEqual(error.url, "https://example.com/webhook")
        self.assertTrue(error.recoverable)  # 5xx errors are retryable
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.RETRY)

    def test_odps_webhook_delivery_error_4xx(self):
        """Test ODPS webhook delivery error with 4xx status"""
        error = ODPSWebhookDeliveryError(
            message="HTTP 400 error",
            error_code=ODPSWebhookDeliveryError.ERROR_CODE_HTTP_ERROR,
            http_status_code=400,
            url="https://example.com/webhook",
        )

        self.assertEqual(error.http_status_code, 400)
        self.assertFalse(error.recoverable)  # 4xx errors are not retryable
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FAIL)

    def test_odps_webhook_delivery_error_rate_limit(self):
        """Test ODPS webhook delivery error for rate limiting"""
        error = ODPSWebhookDeliveryError(
            message="Rate limited",
            error_code=ODPSWebhookDeliveryError.ERROR_CODE_RATE_LIMITED,
            http_status_code=429,
            retry_after=60,
        )

        self.assertEqual(error.http_status_code, 429)
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.RETRY)
        self.assertEqual(error.retry_after, 60)

    def test_odps_webhook_validation_error(self):
        """Test ODPS webhook validation error"""
        error = ODPSWebhookValidationError(
            message="Invalid event type",
            error_code=ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
            field_path="event_type",
            expected="odps.created",
            actual="contract.created",
        )

        self.assertEqual(error.field_path, "event_type")
        self.assertEqual(error.expected, "odps.created")
        self.assertEqual(error.actual, "contract.created")
        self.assertFalse(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FAIL)

    def test_odps_webhook_payload_error(self):
        """Test ODPS webhook payload error"""
        error = ODPSWebhookPayloadError(
            message="Invalid payload",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_PAYLOAD_STRUCTURE,
            field_path="data.contract_id",
            expected="str",
            actual="int",
        )

        self.assertEqual(error.field_path, "data.contract_id")
        self.assertEqual(error.expected, "str")
        self.assertEqual(error.actual, "int")
        self.assertFalse(error.recoverable)


class ODPSWebhookPayloadValidationTest(TestCase):
    """Test ODPS webhook payload validation"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

    def test_validate_valid_odps_payload(self):
        """Test validation of valid ODPS payload"""
        payload = {
            "event_type": WebhookEventType.ODPS_CREATED,
            "resource_type": "ODPS",
            "resource_id": str(uuid.uuid4()),
            "timestamp": timezone.now().isoformat(),
            "data": {
                "contract_id": str(uuid.uuid4()),
                "status": "ACTIVE",
            },
        }

        # Should not raise
        validate_odps_webhook_payload(
            payload=payload,
            event_type=WebhookEventType.ODPS_CREATED,
            tenant_id=str(self.tenant.id),
        )

    def test_validate_payload_missing_required_field(self):
        """Test validation fails for missing required field"""
        payload = {
            "event_type": WebhookEventType.ODPS_CREATED,
            "resource_type": "ODPS",
            # Missing resource_id
            "timestamp": timezone.now().isoformat(),
            "data": {},
        }

        with self.assertRaises(ODPSWebhookPayloadError) as cm:
            validate_odps_webhook_payload(
                payload=payload,
                event_type=WebhookEventType.ODPS_CREATED,
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD,
        )
        self.assertEqual(cm.exception.field_path, "resource_id")

    def test_validate_payload_invalid_event_type(self):
        """Test validation fails for invalid event type"""
        payload = {
            "event_type": WebhookEventType.ODPS_CREATED,
            "resource_type": "ODPS",
            "resource_id": str(uuid.uuid4()),
            "timestamp": timezone.now().isoformat(),
            "data": {},
        }

        with self.assertRaises(ODPSWebhookValidationError) as cm:
            validate_odps_webhook_payload(
                payload=payload,
                event_type="contract.created",  # Not an ODPS event
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
        )

    def test_validate_payload_event_type_mismatch(self):
        """Test validation fails when payload event_type doesn't match"""
        payload = {
            "event_type": WebhookEventType.ODPS_UPDATED,  # Different from expected
            "resource_type": "ODPS",
            "resource_id": str(uuid.uuid4()),
            "timestamp": timezone.now().isoformat(),
            "data": {},
        }

        with self.assertRaises(ODPSWebhookPayloadError) as cm:
            validate_odps_webhook_payload(
                payload=payload,
                event_type=WebhookEventType.ODPS_CREATED,
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_VALUE,
        )

    def test_validate_payload_invalid_field_type(self):
        """Test validation fails for invalid field type"""
        payload = {
            "event_type": WebhookEventType.ODPS_CREATED,
            "resource_type": "ODPS",
            "resource_id": 12345,  # Should be string
            "timestamp": timezone.now().isoformat(),
            "data": {},
        }

        with self.assertRaises(ODPSWebhookPayloadError) as cm:
            validate_odps_webhook_payload(
                payload=payload,
                event_type=WebhookEventType.ODPS_CREATED,
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
        )
        self.assertEqual(cm.exception.field_path, "resource_id")

    def test_validate_payload_too_large(self):
        """Test validation fails for payload that's too large"""
        # Create a payload that exceeds MAX_PAYLOAD_SIZE
        large_data = {"data": "x" * (MAX_PAYLOAD_SIZE + 1000)}
        payload = {
            "event_type": WebhookEventType.ODPS_CREATED,
            "resource_type": "ODPS",
            "resource_id": str(uuid.uuid4()),
            "timestamp": timezone.now().isoformat(),
            "data": large_data,
        }

        with self.assertRaises(ODPSWebhookPayloadError) as cm:
            validate_odps_webhook_payload(
                payload=payload,
                event_type=WebhookEventType.ODPS_CREATED,
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookPayloadError.ERROR_CODE_PAYLOAD_TOO_LARGE,
        )

    def test_validate_odps_created_event_data(self):
        """Test validation of ODPS created event data"""
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "status": "ACTIVE",
        }

        # Should not raise
        validate_odps_event_data(
            event_data=event_data,
            event_type=WebhookEventType.ODPS_CREATED,
            tenant_id=str(self.tenant.id),
        )

    def test_validate_odps_updated_event_data(self):
        """Test validation of ODPS updated event data"""
        event_data = {
            "changes": {
                "status": "ACTIVE",
            },
        }

        # Should not raise
        validate_odps_event_data(
            event_data=event_data,
            event_type=WebhookEventType.ODPS_UPDATED,
            tenant_id=str(self.tenant.id),
        )

    def test_validate_odps_linked_event_data(self):
        """Test validation of ODPS linked event data"""
        event_data = {
            "source_id": str(uuid.uuid4()),
            "target_id": str(uuid.uuid4()),
        }

        # Should not raise
        validate_odps_event_data(
            event_data=event_data,
            event_type=WebhookEventType.ODPS_LINKED,
            tenant_id=str(self.tenant.id),
        )

    def test_validate_odps_linked_event_data_invalid_type(self):
        """Test validation fails for invalid field type in linked event data"""
        event_data = {
            "source_id": 12345,  # Should be string
            "target_id": str(uuid.uuid4()),
        }

        with self.assertRaises(ODPSWebhookPayloadError) as cm:
            validate_odps_event_data(
                event_data=event_data,
                event_type=WebhookEventType.ODPS_LINKED,
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
        )
        self.assertEqual(cm.exception.field_path, "data.source_id")


class ODPSWebhookDeliveryErrorHandlingTest(TestCase):
    """Test ODPS webhook delivery error handling"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
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
        )

    @override_settings(WEBHOOK_REQUEST_TIMEOUT=2)
    def test_delivery_timeout_error(self):
        """Test handling of timeout errors via real server with delay exceeding client timeout."""
        # Delay (15s) must exceed WEBHOOK_REQUEST_TIMEOUT (overridden to 2s)
        # so the client times out before the server responds.
        with TestWebhookServer(response_status=200, response_delay=15.0) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )
            wait_for_event_persistence(timeout=5.0)
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertIsNotNone(delivery.error_message)
            error_msg_lower = delivery.error_message.lower()
            self.assertTrue(
                "timeout" in error_msg_lower or "timed out" in error_msg_lower,
                f"Expected timeout-related message, got: {delivery.error_message}",
            )
            self.assertIsNotNone(delivery.next_retry_at)

    def test_delivery_connection_error(self):
        """Test handling of connection errors (unreachable URL, no mock)."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="http://127.0.0.1:9/",  # Discard port, no server
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        event_data = {"contract_id": str(uuid.uuid4())}
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )
        wait_for_event_persistence()
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIsNotNone(delivery.error_message)
        self.assertIn("connect", delivery.error_message.lower())

    def test_delivery_http_5xx_error(self):
        """Test handling of HTTP 5xx errors via real server returning 500."""
        with TestWebhookServer(response_status=500) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )
            wait_for_event_persistence()
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertEqual(delivery.http_status_code, 500)
            self.assertIsNotNone(delivery.next_retry_at)

    def test_delivery_http_4xx_error(self):
        """Test handling of HTTP 4xx errors via real server returning 400."""
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
            event_data = {"contract_id": str(uuid.uuid4())}
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )
            wait_for_event_persistence()
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertEqual(delivery.http_status_code, 400)

    def test_delivery_ssl_error(self):
        """Test handling of connection/network errors (unreachable URL; no mock)."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="http://127.0.0.1:9/",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        event_data = {"contract_id": str(uuid.uuid4())}
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )
        wait_for_event_persistence()
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)
        self.assertIsNotNone(delivery.error_message)

    def test_trigger_odps_webhook_invalid_payload(self):
        """Test trigger_odps_webhook raises error for invalid event type"""
        # Invalid event type - not an ODPS event
        event_data = {}

        # This should fail during event type validation (before payload validation)
        with self.assertRaises(ODPSWebhookValidationError):
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type="invalid.event.type",  # This will fail validation
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

    def test_trigger_odps_webhook_invalid_event_type(self):
        """Test trigger_odps_webhook raises error for non-ODPS event type"""
        with self.assertRaises(ODPSWebhookValidationError) as cm:
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.CONTRACT_CREATED,  # Not an ODPS event
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
        )

    def test_deliver_webhook_inactive_webhook(self):
        """Test _deliver_webhook raises error for inactive webhook"""
        self.webhook.status = WebhookStatus.PAUSED
        self.webhook.save()

        with self.assertRaises(ODPSWebhookValidationError) as cm:
            WebhookDeliveryService._deliver_webhook(
                webhook=self.webhook,
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data={"contract_id": str(uuid.uuid4())},
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookValidationError.ERROR_CODE_WEBHOOK_INACTIVE,
        )

    def test_deliver_webhook_not_subscribed(self):
        """Test _deliver_webhook raises error when webhook doesn't subscribe to event"""
        # Create webhook subscribed to different event
        other_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Other Webhook",
            url="https://example.com/other",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_UPDATED],  # Different event
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        with self.assertRaises(ODPSWebhookValidationError) as cm:
            WebhookDeliveryService._deliver_webhook(
                webhook=other_webhook,
                event_type=WebhookEventType.ODPS_CREATED,  # Not subscribed
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data={"contract_id": str(uuid.uuid4())},
            )

        self.assertEqual(
            cm.exception.error_code,
            ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
        )
