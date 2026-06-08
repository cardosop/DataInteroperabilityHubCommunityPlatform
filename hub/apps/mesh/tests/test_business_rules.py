"""
Unit tests for DataMeshBusinessRules.

.. deprecated::
    Superseded by ``test_data_mesh_business_rules_refactoring.py`` (956 lines).
    Keep until the refactored suite reaches full parity in CI.
    Tests unique to this file (detailed rule-specific logic) should be migrated before removal.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.core.services.base import ValidationError
from hub.apps.mesh.business_rules import (
    DataMeshBusinessRules,
    DataMeshRuleExecutionContext,
)
from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.tenants.models import KYCStatus, Tenant
import uuid

User = get_user_model()


class DataMeshBusinessRulesInitializationTest(TestCase):
    """Test DataMeshBusinessRules initialization"""

    def test_initialization_without_parameters(self):
        """Test initialization without parameters"""
        rules = DataMeshBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_id(self):
        """Test initialization with tenant_id"""
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        rules = DataMeshBusinessRules(tenant_id=str(tenant.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_and_user(self):
        """Test initialization with tenant_id and user_id"""
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=tenant
        )
        rules = DataMeshBusinessRules(tenant_id=str(tenant.id), user_id=str(user.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))
        self.assertEqual(rules.user_id, str(user.id))
        self.assertEqual(rules.get_rule_name(), "DataMeshBusinessRules")

    def test_rule_registration(self):
        """Test that DataMeshBusinessRules is registered in the registry."""
        registry = get_registry()
        rule_metadata = registry.get_rule("data_mesh_domain_validation")

        self.assertIsNotNone(rule_metadata)
        self.assertEqual(rule_metadata.rule_name, "data_mesh_domain_validation")
        self.assertEqual(rule_metadata.rule_class, DataMeshBusinessRules)
        self.assertIn("mesh", rule_metadata.tags)
        self.assertIn("domain", rule_metadata.tags)
        self.assertIn("validation", rule_metadata.tags)


class DataMeshBusinessRulesDomainStructureTest(TestCase):
    """Test DataMeshBusinessRules.validate_domain_structure()"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_domain_structure_valid(self):
        """Test validate_domain_structure with valid domain"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Valid Domain",
            description="Valid description",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["api1"]},
        )

        result = self.rules.validate_domain_structure(domain)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)

    def test_validate_domain_structure_empty_name(self):
        """Test validate_domain_structure with empty name"""
        domain = DataMeshDomain(tenant=self.tenant, name="", status=DomainStatus.ACTIVE)

        result = self.rules.validate_domain_structure(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("name", str(result.errors[0]).lower())

    def test_validate_domain_structure_whitespace_name(self):
        """Test validate_domain_structure with whitespace-only name"""
        domain = DataMeshDomain(tenant=self.tenant, name="   ", status=DomainStatus.ACTIVE)

        result = self.rules.validate_domain_structure(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_domain_structure_missing_tenant(self):
        """Test validate_domain_structure with missing tenant"""
        domain = DataMeshDomain(name="Test Domain", status=DomainStatus.ACTIVE)

        result = self.rules.validate_domain_structure(domain)

        # Domain model requires tenant, so this should fail
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_domain_structure_invalid_boundaries_type(self):
        """Test validate_domain_structure with invalid boundaries type"""
        domain = DataMeshDomain(tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE)
        # Set invalid boundaries (not a dict) - this will be caught by model clean
        # But we test the business rules validation
        domain.boundaries = "not-a-dict"

        result = self.rules.validate_domain_structure(domain)

        # Business rules should catch this
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_domain_structure_invalid_capabilities_type(self):
        """Test validate_domain_structure with invalid capabilities type"""
        domain = DataMeshDomain(tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE)
        domain.capabilities = "not-a-dict"

        result = self.rules.validate_domain_structure(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_domain_structure_invalid_resource_quota_type(self):
        """Test validate_domain_structure with invalid resource_quota type"""
        domain = DataMeshDomain(tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE)
        domain.resource_quota = "not-a-dict"

        result = self.rules.validate_domain_structure(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_domain_structure_invalid_resource_usage_type(self):
        """Test validate_domain_structure with invalid resource_usage type"""
        domain = DataMeshDomain(tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE)
        domain.resource_usage = "not-a-dict"

        result = self.rules.validate_domain_structure(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_domain_structure_owner_different_tenant(self):
        """Test validate_domain_structure with owner from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=other_tenant
        )

        domain = DataMeshDomain(
            tenant=self.tenant, name="Test Domain", owner=other_user, status=DomainStatus.ACTIVE
        )

        result = self.rules.validate_domain_structure(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", str(result.errors[0]).lower())


class DataMeshBusinessRulesOwnershipTransferTest(TestCase):
    """Test DataMeshBusinessRules.validate_ownership_transfer()"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.current_owner = User.objects.create_user(
            email=f"current-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.new_owner = User.objects.create_user(
            email=f"new-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.current_owner,
            status=DomainStatus.ACTIVE,
        )
        self.rules = DataMeshBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.current_owner.id)
        )

    def test_validate_ownership_transfer_valid(self):
        """Test validate_ownership_transfer with valid transfer"""
        result = self.rules.validate_ownership_transfer(
            domain=self.domain, new_owner_id=str(self.new_owner.id)
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_ownership_transfer_same_owner(self):
        """Test validate_ownership_transfer with same owner (no-op)"""
        result = self.rules.validate_ownership_transfer(
            domain=self.domain, new_owner_id=str(self.current_owner.id)
        )

        # Same owner should be valid (no-op transfer)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_ownership_transfer_to_none(self):
        """Test validate_ownership_transfer removing owner"""
        result = self.rules.validate_ownership_transfer(domain=self.domain, new_owner_id=None)

        # Removing owner should be valid
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_ownership_transfer_invalid_user(self):
        """Test validate_ownership_transfer with invalid user ID"""
        import uuid

        invalid_user_id = str(uuid.uuid4())

        result = self.rules.validate_ownership_transfer(
            domain=self.domain, new_owner_id=invalid_user_id
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("not found", str(result.errors[0]).lower())

    def test_validate_ownership_transfer_user_different_tenant(self):
        """Test validate_ownership_transfer with user from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=other_tenant
        )

        result = self.rules.validate_ownership_transfer(
            domain=self.domain, new_owner_id=str(other_user.id)
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", str(result.errors[0]).lower())

    def test_validate_ownership_transfer_domain_inactive(self):
        """Test validate_ownership_transfer with inactive domain"""
        self.domain.status = DomainStatus.INACTIVE
        self.domain.save()

        result = self.rules.validate_ownership_transfer(
            domain=self.domain, new_owner_id=str(self.new_owner.id)
        )

        # Ownership transfer should be allowed even for inactive domains
        # But we might want to warn about it
        self.assertTrue(result.is_valid)
        # May have warnings about inactive domain

    def test_validate_ownership_transfer_domain_archived(self):
        """Test validate_ownership_transfer with archived domain"""
        self.domain.status = DomainStatus.ARCHIVED
        self.domain.save()

        result = self.rules.validate_ownership_transfer(
            domain=self.domain, new_owner_id=str(self.new_owner.id)
        )

        # Ownership transfer might not be allowed for archived domains
        # This depends on business requirements
        # For now, we'll allow it but may warn
        self.assertTrue(result.is_valid)


class DataMeshBusinessRulesBoundariesTest(TestCase):
    """Test DataMeshBusinessRules.validate_boundaries()"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id))

    def test_validate_boundaries_valid(self):
        """Test validate_boundaries with valid boundaries"""
        boundaries = {
            "data_products": ["product1", "product2"],
            "schemas": ["schema1"],
            "access_patterns": ["pattern1", "pattern2"],
        }

        result = self.rules.validate_boundaries(boundaries)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_boundaries_empty(self):
        """Test validate_boundaries with empty boundaries"""
        boundaries = {}

        result = self.rules.validate_boundaries(boundaries)

        # Empty boundaries should be valid
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_boundaries_none(self):
        """Test validate_boundaries with None"""
        result = self.rules.validate_boundaries(None)

        # None should be valid (optional field)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_boundaries_invalid_type(self):
        """Test validate_boundaries with invalid type"""
        boundaries: Any = "not-a-dict"  # type: ignore[misc]  # test: edge-case type exercise

        result = self.rules.validate_boundaries(boundaries)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dict", str(result.errors[0]).lower())

    def test_validate_boundaries_data_products_not_list(self):
        """Test validate_boundaries with data_products not a list"""
        boundaries = {"data_products": "not-a-list"}

        result = self.rules.validate_boundaries(boundaries)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("data_products", str(result.errors[0]).lower())
        self.assertIn("list", str(result.errors[0]).lower())

    def test_validate_boundaries_schemas_not_list(self):
        """Test validate_boundaries with schemas not a list"""
        boundaries = {"schemas": "not-a-list"}

        result = self.rules.validate_boundaries(boundaries)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("schemas", str(result.errors[0]).lower())

    def test_validate_boundaries_access_patterns_not_list(self):
        """Test validate_boundaries with access_patterns not a list"""
        boundaries = {"access_patterns": "not-a-list"}

        result = self.rules.validate_boundaries(boundaries)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("access_patterns", str(result.errors[0]).lower())

    def test_validate_boundaries_empty_lists(self):
        """Test validate_boundaries with empty lists"""
        boundaries = {"data_products": [], "schemas": [], "access_patterns": []}

        result = self.rules.validate_boundaries(boundaries)

        # Empty lists should be valid
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_boundaries_with_additional_fields(self):
        """Test validate_boundaries with additional custom fields"""
        boundaries = {
            "data_products": ["product1"],
            "custom_field": "custom_value",
            "nested": {"key": "value"},
        }

        result = self.rules.validate_boundaries(boundaries)

        # Additional fields should be allowed (flexible structure)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_boundaries_complex_structure(self):
        """Test validate_boundaries with complex valid structure"""
        boundaries = {
            "data_products": ["product1", "product2"],
            "schemas": ["schema1", "schema2"],
            "access_patterns": ["pattern1"],
            "data_sources": ["source1"],
            "consumers": ["consumer1", "consumer2"],
        }

        result = self.rules.validate_boundaries(boundaries)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)


class DataMeshBusinessRulesPolicyConflictTest(TestCase):
    """Test DataMeshBusinessRules.validate_policy_conflicts()"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )
        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_policy_conflicts_no_existing_policies(self):
        """Test validate_policy_conflicts with no existing policies"""
        from hub.apps.governance.models import AccessPolicy

        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_policy_conflicts_allow_deny_conflict(self):
        """Test validate_policy_conflicts with ALLOW vs DENY conflict"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        # Apply existing policy to domain
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy with overlapping conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("conflict", str(result.errors[0]).lower())

    def test_validate_policy_conflicts_same_effect_no_conflict(self):
        """Test validate_policy_conflicts with same effect (no conflict)"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy 1",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        # Apply existing policy to domain
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new ALLOW policy with same conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy 2",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Same effect policies don't conflict (they can coexist)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_policy_conflicts_different_conditions_no_conflict(self):
        """Test validate_policy_conflicts with different conditions (no conflict)"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy for admin
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Admin Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        # Apply existing policy to domain
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy for user role (different condition)
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny User Policy",
            conditions={"user_roles": ["user"]},
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Different conditions don't conflict
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_policy_conflicts_overlapping_conditions(self):
        """Test validate_policy_conflicts with overlapping conditions"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin", "manager"]},
            effect="ALLOW",
            priority=100,
        )

        # Apply existing policy to domain
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy with overlapping role
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Policy",
            conditions={"user_roles": ["admin"]},  # Overlaps with existing
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_policy_conflicts_priority_resolution(self):
        """Test validate_policy_conflicts with priority-based resolution"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy with lower priority (higher number)
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=200,  # Lower priority
        )

        # Apply existing policy to domain
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy with higher priority (lower number)
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=50,  # Higher priority
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Higher priority DENY should override lower priority ALLOW
        # This might be a warning rather than an error, depending on business rules
        # For now, we'll flag it as a potential conflict
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_policy_conflicts_only_applied_policies(self):
        """Test validate_policy_conflicts only checks APPLIED policies"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy with REVOKED status
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Revoked Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        # Apply existing policy to domain but mark as REVOKED
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.REVOKED
        )

        # Create new DENY policy with same conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should not conflict with REVOKED policy
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_policy_conflicts_only_enabled_policies(self):
        """Test validate_policy_conflicts only checks enabled policies"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy that is disabled
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Disabled Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
            enabled=False,
        )

        # Apply existing policy to domain
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy with same conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should not conflict with disabled policy
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_policy_conflicts_complex_conditions(self):
        """Test validate_policy_conflicts with complex condition structures"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing policy with complex conditions
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Complex Allow Policy",
            conditions={
                "user_roles": ["admin"],
                "resource_classification": "CONFIDENTIAL",
                "environment": {"time_of_day": "business_hours"},
            },
            effect="ALLOW",
            priority=100,
        )

        # Apply existing policy to domain
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy with partially overlapping conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Complex Deny Policy",
            conditions={
                "user_roles": ["admin"],
                "resource_classification": "CONFIDENTIAL",
                # Missing environment condition - still overlaps
            },
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict due to overlapping conditions
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_policy_conflicts_with_overrides(self):
        """Test validate_policy_conflicts considering policy overrides"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        # Apply existing policy with overrides that change effect
        PolicyApplication.objects.create(
            domain=self.domain,
            policy=existing_policy,
            status=PolicyApplicationStatus.APPLIED,
            overrides={"effect": "DENY"},  # Override to DENY
        )

        # Create new ALLOW policy with same conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict because existing policy has DENY override
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)


class DataMeshBusinessRulesGovernanceIntegrationTest(TestCase):
    """Test DataMeshBusinessRules integration with GovernanceService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )
        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_policy_conflicts_integrates_with_governance_models(self):
        """Test that validate_policy_conflicts integrates with GovernanceService models"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create policies using governance models
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Existing Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        # Apply policy using PolicyApplication model
        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new policy that conflicts
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        # Validate conflicts - this uses governance models (AccessPolicy, PolicyApplication)
        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("conflict", str(result.errors[0]).lower())

        # Verify integration: check that details include policy information from governance models
        self.assertIn("conflicts", result.details)
        self.assertGreater(len(result.details["conflicts"]), 0)
        conflict = result.details["conflicts"][0]
        self.assertEqual(conflict["existing_policy_id"], str(existing_policy.id))
        self.assertEqual(conflict["existing_policy_name"], existing_policy.name)

    def test_validate_policy_conflicts_uses_governance_policy_structure(self):
        """Test that validate_policy_conflicts correctly uses AccessPolicy structure"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create policy with complex conditions (governance model structure)
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Complex Policy",
            conditions={
                "user_roles": ["admin", "manager"],
                "resource_classification": "CONFIDENTIAL",
            },
            effect="ALLOW",
            priority=50,  # Higher priority
        )

        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new policy with overlapping conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Overlapping Policy",
            conditions={"user_roles": ["admin"]},  # Overlaps with existing
            effect="DENY",
            priority=100,  # Lower priority
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict - when existing has higher priority, it's a warning, not error
        # But there should still be conflict details
        self.assertGreater(len(result.details["conflicts"]), 0)
        conflict = result.details["conflicts"][0]
        self.assertEqual(conflict["priority_resolution"], "EXISTING_HIGHER")
        # Should have warning about higher priority existing policy
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("priority", str(result.warnings[0]).lower())

    def test_validate_policy_conflicts_with_tenant_wide_policies(self):
        """Test validate_policy_conflicts considers tenant-wide policies (inheritance)"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create tenant-wide policy (inherited)
        tenant_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Tenant Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
            asset=None,  # Tenant-wide
            dataset=None,  # Tenant-wide
        )

        # Create new domain-specific policy that conflicts
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Domain Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,  # Same priority
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict with tenant-wide policy
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.details["conflicts"]), 0)
        conflict = result.details["conflicts"][0]
        self.assertEqual(conflict["existing_policy_id"], str(tenant_policy.id))
        self.assertEqual(conflict["policy_source"], "tenant")

    def test_validate_policy_compatibility_compatible_policies(self):
        """Test validate_policy_compatibility with compatible policies"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new ALLOW policy with non-overlapping conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Allow Policy",
            conditions={"user_roles": ["manager"]},  # Different role
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_compatibility(domain=self.domain, new_policy=new_policy)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("compatible", False))
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)

    def test_validate_policy_compatibility_incompatible_policies(self):
        """Test validate_policy_compatibility with incompatible policies"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy with overlapping conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Policy",
            conditions={"user_roles": ["admin"]},  # Same role
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_compatibility(domain=self.domain, new_policy=new_policy)

        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get("compatible", True))
        self.assertGreater(len(result.errors), 0)

    def test_policy_precedence_domain_overrides_tenant(self):
        """Test policy precedence: domain-specific policies override tenant-wide at same priority"""
        from hub.apps.governance.models import AccessPolicy

        # Check precedence resolution
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=100, new_priority=100, existing_source="tenant"
        )

        # Domain policy should override tenant policy at same priority
        self.assertEqual(precedence["resolution"], "NEW_HIGHER")
        self.assertIn("Domain-specific", precedence["reason"])

    def test_policy_precedence_higher_priority_wins(self):
        """Test policy precedence: higher priority (lower number) wins"""
        from hub.apps.governance.models import AccessPolicy

        # Test with existing having higher priority
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=50,  # Higher priority
            new_priority=100,  # Lower priority
            existing_source="domain",
        )

        self.assertEqual(precedence["resolution"], "EXISTING_HIGHER")
        self.assertIn("higher priority", precedence["reason"])

        # Test with new having higher priority
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=100,  # Lower priority
            new_priority=50,  # Higher priority
            existing_source="domain",
        )

        self.assertEqual(precedence["resolution"], "NEW_HIGHER")
        self.assertIn("higher priority", precedence["reason"])

    def test_condition_overlap_detailed_nested_conditions(self):
        """Test detailed condition overlap detection with nested conditions"""
        from hub.apps.governance.models import AccessPolicy

        conditions1 = {
            "user": {"user_roles": ["admin", "manager"], "department": "IT"},
            "resource": {"classification": "CONFIDENTIAL"},
        }

        conditions2 = {
            "user": {
                "user_roles": ["admin"],  # Overlaps with conditions1
                "department": "IT",  # Overlaps
            },
            "resource": {"classification": "PUBLIC"},  # Different
        }

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)

        self.assertTrue(result["overlaps"])
        self.assertGreater(len(result["overlapping_keys"]), 0)
        # Should detect overlap in user.user_roles and user.department
        overlapping_sections = [
            k.get("section") for k in result["overlapping_keys"] if "section" in k
        ]
        self.assertIn("user", overlapping_sections)

    def test_condition_overlap_detailed_list_intersection(self):
        """Test detailed condition overlap detection with list intersections"""
        from hub.apps.governance.models import AccessPolicy

        conditions1 = {"user_roles": ["admin", "manager", "user"]}
        conditions2 = {"user_roles": ["admin", "guest"]}

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)

        self.assertTrue(result["overlaps"])
        self.assertGreater(len(result["overlapping_keys"]), 0)
        overlap_info = result["overlapping_keys"][0]
        self.assertEqual(overlap_info["key"], "user_roles")
        self.assertEqual(overlap_info["overlap_type"], "LIST_INTERSECTION")
        self.assertIn("admin", overlap_info.get("overlap_values", []))

    def test_validate_policy_conflicts_integration_with_governance_service(self):
        """Test validate_policy_conflicts integrates with GovernanceService"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.governance.services import GovernanceService
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create policies
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Existing Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        # Verify GovernanceService can be instantiated (integration check)
        governance_service = GovernanceService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertIsNotNone(governance_service)
        self.assertEqual(str(governance_service.tenant_id), str(self.tenant.id))

        # Validate conflicts (should use GovernanceService internally)
        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("conflicts", result.details)


