"""
Comprehensive test suite for DataMeshBusinessRules refactoring.

Tests all DataMeshBusinessRules methods and framework features:
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

import time
import uuid
from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.mesh.business_rules import (
    DataMeshBusinessRules,
    DataMeshRuleExecutionContext,
)
from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.tenants.models import KYCStatus, Tenant

User = get_user_model()


class DataMeshBusinessRulesFrameworkFeaturesTest(TestCase):
    """Test framework features: caching, metrics, tracing, logging"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )
        self.rules = DataMeshBusinessRules(
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

        self.assertFalse(combined.is_valid)  # False AND False = False
        self.assertEqual(len(combined.errors), 2)
        self.assertEqual(len(combined.warnings), 2)
        self.assertEqual(combined.details["key1"], "value1")
        self.assertEqual(combined.details["key2"], "value2")

    def test_validation_result_string_representation(self):
        """Test ValidationResult string representation"""
        result = ValidationResult(
            is_valid=True,
            errors=["error1"],
            warnings=["warning1"],
        )

        str_repr = str(result)
        self.assertIn("VALID", str_repr)
        self.assertIn("errors=1", str_repr)
        self.assertIn("warnings=1", str_repr)

    def test_rule_execution_context_creation(self):
        """Test RuleExecutionContext creation"""
        context = self.rules.create_context(
            resource=self.domain,
            metadata={"key": "value"},
        )

        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.resource, self.domain)
        self.assertEqual(context.metadata["key"], "value")

    def test_data_mesh_rule_execution_context(self):
        """Test DataMeshRuleExecutionContext"""
        context = DataMeshRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            domain=self.domain,
        )

        self.assertEqual(context.domain, self.domain)
        self.assertIsNone(context.asset)

        # Test to_dict method
        context_dict = context.to_dict()
        self.assertEqual(context_dict["domain_id"], str(self.domain.id))
        self.assertIsNone(context_dict["asset_id"])

    def test_caching_enabled(self):
        """Test that caching works correctly"""
        # Clear cache first
        cache.clear()

        # First execution - should not be cached
        context = self.rules.create_context(resource=self.domain)
        result1 = self.rules.execute(context, domain=self.domain)

        # Second execution - should be cached (if result was valid)
        if result1.is_valid:
            result2 = self.rules.execute(context, domain=self.domain)

            # Results should be equal
            self.assertEqual(result1.is_valid, result2.is_valid)
            self.assertEqual(len(result1.errors), len(result2.errors))
            self.assertEqual(len(result1.warnings), len(result2.warnings))

    def test_caching_disabled(self):
        """Test that caching can be disabled"""
        rules_no_cache = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=False,
        )

        context = self.rules.create_context(resource=self.domain)
        result1 = rules_no_cache.execute(context, domain=self.domain)
        result2 = rules_no_cache.execute(context, domain=self.domain)

        # Results should be equal but not cached
        self.assertEqual(result1.is_valid, result2.is_valid)

    def test_caching_with_use_cache_override(self):
        """Test use_cache parameter override"""
        # Clear cache
        cache.clear()

        context = self.rules.create_context(resource=self.domain)

        # Execute with caching disabled via parameter
        result1 = self.rules.execute(
            context, domain=self.domain, use_cache=False
        )

        # Execute again with caching enabled
        result2 = self.rules.execute(
            context, domain=self.domain, use_cache=True
        )

        # Both should execute (not use cache on first, may use cache on second if valid)
        self.assertEqual(result1.is_valid, result2.is_valid)

    def test_get_rule_name(self):
        """Test get_rule_name() method"""
        rule_name = self.rules.get_rule_name()
        self.assertEqual(rule_name, "DataMeshBusinessRules")

    def test_get_cache_ttl(self):
        """Test get_cache_ttl() method"""
        ttl = self.rules.get_cache_ttl()
        self.assertIsInstance(ttl, int)
        self.assertGreater(ttl, 0)

    def test_framework_features_initialization(self):
        """Test that framework features are initialized correctly"""
        # Test with all features enabled
        rules_all = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=True,
            enable_metrics=True,
            enable_tracing=True,
            enable_logging=True,
        )

        self.assertTrue(rules_all.enable_caching)
        self.assertTrue(rules_all.enable_metrics)
        self.assertTrue(rules_all.enable_tracing)
        self.assertTrue(rules_all.enable_logging)

        # Test with all features disabled
        rules_none = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=False,
            enable_metrics=False,
            enable_tracing=False,
            enable_logging=False,
        )

        self.assertFalse(rules_none.enable_caching)
        self.assertFalse(rules_none.enable_metrics)
        self.assertFalse(rules_none.enable_tracing)
        self.assertFalse(rules_none.enable_logging)


