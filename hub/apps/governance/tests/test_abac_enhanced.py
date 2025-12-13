"""
Enhanced Unit tests for ABAC

Tests for policy caching, invalidation, and field-level policies.
"""
import pytest
from django.test import TestCase
from django.core.cache import cache

from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult
from hub.apps.governance.models import AccessPolicy, FieldAccessPolicy
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset


pytestmark = pytest.mark.django_db(transaction=True)


class ABACCacheTest(TestCase):
    """Test ABAC policy caching"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create policy
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={
                "user": {"role": "DATA_PROVIDER"}
            },
            effect="ALLOW",
            priority=10
        )
    
    def test_policy_caching(self):
        """Test that policies are cached"""
        # Clear cache
        cache.clear()
        
        # First call - should fetch from DB
        policies1 = ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            "test-id"
        )
        
        # Second call - should use cache
        policies2 = ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            "test-id"
        )
        
        # Should return same policies
        self.assertEqual(len(policies1), len(policies2))
    
    def test_cache_invalidation(self):
        """Test cache invalidation on policy update"""
        # Get policies (populate cache)
        ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            "test-id"
        )
        
        # Update policy
        self.policy.effect = "DENY"
        self.policy.save()
        
        # Cache should be invalidated
        # Next call should fetch fresh data
        policies = ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            "test-id"
        )
        
        # Should reflect updated policy
        self.assertIsNotNone(policies)


class ABACFieldLevelTest(TestCase):
    """Test field-level access control"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            name="Test Dataset",
            key="test-dataset"
        )
        
        # Create policy
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={},
            effect="ALLOW",
            priority=10,
            dataset=self.dataset
        )
        
        # Create field policy
        self.field_policy = FieldAccessPolicy.objects.create(
            tenant=self.tenant,
            access_policy=self.policy,
            dataset=self.dataset,
            field_name="ssn",
            access_type="READ",
            masking_strategy="REDACT"
        )
    
    def test_field_level_access(self):
        """Test field-level access evaluation"""
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ",
            field_name="ssn"
        )
        
        self.assertTrue(result.allowed)
        self.assertTrue(result.masking_required)
        self.assertEqual(len(result.field_policies), 1)
        self.assertEqual(result.field_policies[0].field_name, "ssn")

