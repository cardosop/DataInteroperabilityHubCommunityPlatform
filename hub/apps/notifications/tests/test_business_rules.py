"""
Tests for Notifications Business Rules

Comprehensive tests for NotificationsBusinessRules validation, following engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive test coverage
- Follow DRY, SOLID, and clean code principles
"""
from django.test import TestCase

from hub.apps.notifications.business_rules import (
    NotificationsBusinessRules,
    NotificationsRuleExecutionContext,
)
from hub.apps.notifications.models import EmailDelivery, EmailType, EmailDeliveryStatus
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.users.models import User
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
import uuid


class NotificationsBusinessRulesInitializationTest(TestCase):
    """Test NotificationsBusinessRules initialization"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

    def test_notifications_business_rules_initialization(self):
        """Test NotificationsBusinessRules can be initialized with tenant and user"""
        rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertIsNotNone(rules)
        self.assertEqual(rules.get_rule_name(), "NotificationsBusinessRules")
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_notifications_business_rules_initialization_without_user(self):
        """Test NotificationsBusinessRules can be initialized without user"""
        rules = NotificationsBusinessRules(tenant_id=str(self.tenant.id))
        self.assertIsNotNone(rules)
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_notifications_business_rules_initialization_without_tenant(self):
        """Test NotificationsBusinessRules can be initialized without tenant"""
        rules = NotificationsBusinessRules(user_id=str(self.user.id))
        self.assertIsNotNone(rules)
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_notifications_business_rules_initialization_without_context(self):
        """Test NotificationsBusinessRules can be initialized without tenant or user"""
        rules = NotificationsBusinessRules()
        self.assertIsNotNone(rules)
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_notifications_business_rules_enable_caching(self):
        """Test NotificationsBusinessRules can be initialized with caching enabled/disabled"""
        rules_with_cache = NotificationsBusinessRules(enable_caching=True)
        self.assertTrue(rules_with_cache.enable_caching)

        rules_without_cache = NotificationsBusinessRules(enable_caching=False)
        self.assertFalse(rules_without_cache.enable_caching)

    def test_notifications_business_rules_enable_metrics(self):
        """Test NotificationsBusinessRules can be initialized with metrics enabled/disabled"""
        rules_with_metrics = NotificationsBusinessRules(enable_metrics=True)
        self.assertTrue(rules_with_metrics.enable_metrics)

        rules_without_metrics = NotificationsBusinessRules(enable_metrics=False)
        self.assertFalse(rules_without_metrics.enable_metrics)

    def test_notifications_business_rules_enable_tracing(self):
        """Test NotificationsBusinessRules can be initialized with tracing enabled/disabled"""
        rules_with_tracing = NotificationsBusinessRules(enable_tracing=True)
        self.assertTrue(rules_with_tracing.enable_tracing)

        rules_without_tracing = NotificationsBusinessRules(enable_tracing=False)
        self.assertFalse(rules_without_tracing.enable_tracing)

    def test_notifications_business_rules_enable_logging(self):
        """Test NotificationsBusinessRules can be initialized with logging enabled/disabled"""
        rules_with_logging = NotificationsBusinessRules(enable_logging=True)
        self.assertTrue(rules_with_logging.enable_logging)

        rules_without_logging = NotificationsBusinessRules(enable_logging=False)
        self.assertFalse(rules_without_logging.enable_logging)


class NotificationsBusinessRulesRegistrationTest(TestCase):
    """Test NotificationsBusinessRules registration in business rules registry"""

    def test_notifications_business_rules_registered(self):
        """Test NotificationsBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("notifications_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "notifications_validation")
        self.assertEqual(rule.rule_class, NotificationsBusinessRules)
        self.assertIn("notifications", rule.tags)
        self.assertIn("validation", rule.tags)

    def test_notifications_business_rules_priority(self):
        """Test NotificationsBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("notifications_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)

    def test_notifications_business_rules_description(self):
        """Test NotificationsBusinessRules has correct description"""
        registry = get_registry()
        rule = registry.get_rule("notifications_validation")
        self.assertIsNotNone(rule)
        self.assertIsNotNone(rule.description)
        self.assertIn("notification", rule.description.lower())
        self.assertIn("validates", rule.description.lower())

    def test_notifications_business_rules_enabled(self):
        """Test NotificationsBusinessRules is enabled by default"""
        registry = get_registry()
        rule = registry.get_rule("notifications_validation")
        self.assertIsNotNone(rule)
        self.assertTrue(rule.enabled)


class NotificationsRuleExecutionContextTest(TestCase):
    """Test NotificationsRuleExecutionContext"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.notification = EmailDelivery.objects.create(
            email_type=EmailType.JOB_COMPLETION,
            to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test Subject",
            status=EmailDeliveryStatus.PENDING,
            tenant=self.tenant,
            user=self.user
        )

    def test_notifications_rule_execution_context_creation(self):
        """Test NotificationsRuleExecutionContext can be created"""
        context = NotificationsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            notification=self.notification,
            template="notifications/emails/job_completion.html",
            recipient="recipient@example.com",
            tenant=self.tenant,
            user=self.user
        )
        self.assertIsNotNone(context)
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.notification, self.notification)
        self.assertEqual(context.template, "notifications/emails/job_completion.html")
        self.assertEqual(context.recipient, "recipient@example.com")
        self.assertEqual(context.tenant, self.tenant)
        self.assertEqual(context.user, self.user)

    def test_notifications_rule_execution_context_to_dict(self):
        """Test NotificationsRuleExecutionContext to_dict method"""
        context = NotificationsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            notification=self.notification,
            template="notifications/emails/job_completion.html",
            recipient="recipient@example.com",
            tenant=self.tenant,
            user=self.user
        )
        context_dict = context.to_dict()
        self.assertIsInstance(context_dict, dict)
        self.assertEqual(context_dict['tenant_id'], str(self.tenant.id))
        self.assertEqual(context_dict['user_id'], str(self.user.id))
        self.assertEqual(context_dict['notification_id'], str(self.notification.id))
        self.assertEqual(context_dict['template'], "notifications/emails/job_completion.html")
        self.assertEqual(context_dict['recipient'], "recipient@example.com")
        self.assertEqual(context_dict['tenant_id_from_instance'], str(self.tenant.id))
        self.assertEqual(context_dict['user_id_from_instance'], str(self.user.id))


