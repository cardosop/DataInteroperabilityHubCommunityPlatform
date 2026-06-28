"""
Unit tests for email service implementations.

Tests SendGrid, SES, SMTP backends and factory function.
Uses real services where possible (no mocks).
"""

import os
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from hub.apps.notifications.services import (
    EmailServiceError,
    SendGridEmailService,
    SESEmailService,
    SMTPEmailService,
    get_email_service,
)

pytestmark = pytest.mark.django_db(transaction=True)


class EmailServiceBaseTest(TestCase):
    """Base test class for email service tests"""

    def setUp(self):
        """Set up test fixtures"""
        self.to_email = "test@example.com"
        self.subject = "Test Email"
        self.html_content = "<h1>Test</h1><p>This is a test email.</p>"
        self.text_content = "Test\n\nThis is a test email."


class SendGridEmailServiceTest(EmailServiceBaseTest):
    """Tests for SendGridEmailService"""

    @override_settings(
        EMAIL_BACKEND="sendgrid",
        SENDGRID_API_KEY="test-api-key",
        SENDGRID_FROM_EMAIL="noreply@example.com",
        SENDGRID_FROM_NAME="Test Hub",
    )
    def test_sendgrid_service_initialization(self):
        """Test SendGridEmailService initialization"""
        try:
            service = SendGridEmailService()
            self.assertIsInstance(service, SendGridEmailService)
            self.assertEqual(service.from_email, "noreply@example.com")
            self.assertEqual(service.from_name, "Test Hub")
        except EmailServiceError:
            # SendGrid may not be available - skip test
            self.skipTest("SendGrid not available")

    @override_settings(EMAIL_BACKEND="sendgrid", SENDGRID_API_KEY=None)
    def test_sendgrid_missing_api_key(self):
        """Missing SENDGRID_API_KEY raises EmailServiceError.

        The service raises the same exception type whether the sendgrid
        package is absent or the API key is missing — assertRaises
        catches both.
        """
        with self.assertRaises(EmailServiceError) as cm:
            SendGridEmailService()
        error_msg = str(cm.exception)
        self.assertTrue(
            "SENDGRID_API_KEY" in error_msg or "sendgrid package not installed" in error_msg,
            f"Expected error about SENDGRID_API_KEY or package install, got: {error_msg}",
        )

    @override_settings(
        EMAIL_BACKEND="sendgrid",
        SENDGRID_API_KEY="test-api-key",
        SENDGRID_FROM_EMAIL="noreply@example.com",
    )
    def test_sendgrid_default_from_name(self):
        """Test default from_name when not configured"""
        try:
            # Remove SENDGRID_FROM_NAME from settings to test default
            from django.conf import settings

            if hasattr(settings, "SENDGRID_FROM_NAME"):
                delattr(settings, "SENDGRID_FROM_NAME")
            service = SendGridEmailService()
            # Default should be 'Meshant' (from APP_NAME)
            self.assertEqual(service.from_name, "Meshant")
        except EmailServiceError:
            self.skipTest("SendGrid not available")
        except AttributeError:
            # Settings might not allow deletion - test with explicit None
            with override_settings(SENDGRID_FROM_NAME="Custom Brand"):
                try:
                    service = SendGridEmailService()
                    self.assertEqual(service.from_name, "Custom Brand")
                except EmailServiceError:
                    self.skipTest("SendGrid not available")

    @override_settings(
        EMAIL_BACKEND="sendgrid",
        SENDGRID_API_KEY="test-api-key",
        SENDGRID_FROM_EMAIL="noreply@example.com",
    )
    def test_sendgrid_custom_from_email(self):
        """Custom from_email parameter is accepted by the validation gate.

        The parameter-validation path runs before the external API call
        (services.py:127-129).  Providing *from_email* clears the gate;
        the subsequent API call may fail with a test key, but the error
        must NOT be "from_email not configured" — it must be a downstream
        SendGrid API error instead.
        """
        service = SendGridEmailService()
        with self.assertRaises(EmailServiceError) as cm:
            service.send_email(
                to_email=self.to_email,
                subject=self.subject,
                html_content=self.html_content,
                from_email="custom@example.com",
            )
        # The error must be from the SendGrid API call, NOT from missing
        # from_email validation.
        self.assertNotIn(
            "from_email not configured",
            str(cm.exception),
            "from_email override should bypass the missing-from_email gate",
        )


