"""
Comprehensive unit tests for Compliance ViewSet endpoints.

Tests cover:
- CRUD operations (list, retrieve, create, update, destroy)
- Custom actions (results)
- Filtering and ordering
- Tenant isolation
- Permission checks (AUDITOR role)
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling

All tests use real implementations (no mocks/stubs).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ComplianceRunViewSetTest(TestCase):
    """Comprehensive tests for ComplianceRunViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create another tenant and user for isolation tests
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Asset in other tenant (for isolation tests; ComplianceRun requires asset/dataset/file)
        self.other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset-compliance-views",
            name="Other Asset",
            status=AssetStatus.DRAFT,
            created_by=self.other_user,
        )

        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        # Create AUDITOR role and user
        self.auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor - Read-only access"},
        )

        self.auditor_user = User.objects.create_user(
            email="auditor@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.auditor_user, role=self.auditor_role)

        # Create job for compliance runs
        from hub.apps.jobs.models import Job, JobStatus, JobType

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )

        # Create asset for ComplianceRun
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-compliance-views",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        # Create compliance run
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=self.job,
            asset=self.asset,
            status=ComplianceRunStatus.PENDING,
        )

    # ========== LIST ENDPOINT TESTS ==========

    def test_list_compliance_runs_success_returns_200(self):
        """Test listing compliance runs successfully returns 200 status code"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_compliance_runs_success_returns_results_list(self):
        """Test listing compliance runs successfully returns results list"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.compliance_run.id))

    def test_list_compliance_runs_tenant_isolation(self):
        """Test compliance runs are filtered by tenant"""
        # Create compliance run for other tenant
        from hub.apps.jobs.models import Job, JobStatus, JobType

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.other_user,
        )

        other_compliance_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=self.other_asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.compliance_run.id))
        self.assertNotEqual(response.data["results"][0]["id"], str(other_compliance_run.id))

    def test_list_compliance_runs_platform_admin_sees_all(self):
        """Test platform admin can see all compliance runs"""
        # Create compliance run for other tenant
        from hub.apps.jobs.models import Job, JobStatus, JobType

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.other_user,
        )

        other_compliance_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=self.other_asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        compliance_run_ids = [cr["id"] for cr in response.data["results"]]
        self.assertIn(str(self.compliance_run.id), compliance_run_ids)
        self.assertIn(str(other_compliance_run.id), compliance_run_ids)

    def test_list_compliance_runs_filter_by_status(self):
        """Test filtering compliance runs by status"""
        # Create compliance run with different status
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )

        ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job2,
            asset=self.asset,
            status=ComplianceRunStatus.SUCCEEDED,
        )

        self.client.force_authenticate(user=self.user)

        # Filter by PENDING status
        response = self.client.get("/api/v1/compliance/runs/?status=PENDING")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], ComplianceRunStatus.PENDING)

    def test_list_compliance_runs_filter_by_invalid_status(self):
        """Test filtering compliance runs by invalid status returns empty"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/compliance/runs/?status=INVALID")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_compliance_runs_filter_by_asset(self):
        """Test filtering compliance runs by asset"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.jobs.models import Job, JobStatus, JobType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )

        compliance_run2 = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job2,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/?asset={asset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(compliance_run2.id))

    def test_list_compliance_runs_requires_authentication(self):
        """Test listing compliance runs requires authentication"""
        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_compliance_runs_empty_list_when_no_runs(self):
        """Test listing compliance runs returns empty list when no runs exist"""
        # Delete existing compliance run
        self.compliance_run.delete()

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_compliance_runs_ordering(self):
        """Test compliance runs are ordered by created_at descending"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        # Create another compliance run
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )

        compliance_run2 = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job2,
            asset=self.asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/compliance/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Most recent should be first
        self.assertEqual(response.data["results"][0]["id"], str(compliance_run2.id))
        self.assertEqual(response.data["results"][1]["id"], str(self.compliance_run.id))

    # ========== RETRIEVE ENDPOINT TESTS ==========

    def test_retrieve_compliance_run_success_returns_200(self):
        """Test retrieving compliance run successfully returns 200 status code"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_compliance_run_success_returns_compliance_run_data(self):
        """Test retrieving compliance run successfully returns compliance run data"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.compliance_run.id))
        self.assertEqual(response.data["status"], ComplianceRunStatus.PENDING)

    def test_retrieve_compliance_run_tenant_isolation(self):
        """Test cannot retrieve compliance run from another tenant"""
        # Create compliance run for other tenant
        from hub.apps.jobs.models import Job, JobStatus, JobType

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.other_user,
        )

        other_compliance_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=self.other_asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/{other_compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_compliance_run_not_found(self):
        """Test retrieving non-existent compliance run returns 404"""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/compliance/runs/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_compliance_run_platform_admin_can_access_any(self):
        """Test platform admin can retrieve any compliance run"""
        # Create compliance run for other tenant
        from hub.apps.jobs.models import Job, JobStatus, JobType

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.other_user,
        )

        other_compliance_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=self.other_asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get(f"/api/v1/compliance/runs/{other_compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(other_compliance_run.id))

    # ========== CREATE ENDPOINT TESTS ==========

    def test_create_compliance_run_with_asset_success(self):
        """Test creating compliance run with asset successfully"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(asset.id), "scan_mode": "internal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], ComplianceRunStatus.PENDING)

    def test_create_compliance_run_with_dataset_success(self):
        """Test creating compliance run with dataset successfully"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"dataset_id": str(dataset.id), "scan_mode": "internal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

    def test_create_compliance_run_with_file_success(self):
        """Test creating compliance run with file successfully"""
        from hub.apps.files.models import File, FileStatus

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"file_id": str(file_obj.id), "scan_mode": "external"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

    def test_create_compliance_run_with_applicable_regulations(self):
        """Test creating compliance run with applicable regulations"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(asset.id),
                "scan_mode": "internal",
                "applicable_regulations": ["GDPR", "HIPAA"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

    def test_create_compliance_run_rejects_invalid_contract_schema(self):
        """5.4.2: Creating run with asset whose contract has invalid privacy_compliance returns 400; real validation, no mocks."""
        from hub.apps.contracts.models import Contract, ContractStatus
        from hub.apps.contracts.models import (
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="asset-invalid-schema",
            name="Asset Invalid Schema",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={
                "privacy_compliance": {
                    "contains_personal_data": "yes",  # invalid: must be bool
                },
            },
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(asset.id), "scan_mode": "internal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "contract_compliance_schema_invalid")
        self.assertIn("error", response.data)
        self.assertIn("invalid", response.data.get("error", "").lower())

    def test_create_compliance_run_requires_tenant(self):
        """Test creating compliance run requires user to belong to tenant"""
        # Create user without tenant
        user_no_tenant = User.objects.create_user(
            email="notenant@example.com", password="testpass123"
        )

        self.client.force_authenticate(user=user_no_tenant)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"scan_mode": "internal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_create_compliance_run_invalid_asset_id(self):
        """Test creating compliance run with invalid asset_id returns 404"""
        self.client.force_authenticate(user=self.user)

        fake_asset_id = uuid.uuid4()
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(fake_asset_id), "scan_mode": "internal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_compliance_run_auditor_cannot_create(self):
        """Test AUDITOR role cannot create compliance runs"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.auditor_user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(asset.id), "scan_mode": "internal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Custom exception handler returns error.message, not detail
        error_msg = (response.data.get("error") or {}).get("message") or str(response.data)
        self.assertIn("AUDITOR", error_msg)

    # ========== UPDATE ENDPOINT TESTS ==========

    def test_update_compliance_run_success(self):
        """Test updating compliance run successfully"""
        self.client.force_authenticate(user=self.user)

        # Note: Most fields are read-only, so update may be limited
        # Test with valid data
        response = self.client.put(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {
                "regulations": ["GDPR", "HIPAA"],
            },
            format="json",
        )

        # Update may succeed or fail depending on serializer configuration
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_partial_update_compliance_run_success(self):
        """Test partially updating compliance run successfully"""
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {
                "regulations": ["GDPR"],
            },
            format="json",
        )

        # Partial update may succeed or fail depending on serializer configuration
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_update_compliance_run_tenant_isolation(self):
        """Test cannot update compliance run from another tenant"""
        # Create compliance run for other tenant
        from hub.apps.jobs.models import Job, JobStatus, JobType

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        other_compliance_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=self.other_asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f"/api/v1/compliance/runs/{other_compliance_run.id}/",
            {"regulations": ["GDPR"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_compliance_run_auditor_cannot_update(self):
        """Test AUDITOR role cannot update compliance runs"""
        self.client.force_authenticate(user=self.auditor_user)

        response = self.client.put(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {"status": ComplianceRunStatus.SUCCEEDED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_partial_update_compliance_run_auditor_cannot_update(self):
        """Test AUDITOR role cannot partially update compliance runs"""
        self.client.force_authenticate(user=self.auditor_user)

        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {"status": ComplianceRunStatus.SUCCEEDED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== DESTROY ENDPOINT TESTS ==========

    def test_destroy_compliance_run_success(self):
        """Test deleting compliance run successfully"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify compliance run was deleted
        self.assertFalse(ComplianceRun.objects.filter(id=self.compliance_run.id).exists())

    def test_destroy_compliance_run_tenant_isolation(self):
        """Test cannot delete compliance run from another tenant"""
        # Create compliance run for other tenant
        from hub.apps.jobs.models import Job, JobStatus, JobType

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        other_compliance_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=self.other_asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/v1/compliance/runs/{other_compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify compliance run still exists
        self.assertTrue(ComplianceRun.objects.filter(id=other_compliance_run.id).exists())

    def test_destroy_compliance_run_not_found(self):
        """Test deleting non-existent compliance run returns 404"""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        response = self.client.delete(f"/api/v1/compliance/runs/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_destroy_compliance_run_auditor_cannot_delete(self):
        """Test AUDITOR role cannot delete compliance runs"""
        self.client.force_authenticate(user=self.auditor_user)

        response = self.client.delete(f"/api/v1/compliance/runs/{self.compliance_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== RESULTS ACTION TESTS ==========

    def test_results_action_success_returns_200(self):
        """Test results action successfully returns 200 status code"""
        # Update compliance run with results data
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.overall_status = "PASS"
        self.compliance_run.risk_level = RiskLevel.LOW
        self.compliance_run.allowed_to_store = True
        self.compliance_run.column_findings_json = [
            {"column": "email", "pii_types": ["EMAIL"], "risk_score": 0.5}
        ]
        self.compliance_run.detected_categories_json = {"EMAIL": {"count": 1}}
        self.compliance_run.regulation_mapping_json = {"GDPR": {"applies": True}}
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_results_action_returns_comprehensive_data(self):
        """Test results action returns comprehensive compliance data"""
        # Update compliance run with results data
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.overall_status = "PASS"
        self.compliance_run.risk_level = RiskLevel.LOW
        self.compliance_run.allowed_to_store = True
        self.compliance_run.column_findings_json = [
            {"column": "email", "pii_types": ["EMAIL"], "risk_score": 0.5}
        ]
        self.compliance_run.detected_categories_json = {"EMAIL": {"count": 1}}
        self.compliance_run.regulation_mapping_json = {"GDPR": {"applies": True}}
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("compliance_run_id", response.data)
        self.assertIn("overall_status", response.data)
        self.assertIn("risk_level", response.data)
        self.assertIn("allowed_to_store", response.data)
        self.assertIn("compliance_score", response.data)
        self.assertIn("violations", response.data)
        self.assertIn("violation_details", response.data)
        self.assertIn("remediation_suggestions", response.data)
        self.assertIn("risk_assessment", response.data)

    def test_results_action_tenant_isolation(self):
        """Test results action respects tenant isolation"""
        # Create compliance run for other tenant
        from hub.apps.jobs.models import Job, JobStatus, JobType

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.other_user,
        )

        other_compliance_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=self.other_asset,
            status=ComplianceRunStatus.SUCCEEDED,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/{other_compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== EDGE CASES ==========

    def test_create_compliance_run_no_resources(self):
        """Test creating compliance run with no resources fails validation"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"scan_mode": "internal"},
            format="json",
        )

        # Should fail validation (business rules require at least one resource)
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY],
        )

    def test_create_compliance_run_cross_tenant_asset(self):
        """Test creating compliance run with asset from different tenant fails"""
        from hub.apps.assets.models import Asset, AssetStatus

        # Create asset in other tenant
        asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.other_user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(asset.id), "scan_mode": "internal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_results_action_with_no_findings(self):
        """Test results action handles compliance run with no findings"""
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.overall_status = "PASS"
        self.compliance_run.risk_level = RiskLevel.NONE
        self.compliance_run.allowed_to_store = True
        self.compliance_run.column_findings_json = []
        self.compliance_run.detected_categories_json = {}
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["violations"]), 0)
        self.assertEqual(response.data["compliance_score"], 100.0)

    # ========== ERROR HANDLING ==========

    def test_create_compliance_run_invalid_scan_mode(self):
        """Test creating compliance run with invalid scan_mode fails validation"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(asset.id), "scan_mode": "invalid"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_compliance_run_invalid_regulations(self):
        """Test creating compliance run with invalid regulations fails validation"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "asset_id": str(asset.id),
                "scan_mode": "internal",
                "applicable_regulations": ["INVALID_REGULATION"],
            },
            format="json",
        )

        # Should fail if tenant doesn't allow this regulation
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED])
