"""
Unit tests for EmailService implementations.
"""
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.conf import settings
from django.core import mail

from hub.apps.notifications.services import (
    EmailService,
    EmailServiceError,
    SendGridEmailService,
    SESEmailService,
    SMTPEmailService,
    get_email_service
)


class EmailServiceTest(TestCase):
    """Base test class for email service tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.to_email = 'test@example.com'
        self.subject = 'Test Email'
        self.html_content = '<h1>Test</h1><p>This is a test email.</p>'
        self.text_content = 'Test\n\nThis is a test email.'


class SendGridEmailServiceTest(EmailServiceTest):
    """Tests for SendGridEmailService"""
    
    @patch('hub.apps.notifications.services.sendgrid.SendGridAPIClient')
    def test_send_email_success(self, mock_client_class):
        """Test successful email sending via SendGrid"""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.headers = {'X-Message-Id': 'test-message-id'}
        mock_client.send.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Configure settings
        with self.settings(
            EMAIL_BACKEND='sendgrid',
            SENDGRID_API_KEY='test-api-key',
            SENDGRID_FROM_EMAIL='noreply@example.com',
            SENDGRID_FROM_NAME='Test Hub'
        ):
            service = SendGridEmailService()
            result = service.send_email(
                to_email=self.to_email,
                subject=self.subject,
                html_content=self.html_content,
                text_content=self.text_content
            )
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['message_id'], 'test-message-id')
        self.assertEqual(result['status_code'], 202)
        mock_client.send.assert_called_once()
        # Verify the Mail object was constructed with correct recipient and subject
        mail_obj = mock_client.send.call_args[0][0]
        # SendGrid Mail object stores personalizations as SDK objects;
        # serialize to dict via .get() to inspect the contents.
        mail_dict = mail_obj.get()
        personalizations = mail_dict.get('personalizations', [])
        self.assertGreater(len(personalizations), 0)
        to_emails = [e['email'] for e in personalizations[0].get('to', [])]
        self.assertIn(self.to_email, to_emails)
        self.assertEqual(mail_dict.get('subject'), self.subject)
    
    @patch('hub.apps.notifications.services.sendgrid.SendGridAPIClient')
    def test_send_email_with_attachments(self, mock_client_class):
        """Test email sending with attachments"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.headers = {}
        mock_client.send.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        attachments = [
            {
                'filename': 'test.pdf',
                'content': b'PDF content',
                'content_type': 'application/pdf'
            }
        ]
        
        with self.settings(
            EMAIL_BACKEND='sendgrid',
            SENDGRID_API_KEY='test-api-key',
            SENDGRID_FROM_EMAIL='noreply@example.com'
        ):
            service = SendGridEmailService()
            result = service.send_email(
                to_email=self.to_email,
                subject=self.subject,
                html_content=self.html_content,
                attachments=attachments
            )
        
        self.assertTrue(result['success'])
        # Verify attachment was added with correct properties
        mail_obj = mock_client.send.call_args[0][0]
        self.assertTrue(hasattr(mail_obj, 'attachments'), "Mail object has no attachments")
        self.assertEqual(len(mail_obj.attachments), 1)
        attachment = mail_obj.attachments[0]
        self.assertEqual(attachment.file_name.get(), 'test.pdf')
        self.assertEqual(attachment.file_type.get(), 'application/pdf')
    
    def test_sendgrid_missing_api_key(self):
        """Test error when SENDGRID_API_KEY is missing"""
        with self.settings(
            EMAIL_BACKEND='sendgrid',
            SENDGRID_API_KEY=None
        ):
            with self.assertRaises(EmailServiceError) as cm:
                SendGridEmailService()
            self.assertIn('SENDGRID_API_KEY', str(cm.exception))
    
    @patch('hub.apps.notifications.services.sendgrid.SendGridAPIClient')
    def test_sendgrid_send_failure(self, mock_client_class):
        """Test error handling when SendGrid send fails"""
        mock_client = Mock()
        mock_client.send.side_effect = Exception('SendGrid API error')
        mock_client_class.return_value = mock_client
        
        with self.settings(
            EMAIL_BACKEND='sendgrid',
            SENDGRID_API_KEY='test-api-key',
            SENDGRID_FROM_EMAIL='noreply@example.com'
        ):
            service = SendGridEmailService()
            with self.assertRaises(EmailServiceError) as cm:
                service.send_email(
                    to_email=self.to_email,
                    subject=self.subject,
                    html_content=self.html_content
                )
            self.assertIn('SendGrid email sending failed', str(cm.exception))


