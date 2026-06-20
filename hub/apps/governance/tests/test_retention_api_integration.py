"""
Integration tests for Retention Policy API (Phase 12.1.4)

Tests for RetentionPolicyViewSet create and update endpoints via API
with real DB and real audit events. No mocks.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import RetentionAction, RetentionPolicy, RetentionPolicyType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class RetentionPolicyAPIIntegrationTest(TestCase):
    """Test RetentionPolicyViewSet API endpoints with real DB and audit (Phase 12.1.4)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)

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

        self.client.force_authenticate(user=self.user)

    def test_create_retention_policy_via_api(self):
        """Test creating retention policy via API endpoint (Phase 12.1.4)"""
        initial_audit_count = AuditEvent.objects.filter(resource_type="RETENTION_POLICY").count()

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "30 Day Retention",
                "description": "Delete after 30 days",
                "asset_id": str(self.asset.id),
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "retention_period_days": 30,
                "action": RetentionAction.SOFT_DELETE.value,
                "grace_period_days": 7,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

        policy_id = response.data["id"]
        policy = RetentionPolicy.objects.get(id=policy_id)
        self.assertEqual(policy.name, "30 Day Retention")

        # Verify exactly one audit event was created (Phase 12.4.1)
        audit_events = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            resource_id=policy_id,
        )
        self.assertEqual(audit_events.count(), 1, "Exactly one audit event should be created")

        # Verify no duplicate audit events
        total_audit_count = AuditEvent.objects.filter(resource_type="RETENTION_POLICY").count()
        self.assertEqual(
            total_audit_count, initial_audit_count + 1, "Only one new audit event should exist"
        )

    def test_update_retention_policy_via_api(self):
        """Test updating retention policy via API endpoint (Phase 12.1.4)"""
        # Create policy first
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Original Name",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            created_by=self.user,
        )

        initial_audit_count = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY", action="RETENTION_POLICY_UPDATED"
        ).count()

        response = self.client.patch(
            f"/api/v1/governance/retention-policies/{policy.id}/",
            {
                "name": "Updated Name",
                "retention_period_days": 60,
                "enabled": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        policy.refresh_from_db()
        self.assertEqual(policy.name, "Updated Name")
        self.assertEqual(policy.retention_period_days, 60)
        self.assertEqual(policy.enabled, False)

        # Verify exactly one audit event was created for update
        audit_events = AuditEvent.objects.filter(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_UPDATED",
            resource_id=str(policy.id),
        )
        self.assertEqual(
            audit_events.count(),
            initial_audit_count + 1,
            "Exactly one new audit event should be created for update",
        )

    # ========== FAILURE SCENARIOS TESTS ==========

    def test_create_retention_policy_api_validation_error_no_resource(self):
        """Test that creating policy via API without resource returns error"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Invalid Policy",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "retention_period_days": 30,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("asset_id, dataset_id, or file_id", str(response.data).lower())

    def test_create_retention_policy_api_validation_error_time_based_no_days(self):
        """Test that creating time-based policy via API without retention_period_days returns error"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Invalid Policy",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("retention_period_days", str(response.data).lower())

    def test_create_retention_policy_api_validation_error_event_based_no_trigger(self):
        """Test that creating event-based policy via API without event_trigger returns error"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Invalid Policy",
                "policy_type": RetentionPolicyType.EVENT_BASED.value,
                "asset_id": str(self.asset.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("event_trigger", str(response.data).lower())

    def test_create_retention_policy_api_nonexistent_asset(self):
        """Test that creating policy via API with nonexistent asset returns error"""
        import uuid

        fake_asset_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Policy",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": fake_asset_id,
                "retention_period_days": 30,
            },
            format="json",
        )

        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
        )

    def test_update_retention_policy_api_nonexistent(self):
        """Test that updating nonexistent policy via API returns 404"""
        import uuid

        fake_policy_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/governance/retention-policies/{fake_policy_id}/",
            {"name": "Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_retention_policy_api_validation_error_negative_days(self):
        """Test that updating policy via API with negative retention_period_days returns error"""
        # Create policy first
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Policy",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/governance/retention-policies/{policy.id}/",
            {"retention_period_days": -1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== EDGE CASES TESTS ==========

    def test_create_retention_policy_api_with_grace_period(self):
        """Test creating retention policy via API with grace period"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Policy with Grace Period",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
                "retention_period_days": 30,
                "grace_period_days": 7,
                "action": RetentionAction.SOFT_DELETE.value,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["grace_period_days"], 7)

    def test_create_retention_policy_api_with_legal_hold(self):
        """Test creating retention policy via API with legal hold"""
        self.client.force_authenticate(user=self.user)

        legal_hold_expires_at = (timezone.now() + timedelta(days=90)).isoformat()

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Policy with Legal Hold",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
                "retention_period_days": 30,
                "legal_hold": True,
                "legal_hold_reason": "Legal investigation",
                "legal_hold_expires_at": legal_hold_expires_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["legal_hold"])
        self.assertEqual(response.data["legal_hold_reason"], "Legal investigation")

    def test_create_retention_policy_api_disabled(self):
        """Test creating retention policy via API as disabled"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Disabled Policy",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
                "retention_period_days": 30,
                "enabled": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["enabled"])

    def test_update_retention_policy_api_partial_update(self):
        """Test updating retention policy via API with partial fields"""
        # Create policy first
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Original Name",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            enabled=True,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/governance/retention-policies/{policy.id}/",
            {"name": "Updated Name Only"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name Only")
        # Other fields should remain unchanged
        self.assertEqual(response.data["retention_period_days"], 30)

    def test_create_retention_policy_api_multiple_policies_same_asset(self):
        """Test creating multiple retention policies via API for same asset"""
        self.client.force_authenticate(user=self.user)

        response1 = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Policy 1",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
                "retention_period_days": 30,
            },
            format="json",
        )

        response2 = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Policy 2",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
                "retention_period_days": 60,
            },
            format="json",
        )

        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response1.data["id"], response2.data["id"])

    # ========== ERROR HANDLING TESTS ==========

    def test_create_retention_policy_api_requires_authentication(self):
        """Test that creating retention policy via API requires authentication"""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Policy",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
                "retention_period_days": 30,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_retention_policy_api_requires_authentication(self):
        """Test that updating retention policy via API requires authentication"""
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Policy",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            created_by=self.user,
        )

        self.client.force_authenticate(user=None)
        response = self.client.patch(
            f"/api/v1/governance/retention-policies/{policy.id}/",
            {"name": "Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_retention_policy_api_malformed_json(self):
        """Test that creating retention policy via API with malformed JSON returns error"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            "invalid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== TDD COMPLIANCE TESTS ==========

    def test_create_retention_policy_api_sets_all_required_fields(self):
        """Test that created retention policy via API has all required fields"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/retention-policies/",
            {
                "name": "Complete Policy",
                "policy_type": RetentionPolicyType.TIME_BASED.value,
                "asset_id": str(self.asset.id),
                "retention_period_days": 30,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify all required fields are present
        self.assertIn("id", response.data)
        self.assertIn("tenant", response.data)
        self.assertIn("name", response.data)
        self.assertIn("policy_type", response.data)
        self.assertIn("asset", response.data)
        self.assertIn("retention_period_days", response.data)
        self.assertIn("created_by", response.data)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)

    def test_update_retention_policy_api_updates_timestamp(self):
        """Test that updating retention policy via API updates updated_at timestamp"""
        # Create policy first
        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="Original Name",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            created_by=self.user,
        )

        # Force a past timestamp to avoid sleep
        past_time = timezone.now() - timedelta(seconds=10)
        RetentionPolicy.objects.filter(pk=policy.pk).update(updated_at=past_time)
        policy.refresh_from_db()
        original_updated_at = policy.updated_at

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/governance/retention-policies/{policy.id}/",
            {"name": "Updated Name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated_at_str = response.data["updated_at"]
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        self.assertGreater(updated_at, original_updated_at)