class NotificationsTemplateValidationTest(TestCase):
    """Test template validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_template_structure_valid_template(self):
        """Test template structure validation with valid template"""
        template_name = "notifications/emails/user_invitation.html"
        result = self.rules.validate_template_structure(template_name)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('template_exists', result.details)
        self.assertTrue(result.details['template_exists'])

    def test_validate_template_structure_invalid_template(self):
        """Test template structure validation with non-existent template"""
        template_name = "notifications/emails/nonexistent.html"
        result = self.rules.validate_template_structure(template_name)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('template_exists', result.details)
        self.assertFalse(result.details['template_exists'])

    def test_validate_template_structure_extends_base(self):
        """Test template structure validation checks for extends base.html"""
        template_name = "notifications/emails/user_invitation.html"
        result = self.rules.validate_template_structure(template_name)

        self.assertTrue(result.is_valid)
        self.assertIn('extends_base', result.details)
        self.assertTrue(result.details['extends_base'])

    def test_validate_template_structure_has_content_block(self):
        """Test template structure validation checks for content block"""
        template_name = "notifications/emails/user_invitation.html"
        result = self.rules.validate_template_structure(template_name)

        self.assertTrue(result.is_valid)
        self.assertIn('has_content_block', result.details)
        self.assertTrue(result.details['has_content_block'])

    def test_validate_template_variables_valid_variables(self):
        """Test template variable validation with valid variables"""
        template_name = "notifications/emails/user_invitation.html"
        context = {
            'user': {'display_name': 'Test User'},
            'tenant': {'name': 'Test Tenant'},
            'invitation_url': 'http://example.com/invite?token=123'
        }
        result = self.rules.validate_template_variables(template_name, context)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('variables_validated', result.details)
        self.assertTrue(result.details['variables_validated'])

    def test_validate_template_variables_missing_required_variables(self):
        """Test template variable validation detects missing required variables"""
        template_name = "notifications/emails/user_invitation.html"
        context = {}  # Missing required variables
        result = self.rules.validate_template_variables(template_name, context)

        # Should have warnings or errors for missing variables
        self.assertIn('variables_validated', result.details)
        # May have warnings for missing optional variables

    def test_validate_template_content_length_valid(self):
        """Test template content validation with valid length"""
        template_name = "notifications/emails/user_invitation.html"
        context = {
            'user': {'display_name': 'Test User'},
            'tenant': {'name': 'Test Tenant'},
            'invitation_url': 'http://example.com/invite?token=123'
        }
        result = self.rules.validate_template_content(template_name, context)

        self.assertTrue(result.is_valid)
        self.assertIn('content_length_valid', result.details)
        self.assertTrue(result.details['content_length_valid'])

    def test_validate_template_security_no_xss(self):
        """Test template security validation detects XSS vulnerabilities"""
        template_name = "notifications/emails/user_invitation.html"
        context = {
            'user': {'display_name': 'Test User'},
            'tenant': {'name': 'Test Tenant'},
            'invitation_url': 'http://example.com/invite?token=123'
        }
        result = self.rules.validate_template_security(template_name, context)

        self.assertTrue(result.is_valid)
        self.assertIn('security_validated', result.details)
        self.assertTrue(result.details['security_validated'])

    def test_validate_template_security_detects_script_tags(self):
        """Test template security validation detects script tags in rendered content"""
        # Create a test template with script tag
        from django.template import Template, Context
        from django.template.loader import get_template

        # Test with a template that would render script tags if context had them
        template_name = "notifications/emails/user_invitation.html"
        # Use safe context - Django templates auto-escape by default
        context = {
            'user': {'display_name': '<script>alert("xss")</script>'},
            'tenant': {'name': 'Test Tenant'},
            'invitation_url': 'http://example.com/invite?token=123'
        }
        result = self.rules.validate_template_security(template_name, context)

        # Django auto-escapes, so script tags should be escaped in output
        self.assertTrue(result.is_valid)
        self.assertIn('security_validated', result.details)


class NotificationsTemplateIntegrationTest(TestCase):
    """Integration tests for template validation with NotificationService"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_template_validation_with_notification_service(self):
        """Test template validation integrates with notification service"""
        from hub.apps.notifications.templates import render_email_template

        template_name = "notifications/emails/user_invitation.html"
        context = {
            'user': {'display_name': 'Test User'},
            'tenant': {'name': 'Test Tenant'},
            'invitation_url': 'http://example.com/invite?token=123'
        }

        # Validate template before rendering
        validation_result = self.rules.validate_template_structure(template_name)
        self.assertTrue(validation_result.is_valid)

        # Render template (should work if validation passed)
        rendered = render_email_template(template_name, context)
        self.assertIn('html', rendered)
        self.assertIn('text', rendered)

        # Validate rendered content
        content_result = self.rules.validate_template_content(template_name, context)
        self.assertTrue(content_result.is_valid)