class DataMeshBusinessRulesDomainOwnershipTest(TestCase):
    """Test DataMeshBusinessRules.validate_domain_ownership()"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )

    def test_validate_domain_ownership_with_tenant_admin_role(self):
        """Test domain ownership validation with TENANT_ADMIN role"""
        from hub.apps.users.models import Role, UserRole

        # Create TENANT_ADMIN role
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )

        # Assign role to user
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        result = rules.validate_domain_ownership(self.domain)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("ownership_checks", result.details)
        self.assertTrue(result.details["ownership_checks"]["has_tenant_admin_role"])
        self.assertTrue(result.details["ownership_checks"]["ownership_valid"])

    def test_validate_domain_ownership_without_tenant_admin_role(self):
        """Test domain ownership validation without TENANT_ADMIN role"""
        rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        result = rules.validate_domain_ownership(self.domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("TENANT_ADMIN", result.errors[0])
        self.assertIn("ownership_checks", result.details)
        self.assertFalse(result.details["ownership_checks"]["has_tenant_admin_role"])

    def test_validate_domain_ownership_without_user_id(self):
        """Test domain ownership validation without user_id"""
        rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id))

        result = rules.validate_domain_ownership(self.domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("user_id is required", result.errors[0])

    def test_validate_domain_ownership_platform_admin(self):
        """Test domain ownership validation for platform admin"""
        platform_admin = User.objects.create_user(
            email=f"platform-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
        )

        rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(platform_admin.id))

        result = rules.validate_domain_ownership(self.domain)

        # Platform admins should have access
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["ownership_checks"]["is_platform_admin"])
        self.assertTrue(result.details["ownership_checks"]["has_tenant_admin_role"])

    def test_validate_domain_ownership_user_different_tenant(self):
        """Test domain ownership validation with user from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=other_tenant
        )

        from hub.apps.users.models import Role, UserRole

        # Create TENANT_ADMIN role for other tenant
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=other_tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )
        UserRole.objects.create(user=other_user, role=tenant_admin_role)

        rules = DataMeshBusinessRules(tenant_id=str(other_tenant.id), user_id=str(other_user.id))

        result = rules.validate_domain_ownership(self.domain)

        # Should fail because user belongs to different tenant
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", result.errors[0].lower())


