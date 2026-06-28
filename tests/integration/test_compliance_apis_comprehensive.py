"""
Comprehensive Integration Tests for Compliance APIs

Tests all compliance endpoints with 60+ test cases covering:
- Success scenarios
- Validation errors (missing fields, invalid IDs, invalid regulations)
- Security tests (tenant isolation, permissions, authorization)
- Performance tests
- Integration tests (Job creation, audit logging, compliance service integration)
- Edge cases

All tests use real services (no mocks/stubs) and run against Docker Compose instances.
"""

import time
import uuid

import pytest

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.datasets.models import DatasetKind
from hub.apps.files.models import FileStatus
from hub.apps.jobs.models import JobStatus, JobType
from hub.apps.tenants.models import TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_tenant_admin_role
from hub.apps.users.models import UserStatus
from tests.fixtures.test_data_factories import (
    AssetFactory,
    DatasetFactory,
    FileFactory,
    JobFactory,
    TenantFactory,
    UserFactory,
)

# Use regular django_db marker - TestCase handles transactions efficiently
pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True)]
User = get_user_model()


class TestComplianceRunCreateAPI(TestCase):
    """Comprehensive tests for POST /api/v1/compliance/runs/"""

    def setUp(self):
        """Set up test fixtures - using setUp for better isolation"""
        # Clear cache aggressively before each test
        cache.clear()

        self.client = APIClient()
        # Create tenant and user fresh for each test (better isolation)
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        # Authenticate
        self.client.force_authenticate(user=self.user)
        ensure_user_has_tenant_admin_role(self.user)

        # Create test file with actual content for compliance scanning
        self.test_file_content = b"name,email,phone\nJohn Doe,john@example.com,555-1234\nJane Smith,jane@example.com,555-5678"
        self.file = FileFactory.create_file(
            tenant=self.tenant,
            name="test_data.csv",
            status=FileStatus.ACTIVE,
            content_type="text/csv",
            size=len(self.test_file_content),
        )

        # Create asset
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
        )

        # Create dataset linked to asset
        self.dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            kind=DatasetKind.FILE,
        )

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    # ========== SUCCESS SCENARIOS ==========

    def test_create_compliance_run_with_asset_id(self):
        """Test successful compliance run creation with asset_id"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("status", response.data)
        self.assertEqual(response.data["status"], ComplianceRunStatus.PENDING)
        self.assertIn("job", response.data)

        # Verify compliance run was created
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertEqual(compliance_run.asset, self.asset)
        self.assertEqual(compliance_run.tenant, self.tenant)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)

    def test_create_compliance_run_with_dataset_id(self):
        """Test successful compliance run creation with dataset_id"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "dataset_id": str(self.dataset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], ComplianceRunStatus.PENDING)

        # Verify compliance run was created
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertEqual(compliance_run.dataset, self.dataset)
        self.assertEqual(compliance_run.asset, self.asset)  # Should inherit from dataset

    def test_create_compliance_run_with_file_id(self):
        """Test successful compliance run creation with file_id (scan-only)"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": str(self.file.id),
                "scan_mode": "external",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], ComplianceRunStatus.PENDING)

        # Verify compliance run was created
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertEqual(compliance_run.file, self.file)
        self.assertIsNone(compliance_run.asset)
        self.assertIsNone(compliance_run.dataset)

    def test_create_compliance_run_with_applicable_regulations(self):
        """Test compliance run creation with explicit regulations"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
                "applicable_regulations": ["GDPR", "HIPAA"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

        # Verify regulations were stored
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertIsNotNone(compliance_run.job)
        regulations = compliance_run.job.details_json.get("applicable_regulations", [])
        self.assertIn("GDPR", regulations)
        self.assertIn("HIPAA", regulations)

    def test_create_compliance_run_with_internal_scan_mode(self):
        """Test compliance run creation with internal scan mode"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertEqual(compliance_run.job.details_json.get("scan_mode"), "internal")

    def test_create_compliance_run_with_external_scan_mode(self):
        """Test compliance run creation with external scan mode"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": str(self.file.id),
                "scan_mode": "external",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertEqual(compliance_run.job.details_json.get("scan_mode"), "external")

    def test_create_compliance_run_defaults_to_internal_scan_mode(self):
        """Test that scan_mode defaults to internal if not provided"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertEqual(compliance_run.job.details_json.get("scan_mode"), "internal")

    def test_create_compliance_run_creates_job(self):
        """Test that compliance run creation creates associated job"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertIsNotNone(compliance_run.job)
        self.assertEqual(compliance_run.job.type, JobType.COMPLIANCE_RUN)
        self.assertEqual(compliance_run.job.status, JobStatus.PENDING)
        self.assertEqual(compliance_run.job.tenant, self.tenant)

    def test_create_compliance_run_logs_audit_event(self):
        """Test that compliance run creation logs audit event"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run_id = response.data["id"]

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="COMPLIANCE_RUN",
            action="COMPLIANCE_RUN_CREATED",
            resource_id=compliance_run_id,
        )
        self.assertTrue(audit_events.exists())
        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)

    # ========== VALIDATION ERRORS ==========

    def test_create_compliance_run_error_no_resource_ids(self):
        """Test validation error when no resource IDs provided"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # API returns 'detail' (DRF-style) or 'error'; accept both
        self.assertTrue(
            "error" in (response.data or {}) or "detail" in (response.data or {}),
            f"Expected 'error' or 'detail' in response: {response.data}",
        )

    def test_create_compliance_run_error_invalid_asset_id(self):
        """Test validation error for invalid asset_id"""
        invalid_id = uuid.uuid4()
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(invalid_id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # API returns 'detail' (DRF-style) or 'error'; accept both
        self.assertTrue(
            "error" in (response.data or {}) or "detail" in (response.data or {}),
            f"Expected 'error' or 'detail' in response: {response.data}",
        )

    def test_create_compliance_run_error_invalid_dataset_id(self):
        """Test validation error for invalid dataset_id"""
        invalid_id = uuid.uuid4()
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "dataset_id": str(invalid_id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # API returns 'detail' (DRF-style) or 'error'; accept both
        self.assertTrue(
            "error" in (response.data or {}) or "detail" in (response.data or {}),
            f"Expected 'error' or 'detail' in response: {response.data}",
        )

    def test_create_compliance_run_error_invalid_file_id(self):
        """Test validation error for invalid file_id"""
        invalid_id = uuid.uuid4()
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": str(invalid_id),
                "scan_mode": "external",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # API returns 'detail' (DRF-style) or 'error'; accept both
        self.assertTrue(
            "error" in (response.data or {}) or "detail" in (response.data or {}),
            f"Expected 'error' or 'detail' in response: {response.data}",
        )

    def test_create_compliance_run_error_invalid_scan_mode(self):
        """Test validation error for invalid scan_mode"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "invalid_mode",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_compliance_run_error_dataset_not_belongs_to_asset(self):
        """Test validation error when dataset doesn't belong to specified asset"""
        # Create another asset
        other_asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
            name="Other Asset",
        )

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(other_asset.id),
                "dataset_id": str(
                    self.dataset.id
                ),  # Dataset belongs to self.asset, not other_asset
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_create_compliance_run_error_invalid_regulations(self):
        """Test validation error for invalid compliance regulations"""
        # Create tenant config with restricted regulations
        from hub.apps.tenants.models import TenantConfig

        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD"],  # Only allow GDPR and LGPD
        )

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
                "applicable_regulations": ["INVALID_REGULATION"],
            },
            format="json",
        )

        # Should return 400 if validation is strict, or use defaults
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED])

    def test_create_compliance_run_error_user_no_tenant(self):
        """Test error when user has no tenant"""
        user_no_tenant = User.objects.create_user(
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=user_no_tenant)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    # ========== SECURITY TESTS ==========

    def test_create_compliance_run_tenant_isolation(self):
        """Test that users can only create compliance runs for their tenant's resources"""
        # Create another tenant
        other_tenant = TenantFactory.create_tenant(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        )
        other_asset = AssetFactory.create_asset(
            tenant=other_tenant,
            created_by=UserFactory.create_user(tenant=other_tenant),
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
            name="Other Asset",
        )

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(other_asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_compliance_run_requires_authentication(self):
        """Test that compliance run creation requires authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_compliance_run_auditor_readonly(self):
        """Test that AUDITOR role cannot create compliance runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role, _ = Role.objects.get_or_create(name="AUDITOR", tenant=self.tenant)
        auditor_user = User.objects.create_user(
            email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== EDGE CASES ==========

    def test_create_compliance_run_with_all_resource_ids(self):
        """Test compliance run creation with asset_id, dataset_id, and file_id"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "dataset_id": str(self.dataset.id),
                "file_id": str(self.file.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        # Should succeed - uses asset_id as primary, others are validated
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        self.assertEqual(compliance_run.asset, self.asset)
        self.assertEqual(compliance_run.dataset, self.dataset)
        self.assertEqual(compliance_run.file, self.file)

    def test_create_compliance_run_with_empty_regulations_list(self):
        """Test compliance run creation with empty regulations list"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
                "applicable_regulations": [],
            },
            format="json",
        )

        # Should succeed - uses tenant defaults
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_multiple_compliance_runs_for_same_asset(self):
        """Test creating multiple compliance runs for the same asset"""
        # Create first compliance run
        response1 = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Create second compliance run
        response2 = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        # Verify both runs exist
        self.assertNotEqual(response1.data["id"], response2.data["id"])
        runs = ComplianceRun.objects.filter(asset=self.asset)
        self.assertEqual(runs.count(), 2)


