"""
Unit tests for DataMeshDomain model.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from hub.apps.tenants.models import Tenant, KYCStatus
import uuid
from hub.apps.mesh.models import (
    DataMeshDomain,
    DomainStatus,
    PolicyApplication,
    PolicyApplicationStatus,
    ComplianceReport,
    MeshComplianceStatus
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DataMeshDomainModelTest(TestCase):
    """Test DataMeshDomain model"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant
        )

    def test_create_domain(self):
        """Test domain creation with minimal required fields"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain"
        )

        self.assertEqual(domain.tenant, self.tenant)
        self.assertEqual(domain.name, "Test Domain")
        self.assertEqual(domain.status, DomainStatus.ACTIVE)
        self.assertIsNone(domain.owner)
        self.assertEqual(domain.boundaries, {})
        self.assertEqual(domain.capabilities, {})
        self.assertEqual(domain.resource_quota, {})
        self.assertEqual(domain.resource_usage, {})
        self.assertIsNotNone(domain.id)
        self.assertIsNotNone(domain.created_at)
        self.assertIsNotNone(domain.updated_at)

    def test_create_domain_with_all_fields(self):
        """Test domain creation with all fields"""
        boundaries = {
            "data_products": ["product1", "product2"],
            "schemas": ["schema1"],
            "access_patterns": ["read", "write"]
        }
        capabilities = {
            "apis": ["api1", "api2"],
            "services": ["service1"],
            "data_products": ["product1"]
        }
        resource_quota = {
            "storage_gb": 1000,
            "compute_hours": 500,
            "api_calls_per_day": 10000
        }
        resource_usage = {
            "storage_gb": 500,
            "compute_hours": 250,
            "api_calls_per_day": 5000
        }

        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Full Domain",
            description="A domain with all fields populated",
            owner=self.user,
            boundaries=boundaries,
            capabilities=capabilities,
            resource_quota=resource_quota,
            resource_usage=resource_usage,
            status=DomainStatus.ACTIVE
        )

        self.assertEqual(domain.name, "Full Domain")
        self.assertEqual(domain.description, "A domain with all fields populated")
        self.assertEqual(domain.owner, self.user)
        self.assertEqual(domain.boundaries, boundaries)
        self.assertEqual(domain.capabilities, capabilities)
        self.assertEqual(domain.resource_quota, resource_quota)
        self.assertEqual(domain.resource_usage, resource_usage)
        self.assertEqual(domain.status, DomainStatus.ACTIVE)

    def test_domain_status_choices(self):
        """Test domain status enum"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Status Test Domain"
        )

        # Test ACTIVE status
        domain.status = DomainStatus.ACTIVE
        domain.save()
        self.assertEqual(domain.status, DomainStatus.ACTIVE)
        self.assertTrue(domain.is_active())
        self.assertFalse(domain.is_inactive())
        self.assertFalse(domain.is_archived())

        # Test INACTIVE status
        domain.status = DomainStatus.INACTIVE
        domain.save()
        self.assertEqual(domain.status, DomainStatus.INACTIVE)
        self.assertFalse(domain.is_active())
        self.assertTrue(domain.is_inactive())
        self.assertFalse(domain.is_archived())

        # Test ARCHIVED status
        domain.status = DomainStatus.ARCHIVED
        domain.save()
        self.assertEqual(domain.status, DomainStatus.ARCHIVED)
        self.assertFalse(domain.is_active())
        self.assertFalse(domain.is_inactive())
        self.assertTrue(domain.is_archived())

    def test_domain_unique_name_per_tenant(self):
        """Test that domain names must be unique per tenant"""
        DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Unique Domain"
        )

        # Same name, same tenant should fail
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            DataMeshDomain.objects.create(
                tenant=self.tenant,
                name="Unique Domain"
            )

        # Same name, different tenant should succeed
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Unique Domain"
        )
        self.assertEqual(other_domain.name, "Unique Domain")
        self.assertEqual(other_domain.tenant, other_tenant)

    def test_domain_clean_validation_empty_name(self):
        """Test domain clean() validation for empty name"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name=""
        )

        with self.assertRaises(ValidationError) as cm:
            domain.clean()
        self.assertIn("name", str(cm.exception))

    def test_domain_clean_validation_whitespace_name(self):
        """Test domain clean() validation for whitespace-only name"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name="   "
        )

        with self.assertRaises(ValidationError) as cm:
            domain.clean()
        self.assertIn("name", str(cm.exception))

    def test_domain_clean_validation_boundaries_not_dict(self):
        """Test domain clean() validation for boundaries not being a dict"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name="Test Domain",
            boundaries=["not", "a", "dict"]
        )

        with self.assertRaises(ValidationError) as cm:
            domain.clean()
        self.assertIn("boundaries", str(cm.exception))

    def test_domain_clean_validation_capabilities_not_dict(self):
        """Test domain clean() validation for capabilities not being a dict"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name="Test Domain",
            capabilities="not a dict"
        )

        with self.assertRaises(ValidationError) as cm:
            domain.clean()
        self.assertIn("capabilities", str(cm.exception))

    def test_domain_clean_validation_resource_quota_not_dict(self):
        """Test domain clean() validation for resource_quota not being a dict"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name="Test Domain",
            resource_quota=["not", "a", "dict"]
        )

        with self.assertRaises(ValidationError) as cm:
            domain.clean()
        self.assertIn("resource_quota", str(cm.exception))

    def test_domain_clean_validation_resource_usage_not_dict(self):
        """Test domain clean() validation for resource_usage not being a dict"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name="Test Domain",
            resource_usage="not a dict"
        )

        with self.assertRaises(ValidationError) as cm:
            domain.clean()
        self.assertIn("resource_usage", str(cm.exception))

    def test_domain_clean_validation_owner_different_tenant(self):
        """Test domain clean() validation for owner from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant
        )

        domain = DataMeshDomain(
            tenant=self.tenant,
            name="Test Domain",
            owner=other_user
        )

        with self.assertRaises(ValidationError) as cm:
            domain.clean()
        self.assertIn("owner", str(cm.exception))
        self.assertIn("same tenant", str(cm.exception))

    def test_domain_clean_validation_owner_same_tenant(self):
        """Test domain clean() validation for owner from same tenant (should pass)"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user
        )

        # Should not raise ValidationError
        try:
            domain.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly")

    def test_domain_save_calls_clean(self):
        """Test that save() calls clean() for validation"""
        domain = DataMeshDomain(
            tenant=self.tenant,
            name=""  # Invalid: empty name
        )

        with self.assertRaises(ValidationError):
            domain.save()

    def test_domain_str_representation(self):
        """Test domain string representation"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain"
        )

        expected_str = f"Test Domain ({self.tenant.name})"
        self.assertEqual(str(domain), expected_str)

    def test_domain_get_resource_usage_percentage(self):
        """Test get_resource_usage_percentage method"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Resource Test Domain",
            resource_quota={
                "storage_gb": 1000,
                "compute_hours": 500
            },
            resource_usage={
                "storage_gb": 500,
                "compute_hours": 250
            }
        )

        # Test 50% usage
        storage_percentage = domain.get_resource_usage_percentage("storage_gb")
        self.assertEqual(storage_percentage, 50.0)

        compute_percentage = domain.get_resource_usage_percentage("compute_hours")
        self.assertEqual(compute_percentage, 50.0)

        # Test 0% usage (no usage recorded)
        domain.resource_usage = {"storage_gb": 0}
        domain.save()
        storage_percentage = domain.get_resource_usage_percentage("storage_gb")
        self.assertEqual(storage_percentage, 0.0)

        # Test 100% usage (capped)
        domain.resource_usage = {"storage_gb": 1000}
        domain.save()
        storage_percentage = domain.get_resource_usage_percentage("storage_gb")
        self.assertEqual(storage_percentage, 100.0)

        # Test >100% usage (capped at 100%)
        domain.resource_usage = {"storage_gb": 2000}
        domain.save()
        storage_percentage = domain.get_resource_usage_percentage("storage_gb")
        self.assertEqual(storage_percentage, 100.0)

        # Test no quota set (returns 0.0)
        domain.resource_quota = {}
        domain.save()
        storage_percentage = domain.get_resource_usage_percentage("storage_gb")
        self.assertEqual(storage_percentage, 0.0)

        # Test quota is 0 (returns 0.0)
        domain.resource_quota = {"storage_gb": 0}
        domain.save()
        storage_percentage = domain.get_resource_usage_percentage("storage_gb")
        self.assertEqual(storage_percentage, 0.0)

    def test_domain_is_resource_quota_exceeded(self):
        """Test is_resource_quota_exceeded method"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Quota Test Domain",
            resource_quota={
                "storage_gb": 1000,
                "compute_hours": 500
            },
            resource_usage={
                "storage_gb": 500,
                "compute_hours": 600
            }
        )

        # Test not exceeded
        self.assertFalse(domain.is_resource_quota_exceeded("storage_gb"))

        # Test exceeded
        self.assertTrue(domain.is_resource_quota_exceeded("compute_hours"))

        # Test no quota set (returns False)
        domain.resource_quota = {}
        domain.save()
        self.assertFalse(domain.is_resource_quota_exceeded("storage_gb"))

        # Test quota not in dict (returns False)
        self.assertFalse(domain.is_resource_quota_exceeded("nonexistent_resource"))

    def test_domain_tenant_cascade_delete(self):
        """Test that domain is deleted when tenant is deleted"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Cascade Test Domain"
        )
        domain_id = domain.id

        # Delete user first (User has RESTRICT foreign key to Tenant)
        self.user.delete()

        # Delete tenant
        self.tenant.delete()

        # Domain should be deleted
        self.assertFalse(DataMeshDomain.objects.filter(id=domain_id).exists())

    def test_domain_owner_set_null_on_delete(self):
        """Test that domain owner is set to NULL when user is deleted"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Owner Test Domain",
            owner=self.user
        )

        # Delete user
        self.user.delete()

        # Domain should still exist but owner should be None
        domain.refresh_from_db()
        self.assertIsNone(domain.owner)

    def test_domain_indexes(self):
        """Test that domain has proper database indexes"""
        # Create domains to test indexes
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Index Test Domain 1",
            owner=self.user,
            status=DomainStatus.ACTIVE
        )
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Index Test Domain 2",
            status=DomainStatus.INACTIVE
        )

        # Test queries that should use indexes
        # Scope all queries to this test's tenant for isolation
        # Tenant index
        tenant_domains = DataMeshDomain.objects.filter(
            tenant=self.tenant,
        )
        self.assertEqual(tenant_domains.count(), 2)

        # Owner index
        owner_domains = DataMeshDomain.objects.filter(
            tenant=self.tenant, owner=self.user,
        )
        self.assertEqual(owner_domains.count(), 1)
        self.assertEqual(owner_domains.first(), domain1)

        # Status index
        active_domains = DataMeshDomain.objects.filter(
            tenant=self.tenant, status=DomainStatus.ACTIVE,
        )
        self.assertEqual(active_domains.count(), 1)
        self.assertEqual(active_domains.first(), domain1)

        # Created_at index (ordering)
        ordered_domains = list(
            DataMeshDomain.objects.filter(tenant=self.tenant)
        )
        # Should be ordered by -created_at (newest first)
        self.assertEqual(ordered_domains[0], domain2)
        self.assertEqual(ordered_domains[1], domain1)

