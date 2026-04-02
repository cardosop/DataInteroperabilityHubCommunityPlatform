"""
Unit tests for Retention Policy Service (Phase 12.1.4)

Tests for GovernanceService.create_retention_policy and update_retention_policy
with real DB and real audit events. No mocks.
"""
import uuid

from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import RetentionAction, RetentionPolicy, RetentionPolicyType
from hub.apps.governance.services import GovernanceService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class RetentionPolicyServiceTest(TestCase):
    """Test RetentionPolicy service methods with real DB and audit (Phase 12.1.4)"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
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
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        self.service = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_create_retention_policy_time_based(self):
        """Test creating time-based retention policy via service (Phase 12.1.4)"""
        initial_audit_count = AuditEvent.objects.filter(resource_type="RETENTION_POLICY").count()

        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="30 Day Retention",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            grace_period_days=7,
        )

        # Verify policy was created
        self.assertIsNotNone(policy.id)
        self.assertEqual(policy.name, "30 Day Retention")
        self.assertEqual(policy.policy_type, RetentionPolicyType.TIME_BASED.value)
        self.assertEqual(policy.retention_period_days, 30)
        self.assertEqual(policy.asset, self.asset)
        self.assertEqual(policy.created_by, self.user)

        # Verify exactly one audit event was created (Phase 12.4.1)
        audit_events = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            resource_id=policy.id,
        )
        self.assertEqual(audit_events.count(), 1, "Exactly one audit event should be created")

        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(str(audit_event.resource_id), str(policy.id))
        details = (
            audit_event.details_json
            if hasattr(audit_event, "details_json")
            else audit_event.details
        )
        self.assertIn("name", details)
        self.assertEqual(details["name"], "30 Day Retention")

    def test_create_retention_policy_event_based(self):
        """Test creating event-based retention policy via service"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Contract Expired Policy",
            policy_type=RetentionPolicyType.EVENT_BASED.value,
            dataset_id=str(self.dataset.id),
            event_trigger="contract_expired",
            action=RetentionAction.HARD_DELETE.value,
        )

        self.assertIsNotNone(policy.id)
        self.assertEqual(policy.policy_type, RetentionPolicyType.EVENT_BASED.value)
        self.assertEqual(policy.event_trigger, "contract_expired")
        self.assertEqual(policy.dataset, self.dataset)

        # Verify audit event
        audit_events = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            resource_id=policy.id,
        )
        self.assertEqual(audit_events.count(), 1)

    def test_create_retention_policy_with_file(self):
        """Test creating retention policy with file reference"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="File Retention",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            file_id=str(self.file.id),
            retention_period_days=90,
        )

        self.assertEqual(policy.file, self.file)

        # Verify audit event includes file_id
        audit_event = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY", resource_id=policy.id
        ).first()
        details = (
            audit_event.details_json
            if hasattr(audit_event, "details_json")
            else audit_event.details
        )
        self.assertIsNotNone(details.get("file_id"))

    def test_create_retention_policy_validation_error_no_resource(self):
        """Test that creating policy without asset/dataset/file fails"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_retention_policy(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Invalid Policy",
                policy_type=RetentionPolicyType.TIME_BASED.value,
                retention_period_days=30,
            )

        self.assertIn("asset_id, dataset_id, or file_id", str(cm.exception))

    def test_create_retention_policy_validation_error_time_based_no_days(self):
        """Test that time-based policy requires retention_period_days"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_retention_policy(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Invalid Policy",
                policy_type=RetentionPolicyType.TIME_BASED.value,
                asset_id=str(self.asset.id),
            )

        self.assertIn("retention_period_days", str(cm.exception))

    def test_create_retention_policy_validation_error_event_based_no_trigger(self):
        """Test that event-based policy requires event_trigger"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_retention_policy(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Invalid Policy",
                policy_type=RetentionPolicyType.EVENT_BASED.value,
                asset_id=str(self.asset.id),
            )

        self.assertIn("event_trigger", str(cm.exception))

    def test_create_retention_policy_not_found_asset(self):
        """Test that non-existent asset raises NotFoundError"""
        import uuid

        fake_asset_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.create_retention_policy(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Policy",
                policy_type=RetentionPolicyType.TIME_BASED.value,
                asset_id=fake_asset_id,
                retention_period_days=30,
            )

        self.assertIn("not found", str(cm.exception).lower())

    def test_update_retention_policy(self):
        """Test updating retention policy via service (Phase 12.1.4)"""
        # Create policy first
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Original Name",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
            enabled=True,
        )

        initial_audit_count = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY", action="RETENTION_POLICY_UPDATED"
        ).count()

        # Update policy
        updated_policy = self.service.update_retention_policy(
            policy_id=str(policy.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
            retention_period_days=60,
            enabled=False,
        )

        # Verify updates
        updated_policy.refresh_from_db()
        self.assertEqual(updated_policy.name, "Updated Name")
        self.assertEqual(updated_policy.retention_period_days, 60)
        self.assertEqual(updated_policy.enabled, False)

        # Verify exactly one audit event was created for update
        audit_events = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_UPDATED",
            resource_id=policy.id,
        )
        self.assertEqual(
            audit_events.count(), 1, "Exactly one audit event should be created for update"
        )

        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        details = (
            audit_event.details_json
            if hasattr(audit_event, "details_json")
            else audit_event.details
        )
        self.assertIn("changes", details)
        self.assertEqual(details["changes"]["name"], "Updated Name")

    def test_update_retention_policy_not_found(self):
        """Test that updating non-existent policy raises NotFoundError"""
        import uuid

        fake_policy_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.update_retention_policy(
                policy_id=fake_policy_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Updated",
            )

    # ========== EDGE CASES TESTS ==========

    def test_create_retention_policy_with_grace_period(self):
        """Test creating retention policy with grace period"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Policy with Grace Period",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
            grace_period_days=7,
            action=RetentionAction.SOFT_DELETE.value,
        )

        self.assertEqual(policy.grace_period_days, 7)

    def test_create_retention_policy_with_legal_hold(self):
        """Test creating retention policy with legal hold"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Policy with Legal Hold",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
            legal_hold=True,
            legal_hold_reason="Legal investigation",
            legal_hold_expires_at=(timezone.now() + timedelta(days=90)).isoformat(),
        )

        self.assertTrue(policy.legal_hold)
        self.assertEqual(policy.legal_hold_reason, "Legal investigation")

    def test_create_retention_policy_disabled(self):
        """Test creating retention policy as disabled"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Disabled Policy",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
            enabled=False,
        )

        self.assertFalse(policy.enabled)

    def test_update_retention_policy_partial_update(self):
        """Test updating retention policy with partial fields"""
        # Create policy first
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Original Name",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
            enabled=True,
        )

        # Update only name
        updated_policy = self.service.update_retention_policy(
            policy_id=str(policy.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name Only",
        )

        updated_policy.refresh_from_db()
        self.assertEqual(updated_policy.name, "Updated Name Only")
        self.assertEqual(updated_policy.retention_period_days, 30)  # Unchanged

    def test_create_retention_policy_multiple_policies_same_asset(self):
        """Test creating multiple retention policies for same asset"""
        policy1 = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Policy 1",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
        )

        policy2 = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Policy 2",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=60,
        )

        self.assertNotEqual(policy1.id, policy2.id)
        self.assertEqual(policy1.asset, policy2.asset)

    def test_create_retention_policy_different_tenants(self):
        """Test creating retention policies for different tenants"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        policy1 = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Policy Tenant 1",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
        )

        service2 = GovernanceService(tenant_id=str(other_tenant.id), user_id=str(self.user.id))
        policy2 = service2.create_retention_policy(
            tenant_id=str(other_tenant.id),
            user_id=str(self.user.id),
            name="Policy Tenant 2",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(other_asset.id),
            retention_period_days=30,
        )

        self.assertNotEqual(policy1.id, policy2.id)
        self.assertNotEqual(policy1.tenant, policy2.tenant)

    # ========== ERROR HANDLING TESTS ==========

    def test_create_retention_policy_validation_error_negative_days(self):
        """Test that creating policy with negative retention_period_days fails"""
        with self.assertRaises(ValidationError):
            self.service.create_retention_policy(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Invalid Policy",
                policy_type=RetentionPolicyType.TIME_BASED.value,
                asset_id=str(self.asset.id),
                retention_period_days=-1,
            )

    def test_create_retention_policy_validation_error_invalid_action(self):
        """Test that creating a retention policy with invalid action raises error."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        with self.assertRaises((ValidationError, DjangoValidationError, Exception)):
            self.service.create_retention_policy(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Invalid Action Policy",
                policy_type=RetentionPolicyType.TIME_BASED.value,
                asset_id=str(self.asset.id),
                retention_period_days=30,
                action="INVALID_ACTION_XYZ",
            )

    def test_update_retention_policy_validation_error_negative_days(self):
        """Test that updating policy with negative retention_period_days fails"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Policy",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
        )

        with self.assertRaises(ValidationError):
            self.service.update_retention_policy(
                policy_id=str(policy.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                retention_period_days=-1,
            )

    # ========== TDD COMPLIANCE TESTS ==========

    def test_create_retention_policy_sets_all_required_fields(self):
        """Test that created retention policy has all required fields"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Complete Policy",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
        )

        # Verify all required fields are set
        self.assertIsNotNone(policy.id)
        self.assertIsNotNone(policy.tenant)
        self.assertIsNotNone(policy.name)
        self.assertIsNotNone(policy.policy_type)
        self.assertIsNotNone(policy.asset)
        self.assertIsNotNone(policy.retention_period_days)
        self.assertIsNotNone(policy.created_by)
        self.assertIsNotNone(policy.created_at)
        self.assertIsNotNone(policy.updated_at)

    def test_update_retention_policy_updates_timestamp(self):
        """Test that updating retention policy updates updated_at timestamp"""
        policy = self.service.create_retention_policy(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Original Name",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            asset_id=str(self.asset.id),
            retention_period_days=30,
        )

        # Force a past timestamp to avoid sleep
        past_time = timezone.now() - timedelta(seconds=10)
        RetentionPolicy.objects.filter(pk=policy.pk).update(updated_at=past_time)
        policy.refresh_from_db()
        original_updated_at = policy.updated_at

        updated_policy = self.service.update_retention_policy(
            policy_id=str(policy.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
        )

        updated_policy.refresh_from_db()
        self.assertGreater(updated_policy.updated_at, original_updated_at)