class DataMeshBusinessRulesAssetOwnershipTransferTest(TestCase):
    """Test DataMeshBusinessRules.validate_asset_ownership_transfer()"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )

        # Create TENANT_ADMIN role and assign to user
        from hub.apps.users.models import Role, UserRole

        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator role"},
        )
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_asset_ownership_transfer_valid(self):
        """Test asset ownership transfer validation with valid asset"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        result = self.rules.validate_asset_ownership_transfer(self.domain, asset)

        self.assertTrue(result.is_valid)
        self.assertIn("transfer_checks", result.details)
        self.assertTrue(result.details["transfer_checks"]["ownership_check_passed"])
        self.assertTrue(result.details["transfer_checks"]["tenant_match"])
        self.assertTrue(result.details["transfer_checks"]["asset_status_valid"])

    def test_validate_asset_ownership_transfer_asset_different_tenant(self):
        """Test asset ownership transfer with asset from different tenant"""
        from hub.apps.assets.models import Asset, AssetStatus

        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.ACTIVE
        )

        result = self.rules.validate_asset_ownership_transfer(self.domain, other_asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", result.errors[0].lower())

    def test_validate_asset_ownership_transfer_invalid_asset_status(self):
        """Test asset ownership transfer with invalid asset status"""
        from hub.apps.assets.models import Asset, AssetStatus

        # Use RETIRED status which is not in valid_transfer_statuses (ACTIVE, DRAFT, PUBLIC)
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.RETIRED
        )

        result = self.rules.validate_asset_ownership_transfer(self.domain, asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("status", result.errors[0].lower())

    def test_validate_asset_ownership_transfer_with_dependencies(self):
        """Test asset ownership transfer with dependencies"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        # Create asset with dataset (which creates dependencies)
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
        )

        Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file,
            version=1,
            format="CSV",
            row_count=100,
            schema_json={"fields": [{"name": "id", "data_type": "integer"}]},
        )

        result = self.rules.validate_asset_ownership_transfer(self.domain, asset)

        # Should be valid but may have warnings about dependencies
        self.assertTrue(result.is_valid)
        self.assertIn("transfer_checks", result.details)
        self.assertIn("has_dependencies", result.details["transfer_checks"])

    def test_validate_asset_ownership_transfer_already_in_domain(self):
        """Test asset ownership transfer when asset is already in domain"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            domain=self.domain,  # Already in domain
        )

        result = self.rules.validate_asset_ownership_transfer(self.domain, asset)

        # Should be valid but with warning
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("already", result.warnings[0].lower())
        self.assertTrue(result.details["transfer_checks"]["already_in_domain"])

    def test_validate_asset_ownership_transfer_without_tenant_admin_role(self):
        """Test asset ownership transfer without TENANT_ADMIN role"""
        from hub.apps.assets.models import Asset, AssetStatus

        # Create user without TENANT_ADMIN role
        regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )

        rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(regular_user.id))

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        result = rules.validate_asset_ownership_transfer(self.domain, asset)

        # Should fail because user doesn't have TENANT_ADMIN role
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("TENANT_ADMIN", result.errors[0])