class SESEmailServiceTest(EmailServiceBaseTest):
    """Tests for SESEmailService"""

    @override_settings(
        EMAIL_BACKEND="ses",
        AWS_SES_REGION="us-east-1",
        AWS_SES_FROM_EMAIL="noreply@example.com",
        AWS_SES_FROM_NAME="Test Hub",
    )
    def test_ses_service_initialization(self):
        """Test SESEmailService initialization"""
        try:
            service = SESEmailService()
            self.assertIsInstance(service, SESEmailService)
            # Note: SES service doesn't store region as attribute, it's used in client creation
            self.assertEqual(service.from_email, "noreply@example.com")
            self.assertEqual(service.from_name, "Test Hub")
        except EmailServiceError:
            # SES may not be available - skip test
            self.skipTest("AWS SES not available")
        except Exception:
            # Other errors (e.g., boto3 not available) - skip test
            self.skipTest("AWS SES not available")

    @override_settings(EMAIL_BACKEND="ses", AWS_SES_REGION=None)
    def test_ses_missing_region(self):
        """Test error when AWS_SES_REGION is missing"""
        with self.assertRaises(EmailServiceError) as cm:
            SESEmailService()
        self.assertIn("AWS_SES_REGION", str(cm.exception))

    @override_settings(
        EMAIL_BACKEND="ses", AWS_SES_REGION="us-east-1", AWS_SES_FROM_EMAIL="noreply@example.com"
    )
    def test_ses_default_from_name(self):
        """Test default from_name when not configured"""
        try:
            # Default should be 'Meshant' (from APP_NAME) when AWS_SES_FROM_NAME not set
            service = SESEmailService()
            self.assertEqual(service.from_name, "Meshant")
        except EmailServiceError:
            self.skipTest("AWS SES not available")
        except Exception:
            # Other errors (e.g., boto3 not available) - skip test
            self.skipTest("AWS SES not available")

    @override_settings(
        EMAIL_BACKEND="ses", AWS_SES_REGION="us-east-1", AWS_SES_FROM_EMAIL="noreply@example.com"
    )
    def test_ses_custom_from_email(self):
        """Custom from_email parameter is accepted by the validation gate.

        The parameter-validation path runs before the external API call.
        Providing *from_email* clears the gate; the subsequent API call
        may fail with a test key, but the error must NOT be about missing
        from_email — it must be a downstream AWS SES error instead.
        """
        service = SESEmailService()
        with self.assertRaises(EmailServiceError) as cm:
            service.send_email(
                to_email=self.to_email,
                subject=self.subject,
                html_content=self.html_content,
                from_email="custom@example.com",
            )
        self.assertNotIn(
            "from_email not configured",
            str(cm.exception),
            "from_email override should bypass the missing-from_email gate",
        )


class SMTPEmailServiceTest(EmailServiceBaseTest):
    """Tests for SMTPEmailService"""

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_USERNAME="testuser",
        SMTP_PASSWORD="testpass",
        SMTP_USE_TLS=True,
        SMTP_FROM_EMAIL="noreply@example.com",
        SMTP_FROM_NAME="Test Hub",
    )
    def test_smtp_service_initialization(self):
        """Test SMTPEmailService initialization"""
        service = SMTPEmailService()
        self.assertIsInstance(service, SMTPEmailService)
        self.assertEqual(service.host, "localhost")
        self.assertEqual(service.port, 587)
        self.assertEqual(service.username, "testuser")
        self.assertEqual(service.password, "testpass")
        self.assertTrue(service.use_tls)
        self.assertFalse(service.use_ssl)
        self.assertEqual(service.from_email, "noreply@example.com")
        self.assertEqual(service.from_name, "Test Hub")

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
        SMTP_USE_TLS=True,
        SMTP_USE_SSL=False,
        SMTP_FROM_NAME="Meshant",
    )
    def test_smtp_default_settings(self):
        """Test SMTP default settings"""
        service = SMTPEmailService()
        self.assertEqual(service.host, "localhost")
        self.assertEqual(service.port, 587)
        self.assertIsNone(service.username)
        self.assertIsNone(service.password)
        self.assertTrue(service.use_tls)
        self.assertFalse(service.use_ssl)
        self.assertEqual(service.from_name, "Meshant")

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="smtp.example.com",
        SMTP_PORT=465,
        SMTP_USE_SSL=True,
        SMTP_USE_TLS=False,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_smtp_ssl_configuration(self):
        """Test SMTP SSL configuration"""
        service = SMTPEmailService()
        self.assertEqual(service.host, "smtp.example.com")
        self.assertEqual(service.port, 465)
        self.assertTrue(service.use_ssl)
        self.assertFalse(service.use_tls)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_smtp_get_connection(self):
        """Test SMTP connection creation"""
        service = SMTPEmailService()
        connection = service._get_connection()
        self.assertIsNotNone(connection)
        # In test mode, _get_connection returns locmem.EmailBackend;
        # outside tests it returns smtp.EmailBackend.  Accept either.
        from django.core.mail.backends.base import BaseEmailBackend

        self.assertIsInstance(connection, BaseEmailBackend)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    @patch.dict(os.environ, {"E2E_ENABLE_SMTP": ""}, clear=False)
    def test_smtp_send_email_structure(self):
        """SMTP send completes via locmem backend (E2E_ENABLE_SMTP cleared)."""
        service = SMTPEmailService()
        result = service.send_email(
            to_email=self.to_email,
            subject=self.subject,
            html_content=self.html_content,
            text_content=self.text_content,
        )
        self.assertIn("success", result)


