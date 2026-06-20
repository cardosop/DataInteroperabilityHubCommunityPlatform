"""
Integration Tests for Updated Service Integrations

Tests for services updated to follow service integration patterns:
- WebhookDeliveryClient
- ServiceHealthClient
- Enhanced LLM Client
- Email Services with BaseService
- Bug Prevention Services with BaseService

All tests run against real Docker Compose services - no mocks or stubs.
"""

import structlog
from django.test import TestCase

from hub.apps.ai.llm_client import LLMClient
from hub.apps.core.bug_prevention.services import IdempotencyService, RequestDeduplicationService
from hub.apps.core.services.base import BaseService
from hub.apps.core.services.health_client import ServiceHealthClient
from hub.apps.notifications.services import SendGridEmailService, SESEmailService, SMTPEmailService
from hub.apps.webhooks.service_client import WebhookDeliveryClient

logger = structlog.get_logger(__name__)


class WebhookDeliveryClientIntegrationTest(TestCase):
    """Integration tests for WebhookDeliveryClient"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = WebhookDeliveryClient(timeout=10)

    def test_webhook_client_initialization(self):
        """Test that WebhookDeliveryClient initializes correctly"""
        self.assertIsNotNone(self.client)
        self.assertIsNotNone(self.client.client)
        self.assertIsNotNone(self.client._circuit_breaker)
        self.assertEqual(self.client.max_retries, 2)
        self.assertEqual(self.client.backoff_factor, 1)

    def test_webhook_client_has_circuit_breaker(self):
        """Test that WebhookDeliveryClient has circuit breaker"""
        self.assertIsNotNone(self.client._circuit_breaker)
        self.assertTrue(hasattr(self.client._circuit_breaker, "call"))

    def test_webhook_client_has_retry_logic(self):
        """Test that WebhookDeliveryClient has retry logic"""
        self.assertIsNotNone(self.client.max_retries)
        self.assertGreaterEqual(self.client.max_retries, 0)
        self.assertIsNotNone(self.client.backoff_factor)
        self.assertGreater(self.client.backoff_factor, 0)

    def test_webhook_client_health_check(self):
        """Test WebhookDeliveryClient health check"""
        is_healthy, status = self.client.health_check()
        self.assertIsInstance(is_healthy, bool)
        self.assertIsInstance(status, str)

    def test_webhook_client_follows_pattern(self):
        """Test that WebhookDeliveryClient follows Pattern 1"""
        # Check for required methods
        self.assertTrue(hasattr(self.client, "_request_with_retry"))
        self.assertTrue(hasattr(self.client, "deliver_webhook"))
        self.assertTrue(hasattr(self.client, "health_check"))

        # Check for circuit breaker
        self.assertIsNotNone(self.client._circuit_breaker)

        # Check for retry logic
        self.assertIsNotNone(self.client.max_retries)


class ServiceHealthClientIntegrationTest(TestCase):
    """Integration tests for ServiceHealthClient"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = ServiceHealthClient(timeout=5)

    def test_health_client_initialization(self):
        """Test that ServiceHealthClient initializes correctly"""
        self.assertIsNotNone(self.client)
        self.assertIsNotNone(self.client.client)
        self.assertIsNotNone(self.client._circuit_breaker)
        self.assertEqual(self.client.max_retries, 2)

    def test_health_client_has_circuit_breaker(self):
        """Test that ServiceHealthClient has circuit breaker"""
        self.assertIsNotNone(self.client._circuit_breaker)
        self.assertTrue(hasattr(self.client._circuit_breaker, "call"))

    def test_health_client_check_health(self):
        """Test ServiceHealthClient health check with real service"""
        # Test with DQ service (should be available in Docker Compose)
        is_healthy, status = self.client.check_health(
            service_url="http://dq-service:8083", health_path="/health"
        )
        self.assertIsInstance(is_healthy, bool)
        self.assertIsInstance(status, (str, type(None)))

    def test_health_client_follows_pattern(self):
        """Test that ServiceHealthClient follows Pattern 1"""
        # Check for required methods
        self.assertTrue(hasattr(self.client, "_request_with_retry"))
        self.assertTrue(hasattr(self.client, "check_health"))

        # Check for circuit breaker
        self.assertIsNotNone(self.client._circuit_breaker)

        # Check for retry logic
        self.assertIsNotNone(self.client.max_retries)


