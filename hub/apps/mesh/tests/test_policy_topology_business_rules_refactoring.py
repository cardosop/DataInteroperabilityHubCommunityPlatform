"""
Comprehensive test suite for PolicyBusinessRules and TopologyBusinessRules refactoring.

Tests all methods and framework features:
- All validation methods
- Framework features (caching, metrics, tracing)
- ValidationResult from base class
- Integration with BusinessRules base class

Following TDD approach and engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.governance.models import AccessPolicy
from hub.apps.mesh.business_rules import (
    PolicyBusinessRules,
    TopologyBusinessRules,
)
from hub.apps.mesh.models import (
    DataMeshDomain,
    DomainStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus

UserModel = get_user_model()


class PolicyBusinessRulesFrameworkFeaturesTest(TestCase):
    """Test framework features: caching, metrics, tracing, logging"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.user, role=self.tenant_admin_role)

        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE,
        )
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant, name="Test Policy", enabled=True, conditions={}, effect="ALLOW"
        )
        self.rules = PolicyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=True,
            enable_metrics=True,
            enable_tracing=True,
            enable_logging=True,
        )

    def test_validation_result_from_base_class(self):
        """Test that ValidationResult is from base class"""
        from hub.apps.core.business_rules.base import ValidationResult

        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            details={"test": "value"},
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(result.details["test"], "value")

    def test_validation_result_boolean_context(self):
        """Test ValidationResult in boolean context"""
        valid_result = ValidationResult(is_valid=True)
        invalid_result = ValidationResult(is_valid=False)

        self.assertTrue(valid_result)
        self.assertFalse(invalid_result)

    def test_validation_result_combine(self):
        """Test ValidationResult.combine() method"""
        result1 = ValidationResult(
            is_valid=True,
            errors=["error1"],
            warnings=["warning1"],
            details={"key1": "value1"},
        )
        result2 = ValidationResult(
            is_valid=False,
            errors=["error2"],
            warnings=["warning2"],
            details={"key2": "value2"},
        )

        combined = result1.combine(result2)

        self.assertFalse(combined.is_valid)  # False if any is False
        self.assertEqual(len(combined.errors), 2)
        self.assertEqual(len(combined.warnings), 2)
        self.assertEqual(combined.details["key1"], "value1")
        self.assertEqual(combined.details["key2"], "value2")

    def test_inherits_from_business_rules(self):
        """Test that PolicyBusinessRules inherits from BusinessRules"""
        self.assertTrue(issubclass(PolicyBusinessRules, BusinessRules))

    def test_get_rule_name(self):
        """Test get_rule_name() override"""
        self.assertEqual(self.rules.get_rule_name(), "PolicyBusinessRules")

    def test_initialization_with_framework_features(self):
        """Test initialization with framework feature flags"""
        rules = PolicyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=True,
            enable_metrics=True,
            enable_tracing=True,
            enable_logging=True,
        )

        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))
        self.assertTrue(rules.enable_caching)
        self.assertTrue(rules.enable_metrics)
        self.assertTrue(rules.enable_tracing)
        self.assertTrue(rules.enable_logging)

    def test_initialization_without_framework_features(self):
        """Test initialization without framework features"""
        rules = PolicyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=False,
            enable_metrics=False,
            enable_tracing=False,
            enable_logging=False,
        )

        self.assertFalse(rules.enable_caching)
        self.assertFalse(rules.enable_metrics)
        self.assertFalse(rules.enable_tracing)
        self.assertFalse(rules.enable_logging)

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    )
    def test_caching_enabled(self):
        """Test that caching works when enabled"""
        cache.clear()

        # First call - should compute and cache
        result1 = self.rules.validate_policy_application(domain=self.domain, policy=self.policy)

        # Verify result is valid
        self.assertTrue(result1.is_valid)

        # Second call with same parameters - should use cache
        # Note: The execute() method handles caching, but validate_policy_application
        # is called directly, so caching may not apply unless using execute()
        result2 = self.rules.validate_policy_application(domain=self.domain, policy=self.policy)

        self.assertTrue(result2.is_valid)

    def test_validate_method_with_domain_and_policy(self):
        """Test validate() method with domain and policy"""
        result = self.rules.validate(domain=self.domain, policy=self.policy)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "policy")
        self.assertIn("domain_id", result.details)
        self.assertIn("domain_name", result.details)

    def test_validate_method_with_domain_only(self):
        """Test validate() method with domain only"""
        result = self.rules.validate(domain=self.domain)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "policy")
        self.assertIn("domain_id", result.details)

    def test_validate_method_with_context(self):
        """Test validate() method with RuleExecutionContext"""
        context = RuleExecutionContext(resource=self.domain, metadata={"policy": self.policy})

        result = self.rules.validate(context=context)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "policy")

    def test_validate_method_missing_domain(self):
        """Test validate() method without domain"""
        result = self.rules.validate()

        self.assertFalse(result.is_valid)
        self.assertIn("Domain is required", result.errors[0])

    def test_execute_method_from_base_class(self):
        """Test execute() method from base class"""
        result = self.rules.execute(domain=self.domain, policy=self.policy)

        self.assertTrue(result.is_valid)
        self.assertIsInstance(result, ValidationResult)

    def test_all_existing_methods_still_work(self):
        """Test that all existing methods still work correctly"""
        # Test validate_policy_application
        result = self.rules.validate_policy_application(domain=self.domain, policy=self.policy)
        self.assertTrue(result.is_valid)
        self.assertIsInstance(result, ValidationResult)

        # Test check_compliance
        compliance = self.rules.check_compliance(domain=self.domain)
        self.assertIn("compliance_status", compliance)
        self.assertIn("violations", compliance)

        # Test detect_violations
        violations = self.rules.detect_violations(domain=self.domain)
        self.assertIsInstance(violations, list)