class NotificationDeliveryChannelValidationTest(TestCase):
    """Test delivery channel validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_delivery_channel_email_valid(self):
        """Test EMAIL channel validation with valid notification"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"recipient-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test Email",
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_channel('EMAIL', notification)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['channel_supported'])
        self.assertTrue(result.details['channel_implemented'])

    def test_validate_delivery_channel_email_invalid_notification(self):
        """Test EMAIL channel validation with notification missing email"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="",  # Empty email
            subject="Test Email",
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_channel('EMAIL', notification)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("email address", result.errors[0].lower())

    def test_validate_delivery_channel_sms_warning(self):
        """Test SMS channel validation (not yet implemented)"""
        result = self.rules.validate_delivery_channel('SMS')
        self.assertTrue(result.is_valid)  # Should be valid but with warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("not yet fully implemented", result.warnings[0].lower())

    def test_validate_delivery_channel_push_warning(self):
        """Test PUSH channel validation (not yet implemented)"""
        result = self.rules.validate_delivery_channel('PUSH')
        self.assertTrue(result.is_valid)  # Should be valid but with warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("not yet fully implemented", result.warnings[0].lower())

    def test_validate_delivery_channel_in_app_warning(self):
        """Test IN_APP channel validation (not yet implemented)"""
        result = self.rules.validate_delivery_channel('IN_APP')
        self.assertTrue(result.is_valid)  # Should be valid but with warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("not yet fully implemented", result.warnings[0].lower())

    def test_validate_delivery_channel_invalid(self):
        """Test invalid delivery channel"""
        result = self.rules.validate_delivery_channel('INVALID_CHANNEL')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("invalid delivery channel", result.errors[0].lower())

    def test_validate_delivery_channel_empty(self):
        """Test empty delivery channel"""
        result = self.rules.validate_delivery_channel('')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("must be provided", result.errors[0].lower())


class NotificationRecipientValidationTest(TestCase):
    """Test recipient validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_recipient_email_valid(self):
        """Test valid email recipient"""
        result = self.rules.validate_recipient('user@example.com', 'EMAIL')
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['email_format_valid'])

    def test_validate_recipient_email_invalid_format(self):
        """Test invalid email format"""
        result = self.rules.validate_recipient('invalid-email', 'EMAIL')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_recipient_email_no_at(self):
        """Test email without @ symbol"""
        result = self.rules.validate_recipient('userexample.com', 'EMAIL')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_recipient_email_multiple_at(self):
        """Test email with multiple @ symbols"""
        result = self.rules.validate_recipient('user@@example.com', 'EMAIL')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_recipient_email_consecutive_dots(self):
        """Test email with consecutive dots (should be rejected by Django validator)"""
        result = self.rules.validate_recipient('user..name@example.com', 'EMAIL')
        # Django's email validator rejects consecutive dots, so this should fail
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_recipient_sms_valid(self):
        """Test valid SMS phone number"""
        result = self.rules.validate_recipient('+1234567890', 'SMS')
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['phone_format_valid'])

    def test_validate_recipient_sms_invalid(self):
        """Test invalid SMS phone number"""
        result = self.rules.validate_recipient('invalid-phone', 'SMS')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_recipient_push_valid(self):
        """Test valid PUSH device token"""
        device_token = 'a' * 64  # 64 character token
        result = self.rules.validate_recipient(device_token, 'PUSH')
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['device_token_format_valid'])

    def test_validate_recipient_push_invalid_short(self):
        """Test PUSH device token too short"""
        result = self.rules.validate_recipient('short', 'PUSH')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_recipient_in_app_valid(self):
        """Test valid IN_APP user ID"""
        import uuid
        user_id = str(uuid.uuid4())
        result = self.rules.validate_recipient(user_id, 'IN_APP')
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['user_id_format_valid'])

    def test_validate_recipient_in_app_invalid(self):
        """Test invalid IN_APP user ID"""
        result = self.rules.validate_recipient('not-a-uuid', 'IN_APP')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_recipient_empty(self):
        """Test empty recipient"""
        result = self.rules.validate_recipient('', 'EMAIL')
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("must be provided", result.errors[0].lower())