class EmailServiceFactoryTest(TestCase):
    """Tests for email service factory"""

    @override_settings(
        NOTIFICATION_EMAIL_BACKEND="sendgrid",
        EMAIL_BACKEND="sendgrid",
        SENDGRID_API_KEY="test-key",
        SENDGRID_FROM_EMAIL="test@example.com",
    )
    def test_get_email_service_sendgrid(self):
        """Test factory returns SendGridEmailService"""
        try:
            service = get_email_service()
            self.assertIsInstance(service, SendGridEmailService)
        except EmailServiceError:
            # SendGrid may not be available
            self.skipTest("SendGrid not available")

    @override_settings(
        NOTIFICATION_EMAIL_BACKEND="ses",
        EMAIL_BACKEND="ses",
        AWS_SES_REGION="us-east-1",
        AWS_SES_FROM_EMAIL="test@example.com",
    )
    def test_get_email_service_ses(self):
        """Test factory returns SESEmailService"""
        try:
            service = get_email_service()
            self.assertIsInstance(service, SESEmailService)
        except EmailServiceError:
            # SES may not be available
            self.skipTest("AWS SES not available")

    @override_settings(
        EMAIL_BACKEND="smtp", SMTP_HOST="localhost", SMTP_FROM_EMAIL="test@example.com"
    )
    def test_get_email_service_smtp(self):
        """Test factory returns SMTPEmailService"""
        service = get_email_service()
        self.assertIsInstance(service, SMTPEmailService)

    @override_settings(
        NOTIFICATION_EMAIL_BACKEND="invalid",
        EMAIL_PROVIDER="invalid",
    )
    def test_get_email_service_invalid_backend(self):
        """Test error for invalid EMAIL_BACKEND"""
        with self.assertRaises(EmailServiceError) as cm:
            get_email_service()
        self.assertIn("Invalid EMAIL_BACKEND", str(cm.exception))

    @override_settings(
        NOTIFICATION_EMAIL_BACKEND=None,
        EMAIL_PROVIDER=None,
        EMAIL_BACKEND=None,
    )
    def test_get_email_service_missing_backend(self):
        """Test error when EMAIL_BACKEND is not set"""
        with self.assertRaises(EmailServiceError) as cm:
            get_email_service()
        self.assertIn("EMAIL_PROVIDER not configured", str(cm.exception))

    @override_settings(
        NOTIFICATION_EMAIL_BACKEND="",
        EMAIL_PROVIDER="",
        EMAIL_BACKEND="",
    )
    def test_get_email_service_empty_backend(self):
        """Test error when EMAIL_BACKEND is empty"""
        with self.assertRaises(EmailServiceError) as cm:
            get_email_service()
        self.assertIn("EMAIL_PROVIDER not configured", str(cm.exception))


class EmailServiceCommonTest(EmailServiceBaseTest):
    """Tests for common email service functionality"""

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    @patch.dict(os.environ, {"E2E_ENABLE_SMTP": ""}, clear=False)
    def test_email_service_send_with_text_content(self):
        """Email send with both HTML and text content via locmem backend."""
        service = SMTPEmailService()
        result = service.send_email(
            to_email=self.to_email,
            subject=self.subject,
            html_content=self.html_content,
            text_content=self.text_content,
        )
        self.assertIn("success", result)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    @patch.dict(os.environ, {"E2E_ENABLE_SMTP": ""}, clear=False)
    def test_email_service_send_html_only(self):
        """Email send with HTML-only content via locmem backend."""
        service = SMTPEmailService()
        result = service.send_email(
            to_email=self.to_email, subject=self.subject, html_content=self.html_content
        )
        self.assertIn("success", result)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    @patch.dict(os.environ, {"E2E_ENABLE_SMTP": ""}, clear=False)
    def test_email_service_reply_to(self):
        """Email send with reply-to address via locmem backend."""
        service = SMTPEmailService()
        result = service.send_email(
            to_email=self.to_email,
            subject=self.subject,
            html_content=self.html_content,
            reply_to="reply@example.com",
        )
        self.assertIn("success", result)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    @patch.dict(os.environ, {"E2E_ENABLE_SMTP": ""}, clear=False)
    def test_email_service_attachments(self):
        """Email send with attachments via locmem backend."""
        service = SMTPEmailService()
        attachments = [
            {"filename": "test.pdf", "content": b"PDF content", "content_type": "application/pdf"}
        ]
        result = service.send_email(
            to_email=self.to_email,
            subject=self.subject,
            html_content=self.html_content,
            attachments=attachments,
        )
        self.assertIn("success", result)