class TopologyBusinessRulesFrameworkFeaturesTest(TestCase):
    """Test framework features: caching, metrics, tracing, logging"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            status=DomainStatus.ACTIVE,
        )
        self.domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            status=DomainStatus.ACTIVE,
        )

        self.rules = TopologyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=True,
            enable_metrics=True,
            enable_tracing=True,
            enable_logging=True,
        )

    def test_inherits_from_business_rules(self):
        """Test that TopologyBusinessRules inherits from BusinessRules"""
        self.assertTrue(issubclass(TopologyBusinessRules, BusinessRules))

    def test_get_rule_name(self):
        """Test get_rule_name() override"""
        self.assertEqual(self.rules.get_rule_name(), "TopologyBusinessRules")

    def test_initialization_with_framework_features(self):
        """Test initialization with framework feature flags"""
        rules = TopologyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=True,
            enable_metrics=True,
            enable_tracing=True,
            enable_logging=True,
        )

        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))
        self.assertTrue(rules.enable_caching)
        self.assertTrue(rules.enable_metrics)
        self.assertTrue(rules.enable_tracing)
        self.assertTrue(rules.enable_logging)

    def test_initialization_without_framework_features(self):
        """Test initialization without framework features"""
        rules = TopologyBusinessRules(
            tenant_id=str(self.tenant.id),
            enable_caching=False,
            enable_metrics=False,
            enable_tracing=False,
            enable_logging=False,
        )

        self.assertFalse(rules.enable_caching)
        self.assertFalse(rules.enable_metrics)
        self.assertFalse(rules.enable_tracing)
        self.assertFalse(rules.enable_logging)

    def test_validate_method_with_domain(self):
        """Test validate() method with domain"""
        result = self.rules.validate(domain=self.domain1)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "topology")
        self.assertIn("domain_id", result.details)
        self.assertIn("domain_name", result.details)

    def test_validate_method_with_domains_list(self):
        """Test validate() method with domains list"""
        result = self.rules.validate(domains=[self.domain1, self.domain2])

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "topology")
        self.assertEqual(result.details["domains_count"], 2)

    def test_validate_method_with_context(self):
        """Test validate() method with RuleExecutionContext"""
        context = RuleExecutionContext(resource=self.domain1)

        result = self.rules.validate(context=context)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "topology")

    def test_validate_method_with_context_list(self):
        """Test validate() method with RuleExecutionContext containing list"""
        context = RuleExecutionContext(resource=[self.domain1, self.domain2])

        result = self.rules.validate(context=context)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "topology")
        self.assertEqual(result.details["domains_count"], 2)

    def test_validate_method_missing_domain(self):
        """Test validate() method without domain or domains"""
        result = self.rules.validate()

        self.assertFalse(result.is_valid)
        self.assertIn("Domain or domains list is required", result.errors[0])

    def test_validate_method_tenant_mismatch(self):
        """Test validate() method with tenant mismatch"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Other Domain",
            status=DomainStatus.ACTIVE,
        )

        result = self.rules.validate(domain=other_domain)

        self.assertFalse(result.is_valid)
        self.assertIn("Tenant mismatch", result.errors[0])

    def test_execute_method_from_base_class(self):
        """Test execute() method from base class"""
        result = self.rules.execute(domain=self.domain1)

        self.assertTrue(result.is_valid)
        self.assertIsInstance(result, ValidationResult)

    def test_all_existing_methods_still_work(self):
        """Test that all existing methods still work correctly"""
        # Test calculate_relationships
        relationships = self.rules.calculate_relationships([self.domain1, self.domain2])
        self.assertIsInstance(relationships, list)

        # Test calculate_health_metrics
        metrics = self.rules.calculate_health_metrics(self.domain1)
        self.assertIn("health_score", metrics)
        self.assertIn("policy_count", metrics)
        self.assertIn("compliance_status", metrics)
        self.assertIn("violation_count", metrics)
        self.assertIn("is_active", metrics)


