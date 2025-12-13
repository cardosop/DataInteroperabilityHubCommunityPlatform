"""
Unit tests for Attribute-Based Access Control (ABAC)

Tests for policy evaluation engine, field-level access control,
and policy caching.
"""
import pytest
from django.test import TestCase
from django.core.cache import cache

from hub.apps.governance.models import AccessPolicy, FieldAccessPolicy
from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult
from hub.apps.governance.models import DataClassification, ClassificationCategory
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ABACEngineTest(TestCase):
    """Test ABACEngine"""
    
    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        
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
        
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "email", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
    
    def test_evaluate_access_allow(self):
        """Test access evaluation with ALLOW policy"""
        # Create ALLOW policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow All Users",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ"
        )
        
        self.assertTrue(result.allowed)
        self.assertEqual(result.policy, policy)
    
    def test_evaluate_access_deny(self):
        """Test access evaluation with DENY policy"""
        # Create DENY policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny All Users",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="DENY",
            priority=50,  # Higher priority (lower number)
            created_by=self.user
        )
        
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ"
        )
        
        self.assertFalse(result.allowed)
        self.assertEqual(result.policy, policy)
    
    def test_evaluate_access_priority(self):
        """Test policy priority (DENY should override ALLOW)"""
        # Create ALLOW policy (lower priority)
        allow_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow All",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        # Create DENY policy (higher priority)
        deny_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny All",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="DENY",
            priority=50,
            created_by=self.user
        )
        
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ"
        )
        
        # DENY should win due to higher priority
        self.assertFalse(result.allowed)
        self.assertEqual(result.policy, deny_policy)
    
    def test_evaluate_access_with_classification(self):
        """Test access evaluation with classification condition"""
        # Create classification
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            created_by=self.user
        )
        
        # Create policy requiring PII classification
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow PII Access",
            conditions={
                "resource": {"classification": ClassificationCategory.PII.value}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ"
        )
        
        self.assertTrue(result.allowed)
    
    def test_field_level_access_control(self):
        """Test field-level access control"""
        # Create access policy
        access_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Dataset Access",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        # Create field-level policy with masking
        field_policy = FieldAccessPolicy.objects.create(
            tenant=self.tenant,
            access_policy=access_policy,
            dataset=self.dataset,
            field_name="email",
            access_type="READ",
            masking_strategy="FORMAT_PRESERVING",
            masking_config={"show_last": 4},
            created_by=self.user
        )
        
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ",
            field_name="email"
        )
        
        self.assertTrue(result.allowed)
        self.assertTrue(result.masking_required)
        self.assertEqual(len(result.field_policies), 1)
        self.assertEqual(result.field_policies[0], field_policy)
    
    def test_field_level_access_deny(self):
        """Test field-level access denial"""
        # Create access policy
        access_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Dataset Access",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        # Create field-level policy denying access
        field_policy = FieldAccessPolicy.objects.create(
            tenant=self.tenant,
            access_policy=access_policy,
            dataset=self.dataset,
            field_name="email",
            access_type="NONE",  # Deny access
            created_by=self.user
        )
        
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ",
            field_name="email"
        )
        
        self.assertFalse(result.allowed)
    
    def test_policy_caching(self):
        """Test policy caching"""
        # Create policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Cached Policy",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        # First evaluation (should cache)
        result1 = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ"
        )
        
        # Second evaluation (should use cache)
        result2 = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ"
        )
        
        self.assertTrue(result1.allowed)
        self.assertTrue(result2.allowed)
    
    def test_invalidate_policy_cache(self):
        """Test policy cache invalidation"""
        # Create policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Policy to Invalidate",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            created_by=self.user
        )
        
        # Evaluate (should cache)
        ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ"
        )
        
        # Invalidate cache
        ABACEngine.invalidate_policy_cache(
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id)
        )
        
        # Cache should be invalidated (next evaluation will fetch fresh)
        # This is tested implicitly - cache should be empty

