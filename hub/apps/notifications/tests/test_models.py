"""
Unit tests for EmailDelivery model.
"""

from django.test import TestCase

from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User


class EmailDeliveryModelTest(TestCase):
    """Tests for EmailDelivery model"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="test@example.com", tenant=self.tenant, display_name="Test User"
        )

    def test_create_email_delivery(self):
        """Test creating email delivery record"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
            tenant=self.tenant,
            user=self.user,
        )

        self.assertEqual(delivery.email_type, EmailType.USER_INVITATION)
        self.assertEqual(delivery.to_email, "recipient@example.com")
        self.assertEqual(delivery.status, EmailDeliveryStatus.PENDING)
        self.assertEqual(delivery.tenant, self.tenant)
        self.assertEqual(delivery.user, self.user)

    def test_mark_sent(self):
        """Test marking email as sent"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
        )

        delivery.mark_sent(message_id="test-message-id")
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)
        self.assertEqual(delivery.message_id, "test-message-id")
        self.assertIsNotNone(delivery.sent_at)

    def test_mark_delivered(self):
        """Test marking email as delivered"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
            status=EmailDeliveryStatus.SENT,
        )

        delivery.mark_delivered()
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDeliveryStatus.DELIVERED)
        self.assertIsNotNone(delivery.delivered_at)

    def test_mark_failed(self):
        """Test marking email as failed"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
        )

        delivery.mark_failed("Connection timeout")
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDeliveryStatus.FAILED)
        self.assertEqual(delivery.error_message, "Connection timeout")
        self.assertIsNotNone(delivery.failed_at)

    def test_mark_bounced(self):
        """Test marking email as bounced"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
        )

        delivery.mark_bounced("Invalid email address")
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDeliveryStatus.BOUNCED)
        self.assertEqual(delivery.error_message, "Invalid email address")
        self.assertIsNotNone(delivery.failed_at)

    def test_can_retry(self):
        """Test can_retry method"""
        # Can retry if failed and retry count < max
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
            status=EmailDeliveryStatus.FAILED,
            retry_count=1,
            max_retries=3,
        )
        self.assertTrue(delivery.can_retry())

        # Cannot retry if max retries reached
        delivery.retry_count = 3
        delivery.save()
        self.assertFalse(delivery.can_retry())

        # Cannot retry if status is not failed/deferred
        delivery.status = EmailDeliveryStatus.SENT
        delivery.save()
        self.assertFalse(delivery.can_retry())

    def test_increment_retry(self):
        """Test incrementing retry count"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
            retry_count=0,
        )

        delivery.increment_retry()
        delivery.refresh_from_db()

        self.assertEqual(delivery.retry_count, 1)

    def test_str_representation(self):
        """Test string representation"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="recipient@example.com",
            subject="Test Email",
            status=EmailDeliveryStatus.SENT,
        )

        str_repr = str(delivery)
        self.assertIn("USER_INVITATION", str_repr)
        self.assertIn("recipient@example.com", str_repr)
        self.assertIn("SENT", str_repr)