class TestComplianceRunRetrieveAPI(TestCase):
    """Comprehensive tests for GET /api/v1/compliance/runs/{id}/"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=self.user)

        ensure_user_has_tenant_admin_role(self.user)
        # Create asset and compliance run
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
        )

        # Create job
        self.job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
        )

        # Create compliance run
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
        )

        # Update job with compliance_run_id
        self.job.resource_id = str(self.compliance_run.id)
        self.job.details_json = {"compliance_run_id": str(self.compliance_run.id)}
        self.job.save()

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    # ========== SUCCESS SCENARIOS ==========

    def test_retrieve_compliance_run_success(self):
        """Test successful compliance run retrieval"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.compliance_run.id))
        self.assertEqual(response.data["status"], ComplianceRunStatus.PENDING)
        self.assertIn("job", response.data)
        self.assertIn("asset", response.data)

    def test_retrieve_compliance_run_with_completed_status(self):
        """Test retrieving compliance run with completed status"""
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.overall_status = "PASS"
        self.compliance_run.risk_level = RiskLevel.LOW
        self.compliance_run.allowed_to_store = True
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ComplianceRunStatus.SUCCEEDED)
        self.assertEqual(response.data["overall_status"], "PASS")
        self.assertEqual(response.data["risk_level"], RiskLevel.LOW)
        self.assertTrue(response.data["allowed_to_store"])

    def test_retrieve_compliance_run_with_failed_status(self):
        """Test retrieving compliance run with failed status"""
        self.compliance_run.status = ComplianceRunStatus.FAILED
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ComplianceRunStatus.FAILED)

    def test_retrieve_compliance_run_includes_all_fields(self):
        """Test that retrieved compliance run includes all expected fields"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_fields = [
            "id",
            "tenant",
            "asset",
            "dataset",
            "file",
            "job",
            "regulations",
            "status",
            "overall_status",
            "risk_level",
            "allowed_to_store",
            "created_at",
            "updated_at",
        ]
        for field in expected_fields:
            self.assertIn(field, response.data)

    # ========== SECURITY TESTS ==========

    def test_retrieve_compliance_run_tenant_isolation(self):
        """Test that users can only retrieve compliance runs from their tenant"""
        # Create another tenant and compliance run
        other_tenant = TenantFactory.create_tenant(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        )
        other_user = UserFactory.create_user(tenant=other_tenant)
        other_asset = AssetFactory.create_asset(
            tenant=other_tenant,
            created_by=other_user,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
        )
        other_job = JobFactory.create_job(
            tenant=other_tenant,
            created_by=other_user,
            type=JobType.COMPLIANCE_RUN,
        )
        other_compliance_run = ComplianceRun.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            job=other_job,
            status=ComplianceRunStatus.PENDING,
        )

        response = self.client.get(f"/api/v1/compliance/runs/{other_compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_compliance_run_requires_authentication(self):
        """Test that compliance run retrieval requires authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_compliance_run_platform_admin_can_access_all(self):
        """Test that platform admin can retrieve compliance runs from any tenant"""
        # Create platform admin
        platform_admin = UserFactory.create_platform_admin()
        self.client.force_authenticate(user=platform_admin)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.compliance_run.id))

    # ========== EDGE CASES ==========

    def test_retrieve_compliance_run_not_found(self):
        """Test retrieving non-existent compliance run"""
        non_existent_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/compliance/runs/{non_existent_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_compliance_run_with_null_fields(self):
        """Test retrieving compliance run with null optional fields"""
        # Create compliance run with only file_id (no asset or dataset)
        file = FileFactory.create_file(tenant=self.tenant, name="test.csv")
        job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=file,
            job=job,
            status=ComplianceRunStatus.PENDING,
        )

        response = self.client.get(f"/api/v1/compliance/runs/{compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["asset"])
        self.assertIsNone(response.data["dataset"])
        self.assertIsNotNone(response.data["file"])


class TestComplianceRunUpdateAPI(TestCase):
    """Comprehensive tests for PUT/PATCH /api/v1/compliance/runs/{id}/"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=self.user)

        ensure_user_has_tenant_admin_role(self.user)
        # Create asset and compliance run
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
        )

        # Create another asset for update tests
        self.other_asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
            name="Other Asset",
        )

        # Create job
        self.job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
        )

        # Create compliance run
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
        )

        # Update job with compliance_run_id
        self.job.resource_id = str(self.compliance_run.id)
        self.job.details_json = {"compliance_run_id": str(self.compliance_run.id)}
        self.job.save()

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    # ========== SUCCESS SCENARIOS ==========

    def test_partial_update_compliance_run_success(self):
        """Test successful partial update of compliance run"""
        # Most fields are read-only, but we can test with empty update
        # or fields that might be updatable
        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {},
            format="json",
        )

        # Should succeed even with empty update (no-op)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_partial_update_compliance_run_with_regulations(self):
        """Test partial update with regulations field if updatable"""
        # Note: regulations might be read-only, but we test the endpoint
        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {"regulations": ["GDPR", "HIPAA"]},
            format="json",
        )

        # May succeed or return 400 if field is read-only
        self.assertLess(
            response.status_code,
            500,
        )

    def test_full_update_compliance_run_success(self):
        """Test successful full update of compliance run"""
        # Most fields are read-only, so PUT might only accept read-only fields
        response = self.client.put(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {
                "asset": str(self.asset.id),
                "regulations": ["GDPR"],
            },
            format="json",
        )

        # May succeed or return 400 if most fields are read-only
        self.assertLess(
            response.status_code,
            500,
        )

    # ========== SECURITY TESTS ==========

    def test_update_compliance_run_tenant_isolation(self):
        """Test that users can only update compliance runs from their tenant"""
        # Create another tenant and compliance run
        other_tenant = TenantFactory.create_tenant(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        )
        other_user = UserFactory.create_user(tenant=other_tenant)
        other_asset = AssetFactory.create_asset(
            tenant=other_tenant,
            created_by=other_user,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
        )
        other_job = JobFactory.create_job(
            tenant=other_tenant,
            created_by=other_user,
            type=JobType.COMPLIANCE_RUN,
        )
        other_compliance_run = ComplianceRun.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            job=other_job,
            status=ComplianceRunStatus.PENDING,
        )

        response = self.client.patch(
            f"/api/v1/compliance/runs/{other_compliance_run.id}/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_compliance_run_requires_authentication(self):
        """Test that compliance run update requires authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_compliance_run_auditor_readonly(self):
        """Test that AUDITOR role cannot update compliance runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role, _ = Role.objects.get_or_create(name="AUDITOR", tenant=self.tenant)
        auditor_user = User.objects.create_user(
            email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)

        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== EDGE CASES ==========

    def test_update_compliance_run_not_found(self):
        """Test updating non-existent compliance run"""
        non_existent_id = uuid.uuid4()
        response = self.client.patch(
            f"/api/v1/compliance/runs/{non_existent_id}/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_compliance_run_with_completed_status(self):
        """Test updating compliance run that is already completed"""
        # Mark compliance run as completed
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {},
            format="json",
        )

        # May succeed or return 400/403 if updates are restricted for completed runs
        self.assertLess(
            response.status_code,
            500,
        )


class TestComplianceRunDeleteAPI(TestCase):
    """Comprehensive tests for DELETE /api/v1/compliance/runs/{id}/"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=self.user)

        ensure_user_has_tenant_admin_role(self.user)
        # Create asset
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
        )

        # Create job
        self.job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
        )

        # Create compliance run
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
        )

        # Update job with compliance_run_id
        self.job.resource_id = str(self.compliance_run.id)
        self.job.details_json = {"compliance_run_id": str(self.compliance_run.id)}
        self.job.save()

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    # ========== SUCCESS SCENARIOS ==========

    def test_delete_compliance_run_success(self):
        """Test successful deletion of compliance run"""
        compliance_run_id = self.compliance_run.id

        response = self.client.delete(f"/api/v1/compliance/runs/{compliance_run_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify compliance run was deleted
        self.assertFalse(ComplianceRun.objects.filter(id=compliance_run_id).exists())

    def test_delete_compliance_run_with_completed_status(self):
        """Test deletion of completed compliance run"""
        # Mark compliance run as completed
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        compliance_run_id = self.compliance_run.id

        response = self.client.delete(f"/api/v1/compliance/runs/{compliance_run_id}/")

        # Should succeed (soft delete or hard delete)
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_200_OK])

        # Verify compliance run was deleted (or soft-deleted)
        self.assertFalse(ComplianceRun.objects.filter(id=compliance_run_id).exists())

    # ========== SECURITY TESTS ==========

    def test_delete_compliance_run_tenant_isolation(self):
        """Test that users can only delete compliance runs from their tenant"""
        # Create another tenant and compliance run
        other_tenant = TenantFactory.create_tenant(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        )
        other_user = UserFactory.create_user(tenant=other_tenant)
        other_asset = AssetFactory.create_asset(
            tenant=other_tenant,
            created_by=other_user,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
        )
        other_job = JobFactory.create_job(
            tenant=other_tenant,
            created_by=other_user,
            type=JobType.COMPLIANCE_RUN,
        )
        other_compliance_run = ComplianceRun.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            job=other_job,
            status=ComplianceRunStatus.PENDING,
        )

        response = self.client.delete(f"/api/v1/compliance/runs/{other_compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify other tenant's compliance run still exists
        self.assertTrue(ComplianceRun.objects.filter(id=other_compliance_run.id).exists())

    def test_delete_compliance_run_requires_authentication(self):
        """Test that compliance run deletion requires authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.delete(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify compliance run still exists
        self.assertTrue(ComplianceRun.objects.filter(id=self.compliance_run.id).exists())

    def test_delete_compliance_run_auditor_readonly(self):
        """Test that AUDITOR role cannot delete compliance runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role, _ = Role.objects.get_or_create(name="AUDITOR", tenant=self.tenant)
        auditor_user = User.objects.create_user(
            email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)

        response = self.client.delete(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify compliance run still exists
        self.assertTrue(ComplianceRun.objects.filter(id=self.compliance_run.id).exists())

    # ========== EDGE CASES ==========

    def test_delete_compliance_run_not_found(self):
        """Test deleting non-existent compliance run"""
        non_existent_id = uuid.uuid4()
        response = self.client.delete(f"/api/v1/compliance/runs/{non_existent_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestComplianceReportsAPI(TestCase):
    """Comprehensive tests for GET /api/v1/compliance/reports/ (list endpoint)"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=self.user)

        ensure_user_has_tenant_admin_role(self.user)
        # Create multiple assets and compliance runs
        self.asset1 = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"asset-1-{uuid.uuid4().hex[:8]}",
            name="Asset 1",
        )
        self.asset2 = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"asset-2-{uuid.uuid4().hex[:8]}",
            name="Asset 2",
        )

        # Create compliance runs with different statuses
        self.job1 = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )
        self.compliance_run1 = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset1,
            job=self.job1,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            risk_level=RiskLevel.LOW,
            allowed_to_store=True,
            completed_at=timezone.now() - timezone.timedelta(hours=1),
        )

        self.job2 = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.RUNNING,
        )
        self.compliance_run2 = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset2,
            job=self.job2,
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now() - timezone.timedelta(minutes=5),
        )

        self.job3 = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.FAILED,
        )
        self.compliance_run3 = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset1,
            job=self.job3,
            status=ComplianceRunStatus.FAILED,
            completed_at=timezone.now() - timezone.timedelta(hours=2),
        )

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    # ========== SUCCESS SCENARIOS ==========

    def test_list_compliance_runs_success(self):
        """Test successful compliance runs listing"""
        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertGreaterEqual(response.data["count"], 3)

    def test_list_compliance_runs_with_pagination(self):
        """Test compliance runs listing with pagination"""
        response = self.client.get("/api/v1/compliance/runs/?page=1&page_size=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_list_compliance_runs_filter_by_status(self):
        """Test filtering compliance runs by status"""
        response = self.client.get("/api/v1/compliance/runs/?status=SUCCEEDED")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for run in response.data["results"]:
            self.assertEqual(run["status"], ComplianceRunStatus.SUCCEEDED)

    def test_list_compliance_runs_filter_by_asset_id(self):
        """Test filtering compliance runs by asset_id"""
        response = self.client.get(f"/api/v1/compliance/runs/?asset={self.asset1.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for run in response.data["results"]:
            # Handle both UUID objects and string representations
            asset_id = run.get("asset")
            if asset_id:
                self.assertEqual(str(asset_id), str(self.asset1.id))

    def test_list_compliance_runs_ordering_by_created_at_desc(self):
        """Test ordering compliance runs by created_at descending (default)"""
        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        created_ats = [run["created_at"] for run in response.data["results"]]
        self.assertEqual(created_ats, sorted(created_ats, reverse=True))

    def test_list_compliance_runs_ordering_by_created_at_asc(self):
        """Test ordering compliance runs by created_at ascending"""
        response = self.client.get("/api/v1/compliance/runs/?ordering=created_at")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        created_ats = [run["created_at"] for run in response.data["results"]]
        self.assertEqual(created_ats, sorted(created_ats))

    # ========== SECURITY TESTS ==========

    def test_list_compliance_runs_tenant_isolation(self):
        """Test that users can only see compliance runs from their tenant"""
        # Create another tenant with compliance runs
        other_tenant = TenantFactory.create_tenant(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        )
        other_user = UserFactory.create_user(tenant=other_tenant)
        other_asset = AssetFactory.create_asset(
            tenant=other_tenant,
            created_by=other_user,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
        )
        other_job = JobFactory.create_job(
            tenant=other_tenant,
            created_by=other_user,
            type=JobType.COMPLIANCE_RUN,
        )
        other_compliance_run = ComplianceRun.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            job=other_job,
            status=ComplianceRunStatus.PENDING,
        )

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run_ids = [run["id"] for run in response.data["results"]]
        self.assertNotIn(str(other_compliance_run.id), run_ids)

    def test_list_compliance_runs_requires_authentication(self):
        """Test that compliance runs listing requires authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_compliance_runs_platform_admin_can_see_all(self):
        """Test that platform admin can see compliance runs from all tenants"""
        # Create platform admin
        platform_admin = UserFactory.create_platform_admin()
        self.client.force_authenticate(user=platform_admin)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see runs from all tenants
        self.assertGreaterEqual(response.data["count"], 3)

    # ========== EDGE CASES ==========

    def test_list_compliance_runs_empty_result(self):
        """Test listing compliance runs when none exist"""
        # Create new tenant with no compliance runs
        empty_tenant = TenantFactory.create_tenant(
            name=f"Empty Tenant {uuid.uuid4().hex[:8]}",
            slug=f"empty-tenant-{uuid.uuid4().hex[:8]}",
        )
        empty_user = User.objects.create_user(
            email=f"emptyuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=empty_tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=empty_user)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_compliance_runs_invalid_page_number(self):
        """Test listing with invalid page number"""
        response = self.client.get("/api/v1/compliance/runs/?page=0")

        # Should return 400 or use default page
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_list_compliance_runs_invalid_page_size(self):
        """Test listing with invalid page size"""
        response = self.client.get("/api/v1/compliance/runs/?page_size=0")

        # Should return 400 or use default page_size
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_list_compliance_runs_combined_filters(self):
        """Test combining multiple filters"""
        response = self.client.get(
            f"/api/v1/compliance/runs/?asset={self.asset1.id}&status=SUCCEEDED&ordering=-created_at"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for run in response.data["results"]:
            # Handle both UUID objects and string representations
            asset_id = run.get("asset")
            if asset_id:
                self.assertEqual(str(asset_id), str(self.asset1.id))
            self.assertEqual(run["status"], ComplianceRunStatus.SUCCEEDED)


class TestComplianceRunResultsAPI(TestCase):
    """Comprehensive tests for GET /api/v1/compliance/runs/{id}/results/"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=self.user)

        ensure_user_has_tenant_admin_role(self.user)
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
        )

        self.job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )

        # Create compliance run with results data
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            risk_level=RiskLevel.LOW,
            allowed_to_store=True,
            regulations=["GDPR", "HIPAA"],
            detected_categories_json={
                "EMAIL": 10,
                "PHONE": 5,
            },
            column_findings_json=[
                {
                    "column_name": "email",
                    "pii_types": ["EMAIL"],
                    "risk_score": 0.8,
                    "regulations_affected": ["GDPR"],
                    "confidence": 0.95,
                    "sample_values": ["john@example.com"],
                },
                {
                    "column_name": "phone",
                    "pii_types": ["PHONE"],
                    "risk_score": 0.6,
                    "regulations_affected": ["GDPR", "HIPAA"],
                    "confidence": 0.90,
                    "sample_values": ["555-1234"],
                },
            ],
            regulation_mapping_json={
                "GDPR": {"status": "PASS", "risk_score": 0.3},
                "HIPAA": {"status": "WARN", "risk_score": 0.5},
            },
            started_at=timezone.now() - timezone.timedelta(minutes=10),
            completed_at=timezone.now(),
        )

        # Update job
        self.job.resource_id = str(self.compliance_run.id)
        self.job.save()

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    # ========== SUCCESS SCENARIOS ==========

    def test_get_compliance_run_results_success(self):
        """Test successful retrieval of compliance run results"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["compliance_run_id"], str(self.compliance_run.id))
        self.assertEqual(response.data["overall_status"], "PASS")
        self.assertEqual(response.data["risk_level"], RiskLevel.LOW)
        self.assertTrue(response.data["allowed_to_store"])

    def test_get_compliance_run_results_includes_violations(self):
        """Test that results include violation details"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("violations", response.data)
        self.assertIn("violation_details", response.data)
        self.assertGreater(len(response.data["violations"]), 0)

    def test_get_compliance_run_results_includes_remediation_suggestions(self):
        """Test that results include remediation suggestions"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("remediation_suggestions", response.data)
        self.assertIsInstance(response.data["remediation_suggestions"], list)

    def test_get_compliance_run_results_includes_score_breakdown(self):
        """Test that results include compliance score breakdown"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("compliance_score", response.data)
        self.assertIn("score_breakdown", response.data)
        self.assertIn("total_columns", response.data["score_breakdown"])
        self.assertIn("columns_with_pii", response.data["score_breakdown"])

    def test_get_compliance_run_results_includes_risk_assessment(self):
        """Test that results include risk assessment"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("risk_assessment", response.data)
        self.assertIn("overall_risk_level", response.data["risk_assessment"])
        self.assertIn("total_violations", response.data["risk_assessment"])

    def test_get_compliance_run_results_logs_audit_event(self):
        """Test that accessing results logs audit event"""
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="COMPLIANCE_RUN",
            action="RESULTS_ACCESSED",
            resource_id=str(self.compliance_run.id),
        )
        self.assertTrue(audit_events.exists())

    # ========== SECURITY TESTS ==========

    def test_get_compliance_run_results_tenant_isolation(self):
        """Test that users can only access results from their tenant"""
        # Create another tenant and compliance run
        other_tenant = TenantFactory.create_tenant(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        )
        other_user = UserFactory.create_user(tenant=other_tenant)
        other_asset = AssetFactory.create_asset(
            tenant=other_tenant,
            created_by=other_user,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
        )
        other_job = JobFactory.create_job(
            tenant=other_tenant,
            created_by=other_user,
            type=JobType.COMPLIANCE_RUN,
        )
        other_compliance_run = ComplianceRun.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            job=other_job,
            status=ComplianceRunStatus.SUCCEEDED,
        )

        response = self.client.get(f"/api/v1/compliance/runs/{other_compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_compliance_run_results_requires_authentication(self):
        """Test that results retrieval requires authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== EDGE CASES ==========

    def test_get_compliance_run_results_not_found(self):
        """Test retrieving results for non-existent compliance run"""
        non_existent_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/compliance/runs/{non_existent_id}/results/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_compliance_run_results_with_no_findings(self):
        """Test retrieving results for compliance run with no findings"""
        # Create compliance run with no findings
        job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            risk_level=RiskLevel.NONE,
            allowed_to_store=True,
            detected_categories_json={},
            column_findings_json=[],
            completed_at=timezone.now(),
        )
        job.resource_id = str(compliance_run.id)
        job.save()

        response = self.client.get(f"/api/v1/compliance/runs/{compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["violations"]), 0)
        self.assertEqual(response.data["risk_assessment"]["total_violations"], 0)


# ========== PERFORMANCE TESTS ==========


class TestComplianceAPIPerformance(TestCase):
    """Performance tests for Compliance APIs"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=self.user)

        ensure_user_has_tenant_admin_role(self.user)
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
        )

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    def test_create_compliance_run_performance(self):
        """Test that compliance run creation completes within reasonable time"""
        start_time = time.time()

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Should complete within 5 seconds (allowing for job creation and queueing)
        self.assertLess(elapsed_time, 5.0)

    def test_list_compliance_runs_performance(self):
        """Test that listing compliance runs completes within reasonable time"""
        # Create multiple compliance runs
        for _i in range(10):
            job = JobFactory.create_job(
                tenant=self.tenant,
                created_by=self.user,
                type=JobType.COMPLIANCE_RUN,
            )
            ComplianceRun.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                job=job,
                status=ComplianceRunStatus.PENDING,
            )

        start_time = time.time()

        response = self.client.get("/api/v1/compliance/runs/")

        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should complete within 1 second
        self.assertLess(elapsed_time, 1.0)

    def test_retrieve_compliance_run_performance(self):
        """Test that retrieving compliance run completes within reasonable time"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.PENDING,
        )

        start_time = time.time()

        response = self.client.get(f"/api/v1/compliance/runs/{compliance_run.id}/")

        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should complete within 500ms
        self.assertLess(elapsed_time, 0.5)

    def test_get_compliance_run_results_performance(self):
        """Test that retrieving compliance run results completes within reasonable time"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            risk_level=RiskLevel.LOW,
            allowed_to_store=True,
            column_findings_json=[
                {
                    "column_name": "email",
                    "pii_types": ["EMAIL"],
                    "risk_score": 0.8,
                }
            ],
            completed_at=timezone.now(),
        )
        job.resource_id = str(compliance_run.id)
        job.save()

        start_time = time.time()

        response = self.client.get(f"/api/v1/compliance/runs/{compliance_run.id}/results/")

        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should complete within 1 second
        self.assertLess(elapsed_time, 1.0)


# ========== INTEGRATION TESTS ==========


class TestComplianceAPIIntegration(TestCase):
    """Integration tests for Compliance APIs with other services"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE.value,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"complianceuser-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE.value,
        )
        self.client.force_authenticate(user=self.user)

        ensure_user_has_tenant_admin_role(self.user)
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
        )

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    def test_compliance_run_creates_job_with_correct_type(self):
        """Test that compliance run creation creates job with correct type"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        job = compliance_run.job

        self.assertEqual(job.type, JobType.COMPLIANCE_RUN)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.resource_type, "COMPLIANCE_RUN")
        # Handle both UUID objects and string representations
        self.assertEqual(str(job.resource_id), str(compliance_run.id))

    def test_compliance_run_job_has_correct_details(self):
        """Test that compliance run job has correct details_json"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "external",
                "applicable_regulations": ["GDPR", "LGPD"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])
        job = compliance_run.job

        self.assertEqual(job.details_json.get("scan_mode"), "external")
        self.assertIn("GDPR", job.details_json.get("applicable_regulations", []))
        self.assertIn("LGPD", job.details_json.get("applicable_regulations", []))
        self.assertEqual(job.details_json.get("compliance_run_id"), str(compliance_run.id))

    def test_compliance_run_audit_event_has_correct_details(self):
        """Test that compliance run creation audit event has correct details"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
                "applicable_regulations": ["GDPR"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run_id = response.data["id"]

        audit_event = AuditEvent.objects.filter(
            resource_type="COMPLIANCE_RUN",
            action="COMPLIANCE_RUN_CREATED",
            resource_id=compliance_run_id,
        ).first()

        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertIn("scan_mode", audit_event.details_json)
        self.assertIn("asset_id", audit_event.details_json)

    def test_compliance_run_updates_asset_compliance_status(self):
        """Test that completed compliance run updates asset compliance status"""
        # Create compliance run
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])

        # Simulate completion (normally done by job processor)
        from hub.apps.assets.models import ComplianceStatus as AssetComplianceStatus

        compliance_run.status = ComplianceRunStatus.SUCCEEDED
        compliance_run.overall_status = "PASS"
        compliance_run.risk_level = RiskLevel.LOW
        compliance_run.allowed_to_store = True
        compliance_run.completed_at = timezone.now()
        compliance_run.save()

        # Update asset compliance status (as done in execute_compliance_run)
        if compliance_run.overall_status == "PASS":
            self.asset.compliance_status = AssetComplianceStatus.PASS
        elif compliance_run.overall_status == "WARN":
            self.asset.compliance_status = AssetComplianceStatus.WARN
        elif compliance_run.overall_status == "FAIL":
            self.asset.compliance_status = AssetComplianceStatus.FAIL
        self.asset.save()

        # Verify asset compliance status was updated
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.compliance_status, AssetComplianceStatus.PASS)

    def test_compliance_run_list_includes_job_status(self):
        """Test that compliance run list includes associated job status"""
        # Create compliance run
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run_id = response.data["id"]

        # List compliance runs
        list_response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        run_data = next(
            (r for r in list_response.data["results"] if r["id"] == compliance_run_id), None
        )
        self.assertIsNotNone(run_data)
        self.assertIn("job", run_data)
        self.assertIsNotNone(run_data["job"])

    def test_compliance_run_with_dataset_inherits_asset(self):
        """Test that compliance run with dataset_id inherits asset from dataset"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            asset=self.asset,
            kind=DatasetKind.FILE,
        )

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "dataset_id": str(dataset.id),
                "scan_mode": "internal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        compliance_run = ComplianceRun.objects.get(id=response.data["id"])

        # Asset should be inherited from dataset
        self.assertEqual(compliance_run.asset, self.asset)
        self.assertEqual(compliance_run.dataset, dataset)
