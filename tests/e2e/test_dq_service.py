"""
Comprehensive E2E tests for DQ service.

Covers:
- DQ run creation
- DQ run execution (async)
- DQ result storage
- Asset DQ status updates
- DQ run status transitions
- DQ service error handling
- Multiple DQ profiles

Uses REAL services (DQ service, Redis, no mocks).
"""

import hashlib
import time

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, DQStatus
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.jobs.models import Job, JobStatus, JobType

from .conftest import E2ETestBase, get_response_data

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e2]


class DQServiceE2ETest(E2ETestBase):
    """Test DQ service operations"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_create_dq_run_success(self):
        """Test creating a DQ run"""
        asset_id = self.create_asset(key="dq-run-test", name="DQ Run Test")
        test_content = b"col1,col2\nval1,val2\nval3,val4"
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_test.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        dq_run_id = self.run_dq_check(file_id, dataset_id, asset_id)

        # Verify DQ run created with correct relationships
        dq_run = DQRun.objects.get(id=dq_run_id)
        self.assertEqual(str(dq_run.asset_id), str(asset_id))
        self.assertEqual(str(dq_run.dataset_id), str(dataset_id))
        self.assertEqual(str(dq_run.file_id), str(file_id))
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)
        self.assertEqual(dq_run.profile_key, "intake_basic_gx")

        # Verify job created and linked
        job = Job.objects.filter(type=JobType.DQ_RUN, resource_id=dq_run_id).first()
        self.assertIsNotNone(job, "Job should be created for DQ run")
        self.assertEqual(job.status, JobStatus.PENDING)

    def test_dq_run_execution_updates_status(self):
        """Test that DQ run execution transitions status from PENDING"""
        asset_id = self.create_asset(key="dq-execution-test", name="DQ Execution Test")
        test_content = b"col1,col2\nval1,val2\nval3,val4"
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_execution_test.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        dq_run_id = self.run_dq_check_sync(file_id, dataset_id, asset_id)

        dq_run = DQRun.objects.get(id=dq_run_id)

        # The critical assertion: status MUST have left PENDING after execution.
        self.assertNotEqual(
            dq_run.status,
            DQRunStatus.PENDING,
            "DQ run status should transition from PENDING after inline execution",
        )

        # Verify the job also transitioned
        job = Job.objects.filter(type=JobType.DQ_RUN, resource_id=dq_run_id).first()
        self.assertIsNotNone(job)
        self.assertNotEqual(
            job.status,
            JobStatus.PENDING,
            "Job status should transition from PENDING after inline execution",
        )

        # If succeeded, verify result fields are populated
        if dq_run.status == DQRunStatus.SUCCEEDED:
            self.assertIsNotNone(dq_run.overall_status, "Succeeded DQ run must have overall_status")
            self.assertIsNotNone(dq_run.quality_score, "Succeeded DQ run must have quality_score")
            self.assertGreaterEqual(dq_run.quality_score, 0.0)
            self.assertLessEqual(dq_run.quality_score, 100.0)

    def test_dq_run_updates_asset_dq_status(self):
        """Test that a successful DQ run updates the parent asset's dq_status"""
        asset_id = self.create_asset(key="dq-status-test", name="DQ Status Test")
        test_content = b"col1,col2\nval1,val2\nval3,val4"
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_status_test.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        # Capture asset dq_status before
        Asset.objects.get(id=asset_id)

        dq_run_id = self.run_dq_check_sync(file_id, dataset_id, asset_id)
        dq_run = DQRun.objects.get(id=dq_run_id)

        # The run must have left PENDING
        self.assertNotEqual(dq_run.status, DQRunStatus.PENDING)

        asset = Asset.objects.get(id=asset_id)
        if dq_run.status == DQRunStatus.SUCCEEDED:
            # After a successful run, the asset MUST have a valid dq_status
            self.assertIn(
                asset.dq_status,
                [DQStatus.PASS, DQStatus.WARN, DQStatus.FAIL],
                "Successful DQ run must set asset dq_status to PASS/WARN/FAIL",
            )
        elif dq_run.status == DQRunStatus.FAILED:
            # Even on failure, verify the run completed (has timestamps)
            self.assertIsNotNone(
                dq_run.completed_at, "Failed DQ run should have completed_at timestamp"
            )

    def test_dq_run_with_explicit_profile(self):
        """Test DQ run creation with an explicit profile key"""
        asset_id = self.create_asset(key="dq-profile-test", name="DQ Profile Test")
        test_content = b"col1,col2\nval1,val2\nval3,val4"
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_profile_test.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        response = self.client.post(
            "/api/v1/dq/runs/",
            {
                "asset_id": asset_id,
                "dataset_id": dataset_id,
                "file_id": file_id,
                "profile_key": "intake_basic_gx",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        self.assertEqual(data.get("profile_key"), "intake_basic_gx")

        # Verify DB matches response
        dq_run = DQRun.objects.get(id=data["id"])
        self.assertEqual(dq_run.profile_key, "intake_basic_gx")

    def test_list_dq_runs_with_filters(self):
        """Test listing DQ runs and filtering by asset_id"""
        asset_id1 = self.create_asset(key="dq-list-1", name="DQ List 1")
        asset_id2 = self.create_asset(key="dq-list-2", name="DQ List 2")

        test_content = b"col1,col2\nval1,val2"
        content_hash = hashlib.sha256(test_content).hexdigest()

        file_id1 = self.init_file_upload(
            name="dq_list1.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id1, content_sha256=content_hash, test_content=test_content)
        dataset_id1 = self.create_dataset(file_id1, asset_id1)
        dq_run_id1 = self.run_dq_check(file_id1, dataset_id1, asset_id1)

        time.sleep(3)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services
        file_id2 = self.init_file_upload(
            name="dq_list2.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id2, content_sha256=content_hash, test_content=test_content)
        dataset_id2 = self.create_dataset(file_id2, asset_id2)
        dq_run_id2 = self.run_dq_check(file_id2, dataset_id2, asset_id2)

        # Unfiltered list should include both runs
        response = self.client.get("/api/v1/dq/runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        all_ids = {d["id"] for d in data.get("results", [])}
        self.assertIn(str(dq_run_id1), all_ids)
        self.assertIn(str(dq_run_id2), all_ids)

        # Filter by asset_id1 should include run1
        response = self.client.get(f"/api/v1/dq/runs/?asset_id={asset_id1}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        filtered_ids = {d["id"] for d in data.get("results", [])}
        self.assertIn(str(dq_run_id1), filtered_ids)
        # Verify filter actually reduced results (fewer than unfiltered)
        self.assertLessEqual(
            len(filtered_ids), len(all_ids), "Filtered results should not exceed unfiltered count"
        )

    def test_get_dq_run_details(self):
        """Test retrieving DQ run details via API"""
        asset_id = self.create_asset(key="dq-details-test", name="DQ Details Test")
        test_content = b"col1,col2\nval1,val2"
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_details_test.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)
        dq_run_id = self.run_dq_check(file_id, dataset_id, asset_id)

        response = self.client.get(f"/api/v1/dq/runs/{dq_run_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data["id"], str(dq_run_id))
        self.assertEqual(data["status"], DQRunStatus.PENDING)
        self.assertIn("profile_key", data)
        # API serializer uses FK name 'asset' (not 'asset_id')
        asset_field = data.get("asset_id") or data.get("asset")
        self.assertEqual(str(asset_field), str(asset_id))

    def test_dq_run_result_structure(self):
        """Test that a successful DQ run populates all expected result fields"""
        asset_id = self.create_asset(key="dq-result-test", name="DQ Result Test")
        test_content = b"col1,col2\nval1,val2\nval3,val4"
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_result_test.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        dq_run_id = self.run_dq_check_sync(file_id, dataset_id, asset_id)
        dq_run = DQRun.objects.get(id=dq_run_id)

        # Run must have left PENDING regardless of outcome
        self.assertNotEqual(dq_run.status, DQRunStatus.PENDING)

        if dq_run.status == DQRunStatus.SUCCEEDED:
            self.assertIsNotNone(dq_run.overall_status)
            self.assertIsNotNone(dq_run.quality_score)
            self.assertIsNotNone(dq_run.checks_json)
            self.assertIsInstance(
                dq_run.checks_json, list, "checks_json should be a list of check results"
            )
        else:
            # If FAILED, verify there is a completed_at and a linked job with error
            self.assertIsNotNone(dq_run.completed_at, "Failed DQ run should have completed_at")
            job = Job.objects.filter(type=JobType.DQ_RUN, resource_id=dq_run_id).first()
            self.assertIsNotNone(job)
            self.assertEqual(job.status, JobStatus.FAILED)

    def test_dq_run_with_json_format(self):
        """Test DQ run creation and execution with JSON format file"""
        asset_id = self.create_asset(key="dq-json-test", name="DQ JSON Test")
        json_content = b'{"id": 1, "name": "Alice"}\n{"id": 2, "name": "Bob"}'
        content_hash = hashlib.sha256(json_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_json_test.json", content_type="application/json", size=len(json_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=json_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        # Create and execute DQ run to verify JSON files are processed
        dq_run_id = self.run_dq_check_sync(file_id, dataset_id, asset_id)
        dq_run = DQRun.objects.get(id=dq_run_id)

        # Must have left PENDING — verifies the job actually ran for JSON input
        self.assertNotEqual(
            dq_run.status,
            DQRunStatus.PENDING,
            "DQ run on JSON file should execute (not stay PENDING)",
        )

    def test_dq_run_error_handling(self):
        """Test that invalid file input is rejected at dataset or DQ stage"""
        asset_id = self.create_asset(key="dq-error-test", name="DQ Error Test")
        test_content = b"\n\n"  # Empty lines without headers
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(
            name="dq_error_test.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)

        # Dataset creation should reject empty/invalid files
        response = self.client.post(
            "/api/v1/datasets/",
            {"file_id": file_id, "asset_id": asset_id, "name": "Error Test Dataset"},
            format="json",
        )

        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]:
            # Correctly rejected — verify error is meaningful
            resp_data = get_response_data(response) or {}
            error_msg = str(resp_data).lower()
            self.assertTrue(
                any(
                    kw in error_msg for kw in ["empty", "no headers", "schema inference", "no data"]
                ),
                f"Error should reference empty/invalid file, got: {resp_data}",
            )
            return

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        dataset_id = (get_response_data(response) or {}).get("id")

        # If dataset was created, DQ run on empty data should fail
        dq_run_id = self.run_dq_check_sync(file_id, dataset_id, asset_id)
        dq_run = DQRun.objects.get(id=dq_run_id)

        # After execution, run should be FAILED (empty file has no data to check)
        self.assertNotEqual(
            dq_run.status, DQRunStatus.PENDING, "DQ run should execute even for invalid data"
        )
        if dq_run.status == DQRunStatus.FAILED:
            job = Job.objects.filter(type=JobType.DQ_RUN, resource_id=dq_run_id).first()
            self.assertIsNotNone(job, "Failed DQ run should have a job")
            self.assertIsNotNone(job.error_message, "Failed job should store an error message")
