"""
Unit tests for Retention Policies

Tests for time-based and event-based retention policies, legal hold,
soft/hard delete, and archive operations.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.governance.models import (
    RetentionPolicy,
    RetentionPolicyType,
    RetentionAction
)
from hub.apps.governance.retention import RetentionPolicyEnforcer
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class RetentionPolicyTest(TestCase):
    """Test RetentionPolicy model"""
    
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
    
    def test_create_time_based_policy(self):
        """Test creating time-based retention policy"""
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="30 Day Retention",
            description="Delete after 30 days",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            grace_period_days=7,
            created_by=self.user
        )
        
        self.assertIsNotNone(policy)
        self.assertEqual(policy.policy_type, RetentionPolicyType.TIME_BASED.value)
        self.assertEqual(policy.retention_period_days, 30)
        self.assertEqual(policy.action, RetentionAction.SOFT_DELETE.value)
    
    def test_create_event_based_policy(self):
        """Test creating event-based retention policy"""
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Contract Expired",
            description="Delete when contract expires",
            asset=self.asset,
            policy_type=RetentionPolicyType.EVENT_BASED.value,
            event_trigger="contract_expired",
            action=RetentionAction.HARD_DELETE.value,
            created_by=self.user
        )
        
        self.assertIsNotNone(policy)
        self.assertEqual(policy.policy_type, RetentionPolicyType.EVENT_BASED.value)
        self.assertEqual(policy.event_trigger, "contract_expired")
    
    def test_legal_hold(self):
        """Test legal hold on retention policy"""
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Legal Hold Policy",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            legal_hold=True,
            legal_hold_reason="Pending litigation",
            created_by=self.user
        )
        
        self.assertTrue(policy.legal_hold)
        self.assertEqual(policy.legal_hold_reason, "Pending litigation")
    
    def test_enforce_time_based_policy_not_expired(self):
        """Test time-based policy enforcement when not expired"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user
        )
        # Set created_at to recent date
        dataset.created_at = timezone.now() - timedelta(days=10)
        dataset.save()
        
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="30 Day Retention",
            dataset=dataset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            created_by=self.user
        )
        
        result = RetentionPolicyEnforcer.enforce_time_based_policy(policy)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'NO_ACTION')
    
    def test_enforce_time_based_policy_expired_soft_delete(self):
        """Test time-based policy enforcement with soft delete"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user
        )
        # Set created_at to past date (expired)
        dataset.created_at = timezone.now() - timedelta(days=40)
        dataset.save()
        
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="30 Day Retention",
            dataset=dataset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            grace_period_days=7,
            created_by=self.user
        )
        
        result = RetentionPolicyEnforcer.enforce_time_based_policy(policy)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'SOFT_DELETE')
        self.assertIsNotNone(policy.last_enforced_at)
    
    def test_enforce_time_based_policy_grace_period(self):
        """Test time-based policy enforcement in grace period"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user
        )
        # Set created_at to expired but within grace period
        dataset.created_at = timezone.now() - timedelta(days=32)
        dataset.save()
        
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="30 Day Retention",
            dataset=dataset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            grace_period_days=7,
            created_by=self.user
        )
        
        result = RetentionPolicyEnforcer.enforce_time_based_policy(policy)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'GRACE_PERIOD')
    
    def test_enforce_event_based_policy(self):
        """Test event-based policy enforcement"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Contract Expired",
            dataset=dataset,
            policy_type=RetentionPolicyType.EVENT_BASED.value,
            event_trigger="contract_expired",
            action=RetentionAction.HARD_DELETE.value,
            created_by=self.user
        )
        
        # Test with event not occurred
        result = RetentionPolicyEnforcer.enforce_event_based_policy(policy, event_occurred=False)
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'NO_ACTION')
        
        # Test with event occurred
        result = RetentionPolicyEnforcer.enforce_event_based_policy(policy, event_occurred=True)
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'HARD_DELETE')
    
    def test_legal_hold_prevention(self):
        """Test that legal hold prevents policy enforcement"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user
        )
        dataset.created_at = timezone.now() - timedelta(days=40)
        dataset.save()
        
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Legal Hold Policy",
            dataset=dataset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            legal_hold=True,
            legal_hold_reason="Pending litigation",
            created_by=self.user
        )
        
        # Policy should not be in list of policies to enforce
        policies = RetentionPolicyEnforcer.get_policies_to_enforce(tenant_id=str(self.tenant.id))
        self.assertNotIn(policy, policies)
    
    def test_enforce_all_policies(self):
        """Test enforcing all applicable policies"""
        # Create multiple policies
        dataset1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user
        )
        dataset1.created_at = timezone.now() - timedelta(days=40)
        dataset1.save()
        
        policy1 = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Policy 1",
            dataset=dataset1,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            grace_period_days=0,  # No grace so this policy is enforced (SOFT_DELETE)
            enabled=True,
            created_by=self.user
        )
        
        dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=2,
            created_by=self.user
        )
        dataset2.created_at = timezone.now() - timedelta(days=10)
        dataset2.save()
        
        policy2 = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Policy 2",
            dataset=dataset2,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            enabled=True,
            created_by=self.user
        )
        
        results = RetentionPolicyEnforcer.enforce_all_policies(tenant_id=str(self.tenant.id))
        
        self.assertEqual(results['total_policies'], 2)
        self.assertGreater(results['enforced'], 0)
        self.assertGreater(results['no_action'], 0)

