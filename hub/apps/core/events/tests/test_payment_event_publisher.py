"""
Integration tests for PaymentEventPublisher.

Tests event publishing using real EventPublisher and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.core.events.service_publishers import PaymentEventPublisher
from hub.apps.core.events.models import Event
import uuid

uid = uuid.uuid4().hex[:8]


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class PaymentEventPublisherIntegrationTest(TestCase):
    """Integration tests for PaymentEventPublisher using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
            region="us-east-1"
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create test IDs
        self.payment_id = str(uuid.uuid4())
        self.order_id = str(uuid.uuid4())

        # Create a test service with PaymentEventPublisher
        class TestPaymentService(PaymentEventPublisher):
            def __init__(self, tenant_id=None, user_id=None):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__(tenant_id=tenant_id, user_id=user_id)

        self.service = TestPaymentService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_publish_payment_initiated_event(self):
        """Test publishing payment.initiated event with real EventPublisher."""
        event_id = self.service.publish_payment_initiated(
            payment_id=self.payment_id,
            order_id=self.order_id,
            amount=99.99,
            currency="USD",
            gateway="stripe",
            payment_method="card"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.initiated")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertEqual(event.data["amount"], 99.99)
        self.assertEqual(event.data["currency"], "USD")
        self.assertEqual(event.data["gateway"], "stripe")
        self.assertEqual(event.data["payment_method"], "card")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        # The source_service is set to the service_name from EventPublisher
        self.assertEqual(event.source_service, "payment_service")

    def test_publish_payment_initiated_with_minimal_data(self):
        """Test publishing payment.initiated event with only required fields."""
        event_id = self.service.publish_payment_initiated(
            payment_id=self.payment_id,
            order_id=self.order_id
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.initiated")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertIsNone(event.data.get("amount"))
        self.assertIsNone(event.data.get("currency"))
        self.assertIsNone(event.data.get("gateway"))
        self.assertIsNone(event.data.get("payment_method"))

    def test_publish_payment_completed_event(self):
        """Test publishing payment.completed event with real EventPublisher."""
        gateway_transaction_id = "txn_1234567890"
        processed_at = timezone.now().isoformat()

        event_id = self.service.publish_payment_completed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            status="SUCCEEDED",
            amount=99.99,
            currency="USD",
            gateway="stripe",
            gateway_transaction_id=gateway_transaction_id,
            processed_at=processed_at
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.completed")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertEqual(event.data["status"], "SUCCEEDED")
        self.assertEqual(event.data["amount"], 99.99)
        self.assertEqual(event.data["currency"], "USD")
        self.assertEqual(event.data["gateway"], "stripe")
        self.assertEqual(event.data["gateway_transaction_id"], gateway_transaction_id)
        self.assertEqual(event.data["processed_at"], processed_at)

    def test_publish_payment_completed_with_auto_timestamp(self):
        """Test publishing payment.completed event with auto-generated timestamp."""
        before_publish = timezone.now()
        event_id = self.service.publish_payment_completed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            status="SUCCEEDED"
        )
        after_publish = timezone.now()

        # Verify event was published
        self.assertIsNotNone(event_id)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.completed")
        self.assertIsNotNone(event.data.get("processed_at"))
        # Verify processed_at is a valid ISO format datetime string
        from datetime import datetime, timezone as dt_timezone
        processed_at = datetime.fromisoformat(event.data["processed_at"].replace('Z', '+00:00'))
        self.assertGreaterEqual(processed_at, before_publish.replace(tzinfo=dt_timezone.utc))
        self.assertLessEqual(processed_at, after_publish.replace(tzinfo=dt_timezone.utc))

    def test_publish_payment_completed_with_minimal_data(self):
        """Test publishing payment.completed event with only required fields."""
        event_id = self.service.publish_payment_completed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            status="SUCCEEDED"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.completed")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertEqual(event.data["status"], "SUCCEEDED")
        self.assertIsNone(event.data.get("amount"))
        self.assertIsNone(event.data.get("currency"))
        self.assertIsNone(event.data.get("gateway"))
        self.assertIsNone(event.data.get("gateway_transaction_id"))

    def test_publish_payment_failed_event(self):
        """Test publishing payment.failed event with real EventPublisher."""
        error_message = "Card declined"
        error_details = {"decline_code": "insufficient_funds", "code": "card_declined"}
        failed_at = timezone.now().isoformat()

        event_id = self.service.publish_payment_failed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            error_message=error_message,
            error_details=error_details,
            amount=99.99,
            currency="USD",
            gateway="stripe",
            failed_at=failed_at
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.failed")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertEqual(event.data["error_message"], error_message)
        self.assertEqual(event.data["error_details"], error_details)
        self.assertEqual(event.data["amount"], 99.99)
        self.assertEqual(event.data["currency"], "USD")
        self.assertEqual(event.data["gateway"], "stripe")
        self.assertEqual(event.data["failed_at"], failed_at)

    def test_publish_payment_failed_with_auto_timestamp(self):
        """Test publishing payment.failed event with auto-generated timestamp."""
        before_publish = timezone.now()
        event_id = self.service.publish_payment_failed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            error_message="Payment gateway timeout"
        )
        after_publish = timezone.now()

        # Verify event was published
        self.assertIsNotNone(event_id)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.failed")
        self.assertIsNotNone(event.data.get("failed_at"))
        # Verify failed_at is a valid ISO format datetime string
        from datetime import datetime, timezone as dt_timezone
        failed_at = datetime.fromisoformat(event.data["failed_at"].replace('Z', '+00:00'))
        self.assertGreaterEqual(failed_at, before_publish.replace(tzinfo=dt_timezone.utc))
        self.assertLessEqual(failed_at, after_publish.replace(tzinfo=dt_timezone.utc))

    def test_publish_payment_failed_with_minimal_data(self):
        """Test publishing payment.failed event with only required fields."""
        event_id = self.service.publish_payment_failed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            error_message="Payment processing failed"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.failed")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertEqual(event.data["error_message"], "Payment processing failed")
        self.assertIsNone(event.data.get("error_details"))
        self.assertIsNone(event.data.get("amount"))
        self.assertIsNone(event.data.get("currency"))
        self.assertIsNone(event.data.get("gateway"))

    def test_publish_payment_refunded_event(self):
        """Test publishing payment.refunded event with real EventPublisher."""
        gateway_refund_id = "re_1234567890"
        refund_reason = "Customer requested refund"
        refunded_at = timezone.now().isoformat()

        event_id = self.service.publish_payment_refunded(
            payment_id=self.payment_id,
            order_id=self.order_id,
            refund_amount=99.99,
            currency="USD",
            gateway="stripe",
            gateway_refund_id=gateway_refund_id,
            refund_reason=refund_reason,
            refunded_at=refunded_at
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.refunded")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertEqual(event.data["refund_amount"], 99.99)
        self.assertEqual(event.data["currency"], "USD")
        self.assertEqual(event.data["gateway"], "stripe")
        self.assertEqual(event.data["gateway_refund_id"], gateway_refund_id)
        self.assertEqual(event.data["refund_reason"], refund_reason)
        self.assertEqual(event.data["refunded_at"], refunded_at)

    def test_publish_payment_refunded_with_auto_timestamp(self):
        """Test publishing payment.refunded event with auto-generated timestamp."""
        before_publish = timezone.now()
        event_id = self.service.publish_payment_refunded(
            payment_id=self.payment_id,
            order_id=self.order_id
        )
        after_publish = timezone.now()

        # Verify event was published
        self.assertIsNotNone(event_id)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.refunded")
        self.assertIsNotNone(event.data.get("refunded_at"))
        # Verify refunded_at is a valid ISO format datetime string
        from datetime import datetime, timezone as dt_timezone
        refunded_at = datetime.fromisoformat(event.data["refunded_at"].replace('Z', '+00:00'))
        self.assertGreaterEqual(refunded_at, before_publish.replace(tzinfo=dt_timezone.utc))
        self.assertLessEqual(refunded_at, after_publish.replace(tzinfo=dt_timezone.utc))

    def test_publish_payment_refunded_with_minimal_data(self):
        """Test publishing payment.refunded event with only required fields."""
        event_id = self.service.publish_payment_refunded(
            payment_id=self.payment_id,
            order_id=self.order_id
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "payment.refunded")
        self.assertEqual(event.data["payment_id"], self.payment_id)
        self.assertEqual(event.data["order_id"], self.order_id)
        self.assertIsNone(event.data.get("refund_amount"))
        self.assertIsNone(event.data.get("currency"))
        self.assertIsNone(event.data.get("gateway"))
        self.assertIsNone(event.data.get("gateway_refund_id"))
        self.assertIsNone(event.data.get("refund_reason"))

    def test_event_source_includes_tenant_and_user(self):
        """Test that events include tenant_id and user_id in source."""
        event_id = self.service.publish_payment_initiated(
            payment_id=self.payment_id,
            order_id=self.order_id
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        # The source_service is set to the service_name from EventPublisher
        self.assertEqual(event.source_service, "payment_service")

    def test_event_timestamp_is_set(self):
        """Test that events have timestamp set."""
        before_publish = timezone.now()
        event_id = self.service.publish_payment_initiated(
            payment_id=self.payment_id,
            order_id=self.order_id
        )
        after_publish = timezone.now()

        event = Event.objects.get(event_id=event_id)
        self.assertIsNotNone(event.timestamp)
        # Verify timestamp is between before and after
        self.assertGreaterEqual(event.timestamp, before_publish)
        self.assertLessEqual(event.timestamp, after_publish)

    def test_event_tags_are_set(self):
        """Test that events have appropriate tags set."""
        # Test payment.initiated tags
        event_id = self.service.publish_payment_initiated(
            payment_id=self.payment_id,
            order_id=self.order_id
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("payment", event.metadata.get("tags", []))
        self.assertIn("initiated", event.metadata.get("tags", []))

        # Test payment.completed tags
        event_id = self.service.publish_payment_completed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            status="SUCCEEDED"
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("payment", event.metadata.get("tags", []))
        self.assertIn("completed", event.metadata.get("tags", []))

        # Test payment.failed tags
        event_id = self.service.publish_payment_failed(
            payment_id=self.payment_id,
            order_id=self.order_id,
            error_message="Payment failed"
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("payment", event.metadata.get("tags", []))
        self.assertIn("failed", event.metadata.get("tags", []))

        # Test payment.refunded tags
        event_id = self.service.publish_payment_refunded(
            payment_id=self.payment_id,
            order_id=self.order_id
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("payment", event.metadata.get("tags", []))
        self.assertIn("refunded", event.metadata.get("tags", []))

    def test_publisher_initialization_without_tenant_or_user(self):
        """Test that publisher can be initialized without tenant_id or user_id."""
        class TestPaymentService(PaymentEventPublisher):
            def __init__(self):
                super().__init__()

        service = TestPaymentService()
        self.assertIsNotNone(service._event_publisher)
        self.assertIsNone(service._event_publisher.default_tenant_id)
        self.assertIsNone(service._event_publisher.default_user_id)

    def test_publisher_uses_service_tenant_and_user(self):
        """Test that event publisher uses service tenant_id and user_id by default."""
        # Create service with tenant and user
        service = self.service

        # Publish an event without explicitly passing tenant_id/user_id
        event_id = service.publish_payment_initiated(
            payment_id=self.payment_id,
            order_id=self.order_id
        )

        # Verify event has correct tenant_id and user_id
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