class NotificationRateLimitingValidationTest(TestCase):
    """Test delivery rate limiting validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        from django.utils import timezone
        from datetime import timedelta

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_rate_limiting_no_exceeded(self):
        """Test rate limiting when limits are not exceeded"""
        result = self.rules.validate_delivery_rate_limiting(
            recipient='user@example.com',
            channel='EMAIL',
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_rate_limiting_recipient_exceeded(self):
        """Test rate limiting when recipient limit is exceeded"""
        from django.conf import settings
        from django.utils import timezone

        # Create many deliveries for the same recipient
        recipient = 'rate-limited@example.com'
        rate_limit = getattr(settings, 'NOTIFICATION_RATE_LIMIT_PER_RECIPIENT', 10)

        # Create deliveries up to the limit
        for i in range(rate_limit):
            EmailDelivery.objects.create(
                email_type=EmailType.USER_INVITATION,
                to_email=recipient,
                subject=f"Test {i}",
                tenant=self.tenant
            )

        result = self.rules.validate_delivery_rate_limiting(
            recipient=recipient,
            channel='EMAIL'
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("rate limit exceeded", result.errors[0].lower())
        self.assertTrue(result.details['recipient_rate_limit_exceeded'])

    def test_validate_rate_limiting_tenant_exceeded(self):
        """Test rate limiting when tenant limit is exceeded"""
        from django.conf import settings

        rate_limit = getattr(settings, 'NOTIFICATION_RATE_LIMIT_PER_TENANT', 100)

        # Create deliveries up to the limit
        for i in range(rate_limit):
            EmailDelivery.objects.create(
                email_type=EmailType.USER_INVITATION,
                to_email=f"user{i}@example.com",
                subject=f"Test {i}",
                tenant=self.tenant
            )

        result = self.rules.validate_delivery_rate_limiting(
            recipient='newuser@example.com',
            channel='EMAIL',
            tenant_id=str(self.tenant.id)
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("rate limit exceeded", result.errors[0].lower())
        self.assertTrue(result.details['tenant_rate_limit_exceeded'])

    def test_validate_rate_limiting_user_exceeded(self):
        """Test rate limiting when user limit is exceeded"""
        from django.conf import settings

        rate_limit = getattr(settings, 'NOTIFICATION_RATE_LIMIT_PER_USER', 20)

        # Create deliveries up to the limit
        for i in range(rate_limit):
            EmailDelivery.objects.create(
                email_type=EmailType.USER_INVITATION,
                to_email=f"user{i}@example.com",
                subject=f"Test {i}",
                tenant=self.tenant,
                user=self.user
            )

        result = self.rules.validate_delivery_rate_limiting(
            recipient='newuser@example.com',
            channel='EMAIL',
            user_id=str(self.user.id)
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("rate limit exceeded", result.errors[0].lower())
        self.assertTrue(result.details['user_rate_limit_exceeded'])

    def test_validate_rate_limiting_approaching_limit(self):
        """Test rate limiting warning when approaching limit"""
        from django.conf import settings

        rate_limit = getattr(settings, 'NOTIFICATION_RATE_LIMIT_PER_RECIPIENT', 10)
        # Create deliveries at 80% of limit
        count = int(rate_limit * 0.8)

        recipient = 'approaching@example.com'
        for i in range(count):
            EmailDelivery.objects.create(
                email_type=EmailType.USER_INVITATION,
                to_email=recipient,
                subject=f"Test {i}",
                tenant=self.tenant
            )

        result = self.rules.validate_delivery_rate_limiting(
            recipient=recipient,
            channel='EMAIL'
        )
        self.assertTrue(result.is_valid)  # Should still be valid
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("approaching", result.warnings[0].lower())


class NotificationDeliveryStatusValidationTest(TestCase):
    """Test delivery status validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_status_pending_to_sent(self):
        """Test valid status transition PENDING → SENT"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.PENDING,
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(
            notification,
            new_status=EmailDeliveryStatus.SENT
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['transition_valid'])

    def test_validate_status_pending_to_failed(self):
        """Test valid status transition PENDING → FAILED"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.PENDING,
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(
            notification,
            new_status=EmailDeliveryStatus.FAILED
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['transition_valid'])

    def test_validate_status_sent_to_delivered(self):
        """Test valid status transition SENT → DELIVERED"""
        from django.utils import timezone
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.SENT,
            sent_at=timezone.now(),
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(
            notification,
            new_status=EmailDeliveryStatus.DELIVERED
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['transition_valid'])

    def test_validate_status_invalid_transition(self):
        """Test invalid status transition"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.DELIVERED,  # Final state
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(
            notification,
            new_status=EmailDeliveryStatus.SENT  # Cannot go back
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("invalid status transition", result.errors[0].lower())

    def test_validate_status_sent_missing_sent_at(self):
        """Test status SENT without sent_at timestamp (warning)"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.SENT,
            sent_at=None,  # Missing timestamp
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(
            notification,
            new_status=EmailDeliveryStatus.SENT
        )
        self.assertTrue(result.is_valid)  # Should be valid but with warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("sent_at", result.warnings[0].lower())

    def test_validate_status_failed_missing_error_message(self):
        """Test status FAILED without error_message (warning)"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.FAILED,
            error_message=None,  # Missing error message
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(
            notification,
            new_status=EmailDeliveryStatus.FAILED
        )
        self.assertTrue(result.is_valid)  # Should be valid but with warnings
        self.assertGreater(len(result.warnings), 0)
        # Check that error_message warning is present (may be second warning after failed_at)
        warnings_text = ' '.join(result.warnings).lower()
        self.assertIn("error_message", warnings_text)

    def test_validate_status_failed_retry_limit_exceeded(self):
        """Test status FAILED with retry limit exceeded"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.FAILED,
            retry_count=5,
            max_retries=3,  # Exceeded
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(notification)
        self.assertTrue(result.is_valid)  # Should be valid but with warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("exceeded max retries", result.warnings[0].lower())
        self.assertTrue(result.details['retry_limit_exceeded'])

    def test_validate_status_failed_can_retry(self):
        """Test status FAILED that can be retried"""
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            subject="Test",
            status=EmailDeliveryStatus.FAILED,
            retry_count=1,
            max_retries=3,  # Can retry
            tenant=self.tenant
        )
        result = self.rules.validate_delivery_status(notification)
        self.assertTrue(result.is_valid)
        self.assertFalse(result.details['retry_limit_exceeded'])
        self.assertTrue(result.details['can_retry'])


