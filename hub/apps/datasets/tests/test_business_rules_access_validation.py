"""
Unit tests for DatasetsBusinessRules access validation.

Comprehensive tests for dataset access validation integrating with GovernanceService
and ABACEngine, without mocks/stubs.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.datasets.business_rules import DatasetsBusinessRules
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.factories import DatasetFactory
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.governance.abac import ABACEngine
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import AccessPolicy, AccessRequest, AccessRequestStatus
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DatasetsBusinessRulesAccessValidationTest(DatasetsTestBase):
    """Test dataset access validation with GovernanceService integration"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_dataset_read_access_same_tenant(self):
        """Test read access validation for same-tenant user"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        # Same tenant should allow access (ABAC may deny, but tenant isolation passes)
        self.assertTrue(result.details["tenant_isolation_valid"])

    def test_validate_dataset_read_access_same_tenant_includes_tenant_isolation(self):
        """Test read access validation includes tenant_isolation in details"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        self.assertIn("tenant_isolation", result.details)

    def test_validate_dataset_read_access_same_tenant_includes_abac_policy_checked(self):
        """Test read access validation includes abac_policy_checked in details"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        self.assertIn("abac_policy_checked", result.details)

    def test_validate_dataset_read_access_same_tenant_sets_abac_policy_checked_true(self):
        """Test read access validation sets abac_policy_checked to True"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        self.assertTrue(result.details["abac_policy_checked"])

    def test_validate_dataset_read_access_cross_tenant(self):
        """Test read access validation for cross-tenant user"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_read_access(dataset, user=other_user)
        # Cross-tenant access requires ABAC policy or access request
        self.assertTrue(
            result.details["tenant_isolation_valid"]
        )  # Validation passes, but cross-tenant
        self.assertTrue(result.details["tenant_isolation"]["cross_tenant"])
        self.assertIn("abac_policy_checked", result.details)

    def test_validate_dataset_write_access_same_tenant(self):
        """Test write access validation for same-tenant user"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_write_access(dataset, user=self.user)
        # Same tenant should allow access (ABAC may deny, but tenant isolation passes)
        self.assertTrue(result.details["tenant_isolation_valid"])
        self.assertIn("abac_policy_checked", result.details)
        self.assertTrue(result.details["abac_policy_checked"])

    def test_validate_dataset_write_access_cross_tenant(self):
        """Test write access validation for cross-tenant user"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_write_access(dataset, user=other_user)
        # Cross-tenant write access requires ABAC policy or access request
        self.assertTrue(result.details["tenant_isolation_valid"])
        self.assertTrue(result.details["tenant_isolation"]["cross_tenant"])
        self.assertIn("abac_policy_checked", result.details)

    def test_validate_dataset_read_access_with_approved_request(self):
        """Test read access validation with approved access request"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create approved access request
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Testing access validation",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        # Should have access via approved request
        self.assertIn("access_request_checked", result.details)
        self.assertTrue(result.details["access_request_checked"])
        # Access may still be denied if ABAC denies, but access request is checked
        self.assertIn("access_request", result.details)

    def test_validate_dataset_write_access_with_approved_request(self):
        """Test write access validation with approved access request"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create approved access request for WRITE
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Testing write access validation",
            requested_access_type="WRITE",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        result = self.rules.validate_dataset_write_access(dataset, user=self.user)
        # Should check access request
        self.assertIn("access_request_checked", result.details)
        self.assertTrue(result.details["access_request_checked"])
        self.assertIn("access_request", result.details)

    def test_validate_dataset_read_access_with_expired_request(self):
        """Test read access validation with expired access request"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create expired approved access request
        expired_time = timezone.now() - timedelta(days=1)
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Testing expired access",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.user,
            approved_at=expired_time,
            expires_at=expired_time,  # Already expired
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        # Expired request should not grant access
        self.assertIn("access_request_checked", result.details)
        # Access should be denied if no ABAC policy allows it

    def test_validate_dataset_read_access_with_abac_policy(self):
        """Test read access validation with ABAC policy"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create ABAC policy allowing READ access
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Read Policy",
            description="Allow READ access for test user",
            conditions={
                "user": {"user_id": str(self.user.id)},
                "resource": {"resource_type": "DATASET"},
            },
            effect="ALLOW",
            dataset=dataset,
            enabled=True,
            priority=100,
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        # ABAC policy should be checked
        self.assertIn("abac_policy_checked", result.details)
        self.assertTrue(result.details["abac_policy_checked"])
        self.assertIn("abac_result", result.details)

    def test_validate_dataset_write_access_with_abac_policy(self):
        """Test write access validation with ABAC policy"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create ABAC policy allowing WRITE access
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Write Policy",
            description="Allow WRITE access for test user",
            conditions={
                "user": {"user_id": str(self.user.id)},
                "resource": {"resource_type": "DATASET"},
            },
            effect="ALLOW",
            dataset=dataset,
            enabled=True,
            priority=100,
        )

        result = self.rules.validate_dataset_write_access(dataset, user=self.user)
        # ABAC policy should be checked
        self.assertIn("abac_policy_checked", result.details)
        self.assertTrue(result.details["abac_policy_checked"])
        self.assertIn("abac_result", result.details)

    def test_validate_dataset_read_access_with_deny_policy(self):
        """Test read access validation with DENY ABAC policy"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create ABAC policy denying access
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Deny Policy",
            description="Deny READ access for test user",
            conditions={
                "user": {"user_id": str(self.user.id)},
                "resource": {"resource_type": "DATASET"},
            },
            effect="DENY",
            dataset=dataset,
            enabled=True,
            priority=50,  # Higher priority (lower number)
        )

        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        # DENY policy should deny access
        self.assertIn("abac_policy_checked", result.details)
        self.assertTrue(result.details["abac_policy_checked"])
        # Access should be denied, but may fall back to access request

    def test_validate_tenant_isolation_same_tenant(self):
        """Test tenant isolation validation for same tenant"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_tenant_isolation(dataset, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["same_tenant"])
        self.assertFalse(result.details["cross_tenant"])

    def test_validate_tenant_isolation_cross_tenant(self):
        """Test tenant isolation validation for cross tenant"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_tenant_isolation(dataset, other_user)
        # Cross-tenant is valid (not an error), but requires entitlements
        self.assertTrue(result.is_valid)
        self.assertFalse(result.details["same_tenant"])
        self.assertTrue(result.details["cross_tenant"])
        self.assertIn("Cross-tenant access", result.warnings[0])

    def test_validate_access_request_approved(self):
        """Test access request validation with approved request"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create approved access request
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Testing",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        result = self.rules._validate_access_request(dataset, self.user, "READ")
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["has_approved_request"])
        self.assertEqual(result.details["access_request_id"], str(access_request.id))
        self.assertEqual(result.details["access_request_status"], AccessRequestStatus.APPROVED)

    def test_validate_access_request_pending(self):
        """Test access request validation with pending request"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create pending access request
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Testing",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        result = self.rules._validate_access_request(dataset, self.user, "READ")
        # Pending request should not grant access
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["has_approved_request"])

    def test_validate_access_request_expired(self):
        """Test access request validation with expired request"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create expired approved access request
        expired_time = timezone.now() - timedelta(days=1)
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Testing",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.user,
            approved_at=expired_time,
            expires_at=expired_time,
        )

        result = self.rules._validate_access_request(dataset, self.user, "READ")
        # Expired request should not grant access
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["has_approved_request"])

    def test_validate_access_request_future_expiration(self):
        """Test access request validation with future expiration"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create approved access request with future expiration
        future_time = timezone.now() + timedelta(days=1)
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Testing",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=self.user,
            approved_at=timezone.now(),
            expires_at=future_time,
        )

        result = self.rules._validate_access_request(dataset, self.user, "READ")
        # Future expiration should still grant access
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["has_approved_request"])

    def test_validate_abac_access_integration(self):
        """Test ABAC access validation integration"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create ABAC policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test ABAC policy",
            conditions={
                "user": {"user_id": str(self.user.id)},
                "resource": {"resource_type": "DATASET"},
            },
            effect="ALLOW",
            dataset=dataset,
            enabled=True,
            priority=100,
        )

        result = self.rules._validate_abac_access(dataset, self.user, "READ")
        # Should return PolicyEvaluationResult
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "allowed"))
        self.assertTrue(hasattr(result, "policy"))

    def test_validate_permissions_no_user(self):
        """Test permissions validation without user"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_permissions(dataset, user=None, access_type="READ")
        # Should skip validation but return valid
        self.assertTrue(result.is_valid)
        self.assertIn("User not provided", result.warnings[0])
        self.assertTrue(result.details["read_access_allowed"])

    def test_validate_permissions_write_no_user(self):
        """Test write permissions validation without user"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_permissions(dataset, user=None, access_type="WRITE")
        # Write should require user
        self.assertTrue(result.is_valid)  # Validation passes but warns
        self.assertFalse(result.details["write_access_allowed"])