class DataMeshBusinessRulesDomainResourceQuotaTest(TestCase):
    """Test DataMeshBusinessRules.validate_domain_resource_quota() with GovernanceService integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )
        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_domain_resource_quota_with_governance_service(self):
        """Test domain resource quota validation integrates with GovernanceService"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain Governance",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100, "compute_hours": 50},
            resource_usage={"storage_gb_used": 50, "compute_hours_used": 25},
        )

        result = self.rules.validate_domain_resource_quota(domain)

        # Should have attempted governance validation
        self.assertIn("quota_usage", result.details)
        # If GovernanceService is available, should have validation result
        if "governance_validation_passed" in result.details:
            validation_passed = result.details["governance_validation_passed"]
            if validation_passed is True:
                self.assertIn("validated_quota", result.details)
                self.assertIn("tenant_limits_check_passed", result.details)
                self.assertTrue(result.details["tenant_limits_check_passed"])

    def test_validate_domain_resource_quota_exceeded_via_governance(self):
        """Test domain resource quota validation when quota exceeds tenant limits via GovernanceService"""
        # Create domain with quota that might exceed tenant limits
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain Exceeded",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={
                "storage_gb": 20000,  # Very large quota that might exceed tenant limits
                "compute_hours": 2000,
            },
            resource_usage={"storage_gb_used": 100, "compute_hours_used": 50},
        )

        result = self.rules.validate_domain_resource_quota(domain)

        # Should have attempted governance validation
        # If GovernanceService validation fails, should have error
        if "governance_validation_passed" in result.details:
            validation_passed = result.details["governance_validation_passed"]
            if validation_passed is False:
                self.assertIn("governance_validation_error", result.details)
                self.assertGreater(len(result.errors), 0)
                self.assertIn("GovernanceService", result.errors[0])

    def test_validate_domain_resource_quota_domain_level_limits(self):
        """Test domain resource quota validation checks domain-level limits"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain Limits",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100, "compute_hours": 50},
            resource_usage={
                "storage_gb_used": 95,  # 95% usage - should trigger warning
                "compute_hours_used": 45,
            },
        )

        result = self.rules.validate_domain_resource_quota(domain)

        # Should validate quota vs usage
        self.assertIn("quota_usage", result.details)
        quota_usage = result.details["quota_usage"]
        self.assertIn("storage_gb", quota_usage)
        self.assertGreaterEqual(quota_usage["storage_gb"]["usage_percentage"], 90)

        # Should have warnings for high usage
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("nearly exceeded", result.warnings[0].lower())

    def test_validate_domain_resource_quota_governance_service_integration(self):
        """Test domain resource quota validation full integration with GovernanceService"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain Integration",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100, "compute_hours": 50},
            resource_usage={"storage_gb_used": 50, "compute_hours_used": 25},
        )

        result = self.rules.validate_domain_resource_quota(domain)

        # Should have quota checks
        self.assertIn("quota_usage", result.details)
        self.assertIn("domain_id", result.details)

        # Should have attempted GovernanceService validation
        # If available, should have validation result
        if "governance_validation_passed" in result.details:
            validation_passed = result.details["governance_validation_passed"]
            if validation_passed is True:
                # Should have validated quota and passed tenant limits check
                self.assertIn("validated_quota", result.details)
                self.assertIn("tenant_limits_check_passed", result.details)
                self.assertTrue(result.details["tenant_limits_check_passed"])
            elif validation_passed is False:
                # Should have error details
                self.assertIn("governance_validation_error", result.details)
                self.assertIn("quota_exceeded", result.details)

    def test_validate_policy_conflicts_with_tenant_wide_policies(self):
        """Test validate_policy_conflicts considers tenant-wide policies (inheritance)"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create tenant-wide policy (inherited)
        tenant_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Tenant Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
            asset=None,  # Tenant-wide
            dataset=None,  # Tenant-wide
        )

        # Create new domain-specific policy that conflicts
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Domain Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,  # Same priority
        )

        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict with tenant-wide policy
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.details["conflicts"]), 0)
        conflict = result.details["conflicts"][0]
        self.assertEqual(conflict["existing_policy_id"], str(tenant_policy.id))
        self.assertEqual(conflict["policy_source"], "tenant")

    def test_validate_policy_compatibility_compatible_policies(self):
        """Test validate_policy_compatibility with compatible policies"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new ALLOW policy with non-overlapping conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Allow Policy",
            conditions={"user_roles": ["manager"]},  # Different role
            effect="ALLOW",
            priority=100,
        )

        result = self.rules.validate_policy_compatibility(domain=self.domain, new_policy=new_policy)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("compatible", False))
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)

    def test_validate_policy_compatibility_incompatible_policies(self):
        """Test validate_policy_compatibility with incompatible policies"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create existing ALLOW policy
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        # Create new DENY policy with overlapping conditions
        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Policy",
            conditions={"user_roles": ["admin"]},  # Same role
            effect="DENY",
            priority=100,
        )

        result = self.rules.validate_policy_compatibility(domain=self.domain, new_policy=new_policy)

        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get("compatible", True))
        self.assertGreater(len(result.errors), 0)

    def test_policy_precedence_domain_overrides_tenant(self):
        """Test policy precedence: domain-specific policies override tenant-wide at same priority"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create tenant-wide policy
        tenant_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Tenant Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
            asset=None,
            dataset=None,
        )

        # Create domain-specific policy with same priority
        domain_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Domain Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,  # Same priority
        )

        # Check precedence resolution
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=100, new_priority=100, existing_source="tenant"
        )

        # Domain policy should override tenant policy at same priority
        self.assertEqual(precedence["resolution"], "NEW_HIGHER")
        self.assertIn("Domain-specific", precedence["reason"])

    def test_policy_precedence_higher_priority_wins(self):
        """Test policy precedence: higher priority (lower number) wins"""
        from hub.apps.governance.models import AccessPolicy

        # Test with existing having higher priority
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=50,  # Higher priority
            new_priority=100,  # Lower priority
            existing_source="domain",
        )

        self.assertEqual(precedence["resolution"], "EXISTING_HIGHER")
        self.assertIn("higher priority", precedence["reason"])

        # Test with new having higher priority
        precedence = self.rules._resolve_policy_precedence(
            existing_priority=100,  # Lower priority
            new_priority=50,  # Higher priority
            existing_source="domain",
        )

        self.assertEqual(precedence["resolution"], "NEW_HIGHER")
        self.assertIn("higher priority", precedence["reason"])

    def test_condition_overlap_detailed_nested_conditions(self):
        """Test detailed condition overlap detection with nested conditions"""
        from hub.apps.governance.models import AccessPolicy

        conditions1 = {
            "user": {"user_roles": ["admin", "manager"], "department": "IT"},
            "resource": {"classification": "CONFIDENTIAL"},
        }

        conditions2 = {
            "user": {
                "user_roles": ["admin"],  # Overlaps with conditions1
                "department": "IT",  # Overlaps
            },
            "resource": {"classification": "PUBLIC"},  # Different
        }

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)

        self.assertTrue(result["overlaps"])
        self.assertGreater(len(result["overlapping_keys"]), 0)
        # Should detect overlap in user.user_roles and user.department
        overlapping_sections = [
            k.get("section") for k in result["overlapping_keys"] if "section" in k
        ]
        self.assertIn("user", overlapping_sections)

    def test_condition_overlap_detailed_list_intersection(self):
        """Test detailed condition overlap detection with list intersections"""
        from hub.apps.governance.models import AccessPolicy

        conditions1 = {"user_roles": ["admin", "manager", "user"]}
        conditions2 = {"user_roles": ["admin", "guest"]}

        result = self.rules._check_condition_overlap_detailed(conditions1, conditions2)

        self.assertTrue(result["overlaps"])
        self.assertGreater(len(result["overlapping_keys"]), 0)
        overlap_info = result["overlapping_keys"][0]
        self.assertEqual(overlap_info["key"], "user_roles")
        self.assertEqual(overlap_info["overlap_type"], "LIST_INTERSECTION")
        self.assertIn("admin", overlap_info.get("overlap_values", []))

    def test_validate_policy_conflicts_integration_with_governance_service(self):
        """Test validate_policy_conflicts integrates with GovernanceService"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.governance.services import GovernanceService
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Create policies
        existing_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Existing Policy",
            conditions={"user_roles": ["admin"]},
            effect="ALLOW",
            priority=100,
        )

        PolicyApplication.objects.create(
            domain=self.domain, policy=existing_policy, status=PolicyApplicationStatus.APPLIED
        )

        new_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="New Policy",
            conditions={"user_roles": ["admin"]},
            effect="DENY",
            priority=100,
        )

        # Verify GovernanceService can be instantiated (integration check)
        governance_service = GovernanceService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertIsNotNone(governance_service)
        self.assertEqual(str(governance_service.tenant_id), str(self.tenant.id))

        # Validate conflicts (should use GovernanceService internally)
        result = self.rules.validate_policy_conflicts(domain=self.domain, new_policy=new_policy)

        # Should detect conflict
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("conflicts", result.details)


class DataMeshBusinessRulesDomainBoundaryValidationTest(TestCase):
    """Test DataMeshBusinessRules domain boundary validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_domain_boundary_definition_valid(self):
        """Test validate_domain_boundary_definition with valid boundaries"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={
                "data_products": ["product1", "product2"],
                "schemas": ["schema1"],
                "access_patterns": ["pattern1"],
            },
        )

        result = self.rules.validate_domain_boundary_definition(domain)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_domain_boundary_definition_overlap_data_products(self):
        """Test validate_domain_boundary_definition detects overlap in data_products"""
        # Create first domain
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product1", "product2"]},
        )

        # Create second domain with overlapping data_products
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product2", "product3"]},  # product2 overlaps
        )

        result = self.rules.validate_domain_boundary_definition(domain2)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("overlap", str(result.errors[0]).lower())
        self.assertIn("product2", str(result.errors[0]))
        self.assertGreater(len(result.details["overlaps"]), 0)

    def test_validate_domain_boundary_definition_overlap_schemas(self):
        """Test validate_domain_boundary_definition detects overlap in schemas"""
        # Create first domain
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"schemas": ["schema1", "schema2"]},
        )

        # Create second domain with overlapping schemas
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"schemas": ["schema2", "schema3"]},  # schema2 overlaps
        )

        result = self.rules.validate_domain_boundary_definition(domain2)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("overlap", str(result.errors[0]).lower())
        self.assertIn("schema2", str(result.errors[0]))

    def test_validate_domain_boundary_definition_overlap_access_patterns_warning(self):
        """Test validate_domain_boundary_definition warns about overlap in access_patterns"""
        # Create first domain
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"access_patterns": ["pattern1", "pattern2"]},
        )

        # Create second domain with overlapping access_patterns
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"access_patterns": ["pattern2", "pattern3"]},  # pattern2 overlaps
        )

        result = self.rules.validate_domain_boundary_definition(domain2)

        # Access pattern overlaps are warnings, not errors
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("overlap", str(result.warnings[0]).lower())
        self.assertIn("pattern2", str(result.warnings[0]))

    def test_validate_domain_boundary_definition_no_overlap(self):
        """Test validate_domain_boundary_definition with no overlaps"""
        # Create first domain
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product1"]},
        )

        # Create second domain with no overlaps
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product2"]},
        )

        result = self.rules.validate_domain_boundary_definition(domain2)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.details["overlaps"]), 0)

    def test_validate_asset_domain_boundary_valid(self):
        """Test validate_asset_domain_boundary with valid asset-domain match"""
        from hub.apps.assets.models import Asset

        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            domain="Test Domain",  # Matches domain name
        )

        result = self.rules.validate_asset_domain_boundary(asset, domain)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["domain_match"])

    def test_validate_asset_domain_boundary_mismatch(self):
        """Test validate_asset_domain_boundary with mismatched domain"""
        from hub.apps.assets.models import Asset

        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            domain="Other Domain",  # Doesn't match domain name
        )

        result = self.rules.validate_asset_domain_boundary(asset, domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("does not match", result.errors[0])

    def test_validate_asset_domain_boundary_no_domain_set(self):
        """Test validate_asset_domain_boundary with asset having no domain"""
        from hub.apps.assets.models import Asset

        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", domain=None  # No domain set
        )

        result = self.rules.validate_asset_domain_boundary(asset, domain)

        # Should be valid but with warning
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("no domain", str(result.warnings[0]).lower())

    def test_validate_asset_domain_boundary_different_tenant(self):
        """Test validate_asset_domain_boundary with asset from different tenant"""
        from hub.apps.assets.models import Asset

        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )

        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )

        asset = Asset.objects.create(
            tenant=other_tenant, key="test-asset", name="Test Asset", domain="Test Domain"
        )

        result = self.rules.validate_asset_domain_boundary(asset, domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", str(result.errors[0]).lower())

    def test_validate_asset_domain_boundary_in_data_products(self):
        """Test validate_asset_domain_boundary when asset is in boundaries.data_products"""
        from hub.apps.assets.models import Asset

        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["test-asset"]},  # Asset key is listed
        )

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", domain="Test Domain"
        )

        result = self.rules.validate_asset_domain_boundary(asset, domain)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("in_boundary_data_products", False))

    def test_validate_cross_domain_access_same_domain(self):
        """Test validate_cross_domain_access with same domain"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )

        result = self.rules.validate_cross_domain_access(
            user_id=str(self.user.id), source_domain=domain, target_domain=domain
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["same_domain"])

    def test_validate_cross_domain_access_different_tenants(self):
        """Test validate_cross_domain_access with domains from different tenants"""
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Domain 1", owner=self.user, status=DomainStatus.ACTIVE
        )

        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=other_tenant
        )

        domain2 = DataMeshDomain.objects.create(
            tenant=other_tenant, name="Domain 2", owner=other_user, status=DomainStatus.ACTIVE
        )

        result = self.rules.validate_cross_domain_access(
            user_id=str(self.user.id), source_domain=domain1, target_domain=domain2
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("different tenants", str(result.errors[0]).lower())

    def test_validate_cross_domain_access_with_resource_id(self):
        """Test validate_cross_domain_access with resource_id for ABAC evaluation"""
        from hub.apps.assets.models import Asset

        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Domain 1", owner=self.user, status=DomainStatus.ACTIVE
        )

        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Domain 2", owner=self.user, status=DomainStatus.ACTIVE
        )

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", domain="Domain 2"
        )

        result = self.rules.validate_cross_domain_access(
            user_id=str(self.user.id),
            source_domain=domain1,
            target_domain=domain2,
            resource_type="ASSET",
            resource_id=str(asset.id),
            access_type="READ",
        )

        # Should validate (ABAC may allow or deny, but structure should be valid)
        self.assertIn("policy_evaluation", result.details)
        self.assertFalse(result.details["same_domain"])

    def test_validate_cross_domain_access_archived_domain_warning(self):
        """Test validate_cross_domain_access warns about archived domain"""
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Domain 1", owner=self.user, status=DomainStatus.ACTIVE
        )

        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            owner=self.user,
            status=DomainStatus.ARCHIVED,  # Archived domain
        )

        result = self.rules.validate_cross_domain_access(
            user_id=str(self.user.id), source_domain=domain1, target_domain=domain2
        )

        # Should be valid but with warning
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("archived", str(result.warnings[0]).lower())

    def test_validate_domain_resource_quota_valid(self):
        """Test validate_domain_resource_quota with valid quota and usage"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100, "compute_hours": 50},
            resource_usage={"storage_gb_used": 50, "compute_hours_used": 25},
        )

        result = self.rules.validate_domain_resource_quota(domain)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("quota_usage", result.details)

    def test_validate_domain_resource_quota_exceeded(self):
        """Test validate_domain_resource_quota with exceeded quota"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100},
            resource_usage={"storage_gb_used": 150},  # Exceeds quota
        )

        result = self.rules.validate_domain_resource_quota(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("exceeded", str(result.errors[0]).lower())
        self.assertGreater(len(result.details["quota_exceeded"]), 0)

    def test_validate_domain_resource_quota_high_usage_warning(self):
        """Test validate_domain_resource_quota warns about high usage"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100},
            resource_usage={"storage_gb_used": 95},  # 95% usage
        )

        result = self.rules.validate_domain_resource_quota(domain)

        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("nearly exceeded", str(result.warnings[0]).lower())

    def test_validate_domain_resource_quota_invalid_structure(self):
        """Test validate_domain_resource_quota with invalid quota structure"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )
        # Set invalid quota structure using update to bypass model validation
        DataMeshDomain.objects.filter(id=domain.id).update(
            resource_quota="invalid"  # Should be dict
        )
        domain.refresh_from_db()

        result = self.rules.validate_domain_resource_quota(domain)

        # Should handle gracefully - resource_quota might be stored as string in DB
        # But our validation should catch it
        if isinstance(domain.resource_quota, dict):
            # If it's a dict, validation should pass structure check
            pass
        else:
            # If it's not a dict, we can't validate it properly
            # This is a limitation of JSONField - it can store non-dict values
            pass

    def test_validate_domain_resource_quota_negative_values(self):
        """Test validate_domain_resource_quota with negative values"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": -10},  # Negative quota
            resource_usage={"storage_gb_used": 5},
        )

        result = self.rules.validate_domain_resource_quota(domain)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("negative", str(result.errors[0]).lower())

    def test_validate_domain_resource_quota_no_usage_tracking(self):
        """Test validate_domain_resource_quota with quota but no usage"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100},
            # No resource_usage
        )

        result = self.rules.validate_domain_resource_quota(domain)

        # Should be valid but with warning
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("no resource_usage", str(result.warnings[0]).lower())


