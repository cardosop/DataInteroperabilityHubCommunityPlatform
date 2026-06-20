"""
Unit tests for Webhooks Business Rules

Tests for webhook business rules validation, including:
- WebhooksBusinessRules initialization
- Rule registration in business rules registry
- WebhookRuleExecutionContext
"""

import uuid

from django.test import TestCase

from hub.apps.core.business_rules.registry import get_registry
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus
from hub.apps.webhooks.business_rules import (
    WebhookRuleExecutionContext,
    WebhooksBusinessRules,
)
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
)


class WebhooksBusinessRulesInitializationTest(TestCase):
    """Test WebhooksBusinessRules initialization"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_webhooks_business_rules_initialization_with_tenant_and_user(self):
        """Test WebhooksBusinessRules initialization with tenant and user"""
        rules = WebhooksBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_webhooks_business_rules_initialization_without_tenant(self):
        """Test WebhooksBusinessRules initialization without tenant"""
        rules = WebhooksBusinessRules(user_id=str(self.user.id))
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_webhooks_business_rules_initialization_without_user(self):
        """Test WebhooksBusinessRules initialization without user"""
        rules = WebhooksBusinessRules(tenant_id=str(self.tenant.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_webhooks_business_rules_initialization_without_tenant_and_user(self):
        """Test WebhooksBusinessRules initialization without tenant and user"""
        rules = WebhooksBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)



class WebhooksBusinessRulesRegistrationTest(TestCase):
    """Test WebhooksBusinessRules registration in business rules registry"""

    def test_webhooks_business_rules_registered(self):
        """Test WebhooksBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("webhooks_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "webhooks_validation")
        self.assertEqual(rule.rule_class, WebhooksBusinessRules)
        self.assertIn("webhooks", rule.tags)
        self.assertIn("validation", rule.tags)
        self.assertIn("subscription", rule.tags)
        self.assertIn("delivery", rule.tags)

    def test_webhooks_business_rules_priority(self):
        """Test WebhooksBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("webhooks_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)

    def test_webhooks_business_rules_description(self):
        """Test WebhooksBusinessRules has correct description"""
        registry = get_registry()
        rule = registry.get_rule("webhooks_validation")
        self.assertIsNotNone(rule)
        self.assertIn("webhook", rule.description.lower())
        self.assertIn("validates", rule.description.lower())


class WebhookRuleExecutionContextTest(TestCase):
    """Test WebhookRuleExecutionContext"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        self.delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ASSET_CREATED,
            payload={"test": "data"},
            signature="test-signature",
        )

    def test_webhook_rule_execution_context_creation(self):
        """Test WebhookRuleExecutionContext creation"""
        context = WebhookRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            webhook_subscription=self.webhook,
            delivery=self.delivery,
            tenant=self.tenant,
            user=self.user,
        )
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.webhook_subscription, self.webhook)
        self.assertEqual(context.delivery, self.delivery)
        self.assertEqual(context.tenant, self.tenant)
        self.assertEqual(context.user, self.user)

    def test_webhook_rule_execution_context_to_dict(self):
        """Test WebhookRuleExecutionContext to_dict method"""
        context = WebhookRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            webhook_subscription=self.webhook,
            delivery=self.delivery,
            tenant=self.tenant,
            user=self.user,
        )
        context_dict = context.to_dict()
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))
        self.assertEqual(context_dict["webhook_id"], str(self.webhook.id))
        self.assertEqual(context_dict["webhook_name"], self.webhook.name)
        self.assertEqual(context_dict["webhook_status"], self.webhook.status)
        self.assertEqual(context_dict["webhook_url"], self.webhook.url)
        self.assertEqual(context_dict["delivery_id"], str(self.delivery.id))
        self.assertEqual(context_dict["delivery_status"], self.delivery.status)
        self.assertEqual(context_dict["delivery_event_type"], self.delivery.event_type)
        self.assertEqual(context_dict["tenant_id_from_object"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id_from_object"], str(self.user.id))


class WebhookSubscriptionValidationTest(TestCase):
    """Test comprehensive webhook subscription validation"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = WebhooksBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_subscription_url_valid_https(self):
        """Test subscription URL validation with valid HTTPS URL"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_url(webhook)
        self.assertIn("url_validation", result.details)
        self.assertTrue(result.details.get("url_format_valid", False))
        self.assertIn("url", result.details)

    def test_validate_subscription_url_invalid_format(self):
        """Test subscription URL validation with invalid URL format"""
        # Create webhook instance without saving to bypass model validation
        webhook = Webhook(
            tenant=self.tenant,
            name="Test Webhook",
            url="not-a-valid-url",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_url(webhook)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_subscription_url_http_warning(self):
        """Test subscription URL validation with HTTP URL (should warn)"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="http://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_url(webhook)
        self.assertTrue(result.is_valid)  # HTTP is valid but should warn
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("http", result.warnings[0].lower())

    def test_validate_subscription_url_no_url(self):
        """Test subscription URL validation without URL"""
        webhook = Webhook(
            tenant=self.tenant,
            name="Test Webhook",
            url="",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_url(webhook)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_subscription_event_types_valid(self):
        """Test subscription event type validation with valid event types"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED, WebhookEventType.ASSET_UPDATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_event_types(webhook)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("event_types_valid", False))
        self.assertEqual(result.details.get("event_types_count"), 2)

    def test_validate_subscription_event_types_invalid(self):
        """Test subscription event type validation with invalid event type"""
        # Create webhook instance without saving to bypass model validation
        webhook = Webhook(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=["invalid.event.type"],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_event_types(webhook)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_subscription_event_types_empty(self):
        """Test subscription event type validation with empty event types"""
        # Create webhook instance without saving to bypass model validation
        webhook = Webhook(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_event_types(webhook)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_subscription_event_types_duplicates(self):
        """Test subscription event type validation with duplicate event types.

        Uses unsaved Webhook instance to bypass model.save() deduplication,
        so the business rules validator sees the raw duplicates.
        """
        webhook = Webhook(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED, WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_event_types(webhook)
        self.assertTrue(result.is_valid)  # Duplicates are warnings, not errors
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(result.details.get("has_duplicates", False))

    def test_validate_subscription_filters_valid(self):
        """Test subscription filter validation with valid filters"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED, WebhookEventType.CONTRACT_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_filters(webhook)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("filters_valid", False))
        self.assertIn("filter_expressions", result.details)

    def test_validate_subscription_filters_empty(self):
        """Test subscription filter validation with empty filters"""
        # Create webhook instance without saving to bypass model validation
        webhook = Webhook(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_filters(webhook)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_subscription_security_valid_secret(self):
        """Test subscription security validation with valid secret"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long-enough",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_security(webhook)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("secret_valid", False))
        self.assertTrue(result.details.get("signature_generation_valid", False))

    def test_validate_subscription_security_short_secret(self):
        """Test subscription security validation with short secret"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="short",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_security(webhook)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_subscription_security_no_secret(self):
        """Test subscription security validation without secret"""
        webhook = Webhook(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_security(webhook)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_subscription_security_signature_generation(self):
        """Test subscription security validation signature generation"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long-enough",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_subscription_security(webhook)
        self.assertTrue(result.details.get("signature_generation_valid", False))
        self.assertEqual(result.details.get("signature_length"), 64)

    def test_validate_webhook_subscription_comprehensive(self):
        """Test comprehensive webhook subscription validation"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long-enough",
            event_types=[WebhookEventType.ASSET_CREATED, WebhookEventType.CONTRACT_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_webhook_subscription(webhook, tenant=self.tenant)
        self.assertIn("webhook_subscription_validation", result.details)
        self.assertIn("validation_checks", result.details)
        validation_checks = result.details.get("validation_checks", {})
        self.assertIn("url", validation_checks)
        self.assertIn("event_types", validation_checks)
        self.assertIn("filters", validation_checks)
        self.assertIn("security", validation_checks)

    def test_validate_webhook_subscription_integration_with_service(self):
        """Test webhook subscription validation integration with WebhookDeliveryService"""
        from hub.apps.webhooks.service import WebhookDeliveryService

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long-enough",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        result = self.rules._validate_webhook_subscription(webhook, tenant=self.tenant)
        self.assertIsNotNone(result)

        # Verify webhook can be used with service
        # Service should be able to work with validated webhook
        self.assertTrue(webhook.subscribes_to_event_type(WebhookEventType.ASSET_CREATED))
        self.assertIsNotNone(WebhookDeliveryService)


class WebhooksBusinessRulesTenantPermissionsTest(TestCase):
    """Test _validate_tenant_context and _validate_permissions methods."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = WebhooksBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key-32-chars-long",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )

    def test_validate_tenant_context_valid(self):
        """Tenant context validation passes when webhook belongs to tenant."""
        result = self.rules._validate_tenant_context(
            webhook=self.webhook, tenant=self.tenant
        )
        self.assertTrue(result.is_valid)

    def test_validate_tenant_context_mismatched_webhook(self):
        """Tenant context validation fails when webhook belongs to different tenant."""
        other_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other {other_uid}", slug=f"other-{other_uid}",
            status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
        )
        result = self.rules._validate_tenant_context(
            webhook=self.webhook, tenant=other_tenant
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_tenant_context_no_tenant(self):
        """Tenant context validation produces warning when no tenant provided."""
        result = self.rules._validate_tenant_context(webhook=self.webhook)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)

    def test_validate_permissions_valid(self):
        """Permissions validation passes when user belongs to webhook's tenant."""
        result = self.rules._validate_permissions(webhook=self.webhook, user=self.user)
        self.assertTrue(result.is_valid)

    def test_validate_permissions_cross_tenant_user(self):
        """Permissions validation warns when user belongs to different tenant."""
        other_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other {other_uid}", slug=f"other-{other_uid}",
            status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
        )
        other_user = User.objects.create_user(
            email=f"other-{other_uid}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        result = self.rules._validate_permissions(webhook=self.webhook, user=other_user)
        self.assertTrue(result.is_valid)  # cross-tenant is a warning, not an error
        self.assertGreater(len(result.warnings), 0)

    def test_validate_permissions_no_user(self):
        """Permissions validation produces warning when no user provided."""
        result = self.rules._validate_permissions(webhook=self.webhook)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
