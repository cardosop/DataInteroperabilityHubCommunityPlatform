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
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create another tenant and user for isolation tests
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
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
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
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
            email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
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

    def test_list_compliance_runs_filter_by_asset_id_query_param(self):
        """Phase 231.7 — ``asset_id`` is accepted as an alias of ``asset`` for filters."""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.jobs.models import Job, JobStatus, JobType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="trend-asset",
            name="Trend Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job2,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.LOW,
            completed_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/compliance/runs/?asset_id={asset.id}&status=SUCCEEDED")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(run.id))

    def test_list_compliance_runs_tiebreak_completed_at_with_created_at(self):
        """Phase 231.7 — multi-field ordering so trend queries are deterministic when completed_at ties."""
        from datetime import timedelta

        from hub.apps.jobs.models import Job, JobStatus, JobType

        shared_completed = timezone.now()
        job_a = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )
        job_b = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )
        run_a = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job_a,
            asset=self.asset,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.LOW,
            completed_at=shared_completed,
        )
        run_b = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job_b,
            asset=self.asset,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.HIGH,
            completed_at=shared_completed,
        )
        ComplianceRun.objects.filter(pk=run_a.pk).update(
            created_at=shared_completed - timedelta(seconds=10),
        )
        ComplianceRun.objects.filter(pk=run_b.pk).update(
            created_at=shared_completed - timedelta(seconds=1),
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/compliance/runs/?asset_id={self.asset.id}"
            "&status=SUCCEEDED&ordering=-completed_at,-created_at"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids[0], str(run_b.id))
        self.assertEqual(ids[1], str(run_a.id))

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
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
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
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com", password="testpass123"
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
        """Test patching compliance run regulations successfully"""
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {"regulations": ["GDPR", "HIPAA"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regulations"], ["GDPR", "HIPAA"])

    def test_partial_update_compliance_run_success(self):
        """Test partially updating compliance run regulations"""
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/",
            {"regulations": ["LGPD"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regulations"], ["LGPD"])

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
        self.assertIn("score_breakdown", response.data)
        self.assertIn("violation_timeline", response.data)
        self.assertIn("regulations", response.data)
        self.assertIn("detected_categories", response.data)

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

    def test_results_violation_details_derives_regulations_and_preserves_confidence_label(
        self,
    ):
        """
        Regression: earlier the /results/ endpoint always emitted
        `regulations_affected: []` on every violation because it read a
        non-existent key from column_findings — leaving the frontend
        Regulation filter dropdown empty ("doesn't do anything"). And it
        defaulted `detection_confidence` to 0.0 even though the CLI emits
        a string label (HIGH/MEDIUM/LOW), breaking the frontend renderer
        into "Confidence: NaN%".

        Fix: derive regulations_affected by walking regulation_mapping_json
        (the real source of truth) and preserve the confidence label as-is.
        """
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.overall_status = "FAIL"
        self.compliance_run.risk_level = RiskLevel.CRITICAL
        self.compliance_run.allowed_to_store = False
        self.compliance_run.column_findings_json = [
            {
                "column": "email",
                "categories": ["PII_DIRECT_EMAIL"],
                "confidence": "HIGH",
                "match_ratio": 1.0,
                "total_sampled": 2,
                "sample_matches": 2,
            }
        ]
        self.compliance_run.regulation_mapping_json = {
            "GDPR": {
                "applies": True,
                "applicable_categories": ["PII_DIRECT_EMAIL"],
            },
            "LGPD": {
                "applies": True,
                "applicable_categories": ["PII_DIRECT_EMAIL"],
            },
            "HIPAA": {
                "applies": False,  # applies=False must not surface
                "applicable_categories": ["PII_DIRECT_EMAIL"],
            },
            "metadata": {  # the non-regulation metadata key must be skipped
                "timestamp": "2026-04-24T18:27:15Z",
            },
        }
        self.compliance_run.detected_categories_json = {}
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        self.client.force_authenticate(user=self.user)
        # Type annotation: DRF's APIClient returns a rest_framework.response.Response
        # which has `.data` (the parsed body). pyright sees the base Django
        # type on APIClient.get; annotate locally so .data access is typed
        # correctly without scattering `# type: ignore[misc]  # test: edge-case type exercise` comments.
        from rest_framework.response import Response

        response: Response = self.client.get(  # type: ignore[assignment]  # test: edge-case type exercise
            f"/api/v1/compliance/runs/{self.compliance_run.id}/results/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        details = response.data["violation_details"]
        self.assertEqual(len(details), 1, details)
        d = details[0]

        # regulations_affected must be derived from regulation_mapping_json,
        # filtered by applies=True, excluding the metadata key, sorted.
        self.assertEqual(
            d["regulations_affected"],
            ["GDPR", "LGPD"],
            "regulations_affected must include applies=True regulations listing "
            "this PII type, exclude applies=False, skip the `metadata` key, and "
            "be sorted.",
        )

        # detection_confidence must stay the string label from the CLI.
        # A numeric default (e.g. 0.0) would let a future render site do
        # Math.round(x * 100) and print NaN% or "0%" — both user-visible bugs.
        self.assertEqual(
            d["detection_confidence"],
            "HIGH",
            "detection_confidence must preserve the CLI's qualitative label "
            "(HIGH/MEDIUM/LOW) — not be coerced to a numeric default.",
        )
        self.assertIsInstance(
            d["detection_confidence"],
            str,
            "detection_confidence must be typed as a string label, not a number.",
        )

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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("INVALID_REGULATION", response.data.get("error", ""))

    # ========== CANCEL ACTION TESTS ==========

    def test_cancel_compliance_run_pending_success(self):
        """Cancel a PENDING compliance run marks it FAILED with allowed_to_store=False."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/cancel/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.compliance_run.refresh_from_db()
        self.assertEqual(self.compliance_run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(self.compliance_run.allowed_to_store)
        self.assertIsNotNone(self.compliance_run.completed_at)
        mapping = self.compliance_run.regulation_mapping_json or {}
        self.assertTrue(mapping.get("cancelled"))

    def test_cancel_compliance_run_terminal_status_rejected(self):
        """Cannot cancel a run already in a terminal status (SUCCEEDED)."""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            asset=self.asset,
            status=ComplianceRunStatus.SUCCEEDED,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/compliance/runs/{run.id}/cancel/",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "INVALID_STATUS")

    def test_cancel_compliance_run_auditor_cannot_cancel(self):
        """AUDITOR role cannot cancel compliance runs."""
        self.client.force_authenticate(user=self.auditor_user)

        response = self.client.post(
            f"/api/v1/compliance/runs/{self.compliance_run.id}/cancel/",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== RESULTS SCORE EDGE CASES ==========

    def test_results_compliance_score_all_columns_clean(self):
        """Score is 100 when no columns have PII."""
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.overall_status = "PASS"
        self.compliance_run.risk_level = RiskLevel.NONE
        self.compliance_run.allowed_to_store = True
        self.compliance_run.column_findings_json = [
            {"column": "id", "categories": []},
            {"column": "name", "categories": []},
        ]
        self.compliance_run.detected_categories_json = {}
        self.compliance_run.regulation_mapping_json = {}
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["compliance_score"], 100.0)
        self.assertEqual(response.data["score_breakdown"]["columns_with_pii"], 0)

    def test_results_compliance_score_all_columns_with_pii(self):
        """Score is max(0, 100 - 50) = 50 when all columns have PII."""
        self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
        self.compliance_run.overall_status = "FAIL"
        self.compliance_run.risk_level = RiskLevel.HIGH
        self.compliance_run.allowed_to_store = False
        self.compliance_run.column_findings_json = [
            {"column": "email", "categories": ["PII_DIRECT_EMAIL"]},
            {"column": "ssn", "categories": ["PII_DIRECT_SSN"]},
        ]
        self.compliance_run.detected_categories_json = {}
        self.compliance_run.regulation_mapping_json = {}
        self.compliance_run.completed_at = timezone.now()
        self.compliance_run.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/compliance/runs/{self.compliance_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["compliance_score"], 50.0)
        self.assertEqual(response.data["score_breakdown"]["columns_with_pii"], 2)
        self.assertEqual(response.data["score_breakdown"]["pii_detection_rate"], 1.0)

    # ── /results/ on non-SUCCEEDED status ──────────────────────────────

    @pytest.mark.integration
    def test_results_action_pending_run_returns_empty_results(self):
        """A PENDING run returns 200 with empty/minimal results (no scan data yet)."""
        self.compliance_run.status = ComplianceRunStatus.PENDING
        self.compliance_run.save()
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/compliance/runs/{self.compliance_run.id}/results/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results endpoint always returns 200 and includes the standard keys.
        self.assertIn("compliance_score", response.data)
        self.assertEqual(response.data["compliance_score"], 100.0)

    @pytest.mark.integration
    def test_results_action_running_run_returns_results(self):
        """A RUNNING run returns 200 with partial results (no terminal data yet)."""
        self.compliance_run.status = ComplianceRunStatus.RUNNING
        self.compliance_run.save()
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/compliance/runs/{self.compliance_run.id}/results/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("compliance_score", response.data)

    @pytest.mark.integration
    def test_results_action_failed_run_returns_results(self):
        """A FAILED run returns 200 with results — endpoint is status-agnostic."""
        self.compliance_run.status = ComplianceRunStatus.FAILED
        self.compliance_run.save()
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/compliance/runs/{self.compliance_run.id}/results/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ── PATCH edge cases ───────────────────────────────────────────────

    @pytest.mark.integration
    def test_partial_update_empty_regulations(self):
        """PATCH with empty regulations list should succeed and clear regulations."""
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/compliance/runs/{self.compliance_run.id}/"
        response = self.client.patch(url, {"regulations": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regulations"], [])