class DataMeshBusinessRulesValidateMethodTest(TestCase):
    """Test DataMeshBusinessRules.validate() method comprehensively"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )
        self.rules = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_with_data_mesh_context(self):
        """Test validate() with DataMeshRuleExecutionContext"""
        # Set up TENANT_ADMIN role for user
        from hub.apps.users.models import Role, UserRole
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        context = DataMeshRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            domain=self.domain,
        )

        result = self.rules.validate(context)

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_with_standard_context(self):
        """Test validate() with standard RuleExecutionContext"""
        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource=self.domain,
        )

        result = self.rules.validate(context)

        self.assertIsInstance(result, ValidationResult)

    def test_validate_with_kwargs_domain(self):
        """Test validate() with domain in kwargs"""
        # Set up TENANT_ADMIN role for user
        from hub.apps.users.models import Role, UserRole
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        result = self.rules.validate(domain=self.domain)

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_without_domain(self):
        """Test validate() without domain"""
        result = self.rules.validate()

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("required", result.errors[0].lower())

    def test_validate_with_validation_type_structure(self):
        """Test validate() with validation_type='structure'"""
        result = self.rules.validate(
            domain=self.domain, validation_type="structure"
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertEqual(result.details["validation_type"], "structure")

    def test_validate_with_validation_type_ownership(self):
        """Test validate() with validation_type='ownership'"""
        result = self.rules.validate(
            domain=self.domain, validation_type="ownership"
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertEqual(result.details["validation_type"], "ownership")

    def test_validate_with_validation_type_boundaries(self):
        """Test validate() with validation_type='boundaries'"""
        self.domain.boundaries = {"data_products": ["product1"]}
        self.domain.save()

        result = self.rules.validate(
            domain=self.domain, validation_type="boundaries"
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertEqual(result.details["validation_type"], "boundaries")

    def test_validate_with_validation_type_all(self):
        """Test validate() with validation_type='all'"""
        result = self.rules.validate(domain=self.domain, validation_type="all")

        self.assertIsInstance(result, ValidationResult)
        self.assertEqual(result.details["validation_type"], "all")

    def test_validate_with_asset(self):
        """Test validate() with asset parameter"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
        )

        result = self.rules.validate(domain=self.domain, asset=asset)

        self.assertIsInstance(result, ValidationResult)

    def test_validate_tenant_mismatch(self):
        """Test validate() with tenant mismatch"""
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

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 4)
        self.assertIn("tenant", result.errors[0].lower())