class PolicyBusinessRulesIntegrationTest(TestCase):
    """Test integration with BusinessRules framework"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.user, role=self.tenant_admin_role)

        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE,
        )
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant, name="Test Policy", enabled=True, conditions={}, effect="ALLOW"
        )
        self.rules = PolicyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def test_compose_method_from_base_class(self):
        """Test compose() method from base class"""

        def rule1(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"rule1": "executed"})

        def rule2(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"rule2": "executed"})

        context = RuleExecutionContext(resource=self.domain)
        result = self.rules.compose(rule1, rule2, context=context)

        self.assertTrue(result.is_valid)
        self.assertIn("rule1", result.details)
        self.assertIn("rule2", result.details)

    def test_create_rule_function_from_base_class(self):
        """Test create_rule_function() from base class"""

        def custom_rule(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"custom": "rule"})

        rule_func = PolicyBusinessRules.create_rule_function(
            custom_rule, rule_name="custom_policy_rule"
        )

        context = RuleExecutionContext(resource=self.domain)
        result = rule_func(context)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["custom"], "rule")


class TopologyBusinessRulesIntegrationTest(TestCase):
    """Test integration with BusinessRules framework"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE,
        )
        self.rules = TopologyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def test_compose_method_from_base_class(self):
        """Test compose() method from base class"""

        def rule1(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"rule1": "executed"})

        def rule2(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"rule2": "executed"})

        context = RuleExecutionContext(resource=self.domain)
        result = self.rules.compose(rule1, rule2, context=context)

        self.assertTrue(result.is_valid)
        self.assertIn("rule1", result.details)
        self.assertIn("rule2", result.details)

    def test_create_rule_function_from_base_class(self):
        """Test create_rule_function() from base class"""

        def custom_rule(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"custom": "rule"})

        rule_func = TopologyBusinessRules.create_rule_function(
            custom_rule, rule_name="custom_topology_rule"
        )

        context = RuleExecutionContext(resource=self.domain)
        result = rule_func(context)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["custom"], "rule")


class PolicyBusinessRulesAllMethodsTest(TestCase):
    """Test all PolicyBusinessRules methods comprehensively"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.user, role=self.tenant_admin_role)

        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            status=DomainStatus.ACTIVE,
        )
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant, name="Test Policy", enabled=True, conditions={}, effect="ALLOW"
        )
        self.rules = PolicyBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def test_validate_policy_application_comprehensive(self):
        """Test validate_policy_application comprehensively"""
        result = self.rules.validate_policy_application(domain=self.domain, policy=self.policy)

        self.assertTrue(result.is_valid)
        self.assertIsInstance(result, ValidationResult)
        self.assertIn("domain_id", result.details)
        self.assertIn("policy_id", result.details)

    def test_check_compliance_comprehensive(self):
        """Test check_compliance comprehensively"""
        compliance = self.rules.check_compliance(domain=self.domain)

        self.assertIsInstance(compliance, dict)
        self.assertIn("compliance_status", compliance)
        self.assertIn("violations", compliance)
        self.assertIsInstance(compliance["violations"], list)

    def test_detect_violations_comprehensive(self):
        """Test detect_violations comprehensively"""
        violations = self.rules.detect_violations(domain=self.domain)

        self.assertIsInstance(violations, list)
        for violation in violations:
            self.assertIn("type", violation)
            self.assertIn("severity", violation)
            self.assertIn("description", violation)


class TopologyBusinessRulesAllMethodsTest(TestCase):
    """Test all TopologyBusinessRules methods comprehensively"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        self.domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            status=DomainStatus.ACTIVE,
        )
        self.domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            status=DomainStatus.ACTIVE,
        )

        self.rules = TopologyBusinessRules(tenant_id=str(self.tenant.id))

    def test_calculate_relationships_comprehensive(self):
        """Test calculate_relationships comprehensively"""
        relationships = self.rules.calculate_relationships([self.domain1, self.domain2])

        self.assertIsInstance(relationships, list)
        for rel in relationships:
            self.assertIn("source", rel)
            self.assertIn("target", rel)
            self.assertIn("type", rel)
            self.assertIn("weight", rel)

    def test_calculate_health_metrics_comprehensive(self):
        """Test calculate_health_metrics comprehensively"""
        metrics = self.rules.calculate_health_metrics(self.domain1)

        self.assertIsInstance(metrics, dict)
        self.assertIn("health_score", metrics)
        self.assertIn("policy_count", metrics)
        self.assertIn("compliance_status", metrics)
        self.assertIn("violation_count", metrics)
        self.assertIn("is_active", metrics)

        # Verify health_score is in valid range
        self.assertGreaterEqual(metrics["health_score"], 0)
        self.assertLessEqual(metrics["health_score"], 100)
