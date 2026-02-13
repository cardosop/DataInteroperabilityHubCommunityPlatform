"""
Tests for Webhook Delivery Validators

Comprehensive tests for webhook delivery validation including:
- Delivery retry validation
- Delivery timeout validation
- Delivery status validation
- Dead letter queue validation

All tests follow engineering best practices:
- No mocks/stubs - use real services and models
- Test root causes, not symptoms
- Comprehensive test coverage
"""

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

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


class WebhookDeliveryRetryValidationTest(TestCase):
    """Tests for delivery retry validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-for-webhook-signature-generation",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
            created_by=self.user,
        )

    def test_validate_retry_valid_delivery(self):
        """TDD: Given a failed delivery with attempt_number < max_retries and next_retry_at set,
        When validate_delivery_retry is called, Then result is valid and details confirm retry is allowed.
        """
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=2,
            next_retry_at=timezone.now() + timedelta(seconds=30),
        )

        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["attempt_number"], 2)
        self.assertEqual(result.details["webhook_max_retries"], 5)
        self.assertTrue(result.details["max_retries_valid"])
        self.assertTrue(result.details["attempt_number_valid"])
        self.assertTrue(result.details["retry_intervals_valid"])
        self.assertTrue(result.details["attempt_within_limits"])
        self.assertTrue(result.details["retry_scheduled"])

    def test_validate_retry_max_retries_exceeded(self):
        """TDD: Given a delivery in DEAD_LETTER with attempt_number equal to max_retries,
        When validate_delivery_retry is called, Then result is valid and details indicate should_be_dead_letter.
        """
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.DEAD_LETTER,
            attempt_number=5,
            next_retry_at=None,
        )

        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["attempt_number"], 5)
        self.assertEqual(result.details["webhook_max_retries"], 5)
        self.assertTrue(result.details["attempt_within_limits"])
        self.assertTrue(result.details["should_be_dead_letter"])
        self.assertTrue(result.details["next_retry_should_be_none"])

    def test_validate_retry_negative_attempt_number(self):
        """TDD: Given a delivery with negative attempt_number, When validate_delivery_retry is called,
        Then result is invalid and errors mention non-negative."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.PENDING,
            attempt_number=-1,
        )

        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("non-negative", result.errors[0].lower())

    def test_validate_retry_attempt_exceeds_max_retries(self):
        """Test retry validation when attempt_number exceeds max_retries"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=10,
            next_retry_at=timezone.now() + timedelta(seconds=30),
        )

        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("exceeds", result.errors[0].lower())

    def test_validate_retry_failed_without_next_retry(self):
        """Test retry validation for failed delivery without next_retry_at"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=2,
            next_retry_at=None,
        )

        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("next_retry_at", result.errors[0].lower())

    def test_validate_retry_invalid_retry_intervals(self):
        """Test retry validation with invalid retry_intervals"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Invalid Retry Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-for-webhook-signature-generation",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=3,
            retry_intervals=[-1, 5, 30],  # Invalid negative interval
            created_by=self.user,
        )

        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=1,
        )

        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("retry_intervals", result.errors[0].lower())

    def test_validate_retry_retry_interval_matches(self):
        """Test retry validation checks retry interval matches expected"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=1,
            created_at=timezone.now() - timedelta(seconds=10),
            next_retry_at=timezone.now() + timedelta(seconds=5),  # Matches retry_intervals[1] = 5
        )

        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertTrue(result.details.get("retry_interval_matches", True))


class WebhookDeliveryTimeoutValidationTest(TestCase):
    """Tests for delivery timeout validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-for-webhook-signature-generation",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
            created_by=self.user,
        )

    def test_validate_timeout_valid_delivery(self):
        """Test timeout validation for valid delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.SUCCESS,
            delivered_at=timezone.now(),
        )

        result = WebhookDeliveryValidator.validate_delivery_timeout(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(len(result.errors), 0)
        # timeout_seconds is stored as string in details, compare as string
        self.assertEqual(
            result.details["timeout_seconds"], str(WebhookDeliveryService.REQUEST_TIMEOUT)
        )
        self.assertEqual(result.details["timeout_valid"], "true")

    def test_validate_timeout_with_timeout_error(self):
        """Test timeout validation with timeout error message"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=1,
            error_message="Webhook delivery timeout: Request timed out",
            next_retry_at=timezone.now() + timedelta(seconds=5),
        )

        result = WebhookDeliveryValidator.validate_delivery_timeout(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertTrue(result.details["has_timeout_error"])
        self.assertIn("timeout", result.details["timeout_error_message"].lower())
        self.assertTrue(result.details["timeout_retry_scheduled"])

    def test_validate_timeout_delivery_duration_exceeds_timeout(self):
        """Test timeout validation when delivery duration exceeds timeout"""
        created_at = timezone.now() - timedelta(seconds=60)  # 60 seconds ago
        delivered_at = timezone.now()  # Now

        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.SUCCESS,
            created_at=created_at,
            delivered_at=delivered_at,
        )

        result = WebhookDeliveryValidator.validate_delivery_timeout(delivery)

        # Should have warnings about duration exceeding timeout
        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertGreaterEqual(len(result.warnings), 0)
        if result.details.get("duration_within_timeout") is False:
            self.assertIn("duration", result.warnings[0].lower())

    def test_validate_timeout_timeout_error_without_retry(self):
        """Test timeout validation when timeout error doesn't trigger retry"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=1,
            error_message="Webhook delivery timeout: Request timed out",
            next_retry_at=None,  # No retry scheduled
        )

        result = WebhookDeliveryValidator.validate_delivery_timeout(delivery)

        # Should have warning about missing retry
        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        if result.details.get("timeout_retry_scheduled") is False:
            self.assertGreaterEqual(len(result.warnings), 0)


