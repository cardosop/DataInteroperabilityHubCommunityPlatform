"""
Enhanced Unit tests for ABAC

Tests for policy caching, invalidation, and field-level policies.
"""
import uuid

import pytest
from django.test import TestCase
from django.core.cache import cache

from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult
from hub.apps.governance.models import AccessPolicy, FieldAccessPolicy
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ABACCacheTest(TestCase):
    """Test ABAC policy caching"""
    
    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

    def test_policy_caching(self):
        """Test that policies are cached"""
        # Clear cache
        cache.clear()
        # resource_id must be a valid UUID (asset_id is UUIDField)
        resource_uuid = str(uuid.uuid4())

        # First call - should fetch from DB
        policies1 = ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            resource_uuid,
        )

        # Second call - should use cache
        policies2 = ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            resource_uuid,
        )

        # Should return same policies
        self.assertEqual(len(policies1), len(policies2))

    def test_cache_invalidation(self):
        """Test cache invalidation on policy update"""
        # Create policy — scoped to this test only
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy for Invalidation",
            conditions={
                "user": {"role": "DATA_PROVIDER"}
            },
            effect="ALLOW",
            priority=10,
        )
        resource_uuid = str(uuid.uuid4())

        # Get policies (populate cache)
        ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            resource_uuid,
        )

        # Update policy
        policy.effect = "DENY"
        policy.save()

        # Cache should be invalidated
        # Next call should fetch fresh data
        policies = ABACEngine._get_applicable_policies(
            str(self.tenant.id),
            "ASSET",
            resource_uuid,
        )

        # Should reflect updated policy
        self.assertIsNotNone(policies)
        # Verify the policy reflects the DENY update
        updated = [p for p in policies if str(p.id) == str(policy.id)]
        self.assertTrue(len(updated) > 0, "Updated policy should be present in results")
        self.assertEqual(updated[0].effect, "DENY")


class ABACFieldLevelTest(TestCase):
    """Test field-level access control"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-field",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "ssn", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
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