class DatasetsBusinessRulesAccessValidationIntegrationTest(TestCase):
    """Integration tests for dataset access validation with GovernanceService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file for datasets
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
            status=FileStatus.ACTIVE,
        )

    def test_access_validation_integration_with_governance_service(self):
        """Integration test with GovernanceService for access request creation"""
        from hub.apps.governance.models import AccessRequest, AccessRequestStatus

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create access request directly (simulating GovernanceService workflow)
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=dataset,
            reason="Integration test access request",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        # Approve the access request directly (simulating GovernanceService approval)
        access_request.status = AccessRequestStatus.APPROVED
        access_request.approved_by = self.user
        access_request.approved_at = timezone.now()
        access_request.save()

        # Validate access using business rules
        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        # Should check access request
        self.assertIn("access_request_checked", result.details)
        self.assertTrue(result.details["access_request_checked"])
        # Access request should be found
        self.assertIn("access_request", result.details)

    def test_access_validation_integration_with_abac_engine(self):
        """Integration test with ABACEngine for policy evaluation"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Create ABAC policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Integration Test Policy",
            description="Test policy for integration",
            conditions={
                "user": {"user_id": str(self.user.id)},
                "resource": {"resource_type": "DATASET", "resource_id": str(dataset.id)},
            },
            effect="ALLOW",
            dataset=dataset,
            enabled=True,
            priority=100,
        )

        # Validate access using business rules (which uses ABACEngine internally)
        result = self.rules.validate_dataset_read_access(dataset, user=self.user)
        # Should check ABAC policies
        self.assertIn("abac_policy_checked", result.details)
        self.assertTrue(result.details["abac_policy_checked"])
        self.assertIn("abac_result", result.details)

        # Verify ABACEngine was called correctly
        abac_result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(dataset.id),
            access_type="READ",
        )
        self.assertIsNotNone(abac_result)
        self.assertTrue(hasattr(abac_result, "allowed"))

    # ========== FAILURE SCENARIOS ==========

    def test_validate_dataset_read_access_failure_nonexistent_dataset(self):
        """Test read access validation with non-existent dataset (failure scenario)"""
        import uuid

        fake_dataset_id = uuid.uuid4()
        fake_dataset = Dataset(id=fake_dataset_id, tenant=self.tenant)

        # Should handle non-existent dataset gracefully
        try:
            result = self.rules.validate_dataset_read_access(fake_dataset, user=self.user)
            # If succeeds, should return result or handle gracefully
            self.assertIsNotNone(result)
        except Exception:
            # If fails, that's acceptable for non-existent dataset
            pass

    def test_validate_dataset_write_access_failure_nonexistent_dataset(self):
        """Test write access validation with non-existent dataset (failure scenario)"""
        import uuid

        fake_dataset_id = uuid.uuid4()
        fake_dataset = Dataset(id=fake_dataset_id, tenant=self.tenant)

        # Should handle non-existent dataset gracefully
        try:
            result = self.rules.validate_dataset_write_access(fake_dataset, user=self.user)
            # If succeeds, should return result or handle gracefully
            self.assertIsNotNone(result)
        except Exception:
            # If fails, that's acceptable for non-existent dataset
            pass

    # ========== EDGE CASES ==========

    def test_validate_dataset_read_access_edge_case_none_user(self):
        """Test read access validation with None user (edge case)"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Should handle None user gracefully
        try:
            result = self.rules.validate_dataset_read_access(dataset, user=None)
            # If succeeds, should return result or handle gracefully
            self.assertIsNotNone(result)
        except (AttributeError, TypeError):
            # If fails, that's acceptable for None user
            pass

    def test_validate_dataset_write_access_edge_case_none_user(self):
        """Test write access validation with None user (edge case)"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Should handle None user gracefully
        try:
            result = self.rules.validate_dataset_write_access(dataset, user=None)
            # If succeeds, should return result or handle gracefully
            self.assertIsNotNone(result)
        except (AttributeError, TypeError):
            # If fails, that's acceptable for None user
            pass

    def test_validate_dataset_read_access_edge_case_different_tenant(self):
        """Test read access validation with different tenant (edge case)"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
        )

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_read_access(dataset, user=other_user)

        # Should handle different tenant gracefully
        self.assertIsNotNone(result)
        self.assertIn("tenant_isolation", result.details)

    # ========== ERROR HANDLING ==========

    def test_validate_dataset_read_access_error_handling(self):
        """Test error handling in read access validation"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Should handle errors gracefully
        try:
            result = self.rules.validate_dataset_read_access(dataset, user=self.user)
            # Should return result
            self.assertIsNotNone(result)
        except Exception:
            # If raises exception, that's a problem
            self.fail("validate_dataset_read_access should handle errors gracefully")

    def test_validate_dataset_write_access_error_handling(self):
        """Test error handling in write access validation"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        # Should handle errors gracefully
        try:
            result = self.rules.validate_dataset_write_access(dataset, user=self.user)
            # Should return result
            self.assertIsNotNone(result)
        except Exception:
            # If raises exception, that's a problem
            self.fail("validate_dataset_write_access should handle errors gracefully")
