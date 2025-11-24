"""
Tests for structured logging and PII redaction
"""
from django.test import TestCase
from hub.apps.observability.logging import redact_pii, redact_pii_processor
import structlog


class LoggingTest(TestCase):
    """Test logging functionality"""
    
    def test_redact_pii_email(self):
        """Test PII redaction for email addresses"""
        message = "User test@example.com logged in"
        redacted = redact_pii(message)
        self.assertIn('[EMAIL_REDACTED]', redacted)
        self.assertNotIn('test@example.com', redacted)
    
    def test_redact_pii_credit_card(self):
        """Test PII redaction for credit card numbers"""
        message = "Payment with card 1234-5678-9012-3456"
        redacted = redact_pii(message)
        self.assertIn('[CARD_REDACTED]', redacted)
        self.assertNotIn('1234-5678-9012-3456', redacted)
    
    def test_redact_pii_processor(self):
        """Test PII redaction processor"""
        event_dict = {
            'event': 'User test@example.com logged in',
            'email': 'test@example.com',
            'user_id': '123',
        }
        
        result = redact_pii_processor(None, None, event_dict)
        
        self.assertIn('[EMAIL_REDACTED]', result['event'])
        self.assertEqual(result['email'], '[REDACTED]')
        self.assertEqual(result['user_id'], '123')  # Not PII
    
    def test_structlog_configuration(self):
        """Test structlog is configured correctly"""
        logger = structlog.get_logger(__name__)
        
        # Should not raise exception
        logger.info("test message", key="value")
        
        # Verify logger is bound logger
        self.assertTrue(hasattr(logger, 'info'))

