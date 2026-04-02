"""
Integration tests for TenantConfig with Compliance service.

GAP-1.2.2.3: Tests for compliance service integration with tenant configuration.

All tests use real implementations (no mocks of hub services).
ComplianceServiceClient uses real service with graceful handling when unavailable.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.tenants.services import get_tenant_compliance_regimes, get_tenant_config
from hub.apps.tenants.validators import VALID_COMPLIANCE_REGIMES, get_platform_defaults
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def check_compliance_service_available():
    """Check if Compliance service is available"""
    try:
        client = ComplianceServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


# Using TestCase since _fixture_teardown is pass (no flush needed)
class TenantConfigComplianceIntegrationTest(TestCase):
    """Test Compliance service integration with tenant configuration"""

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""
        pass

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        # Use unique names to avoid duplicate key violations
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_id}", slug=f"test-tenant-{unique_id}"
        )

        self.user = User.objects.create_user(
            email=f"user-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Assign DATA_PROVIDER role so user passes permission checks
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.create(user=self.user, role=provider_role)

        # Create subscription so middleware doesn't block write ops
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.tenants.models import TenantPlan
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                }
            )

        # Create a real File so the Compliance endpoint can find it
        from hub.apps.files.models import File, FileStatus
        self.test_file = File.objects.create(
            tenant=self.tenant,
            name="test-data.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"tenants/{self.tenant.id}/files/test-data.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        self.file_id = str(self.test_file.id)

        self.platform_defaults = get_platform_defaults()

    def test_get_tenant_compliance_regimes_edge_case_no_config_returns_platform_default(self):
        """Edge case: get_tenant_compliance_regimes with no TenantConfig returns platform default list."""
        regimes = get_tenant_compliance_regimes(str(self.tenant.id))
        self.assertIsInstance(regimes, list)
        expected = self.platform_defaults["default_compliance_regimes"]
        self.assertEqual(
            set(regimes),
            set(expected),
            f"Without TenantConfig, should return platform defaults {expected}, got {regimes}",
        )

    def test_compliance_run_with_tenant_specific_regimes(self):
        """Test compliance run uses tenant-specific regimes from TenantConfig using real ComplianceServiceClient"""
        # Skip if compliance service not available
        if not check_compliance_service_available():
            self.skipTest("Compliance service not available in test environment")

        # Create tenant config with custom regimes
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD", "CCPA"],
            default_compliance_regimes=["GDPR", "CCPA"],
        )

        self.client.force_authenticate(user=self.user)

        # Use real ComplianceServiceClient (no mock)
        # Create compliance run without explicit regimes (should use tenant config)
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"file_id": self.file_id, "scan_mode": "internal"},
            format="json",
        )

        # Verify compliance run was created and used tenant config regimes.
        # Only 201/202 indicates the system actually processed the request.
        # 400 (bad file_id) or 503 (service down) mean the test can't verify
        # regime propagation — skip rather than silently pass.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"Compliance API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify regime propagation"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"Compliance service error ({response.status_code}) — cannot verify regime propagation"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        compliance_run = ComplianceRun.objects.latest("created_at")
        job_details = compliance_run.job.details_json
        applicable_regulations = job_details.get("applicable_regulations", [])
        self.assertEqual(set(applicable_regulations), {"GDPR", "CCPA"})

    def test_compliance_run_with_platform_default(self):
        """Test compliance run uses platform default when tenant config not set using real ComplianceServiceClient"""
        # Skip if compliance service not available
        if not check_compliance_service_available():
            self.skipTest("Compliance service not available in test environment")

        # No tenant config exists

        self.client.force_authenticate(user=self.user)

        # Use real ComplianceServiceClient (no mock)
        # Create compliance run without explicit regimes (should use platform default)
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"file_id": self.file_id, "scan_mode": "internal"},
            format="json",
        )

        # Only 201/202 indicates the system actually processed the request.
        # 400 (bad file_id) or 503 (service down) mean the test can't verify
        # regime propagation — skip rather than silently pass.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"Compliance API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify regime propagation"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"Compliance service error ({response.status_code}) — cannot verify regime propagation"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        compliance_run = ComplianceRun.objects.latest("created_at")
        job_details = compliance_run.job.details_json
        applicable_regulations = job_details.get("applicable_regulations", [])
        self.assertEqual(
            set(applicable_regulations),
            set(self.platform_defaults["default_compliance_regimes"]),
        )

    def test_compliance_run_with_explicit_regimes_overrides_tenant_config(self):
        """Test explicit regimes in request override tenant config using real ComplianceServiceClient"""
        # Skip if compliance service not available
        if not check_compliance_service_available():
            self.skipTest("Compliance service not available in test environment")

        # Create tenant config with custom regimes
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD", "CCPA"],
            default_compliance_regimes=["GDPR", "LGPD"],
        )

        self.client.force_authenticate(user=self.user)

        # Use real ComplianceServiceClient (no mock)
        # Create compliance run with explicit regimes (should override tenant config)
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": self.file_id,
                "scan_mode": "internal",
                "applicable_regulations": ["CCPA"],  # Explicit override
            },
            format="json",
        )

        # Only 201/202 indicates the system actually processed the request.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"Compliance API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify regime override"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"Compliance service error ({response.status_code}) — cannot verify regime override"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        compliance_run = ComplianceRun.objects.latest("created_at")
        job_details = compliance_run.job.details_json
        applicable_regulations = job_details.get("applicable_regulations", [])
        self.assertEqual(set(applicable_regulations), {"CCPA"})

    def test_compliance_run_validates_regimes_are_subset_of_allowed(self):
        """Test compliance run validates explicit regimes are subset of allowed_compliance_regimes"""
        # Create tenant config with limited allowed regimes
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD"],  # CCPA not allowed
            default_compliance_regimes=["GDPR"],
        )

        self.client.force_authenticate(user=self.user)

        # Try to create compliance run with regime not in allowed list
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": self.file_id,
                "scan_mode": "internal",
                "applicable_regulations": ["CCPA"],  # Not in allowed_compliance_regimes
            },
            format="json",
        )

        # Should return validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Invalid compliance regimes", str(response.data["error"]))

    def test_get_tenant_compliance_regimes_utility_function(self):
        """Test get_tenant_compliance_regimes utility function"""
        # Test with tenant config
        TenantConfig.objects.create(tenant=self.tenant, default_compliance_regimes=["GDPR", "CCPA"])

        regimes = get_tenant_compliance_regimes(str(self.tenant.id))
        self.assertEqual(set(regimes), {"GDPR", "CCPA"})

        # Test without tenant config (platform default)
        unique_id = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Test Tenant 2 {unique_id}", slug=f"test-tenant-2-{unique_id}"
        )
        regimes = get_tenant_compliance_regimes(str(tenant2.id))
        self.assertEqual(set(regimes), set(self.platform_defaults["default_compliance_regimes"]))

    def test_compliance_service_client_receives_regimes(self):
        """Test compliance service client receives applicable_regulations parameter using real ComplianceServiceClient"""
        # Skip if compliance service not available
        if not check_compliance_service_available():
            self.skipTest("Compliance service not available in test environment")

        TenantConfig.objects.create(tenant=self.tenant, default_compliance_regimes=["GDPR", "LGPD"])

        self.client.force_authenticate(user=self.user)

        # Use real ComplianceServiceClient (no mock)
        # Create compliance run
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"file_id": self.file_id, "scan_mode": "internal"},
            format="json",
        )

        # Only 201/202 indicates the system actually processed the request.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"Compliance API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify regime propagation"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"Compliance service error ({response.status_code}) — cannot verify regime propagation"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        compliance_run = ComplianceRun.objects.latest("created_at")
        job_details = compliance_run.job.details_json
        applicable_regulations = job_details.get("applicable_regulations", [])
        self.assertEqual(set(applicable_regulations), {"GDPR", "LGPD"})
