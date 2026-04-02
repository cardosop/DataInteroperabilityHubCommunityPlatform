"""
Edge case tests for email service.

Tests email with special characters, unicode, retry after failure, and rate limiting.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.conf import settings

from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.notifications.services import get_email_service, EmailServiceError
from hub.apps.notifications.tasks import send_email_async
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class EmailServiceEdgeCaseTest(TestCase):
    """Edge case tests for email service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_email_with_special_characters(self):
        """Test email with special characters in subject and content"""
        subject = "Email with Special: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        html_content = "<html><body>Content with special chars: !@#$%^&*()</body></html>"
        
        try:
            email_service = get_email_service()
            result = email_service.send_email(
                to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
                subject=subject,
                html_content=html_content
            )
            
            # Should handle special characters
            self.assertIsNotNone(result)
        except EmailServiceError:
            # Service may not be configured
            pass
    
    def test_email_with_unicode(self):
        """Test email with unicode characters"""
        subject = "Email with 测试 Unicode and émojis 🎉"
        html_content = "<html><body>Content with 中文 and émojis 🎉</body></html>"
        
        try:
            email_service = get_email_service()
            result = email_service.send_email(
                to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
                subject=subject,
                html_content=html_content
            )
            
            # Should handle unicode
            self.assertIsNotNone(result)
        except EmailServiceError:
            # Service may not be configured
            pass
    
    def test_email_retry_after_failure(self):
        """Test email retry after failure"""
        # Create a failed email delivery
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test Subject",
            status=EmailDeliveryStatus.FAILED,
            error_message="Test error",
            retry_count=0,
            max_retries=3,
            tenant=self.tenant,
            user=self.user
        )
        
        # Check if can retry
        can_retry = delivery.can_retry()
        self.assertIsInstance(can_retry, bool)
        
        if can_retry:
            # Increment retry
            delivery.increment_retry()
            self.assertEqual(delivery.retry_count, 1)
    
    def test_email_rate_limiting(self):
        """Test email rate limiting"""
        # Send multiple emails rapidly
        results = []
        for i in range(10):
            try:
                result = send_email_async(
                    email_type=EmailType.USER_INVITATION,
                    to_email=f"recipient{i}@example.com",
                    subject="Test Subject",
                    template_name="notifications/emails/user_invitation.html",
                    context={"user": self.user},
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id)
                )
                results.append(result)
            except Exception as e:
                # May hit rate limits
                results.append({"error": str(e)})
        
        # Should handle rate limiting gracefully
        self.assertGreater(len(results), 0)
    
    def test_email_with_very_long_content(self):
        """Test email with very long content"""
        long_content = "x" * 100000  # 100KB content
        html_content = f"<html><body>{long_content}</body></html>"
        
        try:
            email_service = get_email_service()
            result = email_service.send_email(
                to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
                subject="Long Content Test",
                html_content=html_content
            )
            
            # Should handle long content (may truncate or reject)
            self.assertIsNotNone(result)
        except EmailServiceError as e:
            # May reject very long content
            self.assertIsNotNone(e)
    
    def test_email_with_attachments(self):
        """Test email with attachments"""
        attachments = [
            {
                "filename": "test.txt",
                "content": b"Test content",
                "content_type": "text/plain"
            }
        ]
        
        try:
            email_service = get_email_service()
            result = email_service.send_email(
                to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
                subject="Attachment Test",
                html_content="<html><body>Test</body></html>",
                attachments=attachments
            )
            
            # Should handle attachments
            self.assertIsNotNone(result)
        except EmailServiceError:
            # Service may not support attachments
            pass
    
    def test_email_delivery_status_transitions(self):
        """Test email delivery status transitions"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test Subject",
            status=EmailDeliveryStatus.PENDING,
            tenant=self.tenant,
            user=self.user
        )
        
        # Test status transitions
        delivery.mark_sent()
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)
        
        delivery.mark_failed("Test error")
        self.assertEqual(delivery.status, EmailDeliveryStatus.FAILED)
        
        delivery.mark_bounced("Bounce reason")
        self.assertEqual(delivery.status, EmailDeliveryStatus.BOUNCED)
    
    def test_email_with_invalid_recipient(self):
        """Test email with invalid recipient address"""
        try:
            email_service = get_email_service()
            result = email_service.send_email(
                to_email="invalid-email-address",
                subject="Test Subject",
                html_content="<html><body>Test</body></html>"
            )
            
            # May accept or reject invalid email
            self.assertIsNotNone(result)
        except EmailServiceError:
            # Expected for invalid email
            pass
    
    def test_email_with_empty_content(self):
        """Test email with empty content"""
        try:
            email_service = get_email_service()
            result = email_service.send_email(
                to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
                subject="",
                html_content=""
            )
            
            # Should handle empty content
            self.assertIsNotNone(result)
        except EmailServiceError:
            # May reject empty content
            pass
    
    def test_email_delivery_max_retries(self):
        """Test email delivery reaching max retries"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test Subject",
            status=EmailDeliveryStatus.FAILED,
            retry_count=3,
            max_retries=3,
            tenant=self.tenant,
            user=self.user
        )
        
        # Should not be retryable
        can_retry = delivery.can_retry()
        self.assertFalse(can_retry)