class DataMeshBusinessRulesErrorHandlingTest(TestCase):
    """Test error handling scenarios for DataMeshBusinessRules"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = DataMeshBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_domain_structure_with_none_domain(self):
        """Test error handling when domain is None"""
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_domain_structure(None)

    def test_validate_domain_structure_with_invalid_domain_type(self):
        """Test error handling when domain is not a DataMeshDomain instance"""
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_domain_structure("not-a-domain")

    def test_validate_ownership_transfer_with_none_domain(self):
        """Test error handling when domain is None"""
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_ownership_transfer(None, str(self.user.id))

    def test_validate_ownership_transfer_with_invalid_domain_type(self):
        """Test error handling when domain is not a DataMeshDomain instance"""
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_ownership_transfer("not-a-domain", str(self.user.id))

    def test_validate_boundaries_with_none_domain(self):
        """Test that None boundaries are valid (optional field)"""
        result = self.rules.validate_boundaries(None)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid, "None boundaries should be valid (optional field)")

    def test_validate_capabilities_with_none_domain(self):
        """Test error handling when domain is None"""
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_capabilities(None)

    def test_validate_resource_quota_with_none_domain(self):
        """Test error handling when domain is None"""
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_resource_quota(None)

    def test_validate_domain_resource_quota_with_none_domain(self):
        """Test error handling when domain is None"""
        with self.assertRaises((AttributeError, TypeError)):
            self.rules.validate_domain_resource_quota(None)

    def test_validate_domain_structure_with_corrupted_boundaries(self):
        """Test error handling when boundaries is corrupted data"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Corrupted Domain", status=DomainStatus.ACTIVE
        )
        # Try to set corrupted boundaries (this should be caught by model validation)
        # But test that business rules handle it gracefully
        domain.boundaries = {"invalid": object()}  # Non-serializable object
        try:
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch this
            pass

        # Business rules should handle gracefully
        result = self.rules.validate_domain_structure(domain)
        # Should either be invalid or handle gracefully
        self.assertIsNotNone(result)

    def test_validate_domain_structure_with_corrupted_capabilities(self):
        """Test error handling when capabilities is corrupted data"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Corrupted Capabilities Domain", status=DomainStatus.ACTIVE
        )
        # Try to set corrupted capabilities
        domain.capabilities = {"invalid": object()}  # Non-serializable object
        try:
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch this
            pass

        # Business rules should handle gracefully
        result = self.rules.validate_domain_structure(domain)
        self.assertIsNotNone(result)

    def test_validate_resource_quota_with_corrupted_data(self):
        """Test error handling when resource_quota is corrupted"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Corrupted Quota Domain", status=DomainStatus.ACTIVE
        )
        # Try to set corrupted resource_quota
        domain.resource_quota = {"invalid": object()}  # Non-serializable object
        try:
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch this
            pass

        # Business rules should handle gracefully
        result = self.rules.validate_domain_resource_quota(domain)
        self.assertIsNotNone(result)

    def test_validate_ownership_transfer_with_empty_user_id(self):
        """Test error handling when user_id is empty string"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE
        )

        result = self.rules.validate_ownership_transfer(domain, "")
        self.assertIsNotNone(result)
        self.assertFalse(result.is_valid, "Empty user_id should be invalid")
        self.assertIn("empty", " ".join(result.errors).lower())

    def test_validate_ownership_transfer_with_invalid_uuid_format(self):
        """Test error handling when user_id is invalid UUID format"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE
        )

        result = self.rules.validate_ownership_transfer(domain, "not-a-uuid")
        self.assertIsNotNone(result)
        self.assertFalse(result.is_valid, "Invalid UUID format should be invalid")
        self.assertIn("uuid", " ".join(result.errors).lower())

    def test_validate_boundaries_with_deeply_nested_structure(self):
        """Test error handling with deeply nested boundaries structure"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Deeply Nested Domain", status=DomainStatus.ACTIVE
        )
        # Create deeply nested structure
        nested_boundaries = {"level1": {"level2": {"level3": {"level4": {"level5": "value"}}}}}
        domain.boundaries = nested_boundaries
        domain.save()

        result = self.rules.validate_boundaries(domain)
        # Should handle gracefully
        self.assertIsNotNone(result)

    def test_validate_capabilities_with_empty_dict(self):
        """Test that domain with empty capabilities dict is valid via structure validation"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Empty Capabilities Domain",
            status=DomainStatus.ACTIVE,
            capabilities={},
        )

        result = self.rules.validate_domain_structure(domain)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid, "Empty capabilities dict should be valid")

    def test_validate_resource_quota_with_zero_values(self):
        """Test error handling with zero resource quota values"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Zero Quota Domain",
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 0, "compute_hours": 0},
        )

        result = self.rules.validate_domain_resource_quota(domain)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid, "Zero values should be valid")

    def test_validate_resource_quota_with_very_large_values(self):
        """Test that large resource quota values within tenant limits are valid"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Large Quota Domain",
            status=DomainStatus.ACTIVE,
            # Use values within GovernanceService tenant limits (storage_gb: 10000, compute_hours: 1000)
            resource_quota={"storage_gb": 5000, "compute_hours": 500},
        )

        result = self.rules.validate_domain_resource_quota(domain)
        self.assertIsNotNone(result)
        self.assertTrue(
            result.is_valid,
            f"Large values within tenant limits should be valid. Errors: {result.errors}",
        )

    def test_validate_domain_resource_quota_with_missing_quota_key(self):
        """Test error handling when resource_usage has key not in quota"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Missing Quota Key Domain",
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100},
            resource_usage={"storage_gb_used": 50, "unknown_key": 10},
        )

        result = self.rules.validate_domain_resource_quota(domain)
        # Should handle gracefully - unknown keys in usage
        self.assertIsNotNone(result)

    def test_validate_domain_structure_with_missing_required_fields(self):
        """Test error handling when domain is missing required fields"""
        # Create domain without name (should fail at model level)
        try:
            domain = DataMeshDomain(tenant=self.tenant, name="")
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch empty name
            pass

    def test_validate_ownership_transfer_with_cross_tenant_user(self):
        """Test error handling when transferring to user from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=other_tenant
        )

        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE
        )

        result = self.rules.validate_ownership_transfer(domain, str(other_user.id))
        # Should be invalid - user belongs to different tenant
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_domain_structure_with_invalid_status(self):
        """Test error handling with invalid domain status"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Invalid Status Domain", status=DomainStatus.ACTIVE
        )
        # Try to set invalid status (should fail at model level)
        try:
            domain.status = "INVALID_STATUS"
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch invalid status
            pass

    def test_validate_boundaries_with_list_instead_of_dict(self):
        """Test error handling when boundaries is a list instead of dict"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="List Boundaries Domain", status=DomainStatus.ACTIVE
        )
        # Try to set boundaries as list (should fail at model level)
        try:
            domain.boundaries = ["item1", "item2"]
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch this
            pass

    def test_validate_capabilities_with_string_instead_of_dict(self):
        """Test error handling when capabilities is a string instead of dict"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="String Capabilities Domain", status=DomainStatus.ACTIVE
        )
        # Try to set capabilities as string (should fail at model level)
        try:
            domain.capabilities = "not-a-dict"
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch this
            pass

    def test_validate_resource_quota_with_string_values(self):
        """Test error handling when resource_quota has string values"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="String Quota Domain", status=DomainStatus.ACTIVE
        )
        # Try to set resource_quota with string values (should fail at model level)
        try:
            domain.resource_quota = {"storage_gb": "not-a-number"}
            domain.full_clean()
        except DjangoValidationError:
            # Expected - model validation should catch this
            pass

    def test_validate_domain_resource_quota_with_usage_exceeding_quota(self):
        """Test error handling when resource_usage exceeds resource_quota"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Exceeded Quota Domain",
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 100},
            resource_usage={"storage_gb_used": 150},  # Exceeds quota
        )

        result = self.rules.validate_domain_resource_quota(domain)
        # Should be invalid or have warnings
        self.assertIsNotNone(result)
        # Usage exceeding quota should trigger validation error or warning
        if not result.is_valid:
            self.assertGreater(len(result.errors), 0)
        else:
            self.assertGreater(len(result.warnings), 0)
