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
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

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
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
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
        DQRun.objects.create(
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
        # Must have results for the loop assertion to be meaningful
        self.assertGreater(
            len(results), 0,
            "Filtering by PENDING status should return at least one result",
        )
        # Should only return pending runs
        for result in results:
            self.assertEqual(result["status"], "PENDING")
        # Verify non-PENDING run (self.dq_run with SUCCEEDED status) is excluded
        result_ids = [r["id"] for r in results]
        self.assertNotIn(str(self.dq_run.id), result_ids)

    def test_list_dq_runs_filter_by_dataset_id(self):
        """Test filtering DQ runs by dataset_id"""
        response = self.client.get(f"/api/v1/dq/runs/?dataset_id={self.dataset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        # Must have results for the loop assertion to be meaningful
        self.assertGreater(
            len(results), 0,
            "Filtering by dataset_id should return at least one result",
        )
        # Should only return runs for this dataset
        for result in results:
            self.assertEqual(str(result["dataset"]), str(self.dataset.id))

    def test_list_dq_runs_filter_by_invalid_dataset_id(self):
        """Test filtering DQ runs by invalid dataset_id (edge case)"""
        response = self.client.get("/api/v1/dq/runs/?dataset_id=invalid-uuid")

        # Should return 200 with empty results (invalid UUID is ignored)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data.get("results", [])), 0,
            "Invalid dataset_id should return empty results",
        )

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
        self.assertNotIn(str(old_run.id), result_ids, "Old run should be excluded from results")
        self.assertIn(str(self.dq_run.id), result_ids, "Recent run should be included in results")

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
                result_date,
                parsed_date_from,
                f"Result {result['id']} created_at {result_date} "
                f"should be >= date_from {parsed_date_from}",
            )

    def test_list_dq_runs_filter_by_invalid_date(self):
        """Test filtering DQ runs by invalid date format (edge case)"""
        response = self.client.get("/api/v1/dq/runs/?date_from=invalid-date")

        # Should return 200 (invalid date is silently ignored)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results should still be returned — invalid date doesn't filter
        self.assertGreater(
            len(response.data.get("results", [])), 0,
            "Invalid date should be ignored; results should still be returned",
        )

    def test_list_dq_runs_filter_by_date_to(self):
        """Test filtering DQ runs by date_to parameter."""
        future_date = timezone.now() + timedelta(days=1)
        response = self.client.get(
            "/api/v1/dq/runs/",
            {"date_to": future_date.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        self.assertGreater(
            len(results), 0,
            "Latest DQ run should be within future date_to range",
        )

    def test_list_dq_runs_pagination(self):
        """Test that list endpoint returns paginated results."""
        for i in range(5):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
                resource_type="DQ_RUN",
                resource_id=uuid.uuid4(),
                created_by=self.user,
                timeout_seconds=1800,
            )
            DQRun.objects.create(
                tenant=self.tenant,
                file=self.file,
                job=job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
            )
        response = self.client.get("/api/v1/dq/runs/?page_size=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertGreaterEqual(response.data["count"], 6)
        # Verify per-page truncation: page_size=2 → at most 2 results
        self.assertLessEqual(
            len(response.data["results"]), 2,
            f"page_size=2 should return at most 2 results, "
            f"got {len(response.data['results'])}",
        )

    def test_list_dq_runs_default_ordering(self):
        """Test that DQ runs are returned in descending created_at order."""
        # Create a second run so we have at least 2 to compare
        extra_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            timeout_seconds=1800,
        )
        DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=extra_job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
        )
        response = self.client.get("/api/v1/dq/runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        self.assertGreaterEqual(
            len(results), 2,
            "Need at least 2 results to verify ordering",
        )
        for i in range(len(results) - 1):
                created_i = datetime.fromisoformat(
                    results[i]["created_at"].replace("Z", "+00:00")
                )
                created_j = datetime.fromisoformat(
                    results[i + 1]["created_at"].replace("Z", "+00:00")
                )
                self.assertGreaterEqual(
                    created_i,
                    created_j,
                    f"Results must be ordered by created_at DESC; "
                    f"found {created_i} before {created_j} at index {i}",
                )

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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(response.data["engine"], "GREAT_EXPECTATIONS")
        self.assertEqual(str(response.data["asset"]), str(self.asset.id))

    def test_create_dq_run_success_with_dataset_id(self):
        """Test creating a DQ run successfully with dataset_id"""
        data = {"dataset_id": str(self.dataset.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(str(response.data["dataset"]), str(self.dataset.id))

    def test_create_dq_run_success_with_file_id(self):
        """Test creating a DQ run successfully with file_id"""
        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(str(response.data["file"]), str(self.file.id))

    def test_create_dq_run_success_with_profile_key(self):
        """Test creating a DQ run successfully with explicit profile_key"""
        data = {"file_id": str(self.file.id), "profile_key": "intake_basic_soda"}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "PENDING")
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
        updated_data = {
            "profile_key": "intake_basic_soda",
            "engine": self.dq_run.engine,
        }

        response = self.client.put(
            f"/api/v1/dq/runs/{self.dq_run.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify data actually changed
        self.dq_run.refresh_from_db()
        self.assertEqual(self.dq_run.profile_key, "intake_basic_soda")

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify data actually changed
        self.dq_run.refresh_from_db()
        self.assertEqual(self.dq_run.profile_key, "intake_basic_soda")

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
        # Additional response keys per the results @action schema
        self.assertIn("score_breakdown", response.data)
        self.assertIn("quality_score_breakdown", response.data)
        self.assertIn("trend_analysis", response.data)
        self.assertIn("anomalies", response.data)
        self.assertIn("engine_type", response.data)
        self.assertIn("engine_version", response.data)
        self.assertIn("profile_key", response.data)
        self.assertIn("metadata", response.data)
        self.assertIn("started_at", response.data)
        self.assertIn("completed_at", response.data)
        # Verify types on key fields
        self.assertIsInstance(response.data["anomalies"], list)
        self.assertIsInstance(response.data["recommendations"], list)
        self.assertEqual(response.data["engine_type"], str(self.dq_run.engine))

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

        auditor_role = Role.objects.create(
            tenant=self.tenant, name="AUDITOR", description="Auditor role"
        )
        UserRole.objects.create(user=self.user, role=auditor_role)

        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_can_list_dq_runs(self):
        """Test that AUDITOR role can list DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role = Role.objects.create(
            tenant=self.tenant, name="AUDITOR", description="Auditor role"
        )
        UserRole.objects.create(user=self.user, role=auditor_role)

        response = self.client.get("/api/v1/dq/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auditor_can_retrieve_dq_run(self):
        """Test that AUDITOR role can retrieve DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role = Role.objects.create(
            tenant=self.tenant, name="AUDITOR", description="Auditor role"
        )
        UserRole.objects.create(user=self.user, role=auditor_role)

        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auditor_cannot_update_dq_run(self):
        """Test that AUDITOR role cannot update DQ runs"""
        # Create user with AUDITOR role
        from hub.apps.users.models import Role, UserRole

        auditor_role = Role.objects.create(
            tenant=self.tenant, name="AUDITOR", description="Auditor role"
        )
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

        auditor_role = Role.objects.create(
            tenant=self.tenant, name="AUDITOR", description="Auditor role"
        )
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
        """Test creating DQ run with user that doesn't belong to tenant (edge case)."""
        # Create user without tenant
        user_no_tenant = User.objects.create_user(
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status="ACTIVE",
        )

        self.client.force_authenticate(user=user_no_tenant)
        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/dq/runs/", data, format="json")

        # DQFeatureFlagMixin fires during initial() BEFORE create().
        # It calls check_data_quality_enabled() which requires a
        # resolved tenant context.  A user with tenant=None cannot
        # satisfy this, so the mixin returns 403 DATA_QUALITY_DISABLED
        # before the view's create() method ever runs.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DQAlertingRuleViewSetTest(DQAPITestBase):
    """CRUD tests for DQAlertingRuleViewSet."""

    def setUp(self):
        super().setUp()
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.dq.models import DQAlertingRule, DQAnomalySeverity

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="alerting-test-asset",
            name="Alerting Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Test Rule",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=["EMAIL"],
            channel_config={"emails": ["test@example.com"]},
            created_by=self.user,
        )

    def test_list_alerting_rules(self):
        response = self.client.get("/api/v1/dq/alerting-rules/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_retrieve_alerting_rule(self):
        response = self.client.get(
            f"/api/v1/dq/alerting-rules/{self.rule.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Rule")
        self.assertEqual(response.data["threshold"], 80.0)

    def test_create_alerting_rule(self):
        data = {"asset_id": str(self.asset.id), "threshold": 90.0}
        response = self.client.post(
            "/api/v1/dq/alerting-rules/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["threshold"], 90.0)
        self.assertIn("id", response.data)

    def test_update_alerting_rule(self):
        data = {
            "metric_type": "quality_score",
            "threshold": 70.0,
            "name": "Updated Rule",
        }
        response = self.client.put(
            f"/api/v1/dq/alerting-rules/{self.rule.id}/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.name, "Updated Rule")
        self.assertEqual(self.rule.threshold, 70.0)

    def test_delete_alerting_rule(self):
        response = self.client.delete(
            f"/api/v1/dq/alerting-rules/{self.rule.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        from hub.apps.dq.models import DQAlertingRule

        self.assertFalse(
            DQAlertingRule.objects.filter(id=self.rule.id).exists()
        )

    def test_filter_alerting_rules_by_enabled(self):
        response = self.client.get(
            "/api/v1/dq/alerting-rules/?enabled=true"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for r in response.data["results"]:
            self.assertTrue(r["enabled"])


class DQAlertingRuleViewSetAuditorTest(DQAPITestBase):
    """Auditor permission tests for DQAlertingRuleViewSet write operations."""

    def setUp(self):
        super().setUp()
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.dq.models import DQAlertingRule, DQAnomalySeverity
        from hub.apps.users.models import Role, UserRole

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="alerting-auditor-asset",
            name="Alerting Auditor Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Test Auditor Rule",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=["EMAIL"],
            channel_config={"emails": ["test@example.com"]},
            created_by=self.user,
        )
        auditor_role = Role.objects.create(
            tenant=self.tenant, name="AUDITOR", description="Auditor role"
        )
        UserRole.objects.create(user=self.user, role=auditor_role)

    def test_auditor_cannot_create_alerting_rule(self):
        data = {"asset_id": str(self.asset.id), "threshold": 80.0}
        response = self.client.post(
            "/api/v1/dq/alerting-rules/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_update_alerting_rule(self):
        data = {
            "name": "Hacked Rule",
            "metric_type": "quality_score",
            "threshold": 50.0,
        }
        response = self.client.put(
            f"/api/v1/dq/alerting-rules/{self.rule.id}/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_delete_alerting_rule(self):
        response = self.client.delete(
            f"/api/v1/dq/alerting-rules/{self.rule.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DQWarehouseRunTest(DQAPITestBase):
    """Functional tests for the warehouse-run POST endpoint."""

    def setUp(self):
        super().setUp()
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="wh-test-asset",
            name="Warehouse Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            format="CSV",
            created_by=self.user,
        )

    def test_warehouse_run_missing_warehouse_config(self):
        response = self.client.post(
            "/api/v1/dq/runs/warehouse-run/",
            data={"dataset_id": str(self.dataset.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_warehouse_run_missing_dataset_id(self):
        response = self.client.post(
            "/api/v1/dq/runs/warehouse-run/",
            data={"warehouse_config": {"type": "postgres"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_warehouse_run_invalid_dataset_id(self):
        response = self.client.post(
            "/api/v1/dq/runs/warehouse-run/",
            data={
                "warehouse_config": {"type": "postgres"},
                "dataset_id": str(uuid.uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_warehouse_run_disabled_feature_flag(self):
        """When warehouse_dq_enabled is False, returns 403."""
        response = self.client.post(
            "/api/v1/dq/runs/warehouse-run/",
            data={
                "warehouse_config": {"type": "postgres"},
                "dataset_id": str(self.dataset.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("error"), "WAREHOUSE_DQ_DISABLED")
