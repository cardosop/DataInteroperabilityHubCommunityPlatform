"""
Unit tests for DQ result structure.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DQResultStructureTest(DQAPITestBase):
    """Test DQ result structure"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_dq_result_structure(self):
        """Test that DQ result has correct structure"""
        # Create DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.5,
            checks_json=[
                {
                    "check_id": "not_null_primary_key",
                    "name": "Primary key not null",
                    "category": "COMPLETENESS",
                    "severity": "ERROR",
                    "status": "PASS",
                    "message": "All ID columns are not null",
                    "target": "COLUMN",
                },
                {
                    "check_id": "null_ratio_threshold",
                    "name": "Null ratio within threshold",
                    "category": "COMPLETENESS",
                    "severity": "WARNING",
                    "status": "WARN",
                    "message": "Column has 2% null ratio (threshold: 1%)",
                    "target": "COLUMN",
                },
            ],
            details_json={
                "engine_type": "GX",
                "engine_version": "0.18.0",
                "profile_key": "intake_basic_gx",
                "metadata": {"total_rows": 100, "total_columns": 5, "execution_time_seconds": 2.5},
                "metering": {
                    "operation_type": "DQ_RUN",
                    "rows_inspected": 100,
                    "columns_inspected": 5,
                    "execution_time_seconds": 2.5,
                    "engine_type": "GX",
                    "profile_key": "intake_basic_gx",
                    "quality_score": 95.5,
                    "checks_count": 2,
                },
            },
        )

        # Retrieve DQ run
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/dq/runs/{dq_run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Verify structure
        self.assertIn("id", data)
        self.assertIn("overall_status", data)
        self.assertIn("quality_score", data)
        self.assertIn("checks_json", data)
        self.assertIn("details_json", data)

        # Verify overall_status
        self.assertEqual(data["overall_status"], "PASS")

        # Verify quality_score
        self.assertEqual(data["quality_score"], 95.5)

        # Verify checks_json structure
        checks = data["checks_json"]
        self.assertIsInstance(checks, list)
        self.assertEqual(len(checks), 2)

        # Verify first check structure
        check1 = checks[0]
        self.assertIn("check_id", check1)
        self.assertIn("name", check1)
        self.assertIn("category", check1)
        self.assertIn("severity", check1)
        self.assertIn("status", check1)
        self.assertIn("message", check1)

        # Verify details_json structure
        details = data["details_json"]
        self.assertIn("engine_type", details)
        self.assertIn("engine_version", details)
        self.assertIn("profile_key", details)
        self.assertIn("metadata", details)
        self.assertIn("metering", details)

        # Verify metering structure
        metering = details["metering"]
        self.assertIn("operation_type", metering)
        self.assertIn("rows_inspected", metering)
        self.assertIn("columns_inspected", metering)
        self.assertIn("execution_time_seconds", metering)
        self.assertIn("engine_type", metering)
        self.assertIn("quality_score", metering)
        self.assertIn("checks_count", metering)

    def test_dq_result_status_mapping(self):
        """Test DQ result status mapping (PASS, FAIL, WARN, UNKNOWN)"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Test PASS status
        dq_run_pass = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=100.0,
        )

        # Test FAIL status
        dq_run_fail = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="FAIL",
            quality_score=50.0,
        )

        # Test WARN status
        dq_run_warn = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="WARN",
            quality_score=80.0,
        )

        self.assertEqual(dq_run_pass.overall_status, "PASS")
        self.assertEqual(dq_run_fail.overall_status, "FAIL")
        self.assertEqual(dq_run_warn.overall_status, "WARN")