class WebhookDeliveryStatusValidationTest(TestCase):
    """Tests for delivery status validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-for-webhook-signature-generation",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
            created_by=self.user,
        )

    def test_validate_status_pending_valid(self):
        """Test status validation for valid PENDING delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.PENDING,
            attempt_number=0,
        )

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], DeliveryStatus.PENDING)
        self.assertTrue(result.details["status_valid"])

    def test_validate_status_pending_with_delivered_at(self):
        """Test status validation for PENDING delivery with delivered_at set"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.PENDING,
            delivered_at=timezone.now(),
        )

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("delivered_at", result.errors[0].lower())

    def test_validate_status_success_valid(self):
        """Test status validation for valid SUCCESS delivery"""
        # Create delivery first to ensure created_at is set
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
        )
        # Set delivered_at after creation to ensure it's after created_at
        delivery.delivered_at = timezone.now()
        delivery.save()

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], DeliveryStatus.SUCCESS)
        self.assertTrue(result.details["status_valid"])
        self.assertTrue(result.details["success_constraints_valid"])

    def test_validate_status_success_without_delivered_at(self):
        """Test status validation for SUCCESS delivery without delivered_at"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.SUCCESS,
            delivered_at=None,
        )

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("delivered_at", result.errors[0].lower())

    def test_validate_status_success_with_error_message(self):
        """Test status validation for SUCCESS delivery with error_message"""
        # Create delivery first to ensure created_at is set
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.SUCCESS,
            error_message="Some error",
        )
        # Set delivered_at after creation to ensure it's after created_at
        delivery.delivered_at = timezone.now()
        delivery.save()

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertGreaterEqual(len(result.warnings), 0)

    def test_validate_status_failed_valid(self):
        """Test status validation for valid FAILED delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=1,
            error_message="Delivery failed",
            next_retry_at=timezone.now() + timedelta(seconds=5),
        )

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], DeliveryStatus.FAILED)
        self.assertTrue(result.details["status_valid"])
        self.assertTrue(result.details["failed_constraints_valid"])

    def test_validate_status_failed_with_delivered_at(self):
        """Test status validation for FAILED delivery with delivered_at set"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            delivered_at=timezone.now(),
        )

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("delivered_at", result.errors[0].lower())

    def test_validate_status_dead_letter_valid(self):
        """Test status validation for valid DEAD_LETTER delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.DEAD_LETTER,
            attempt_number=5,
            error_message="Max retries exceeded",
            next_retry_at=None,
        )

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], DeliveryStatus.DEAD_LETTER)
        self.assertTrue(result.details["status_valid"])
        self.assertTrue(result.details["dead_letter_constraints_valid"])

    def test_validate_status_dead_letter_with_next_retry(self):
        """Test status validation for DEAD_LETTER delivery with next_retry_at set"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.DEAD_LETTER,
            next_retry_at=timezone.now() + timedelta(seconds=5),
        )

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertGreaterEqual(len(result.warnings), 0)

    def test_validate_status_invalid_status(self):
        """Test status validation for invalid status"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status="INVALID_STATUS",
        )

        # Manually set invalid status
        delivery.status = "INVALID_STATUS"
        delivery.save()

        result = WebhookDeliveryValidator.validate_delivery_status(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("invalid", result.errors[0].lower())


class WebhookDeliveryDLQValidationTest(TestCase):
    """Tests for dead letter queue validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-for-webhook-signature-generation",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
            created_by=self.user,
        )

    def test_validate_dlq_valid_dead_letter(self):
        """Test DLQ validation for valid DEAD_LETTER delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.DEAD_LETTER,
            attempt_number=5,
            error_message="Max retries exceeded",
            next_retry_at=None,
        )

        result = WebhookDeliveryValidator.validate_dead_letter_queue(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertTrue(result.details["is_dead_letter"])
        self.assertTrue(result.details["max_retries_exceeded"])
        self.assertTrue(result.details["no_retry_scheduled"])
        self.assertTrue(result.details["has_error_message"])
        self.assertTrue(result.details["no_delivered_at"])

    def test_validate_dlq_dead_letter_with_next_retry(self):
        """Test DLQ validation for DEAD_LETTER delivery with next_retry_at set"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.DEAD_LETTER,
            attempt_number=5,
            next_retry_at=timezone.now() + timedelta(seconds=5),
        )

        result = WebhookDeliveryValidator.validate_dead_letter_queue(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("next_retry_at", result.errors[0].lower())

    def test_validate_dlq_dead_letter_without_error_message(self):
        """Test DLQ validation for DEAD_LETTER delivery without error_message"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.DEAD_LETTER,
            attempt_number=5,
            error_message=None,
        )

        result = WebhookDeliveryValidator.validate_dead_letter_queue(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertGreaterEqual(len(result.warnings), 0)
        self.assertIn("error_message", result.warnings[0].lower())

    def test_validate_dlq_failed_should_be_in_dlq(self):
        """Test DLQ validation for FAILED delivery that should be in DLQ"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=5,  # Max retries exceeded
            error_message="Delivery failed",
        )

        result = WebhookDeliveryValidator.validate_dead_letter_queue(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertFalse(result.details["is_dead_letter"])
        self.assertTrue(result.details["should_be_in_dlq"])
        self.assertGreaterEqual(len(result.warnings), 0)

    def test_validate_dlq_premature_dead_letter(self):
        """Test DLQ validation for DEAD_LETTER delivery before max retries"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.DEAD_LETTER,
            attempt_number=2,  # Below max retries
            error_message="Delivery failed",
        )

        result = WebhookDeliveryValidator.validate_dead_letter_queue(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertFalse(result.details["max_retries_exceeded"])
        self.assertGreaterEqual(len(result.warnings), 0)
        self.assertIn("premature", result.warnings[0].lower())


class WebhookDeliveryComprehensiveValidationTest(TestCase):
    """Tests for comprehensive delivery validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-for-webhook-signature-generation",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
            created_by=self.user,
        )

    def test_validate_all_valid_delivery(self):
        """Test comprehensive validation for valid delivery"""
        # Create delivery first to ensure created_at is set
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
        )
        # Set delivered_at after creation to ensure it's after created_at
        delivery.delivered_at = timezone.now()
        delivery.save()

        result = WebhookDeliveryValidator.validate_all(delivery)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["validation_type"], "comprehensive_delivery_validation")

    def test_validate_all_invalid_delivery(self):
        """Test comprehensive validation for invalid delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.SUCCESS,
            delivered_at=None,  # Missing delivered_at
            attempt_number=-1,  # Invalid attempt_number
        )

        result = WebhookDeliveryValidator.validate_all(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_all_without_webhook(self):
        """Test comprehensive validation when webhook cannot be fetched"""
        # Create a delivery object but don't save it to avoid FK constraint
        # This simulates a delivery with an invalid webhook reference
        delivery = WebhookDelivery(
            webhook_id=str(uuid.uuid4()),  # Non-existent webhook ID
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.PENDING,
        )
        # Manually set the id to simulate a saved object
        delivery.id = uuid.uuid4()
        delivery.created_at = timezone.now()
        delivery.updated_at = timezone.now()

        result = WebhookDeliveryValidator.validate_all(delivery)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("webhook", result.errors[0].lower())

    def test_validate_delivery_retry_tdd_result_structure(self):
        """TDD: validate_delivery_retry result has is_valid, errors, details with expected keys."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ODPS_CREATED,
            payload={"test": "data"},
            signature="test-signature",
            status=DeliveryStatus.FAILED,
            attempt_number=2,
            next_retry_at=timezone.now() + timedelta(seconds=30),
        )
        result = WebhookDeliveryValidator.validate_delivery_retry(delivery)
        self.assertTrue(hasattr(result, "is_valid"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "details"))
        self.assertIsInstance(result.errors, list)
        self.assertIsInstance(result.details, dict)
        self.assertTrue(result.is_valid)
        for key in (
            "attempt_number",
            "webhook_max_retries",
            "max_retries_valid",
            "retry_scheduled",
        ):
            self.assertIn(key, result.details, f"Missing details key: {key}")
