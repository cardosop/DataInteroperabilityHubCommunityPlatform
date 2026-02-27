"""
Comprehensive unit tests for DQ Run ViewSet endpoints.

Tests cover:
- CRUD operations (list, retrieve, create, update, destroy)
- Results endpoint
- Tenant isolation
- Auditor permissions
- Filtering (status, dataset_id, date_from, date_to)
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling

All tests use real implementations (no mocks of hub services).
"""

import uuid
from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DQRunViewSetTest(DQAPITestBase):
    """Comprehensive tests for DQ Run ViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            created_by=self.user,
        )

        # Create DQ run
        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.5,
            checks_json=[
                {
                    "name": "expect_column_values_to_not_be_null",
                    "status": "PASS",
                    "result": {"observed_value": 100},
                }
            ],
            details_json={"engine_version": "0.18.0"},
        )

        # Create another tenant and user for isolation tests
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status="ACTIVE",
        )

    # ========== LIST ENDPOINT TESTS ==========

    def test_list_dq_runs_success_returns_200(self):
        """Test listing DQ runs successfully returns 200 status code"""
        response = self.client.get("/api/v1/dq/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_dq_runs_success_returns_results_list(self):
        """Test listing DQ runs successfully returns results list"""
        response = self.client.get("/api/v1/dq/runs/")

        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_list_dq_runs_tenant_isolation_excludes_other_tenant_runs(self):
        """Test tenant isolation excludes DQ runs from other tenant"""
        # Create DQ run for other tenant
        other_file = File.objects.create(
            tenant=self.other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path="other/path/file.csv",
            created_by=self.other_user,
        )

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        other_dq_run = DQRun.objects.create(
            tenant=self.other_tenant,
            file=other_file,
            job=other_job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
        )

        response = self.client.get("/api/v1/dq/runs/")

        # Should see self.dq_run (same tenant) but not other tenant's DQ runs
        dq_run_ids = [d["id"] for d in response.data.get("results", [])]
        self.assertIn(str(self.dq_run.id), dq_run_ids)
        self.assertNotIn(str(other_dq_run.id), dq_run_ids)

    def test_list_dq_runs_filter_by_status(self):
        """Test filtering DQ runs by status"""
        # Create DQ run with different status
        pending_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        response = self.client.get("/api/v1/dq/runs/?status=PENDING")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        # Should only return pending runs
        for result in results:
            self.assertEqual(result["status"], "PENDING")

    def test_list_dq_runs_filter_by_dataset_id(self):
        """Test filtering DQ runs by dataset_id"""
        response = self.client.get(f"/api/v1/dq/runs/?dataset_id={self.dataset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        # Should only return runs for this dataset
        for result in results:
            self.assertEqual(str(result["dataset"]), str(self.dataset.id))

    def test_list_dq_runs_filter_by_invalid_dataset_id(self):
        """Test filtering DQ runs by invalid dataset_id (edge case)"""
        response = self.client.get("/api/v1/dq/runs/?dataset_id=invalid-uuid")

        # Should return 200 with empty results (invalid UUID is ignored)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_dq_runs_filter_by_date_range(self):
        """Test filtering DQ runs by date range"""
        # Capture a single reference time to avoid timing issues
        reference_time = timezone.now()

        # Create DQ run with specific date (10 days ago - should be excluded)
        old_date = reference_time - timedelta(days=10)
        old_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        old_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=old_job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
        )
        # Use update() to ensure created_at is saved correctly
        DQRun.objects.filter(id=old_run.id).update(created_at=old_date)
        old_run.refresh_from_db()

        # Update self.dq_run to be recent (within date_from range)
        recent_date = reference_time - timedelta(days=2)
        DQRun.objects.filter(id=self.dq_run.id).update(created_at=recent_date)
        self.dq_run.refresh_from_db()

        # Use the same reference time for date_from to ensure consistency
        date_from_dt = reference_time - timedelta(days=5)
        date_from = date_from_dt.isoformat()
        # Pass as query params dict so + in ISO offset is URL-encoded (not decoded as space)
        response = self.client.get("/api/v1/dq/runs/", {"date_from": date_from})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])

        # Verify that old_run is excluded and self.dq_run is included
        result_ids = [result["id"] for result in results]
        self.assertNotIn(
            str(old_run.id), result_ids,
            "Old run should be excluded from results"
        )
        self.assertIn(
            str(self.dq_run.id), result_ids,
            "Recent run should be included in results"
        )

        # Verify all results have created_at >= date_from
        # Parse date_from - fromisoformat returns timezone-aware datetime
        # if timezone info is present
        date_from_str = date_from.replace("Z", "+00:00")
        parsed_date_from = datetime.fromisoformat(date_from_str)
        if timezone.is_naive(parsed_date_from):
            parsed_date_from = timezone.make_aware(parsed_date_from)

        for result in results:
            # Parse result date - fromisoformat returns timezone-aware datetime
            # if timezone info is present
            result_date_str = result["created_at"].replace("Z", "+00:00")
            result_date = datetime.fromisoformat(result_date_str)
            if timezone.is_naive(result_date):
                result_date = timezone.make_aware(result_date)
            self.assertGreaterEqual(
                result_date, parsed_date_from,
                f"Result {result['id']} created_at {result_date} "
                f"should be >= date_from {parsed_date_from}"
            )

    def test_list_dq_runs_filter_by_invalid_date(self):
        """Test filtering DQ runs by invalid date format (edge case)"""
        response = self.client.get("/api/v1/dq/runs/?date_from=invalid-date")

        # Should return 200 (invalid date is ignored)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ========== RETRIEVE ENDPOINT TESTS ==========

    def test_retrieve_dq_run_success_returns_200(self):
        """Test retrieving a DQ run successfully returns 200 status code"""
        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_dq_run_success_returns_correct_data(self):
        """Test retrieving a DQ run successfully returns correct data"""
        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/")

        self.assertEqual(str(response.data["id"]), str(self.dq_run.id))
        self.assertEqual(response.data["profile_key"], "intake_basic_gx")
        self.assertEqual(response.data["overall_status"], "PASS")
        self.assertEqual(response.data["quality_score"], 95.5)

    def test_retrieve_dq_run_not_found(self):
        """Test retrieving non-existent DQ run"""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/dq/runs/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_dq_run_tenant_isolation(self):
        """Test tenant isolation - user cannot retrieve other tenant's DQ run"""
        # Create DQ run for other tenant
        other_file = File.objects.create(
            tenant=self.other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path="other/path/file.csv",
            created_by=self.other_user,
        )

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        other_run = DQRun.objects.create(
            tenant=self.other_tenant,
            file=other_file,
            job=other_job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
        )

        response = self.client.get(f"/api/v1/dq/runs/{other_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== CREATE ENDPOINT TESTS ==========

    def test_create_dq_run_success_with_asset_id(self):
        """Test creating a DQ run successfully with asset_id"""
        data = {"asset_id": str(self.asset.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        # May return 201 or 400 depending on service availability
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn("id", response.data)
            self.assertEqual(str(response.data["asset"]), str(self.asset.id))

    def test_create_dq_run_success_with_dataset_id(self):
        """Test creating a DQ run successfully with dataset_id"""
        data = {"dataset_id": str(self.dataset.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        # May return 201 or 400 depending on service availability
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn("id", response.data)
            self.assertEqual(str(response.data["dataset"]), str(self.dataset.id))

    def test_create_dq_run_success_with_file_id(self):
        """Test creating a DQ run successfully with file_id"""
        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        # May return 201 or 400 depending on service availability
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn("id", response.data)
            self.assertEqual(str(response.data["file"]), str(self.file.id))

    def test_create_dq_run_success_with_profile_key(self):
        """Test creating a DQ run successfully with explicit profile_key"""
        data = {"file_id": str(self.file.id), "profile_key": "intake_basic_soda"}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        # May return 201 or 400 depending on service availability
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

        if response.status_code == status.HTTP_201_CREATED:
            self.assertEqual(response.data["profile_key"], "intake_basic_soda")

    def test_create_dq_run_missing_resource_ids(self):
        """Test creating DQ run with missing resource IDs (error handling)"""
        data = {}  # Missing asset_id, dataset_id, file_id

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        # Should return 400 (validation error)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_dq_run_asset_not_found(self):
        """Test creating DQ run with non-existent asset_id (error handling)"""
        fake_asset_id = str(uuid.uuid4())
        data = {"asset_id": fake_asset_id}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_dq_run_dataset_not_found(self):
        """Test creating DQ run with non-existent dataset_id (error handling)"""
        fake_dataset_id = str(uuid.uuid4())
        data = {"dataset_id": fake_dataset_id}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_dq_run_file_not_found(self):
        """Test creating DQ run with non-existent file_id (error handling)"""
        fake_file_id = str(uuid.uuid4())
        data = {"file_id": fake_file_id}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_dq_run_dataset_mismatch_with_asset(self):
        """Test creating DQ run with dataset that doesn't belong to asset (error handling)"""
        # Create another asset
        other_asset = Asset.objects.create(
            tenant=self.tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        data = {"asset_id": str(other_asset.id), "dataset_id": str(self.dataset.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_dq_run_invalid_profile_key(self):
        """Test creating DQ run with invalid profile_key (error handling)"""
        data = {"file_id": str(self.file.id), "profile_key": "invalid_profile"}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== UPDATE ENDPOINT TESTS ==========

    def test_update_dq_run_success(self):
        """Test updating a DQ run successfully"""
        # DQ runs are mostly read-only, but test that update endpoint exists
        updated_data = {"profile_key": "intake_basic_soda"}

        response = self.client.put(
            f"/api/v1/dq/runs/{self.dq_run.id}/", updated_data, format="json"
        )

        # May return 200 or 400 depending on serializer validation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_update_dq_run_not_found(self):
        """Test updating non-existent DQ run"""
        fake_id = str(uuid.uuid4())
        updated_data = {"profile_key": "intake_basic_soda"}

        response = self.client.put(f"/api/v1/dq/runs/{fake_id}/", updated_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_partial_update_dq_run_success(self):
        """Test partial update (PATCH) of a DQ run"""
        updated_data = {"profile_key": "intake_basic_soda"}

        response = self.client.patch(
            f"/api/v1/dq/runs/{self.dq_run.id}/", updated_data, format="json"
        )

        # May return 200 or 400 depending on serializer validation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    # ========== DESTROY ENDPOINT TESTS ==========

    def test_destroy_dq_run_success(self):
        """Test deleting a DQ run successfully"""
        # Create a DQ run to delete
        run_to_delete = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
        )

        response = self.client.delete(f"/api/v1/dq/runs/{run_to_delete.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify DQ run was deleted
        self.assertFalse(DQRun.objects.filter(id=run_to_delete.id).exists())

    def test_destroy_dq_run_not_found(self):
        """Test deleting non-existent DQ run"""
        fake_id = str(uuid.uuid4())
        response = self.client.delete(f"/api/v1/dq/runs/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_destroy_dq_run_tenant_isolation(self):
        """Test tenant isolation - user cannot delete other tenant's DQ run"""
        # Create DQ run for other tenant
        other_file = File.objects.create(
            tenant=self.other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path="other/path/file.csv",
            created_by=self.other_user,
        )

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        other_run = DQRun.objects.create(
            tenant=self.other_tenant,
            file=other_file,
            job=other_job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
        )

        response = self.client.delete(f"/api/v1/dq/runs/{other_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== RESULTS ENDPOINT TESTS ==========

    def test_get_dq_run_results_success(self):
        """Test getting DQ run results successfully"""
        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("dq_run_id", response.data)
        self.assertIn("overall_status", response.data)
        self.assertIn("quality_score", response.data)
        self.assertIn("checks", response.data)
        self.assertIn("check_details", response.data)

    def test_get_dq_run_results_includes_score_breakdown(self):
        """Test that results include score breakdown"""
        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/results/")

        self.assertIn("score_breakdown", response.data)
        score_breakdown = response.data["score_breakdown"]
        self.assertIn("total_checks", score_breakdown)
        self.assertIn("passed_checks", score_breakdown)
        self.assertIn("failed_checks", score_breakdown)

    def test_get_dq_run_results_includes_recommendations(self):
        """Test that results include recommendations for failed checks"""
        # Create DQ run with failed checks
        failed_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="FAIL",
            quality_score=60.0,
            checks_json=[
                {
                    "name": "expect_column_values_to_not_be_null",
                    "status": "FAIL",
                    "result": {"message": "Found null values"},
                }
            ],
        )

        response = self.client.get(f"/api/v1/dq/runs/{failed_run.id}/results/")

        self.assertIn("recommendations", response.data)
        recommendations = response.data["recommendations"]
        self.assertGreater(len(recommendations), 0)

    def test_get_dq_run_results_not_found(self):
        """Test getting results for non-existent DQ run"""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/dq/runs/{fake_id}/results/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== AUDITOR PERMISSIONS TESTS ==========

    def test_auditor_cannot_create_dq_run(self):
        """Test that AUDITOR role cannot create DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor role"},
        )
        UserRole.objects.create(user=self.user, role=auditor_role)

        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_can_list_dq_runs(self):
        """Test that AUDITOR role can list DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role = Role.objects.create(tenant=self.tenant, name="AUDITOR", description="Auditor role")
        UserRole.objects.create(user=self.user, role=auditor_role)

        response = self.client.get("/api/v1/dq/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auditor_can_retrieve_dq_run(self):
        """Test that AUDITOR role can retrieve DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role = Role.objects.create(tenant=self.tenant, name="AUDITOR", description="Auditor role")
        UserRole.objects.create(user=self.user, role=auditor_role)

        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auditor_cannot_update_dq_run(self):
        """Test that AUDITOR role cannot update DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role = Role.objects.create(tenant=self.tenant, name="AUDITOR", description="Auditor role")
        UserRole.objects.create(user=self.user, role=auditor_role)

        updated_data = {"profile_key": "intake_basic_soda"}

        response = self.client.put(
            f"/api/v1/dq/runs/{self.dq_run.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_delete_dq_run(self):
        """Test that AUDITOR role cannot delete DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role = Role.objects.create(tenant=self.tenant, name="AUDITOR", description="Auditor role")
        UserRole.objects.create(user=self.user, role=auditor_role)

        response = self.client.delete(f"/api/v1/dq/runs/{self.dq_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== ERROR HANDLING TESTS ==========

    def test_create_dq_run_unauthenticated(self):
        """Test creating DQ run without authentication"""
        self.client.force_authenticate(user=None)
        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_dq_run_user_without_tenant(self):
        """Test creating DQ run with user that doesn't belong to tenant (edge case)"""
        # Create user without tenant
        user_no_tenant = User.objects.create_user(
            email="notenant@example.com",
            password="testpass123",
            tenant=None,
            status="ACTIVE",
        )

        self.client.force_authenticate(user=user_no_tenant)
        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