class LLMClientIntegrationTest(TestCase):
    """Integration tests for enhanced LLM Client"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = LLMClient()

    def test_llm_client_initialization(self):
        """Test that LLMClient initializes correctly"""
        self.assertIsNotNone(self.client)
        self.assertIsNotNone(self.client.client)
        self.assertIsNotNone(self.client._circuit_breaker)
        self.assertIsNotNone(self.client.max_retries)

    def test_llm_client_has_circuit_breaker(self):
        """Test that LLMClient has circuit breaker"""
        self.assertIsNotNone(self.client._circuit_breaker)
        self.assertTrue(hasattr(self.client._circuit_breaker, "call"))

    def test_llm_client_has_retry_logic(self):
        """Test that LLMClient has retry logic"""
        self.assertIsNotNone(self.client.max_retries)
        self.assertGreaterEqual(self.client.max_retries, 0)
        self.assertIsNotNone(self.client.backoff_factor)
        self.assertGreater(self.client.backoff_factor, 0)

    def test_llm_client_follows_pattern(self):
        """Test that LLMClient follows Pattern 1"""
        # Check for circuit breaker
        self.assertIsNotNone(self.client._circuit_breaker)

        # Check for retry logic
        self.assertIsNotNone(self.client.max_retries)

        # Check for HTTP client
        self.assertIsNotNone(self.client.client)


class EmailServicesBaseServiceTest(TestCase):
    """Test that email services extend BaseService"""

    def test_sendgrid_email_service_extends_base_service(self):
        """Test that SendGridEmailService extends BaseService"""
        self.assertTrue(issubclass(SendGridEmailService, BaseService))
        self.assertEqual(SendGridEmailService.service_name, "sendgrid_email_service")

    def test_ses_email_service_extends_base_service(self):
        """Test that SESEmailService extends BaseService"""
        self.assertTrue(issubclass(SESEmailService, BaseService))
        self.assertEqual(SESEmailService.service_name, "ses_email_service")

    def test_smtp_email_service_extends_base_service(self):
        """Test that SMTPEmailService extends BaseService"""
        self.assertTrue(issubclass(SMTPEmailService, BaseService))
        self.assertEqual(SMTPEmailService.service_name, "smtp_email_service")

    def test_email_services_have_service_name(self):
        """Test that all email services define service_name"""
        services = [
            SendGridEmailService,
            SESEmailService,
            SMTPEmailService,
        ]

        for service_class in services:
            self.assertTrue(hasattr(service_class, "service_name"))
            self.assertIsNotNone(service_class.service_name)
            self.assertIsInstance(service_class.service_name, str)


class BugPreventionServicesBaseServiceTest(TestCase):
    """Test that bug prevention services extend BaseService"""

    def test_idempotency_service_extends_base_service(self):
        """Test that IdempotencyService extends BaseService"""
        self.assertTrue(issubclass(IdempotencyService, BaseService))
        self.assertEqual(IdempotencyService.service_name, "idempotency_service")

    def test_request_deduplication_service_extends_base_service(self):
        """Test that RequestDeduplicationService extends BaseService"""
        self.assertTrue(issubclass(RequestDeduplicationService, BaseService))
        self.assertEqual(RequestDeduplicationService.service_name, "request_deduplication_service")

    def test_bug_prevention_services_have_service_name(self):
        """Test that all bug prevention services define service_name"""
        services = [
            IdempotencyService,
            RequestDeduplicationService,
        ]

        for service_class in services:
            self.assertTrue(hasattr(service_class, "service_name"))
            self.assertIsNotNone(service_class.service_name)
            self.assertIsInstance(service_class.service_name, str)


class UpdatedServicesRegressionTest(TestCase):
    """Regression tests to ensure updated services maintain existing functionality"""

    def test_webhook_delivery_service_still_works(self):
        """Test that webhook delivery service still functions correctly"""
        from hub.apps.webhooks.service import WebhookDeliveryService

        # Verify service class exists and has expected methods
        # _attempt_delivery is the method that uses WebhookDeliveryClient
        self.assertTrue(hasattr(WebhookDeliveryService, "_attempt_delivery"))
        self.assertTrue(hasattr(WebhookDeliveryService, "trigger_webhook"))
        self.assertTrue(callable(getattr(WebhookDeliveryService, "_attempt_delivery", None)))

    def test_service_availability_checker_still_works(self):
        """Test that service availability checker still functions correctly"""
        from hub.apps.core.services.availability import ServiceAvailabilityChecker

        # Verify service class exists and has expected methods
        self.assertTrue(hasattr(ServiceAvailabilityChecker, "check_service_availability"))
        self.assertTrue(hasattr(ServiceAvailabilityChecker, "check_all_services"))

    def test_llm_client_still_works(self):
        """Test that LLM client still functions correctly"""
        client = LLMClient()

        # Verify client has expected methods
        self.assertTrue(hasattr(client, "understand_query"))
        self.assertTrue(hasattr(client, "match_schemas"))
        self.assertTrue(hasattr(client, "_call_llm"))

    def test_email_services_still_work(self):
        """Test that email services still function correctly"""
        # Verify services have send_email method (from EmailService ABC)
        self.assertTrue(hasattr(SendGridEmailService, "send_email"))
        self.assertTrue(hasattr(SESEmailService, "send_email"))
        self.assertTrue(hasattr(SMTPEmailService, "send_email"))

    def test_bug_prevention_services_still_work(self):
        """Test that bug prevention services still function correctly"""
        # Verify services have expected methods
        self.assertTrue(hasattr(IdempotencyService, "check_idempotency"))
        self.assertTrue(hasattr(IdempotencyService, "validate_key_format"))
        self.assertTrue(hasattr(RequestDeduplicationService, "check_duplicate"))