class DataMeshBusinessRulesAllMethodsTest(TestCase):
    """Test all DataMeshBusinessRules methods comprehensively"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )
        self.rules = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_domain_structure_comprehensive(self):
        """Test validate_domain_structure() comprehensively"""
        # Valid domain
        result = self.rules.validate_domain_structure(self.domain)
        self.assertTrue(result.is_valid)

        # Domain without name
        domain_no_name = DataMeshDomain(tenant=self.tenant, status=DomainStatus.ACTIVE)
        result = self.rules.validate_domain_structure(domain_no_name)
        self.assertFalse(result.is_valid)

        # Domain without tenant
        domain_no_tenant = DataMeshDomain(name="Test", status=DomainStatus.ACTIVE)
        result = self.rules.validate_domain_structure(domain_no_tenant)
        self.assertFalse(result.is_valid)

    def test_validate_ownership_transfer_comprehensive(self):
        """Test validate_ownership_transfer() comprehensively"""
        new_owner = User.objects.create_user(
            email=f"new-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )

        # Valid transfer
        result = self.rules.validate_ownership_transfer(
            self.domain, str(new_owner.id)
        )
        self.assertTrue(result.is_valid)

        # Remove owner
        result = self.rules.validate_ownership_transfer(self.domain, None)
        self.assertTrue(result.is_valid)

        # Invalid user
        invalid_id = str(uuid.uuid4())
        result = self.rules.validate_ownership_transfer(self.domain, invalid_id)
        self.assertFalse(result.is_valid)

    def test_validate_boundaries_comprehensive(self):
        """Test validate_boundaries() comprehensively"""
        # Valid boundaries
        boundaries = {
            "data_products": ["product1"],
            "schemas": ["schema1"],
            "access_patterns": ["pattern1"],
        }
        result = self.rules.validate_boundaries(boundaries)
        self.assertTrue(result.is_valid)

        # None boundaries
        result = self.rules.validate_boundaries(None)
        self.assertTrue(result.is_valid)

        # Invalid type
        result = self.rules.validate_boundaries("not-a-dict")
        self.assertFalse(result.is_valid)

        # Invalid data_products type
        result = self.rules.validate_boundaries({"data_products": "not-a-list"})
        self.assertFalse(result.is_valid)

    def test_validate_domain_boundary_definition_comprehensive(self):
        """Test validate_domain_boundary_definition() comprehensively"""
        # Valid boundaries
        self.domain.boundaries = {"data_products": ["product1"]}
        self.domain.save()

        result = self.rules.validate_domain_boundary_definition(self.domain)
        self.assertTrue(result.is_valid)

        # Overlapping boundaries
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product1"]},  # Overlaps
        )

        result = self.rules.validate_domain_boundary_definition(domain2)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.details["overlaps"]), 1)

    def test_validate_asset_domain_boundary_comprehensive(self):
        """Test validate_asset_domain_boundary() comprehensively"""
        from hub.apps.assets.models import Asset

        # Valid asset-domain match
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            domain="Test Domain",
        )

        result = self.rules.validate_asset_domain_boundary(asset, self.domain)
        self.assertTrue(result.is_valid)

        # Mismatched domain
        asset.domain = "Other Domain"
        asset.save()

        result = self.rules.validate_asset_domain_boundary(asset, self.domain)
        self.assertFalse(result.is_valid)

    def test_validate_cross_domain_access_comprehensive(self):
        """Test validate_cross_domain_access() comprehensively"""
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )

        # Same domain
        result = self.rules.validate_cross_domain_access(
            str(self.user.id), self.domain, self.domain
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["same_domain"])

        # Different domains same tenant
        result = self.rules.validate_cross_domain_access(
            str(self.user.id), self.domain, domain2
        )
        self.assertTrue(result.is_valid)
        self.assertFalse(result.details["same_domain"])

        # Different tenants
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        domain3 = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Domain 3",
            status=DomainStatus.ACTIVE,
        )

        result = self.rules.validate_cross_domain_access(
            str(self.user.id), self.domain, domain3
        )
        self.assertFalse(result.is_valid)

    def test_validate_domain_resource_quota_comprehensive(self):
        """Test validate_domain_resource_quota() comprehensively"""
        # Valid quota
        self.domain.resource_quota = {"storage_gb": 100}
        self.domain.resource_usage = {"storage_gb_used": 50}
        self.domain.save()

        result = self.rules.validate_domain_resource_quota(self.domain)
        self.assertTrue(result.is_valid)

        # Exceeded quota
        self.domain.resource_usage = {"storage_gb_used": 150}
        self.domain.save()

        result = self.rules.validate_domain_resource_quota(self.domain)
        self.assertFalse(result.is_valid)

        # High usage warning
        self.domain.resource_usage = {"storage_gb_used": 95}
        self.domain.save()

        result = self.rules.validate_domain_resource_quota(self.domain)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 1)

    def test_validate_domain_ownership_comprehensive(self):
        """Test validate_domain_ownership() comprehensively"""
        from hub.apps.users.models import Role, UserRole

        # Without TENANT_ADMIN role
        result = self.rules.validate_domain_ownership(self.domain)
        self.assertFalse(result.is_valid)

        # With TENANT_ADMIN role
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        result = self.rules.validate_domain_ownership(self.domain)
        self.assertTrue(result.is_valid)

        # Platform admin
        platform_admin = User.objects.create_user(
            email=f"platform-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
        )

        rules_admin = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(platform_admin.id)
        )

        result = rules_admin.validate_domain_ownership(self.domain)
        self.assertTrue(result.is_valid)

    def test_validate_asset_ownership_transfer_comprehensive(self):
        """Test validate_asset_ownership_transfer() comprehensively"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.users.models import Role, UserRole

        # Create TENANT_ADMIN role
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        # Valid asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
        )

        result = self.rules.validate_asset_ownership_transfer(self.domain, asset)
        self.assertTrue(result.is_valid)

        # Invalid status
        asset.status = AssetStatus.RETIRED
        asset.save()

        result = self.rules.validate_asset_ownership_transfer(self.domain, asset)
        self.assertFalse(result.is_valid)

    def test_validate_policy_conflicts_comprehensive(self):
        """Test validate_policy_conflicts() comprehensively"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # No existing policies
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(self.domain, new_policy)
        self.assertTrue(result.is_valid)

        # Conflicting policies
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Existing Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        PolicyApplication.objects.create(
            domain=self.domain,
            policy=existing_policy,
            status=PolicyApplicationStatus.APPLIED,
        )

        result = self.rules.validate_policy_conflicts(self.domain, new_policy)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.details["conflicts"]), 1)

    def test_validate_policy_compatibility_comprehensive(self):
        """Test validate_policy_compatibility() comprehensively"""
        from hub.apps.governance.models import AccessPolicy

        # Compatible policies
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Policy",
            conditions={"user_roles": ["manager"]},
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_compatibility(self.domain, new_policy)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("compatible", False))

        # Incompatible policies
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Existing Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        PolicyApplication.objects.create(
            domain=self.domain,
            policy=existing_policy,
            status=PolicyApplicationStatus.APPLIED,
        )

        conflicting_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Conflicting Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_compatibility(
            self.domain, conflicting_policy
        )
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get("compatible", True))

    def test_resolve_policy_precedence_comprehensive(self):
        """Test _resolve_policy_precedence() comprehensively"""
        # Existing higher priority
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=50, new_priority=100, existing_source="domain"
        )
        self.assertEqual(precedence["resolution"], "EXISTING_HIGHER")

        # New higher priority
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=100, new_priority=50, existing_source="domain"
        )
        self.assertEqual(precedence["resolution"], "NEW_HIGHER")

        # Same priority, tenant source
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=100, new_priority=100, existing_source="tenant"
        )
        self.assertEqual(precedence["resolution"], "NEW_HIGHER")

        # Same priority, domain source
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=100, new_priority=100, existing_source="domain"
        )
        self.assertEqual(precedence["resolution"], "SAME_PRIORITY")

    def test_check_condition_overlap_detailed_comprehensive(self):
        """Test _check_condition_overlap_detailed() comprehensively"""
        # No overlap
        conditions1 = {"user_roles": ["admin"]}
        conditions2 = {"user_roles": ["user"]}

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)
        self.assertFalse(result["overlaps"])

        # List intersection overlap
        conditions1 = {"user_roles": ["admin", "manager"]}
        conditions2 = {"user_roles": ["admin", "user"]}

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)
        self.assertTrue(result["overlaps"])
        self.assertEqual(len(result["overlapping_keys"]), 1)

        # Exact match
        conditions1 = {"user_roles": ["admin"]}
        conditions2 = {"user_roles": ["admin"]}

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)
        self.assertTrue(result["overlaps"])

        # Nested conditions
        conditions1 = {
            "user": {"user_roles": ["admin"]},
            "resource": {"classification": "CONFIDENTIAL"},
        }
        conditions2 = {
            "user": {"user_roles": ["admin"]},
            "resource": {"classification": "PUBLIC"},
        }

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)
        self.assertTrue(result["overlaps"])

    def test_check_value_overlap_comprehensive(self):
        """Test _check_value_overlap() comprehensively"""
        # List intersection
        result = self.rules._check_value_overlap(["admin", "manager"], ["admin", "user"])
        self.assertTrue(result["overlaps"])
        self.assertEqual(result["type"], "LIST_INTERSECTION")

        # Value in list
        result = self.rules._check_value_overlap(["admin", "manager"], "admin")
        self.assertTrue(result["overlaps"])
        self.assertEqual(result["type"], "VALUE_IN_LIST")

        # Exact match
        result = self.rules._check_value_overlap("admin", "admin")
        self.assertTrue(result["overlaps"])
        self.assertEqual(result["type"], "EXACT_MATCH")

        # No match
        result = self.rules._check_value_overlap("admin", "user")
        self.assertFalse(result["overlaps"])
        self.assertEqual(result["type"], "NO_MATCH")

    def test_conditions_overlap_comprehensive(self):
        """Test _conditions_overlap() comprehensively"""
        # Overlapping conditions
        conditions1 = {"user_roles": ["admin", "manager"]}
        conditions2 = {"user_roles": ["admin", "user"]}

        result = self.rules._conditions_overlap(conditions1, conditions2)
        self.assertTrue(result)

        # Non-overlapping conditions
        conditions1 = {"user_roles": ["admin"]}
        conditions2 = {"user_roles": ["user"]}

        result = self.rules._conditions_overlap(conditions1, conditions2)
        self.assertFalse(result)


class DataMeshBusinessRulesIntegrationTest(TestCase):
    """Test DataMeshBusinessRules integration with base class"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )
        self.rules = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_inherits_from_business_rules(self):
        """Test that DataMeshBusinessRules inherits from BusinessRules"""
        self.assertIsInstance(self.rules, BusinessRules)

    def test_implements_validate_method(self):
        """Test that DataMeshBusinessRules implements validate() method"""
        result = self.rules.validate(domain=self.domain)
        self.assertIsInstance(result, ValidationResult)

    def test_uses_base_class_validation_result(self):
        """Test that DataMeshBusinessRules uses ValidationResult from base class"""
        result = self.rules.validate_domain_structure(self.domain)
        self.assertIsInstance(result, ValidationResult)
        self.assertEqual(type(result).__module__, "hub.apps.core.business_rules.base")

    def test_execute_method_from_base_class(self):
        """Test execute() method from base class"""
        # Set up TENANT_ADMIN role for user
        from hub.apps.users.models import Role, UserRole
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        context = self.rules.create_context(resource=self.domain)
        result = self.rules.execute(context, domain=self.domain)

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_rule_registration(self):
        """Test that DataMeshBusinessRules is registered"""
        registry = get_registry()
        rule_metadata = registry.get_rule("data_mesh_domain_validation")

        self.assertIsNotNone(rule_metadata)
        self.assertEqual(rule_metadata.rule_class, DataMeshBusinessRules)

    def test_compose_method_from_base_class(self):
        """Test compose() method from base class"""
        def rule1(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"rule1": "executed"})

        def rule2(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"rule2": "executed"})

        context = self.rules.create_context(resource=self.domain)
        result = self.rules.compose(rule1, rule2, context=context)

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("rule1", result.details)
        self.assertIn("rule2", result.details)

    def test_compose_with_short_circuit(self):
        """Test compose() with short_circuit=True"""
        def rule1(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=False, errors=["error1"])

        def rule2(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(is_valid=True, details={"rule2": "executed"})

        context = self.rules.create_context(resource=self.domain)
        result = self.rules.compose(rule1, rule2, context=context, short_circuit=True)

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        # rule2 should not have executed due to short circuit
        self.assertNotIn("rule2", result.details)

    def test_create_rule_function_from_base_class(self):
        """Test create_rule_function() from base class"""
        def custom_rule(context: RuleExecutionContext) -> ValidationResult:
            return ValidationResult(
                is_valid=True, details={"rule": "custom", "tenant_id": context.tenant_id}
            )

        rule_func = BusinessRules.create_rule_function(custom_rule, "custom_rule")
        context = self.rules.create_context(resource=self.domain)

        result = rule_func(context)
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("rule", result.details)