class SESEmailServiceTest(EmailServiceTest):
    """Tests for SESEmailService"""
    
    @patch('hub.apps.notifications.services.boto3.client')
    def test_send_email_success(self, mock_boto_client):
        """Test successful email sending via AWS SES"""
        mock_ses = Mock()
        mock_ses.send_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto_client.return_value = mock_ses
        
        with self.settings(
            EMAIL_BACKEND='ses',
            AWS_SES_REGION='us-east-1',
            AWS_SES_FROM_EMAIL='noreply@example.com',
            AWS_SES_FROM_NAME='Test Hub'
        ):
            service = SESEmailService()
            result = service.send_email(
                to_email=self.to_email,
                subject=self.subject,
                html_content=self.html_content,
                text_content=self.text_content
            )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message_id'], 'test-message-id')
        mock_ses.send_email.assert_called_once()
        # Verify SES was called with correct destination and subject
        ses_kwargs = mock_ses.send_email.call_args[1]
        self.assertEqual(
            ses_kwargs['Destination']['ToAddresses'], [self.to_email]
        )
        self.assertEqual(
            ses_kwargs['Message']['Subject']['Data'], self.subject
        )
    
    def test_ses_missing_region(self):
        """Test error when AWS_SES_REGION is missing"""
        with self.settings(
            EMAIL_BACKEND='ses',
            AWS_SES_REGION=None
        ):
            with self.assertRaises(EmailServiceError) as cm:
                SESEmailService()
            self.assertIn('AWS_SES_REGION', str(cm.exception))
    
    @patch('hub.apps.notifications.services.boto3.client')
    def test_ses_client_error(self, mock_boto_client):
        """Test error handling for AWS SES ClientError"""
        from botocore.exceptions import ClientError
        
        mock_ses = Mock()
        error_response = {
            'Error': {
                'Code': 'MessageRejected',
                'Message': 'Email address not verified'
            }
        }
        mock_ses.send_email.side_effect = ClientError(error_response, 'SendEmail')
        mock_boto_client.return_value = mock_ses
        
        with self.settings(
            EMAIL_BACKEND='ses',
            AWS_SES_REGION='us-east-1',
            AWS_SES_FROM_EMAIL='noreply@example.com'
        ):
            service = SESEmailService()
            with self.assertRaises(EmailServiceError) as cm:
                service.send_email(
                    to_email=self.to_email,
                    subject=self.subject,
                    html_content=self.html_content
                )
            self.assertIn('AWS SES email sending failed', str(cm.exception))
            self.assertIn('MessageRejected', str(cm.exception))


class SMTPEmailServiceTest(EmailServiceTest):
    """Tests for SMTPEmailService"""
    
    @patch('hub.apps.notifications.services.get_connection')
    def test_send_email_success(self, mock_get_connection):
        """Test successful email sending via SMTP"""
        mock_connection = Mock()
        mock_connection.send_messages.return_value = 1
        mock_get_connection.return_value = mock_connection
        
        with self.settings(
            EMAIL_BACKEND='smtp',
            SMTP_HOST='smtp.example.com',
            SMTP_PORT=587,
            SMTP_FROM_EMAIL='noreply@example.com',
            SMTP_FROM_NAME='Test Hub'
        ):
            service = SMTPEmailService()
            result = service.send_email(
                to_email=self.to_email,
                subject=self.subject,
                html_content=self.html_content,
                text_content=self.text_content
            )
        
        self.assertTrue(result['success'])
        mock_connection.send_messages.assert_called_once()
        # Verify the EmailMessage was constructed with correct recipient and subject
        messages = mock_connection.send_messages.call_args[0][0]
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        self.assertIn(self.to_email, msg.to)
        self.assertEqual(msg.subject, self.subject)
    
    @patch('hub.apps.notifications.services.get_connection')
    def test_smtp_send_failure(self, mock_get_connection):
        """Test error handling when SMTP send fails"""
        mock_connection = Mock()
        mock_connection.send_messages.side_effect = Exception('SMTP connection error')
        mock_get_connection.return_value = mock_connection
        
        with self.settings(
            EMAIL_BACKEND='smtp',
            SMTP_HOST='smtp.example.com',
            SMTP_PORT=587,
            SMTP_FROM_EMAIL='noreply@example.com'
        ):
            service = SMTPEmailService()
            with self.assertRaises(EmailServiceError) as cm:
                service.send_email(
                    to_email=self.to_email,
                    subject=self.subject,
                    html_content=self.html_content
                )
            self.assertIn('SMTP email sending failed', str(cm.exception))


class EmailServiceFactoryTest(TestCase):
    """Tests for email service factory"""
    
    def test_get_email_service_sendgrid(self):
        """Test factory returns SendGridEmailService"""
        with self.settings(EMAIL_BACKEND='sendgrid', SENDGRID_API_KEY='test-key', SENDGRID_FROM_EMAIL='test@example.com'):
            service = get_email_service()
            self.assertIsInstance(service, SendGridEmailService)
    
    def test_get_email_service_ses(self):
        """Test factory returns SESEmailService"""
        with self.settings(EMAIL_BACKEND='ses', AWS_SES_REGION='us-east-1', AWS_SES_FROM_EMAIL='test@example.com'):
            service = get_email_service()
            self.assertIsInstance(service, SESEmailService)
    
    def test_get_email_service_smtp(self):
        """Test factory returns SMTPEmailService"""
        with self.settings(EMAIL_BACKEND='smtp', SMTP_HOST='localhost', SMTP_FROM_EMAIL='test@example.com'):
            service = get_email_service()
            self.assertIsInstance(service, SMTPEmailService)
    
    def test_get_email_service_invalid_backend(self):
        """Test error for invalid EMAIL_BACKEND"""
        with self.settings(EMAIL_BACKEND='invalid'):
            with self.assertRaises(EmailServiceError) as cm:
                get_email_service()
            self.assertIn('Invalid EMAIL_BACKEND', str(cm.exception))
    
    def test_get_email_service_missing_backend(self):
        """Test error when EMAIL_BACKEND is not set"""
        with self.settings(EMAIL_BACKEND=None):
            with self.assertRaises(EmailServiceError) as cm:
                get_email_service()
            self.assertIn('EMAIL_BACKEND not configured', str(cm.exception))