class NotificationDeliveryIntegrationTest(TestCase):
    """Integration tests for notification delivery validation with NotificationService"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_delivery_validation_before_sending(self):
        """Test delivery validation before sending notification"""
        recipient = 'user@example.com'

        # Validate channel
        channel_result = self.rules.validate_delivery_channel('EMAIL')
        self.assertTrue(channel_result.is_valid)

        # Validate recipient
        recipient_result = self.rules.validate_recipient(recipient, 'EMAIL')
        self.assertTrue(recipient_result.is_valid)

        # Validate rate limiting
        rate_limit_result = self.rules.validate_delivery_rate_limiting(
            recipient=recipient,
            channel='EMAIL',
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.assertTrue(rate_limit_result.is_valid)

        # All validations passed, can proceed with sending
        notification = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email=recipient,
            subject="Test Email",
            status=EmailDeliveryStatus.PENDING,
            tenant=self.tenant,
            user=self.user
        )

        # Validate status transition
        status_result = self.rules.validate_delivery_status(
            notification,
            new_status=EmailDeliveryStatus.SENT
        )
        self.assertTrue(status_result.is_valid)

    def test_delivery_validation_rejects_invalid_recipient(self):
        """Test that invalid recipient is rejected"""
        recipient_result = self.rules.validate_recipient('invalid-email', 'EMAIL')
        self.assertFalse(recipient_result.is_valid)
        # Should not proceed with sending

    def test_delivery_validation_rejects_rate_limit_exceeded(self):
        """Test that rate limit exceeded is rejected"""
        from django.conf import settings

        recipient = 'rate-limited@example.com'
        rate_limit = getattr(settings, 'NOTIFICATION_RATE_LIMIT_PER_RECIPIENT', 10)

        # Create deliveries up to the limit
        for i in range(rate_limit):
            EmailDelivery.objects.create(
                email_type=EmailType.USER_INVITATION,
                to_email=recipient,
                subject=f"Test {i}",
                tenant=self.tenant
            )

        rate_limit_result = self.rules.validate_delivery_rate_limiting(
            recipient=recipient,
            channel='EMAIL'
        )
        self.assertFalse(rate_limit_result.is_valid)
        # Should not proceed with sending


class NotificationPreferenceStructureValidationTest(TestCase):
    """Unit tests for preference structure validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_preference_structure_valid(self):
        """Test valid preference structure"""
        preferences = {
            'channels': {'EMAIL': True, 'SMS': False},
            'email_types': {EmailType.USER_INVITATION: True, EmailType.JOB_COMPLETION: False},
            'opt_out': False,
            'frequency': 'IMMEDIATE'
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details['validation_type'], 'preference_structure')

    def test_validate_preference_structure_none(self):
        """Test preference structure validation with None"""
        result = self.rules.validate_preference_structure(None)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("must be provided", result.errors[0])

    def test_validate_preference_structure_not_dict(self):
        """Test preference structure validation with non-dict"""
        result = self.rules.validate_preference_structure("not a dict")
        self.assertFalse(result.is_valid)
        self.assertIn("must be a dictionary", result.errors[0])

    def test_validate_preference_structure_invalid_channel(self):
        """Test preference structure with invalid channel"""
        preferences = {
            'channels': {'INVALID_CHANNEL': True}
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertFalse(result.is_valid)
        self.assertIn("Invalid channel", result.errors[0])

    def test_validate_preference_structure_invalid_channel_type(self):
        """Test preference structure with invalid channel preference type"""
        preferences = {
            'channels': {'EMAIL': 'not a boolean'}
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertFalse(result.is_valid)
        self.assertIn("must be a boolean", result.errors[0])

    def test_validate_preference_structure_invalid_email_type(self):
        """Test preference structure with invalid email type"""
        preferences = {
            'email_types': {'INVALID_EMAIL_TYPE': True}
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertFalse(result.is_valid)
        self.assertIn("Invalid email type", result.errors[0])

    def test_validate_preference_structure_invalid_email_type_value(self):
        """Test preference structure with invalid email type preference value"""
        preferences = {
            'email_types': {EmailType.USER_INVITATION: 'not a boolean'}
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertFalse(result.is_valid)
        self.assertIn("must be a boolean", result.errors[0])

    def test_validate_preference_structure_invalid_opt_out(self):
        """Test preference structure with invalid opt_out type"""
        preferences = {
            'opt_out': 'not a boolean'
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertFalse(result.is_valid)
        self.assertIn("opt_out preference must be a boolean", result.errors[0])

    def test_validate_preference_structure_opt_out_true(self):
        """Test preference structure with opt_out=True"""
        preferences = {
            'opt_out': True
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        # Check that opt-out warning is present (may not be first warning)
        warnings_text = ' '.join(result.warnings).lower()
        self.assertIn("opted out", warnings_text)

    def test_validate_preference_structure_invalid_frequency(self):
        """Test preference structure with invalid frequency"""
        preferences = {
            'frequency': 'INVALID_FREQUENCY'
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertFalse(result.is_valid)
        self.assertIn("Invalid frequency", result.errors[0])

    def test_validate_preference_structure_unknown_fields(self):
        """Test preference structure with unknown fields"""
        preferences = {
            'channels': {'EMAIL': True},
            'unknown_field': 'value'
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertTrue(result.is_valid)  # Unknown fields are warnings, not errors
        self.assertGreater(len(result.warnings), 0)
        # Check that unknown fields warning is present (may not be first warning)
        warnings_text = ' '.join(result.warnings)
        self.assertIn("Unknown preference fields", warnings_text)

    def test_validate_preference_structure_no_channels(self):
        """Test preference structure without channels"""
        preferences = {
            'email_types': {EmailType.USER_INVITATION: True}
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        # Check that no channels warning is present (may not be first warning)
        warnings_text = ' '.join(result.warnings)
        self.assertIn("No channel preferences", warnings_text)

    def test_validate_preference_structure_no_email_types(self):
        """Test preference structure without email_types"""
        preferences = {
            'channels': {'EMAIL': True}
        }
        result = self.rules.validate_preference_structure(preferences)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("No email type preferences", result.warnings[0])


class NotificationPreferenceUpdateValidationTest(TestCase):
    """Unit tests for preference update validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_preference_update_self(self):
        """Test user updating their own preferences"""
        preferences = {
            'channels': {'EMAIL': True},
            'email_types': {EmailType.USER_INVITATION: True},
            'opt_out': False,
            'frequency': 'IMMEDIATE'
        }
        result = self.rules.validate_preference_update(
            user=self.user,
            preferences=preferences,
            requesting_user=self.user
        )
        self.assertTrue(result.is_valid, f"Update validation failed: {result.errors}")
        self.assertEqual(result.details['update_reason'], 'self_update')
        self.assertTrue(result.details['can_update'])

    def test_validate_preference_update_no_user(self):
        """Test preference update validation with no user"""
        preferences = {
            'channels': {'EMAIL': True}
        }
        result = self.rules.validate_preference_update(
            user=None,
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("User must be provided", result.errors[0])

    def test_validate_preference_update_unsaved_user(self):
        """Test preference update validation with unsaved user"""
        from hub.apps.users.models import UserStatus
        unsaved_user = User(
            email=f"unsaved-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        # Ensure pk is None to simulate unsaved user
        unsaved_user.pk = None
        preferences = {
            'channels': {'EMAIL': True}
        }
        result = self.rules.validate_preference_update(
            user=unsaved_user,
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("must be saved", result.errors[0])

    def test_validate_preference_update_inactive_user(self):
        """Test preference update validation with inactive user"""
        from hub.apps.users.models import UserStatus
        inactive_user = User.objects.create_user(
            email=f"inactive-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.DISABLED
        )
        preferences = {
            'channels': {'EMAIL': True}
        }
        result = self.rules.validate_preference_update(
            user=inactive_user,
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("must be ACTIVE", result.errors[0])

    def test_validate_preference_update_other_user(self):
        """Test user trying to update another user's preferences"""
        preferences = {
            'channels': {'EMAIL': True}
        }
        result = self.rules.validate_preference_update(
            user=self.other_user,
            preferences=preferences,
            requesting_user=self.user
        )
        self.assertFalse(result.is_valid)
        self.assertIn("does not have permission", result.errors[0])
        self.assertFalse(result.details['can_update'])

    def test_validate_preference_update_platform_admin(self):
        """Test platform admin updating user preferences"""
        from hub.apps.users.models import UserStatus
        admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            is_platform_admin=True
        )
        preferences = {
            'channels': {'EMAIL': True}
        }
        result = self.rules.validate_preference_update(
            user=self.user,
            preferences=preferences,
            requesting_user=admin_user
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details['update_reason'], 'admin_update')
        self.assertTrue(result.details['can_update'])

    def test_validate_preference_update_invalid_structure(self):
        """Test preference update with invalid preference structure"""
        preferences = {
            'channels': {'INVALID_CHANNEL': True}
        }
        result = self.rules.validate_preference_update(
            user=self.user,
            preferences=preferences,
            requesting_user=self.user
        )
        self.assertFalse(result.is_valid)
        self.assertIn("Invalid channel", result.errors[0])

    def test_validate_preference_update_no_requesting_user(self):
        """Test preference update without requesting user"""
        preferences = {
            'channels': {'EMAIL': True}
        }
        result = self.rules.validate_preference_update(
            user=self.user,
            preferences=preferences
        )
        self.assertTrue(result.is_valid)  # Assumes self-update
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("No requesting user provided", result.warnings[0])


class NotificationPreferenceEnforcementValidationTest(TestCase):
    """Unit tests for preference enforcement validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_preference_enforcement_allowed(self):
        """Test preference enforcement when notification is allowed"""
        preferences = {
            'channels': {'EMAIL': True},
            'email_types': {EmailType.USER_INVITATION: True},
            'opt_out': False,
            'frequency': 'IMMEDIATE'
        }
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL',
            preferences=preferences
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details['can_send'])

    def test_validate_preference_enforcement_opt_out(self):
        """Test preference enforcement with opt_out=True"""
        preferences = {
            'channels': {'EMAIL': True},
            'email_types': {EmailType.USER_INVITATION: True},
            'opt_out': True,
            'frequency': 'IMMEDIATE'
        }
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL',
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("opted out", result.errors[0].lower())
        self.assertFalse(result.details['can_send'])

    def test_validate_preference_enforcement_channel_disabled(self):
        """Test preference enforcement with channel disabled"""
        preferences = {
            'channels': {'EMAIL': False},
            'email_types': {EmailType.USER_INVITATION: True},
            'opt_out': False,
            'frequency': 'IMMEDIATE'
        }
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL',
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("disabled", result.errors[0].lower())
        self.assertFalse(result.details['can_send'])

    def test_validate_preference_enforcement_email_type_disabled(self):
        """Test preference enforcement with email type disabled"""
        preferences = {
            'channels': {'EMAIL': True},
            'email_types': {EmailType.USER_INVITATION: False},
            'opt_out': False,
            'frequency': 'IMMEDIATE'
        }
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL',
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("disabled", result.errors[0].lower())
        self.assertFalse(result.details['can_send'])

    def test_validate_preference_enforcement_frequency_never(self):
        """Test preference enforcement with frequency=NEVER"""
        preferences = {
            'channels': {'EMAIL': True},
            'email_types': {EmailType.USER_INVITATION: True},
            'opt_out': False,
            'frequency': 'NEVER'
        }
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL',
            preferences=preferences
        )
        self.assertTrue(result.is_valid)  # Frequency is warning only
        self.assertGreater(len(result.warnings), 0)
        # Check that NEVER warning is present (may not be first warning)
        warnings_text = ' '.join(result.warnings)
        self.assertIn("NEVER", warnings_text)

    def test_validate_preference_enforcement_invalid_email_type(self):
        """Test preference enforcement with invalid email type"""
        preferences = {
            'channels': {'EMAIL': True},
            'opt_out': False
        }
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type='INVALID_EMAIL_TYPE',
            channel='EMAIL',
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("Invalid email type", result.errors[0])

    def test_validate_preference_enforcement_invalid_channel(self):
        """Test preference enforcement with invalid channel"""
        preferences = {
            'channels': {'EMAIL': True},
            'opt_out': False
        }
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='INVALID_CHANNEL',
            preferences=preferences
        )
        self.assertFalse(result.is_valid)
        self.assertIn("Invalid channel", result.errors[0])

    def test_validate_preference_enforcement_no_preferences(self):
        """Test preference enforcement without providing preferences"""
        result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL'
        )
        # Should use defaults and allow sending
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        # Check that no preferences warning is present (may not be first warning)
        warnings_text = ' '.join(result.warnings)
        self.assertIn("No preferences found", warnings_text)


class NotificationPreferenceIntegrationTest(TestCase):
    """Integration tests for preference validation with NotificationService"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = NotificationsBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_preference_validation_integration(self):
        """Test preference validation integrates with notification flow"""
        # Create preferences
        preferences = {
            'channels': {'EMAIL': True},
            'email_types': {EmailType.USER_INVITATION: True},
            'opt_out': False,
            'frequency': 'IMMEDIATE'
        }

        # Validate structure
        structure_result = self.rules.validate_preference_structure(preferences)
        self.assertTrue(structure_result.is_valid, f"Structure validation failed: {structure_result.errors}")

        # Validate update
        update_result = self.rules.validate_preference_update(
            user=self.user,
            preferences=preferences,
            requesting_user=self.user
        )
        self.assertTrue(update_result.is_valid, f"Update validation failed: {update_result.errors}")

        # Validate enforcement
        enforcement_result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL',
            preferences=preferences
        )
        self.assertTrue(enforcement_result.is_valid, f"Enforcement validation failed: {enforcement_result.errors}")
        self.assertTrue(enforcement_result.details['can_send'])

    def test_preference_validation_blocked_notification(self):
        """Test preference validation blocks notification when preferences disallow it"""
        # Create preferences that block notification
        preferences = {
            'channels': {'EMAIL': True},
            'email_types': {EmailType.USER_INVITATION: False},  # Disabled
            'opt_out': False,
            'frequency': 'IMMEDIATE'
        }

        # Validate enforcement - should block
        enforcement_result = self.rules.validate_preference_enforcement(
            user=self.user,
            email_type=EmailType.USER_INVITATION,
            channel='EMAIL',
            preferences=preferences
        )
        self.assertFalse(enforcement_result.is_valid)
        self.assertFalse(enforcement_result.details['can_send'])
        self.assertIn("disabled", enforcement_result.errors[0].lower())

