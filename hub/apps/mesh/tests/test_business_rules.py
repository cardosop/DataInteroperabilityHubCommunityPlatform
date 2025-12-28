"""
Unit tests for DataMeshBusinessRules.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from hub.apps.core.services.base import ValidationError
from hub.apps.mesh.business_rules import DataMeshBusinessRules, ValidationResult
from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
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
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        rules = DataMeshBusinessRules(tenant_id=str(tenant.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_and_user(self):
        """Test initialization with tenant_id and user_id"""
        tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=tenant
        )
        rules = DataMeshBusinessRules(tenant_id=str(tenant.id), user_id=str(user.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))
        self.assertEqual(rules.user_id, str(user.id))


class DataMeshBusinessRulesDomainStructureTest(TestCase):
    """Test DataMeshBusinessRules.validate_domain_structure()"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
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
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
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
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.current_owner = User.objects.create_user(
            email="current@example.com", password="testpass123", tenant=self.tenant
        )
        self.new_owner = User.objects.create_user(
            email="new@example.com", password="testpass123", tenant=self.tenant
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
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
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
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
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
        boundaries: Any = "not-a-dict"  # type: ignore

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
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
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
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
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
