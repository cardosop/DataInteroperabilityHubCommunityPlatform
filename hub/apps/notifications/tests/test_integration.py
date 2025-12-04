"""
Integration tests for email sending.
"""
from unittest.mock import patch, Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from hub.apps.notifications.tasks import (
    send_invitation_email,
    send_password_reset_email,
    send_email_async
)
from hub.apps.notifications.models import EmailDelivery, EmailType, EmailDeliveryStatus
from hub.apps.notifications.services import EmailServiceError
from hub.apps.tenants.models import Tenant

User = get_user_model()


class EmailSendingIntegrationTest(TestCase):
    """Integration tests for email sending"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            tenant=self.tenant,
            display_name='Test User'
        )
    
    @patch('hub.apps.notifications.tasks.get_email_service')
    def test_send_invitation_email_integration(self, mock_get_service):
        """Test sending invitation email end-to-end"""
        # Setup mock email service
        mock_service = Mock()
        mock_service.send_email.return_value = {
            'success': True,
            'message_id': 'test-message-id'
        }
        mock_get_service.return_value = mock_service
        
        # Generate invitation token
        import uuid
        self.user.invitation_token = uuid.uuid4()
        self.user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        self.user.save()
        
        # Send email
        result = send_invitation_email(str(self.user.id))
        
        # Verify email was sent
        self.assertTrue(result['success'])
        mock_service.send_email.assert_called_once()
        
        # Verify email delivery record
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.USER_INVITATION,
            to_email=self.user.email
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)
        self.assertEqual(delivery.message_id, 'test-message-id')
    
    @patch('hub.apps.notifications.tasks.get_email_service')
    def test_send_password_reset_email_integration(self, mock_get_service):
        """Test sending password reset email end-to-end"""
        # Setup mock email service
        mock_service = Mock()
        mock_service.send_email.return_value = {
            'success': True,
            'message_id': 'test-message-id'
        }
        mock_get_service.return_value = mock_service
        
        # Generate password reset token
        import uuid
        from django.utils import timezone
        from datetime import timedelta
        self.user.password_reset_token = uuid.uuid4()
        self.user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
        self.user.save()
        
        # Send email
        result = send_password_reset_email(str(self.user.id))
        
        # Verify email was sent
        self.assertTrue(result['success'])
        mock_service.send_email.assert_called_once()
        
        # Verify email delivery record
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.PASSWORD_RESET,
            to_email=self.user.email
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)
    
    @patch('hub.apps.notifications.tasks.get_email_service')
    def test_send_email_async_retry_logic(self, mock_get_service):
        """Test email retry logic on transient failure"""
        from django_rq import get_queue
        from unittest.mock import call
        
        # Setup mock to fail first time, succeed second time
        mock_service = Mock()
        mock_service.send_email.side_effect = [
            EmailServiceError('Connection timeout'),
            {'success': True, 'message_id': 'retry-success'}
        ]
        mock_get_service.return_value = mock_service
        
        # Send email (will fail first time)
        with patch('hub.apps.notifications.tasks.get_queue') as mock_get_queue:
            mock_queue = Mock()
            mock_queue.enqueue_in = Mock()
            mock_get_queue.return_value = mock_queue
            
            result = send_email_async(
                email_type=EmailType.USER_INVITATION,
                to_email='test@example.com',
                subject='Test Email',
                template_name='notifications/emails/user_invitation.html',
                context={'user': self.user, 'tenant': self.tenant},
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                retry_count=0,
                max_retries=3
            )
        
        # Verify retry was scheduled
        self.assertFalse(result['success'])
        self.assertTrue(result.get('retry_scheduled', False))
        mock_queue.enqueue_in.assert_called_once()
        
        # Verify delivery record is deferred
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.USER_INVITATION,
            to_email='test@example.com'
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.DEFERRED)
        self.assertEqual(delivery.retry_count, 0)
    
    @patch('hub.apps.notifications.tasks.get_email_service')
    def test_send_email_async_max_retries(self, mock_get_service):
        """Test email fails after max retries"""
        from hub.apps.notifications.services import EmailServiceError
        
        # Setup mock to always fail
        mock_service = Mock()
        mock_service.send_email.side_effect = EmailServiceError('Persistent error')
        mock_get_service.return_value = mock_service
        
        # Send email with max retries reached
        result = send_email_async(
            email_type=EmailType.USER_INVITATION,
            to_email='test@example.com',
            subject='Test Email',
            template_name='notifications/emails/user_invitation.html',
            context={'user': self.user, 'tenant': self.tenant},
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            retry_count=3,  # Already at max retries
            max_retries=3
        )
        
        # Verify email failed
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        
        # Verify delivery record is failed
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.USER_INVITATION,
            to_email='test@example.com'
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.FAILED)
        self.assertEqual(delivery.retry_count, 3)

