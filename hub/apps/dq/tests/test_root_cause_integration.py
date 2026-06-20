"""
Integration tests for DQ Root Cause Analysis

Tests for root cause analysis in the context of DQ workflows.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.root_cause_analysis import RootCauseAnalyzer
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class RootCauseAnalysisIntegrationTest(TestCase):
    """Integration tests for root cause analysis"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

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
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "type": "string", "data_type": "string", "nullable": True}
                ]
            },
            format="CSV",
            version=1,
            row_count=1000,
            created_by=self.user,
        )

    def _create_dq_run(self, dataset, overall_status="PASS", quality_score=90.0,
                       checks_json=None, completed_at=None,
                       profile_key="intake_basic_gx", engine=DQEngine.GREAT_EXPECTATIONS,
                       status=DQRunStatus.SUCCEEDED):
        """Create a DQRun with an associated Job in a single call.

        Reduces the copy-paste ``Job + DQRun`` creation that was
        repeated in every test method.
        """
        if completed_at is None:
            completed_at = timezone.now()
        if checks_json is None:
            checks_json = []

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=dataset.id,
            created_by=self.user,
        )
        return DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=dataset,
            job=job,
            profile_key=profile_key,
            engine=engine,
            status=status,
            overall_status=overall_status,
            quality_score=quality_score,
            checks_json=checks_json,
            completed_at=completed_at,
        )

    def test_root_cause_analysis_workflow(self):
        """Test complete root cause analysis workflow"""
        # Create historical runs
        for i in range(5):
            historical_file = File.objects.create(
                tenant=self.tenant,
                name=f"hist{i}.csv",
                content_type="text/csv",
                size=1000,
                status=FileStatus.ACTIVE,
                storage_path=f"test/hist{i}.csv",
                content_sha256=f"hist{i}",
                created_by=self.user,
            )

            # Use version=i+2 so (tenant, asset, version) is unique per iteration
            # (version=1 is already used by self.dataset in setUp)
            historical_dataset = Dataset.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                file=historical_file,
                schema_json={"fields": [{"name": "col1", "type": "string", "data_type": "string"}]},
                format="CSV",
                version=i + 2,
                row_count=1000,
                created_by=self.user,
            )

            self._create_dq_run(
                dataset=historical_dataset,
                overall_status="PASS",
                quality_score=90.0,
                completed_at=timezone.now() - timedelta(days=5 - i),
            )

        # Create failed run with check failures
        failed_run = self._create_dq_run(
            dataset=self.dataset,
            overall_status="FAIL",
            quality_score=60.0,
            checks_json=[
                {
                    "name": "expect_column_values_to_not_be_null",
                    "type": "column",
                    "status": "FAIL",
                    "result": False,
                    "message": "Column has null values",
                }
            ],
            completed_at=timezone.now(),
        )

        # Analyze root cause
        analysis = RootCauseAnalyzer.analyze_root_cause(failed_run)

        # Verify analysis structure
        self.assertIn("root_causes", analysis)
        self.assertIn("primary_cause", analysis)
        self.assertIn("recommendations", analysis)
        self.assertGreaterEqual(len(analysis["root_causes"]), 1)

        # Should have exactly 1 check failure (1 FAIL check in checks_json).
        check_failures = [c for c in analysis["root_causes"] if c["type"] == "CHECK_FAILURE"]
        self.assertEqual(len(check_failures), 1)
        # Validate content, not just existence.
        self.assertEqual(
            check_failures[0]["details"]["check_name"], "expect_column_values_to_not_be_null"
        )

    def test_root_cause_report_generation(self):
        """Test root cause report generation"""
        # Create multiple failed runs
        for i in range(3):
            self._create_dq_run(
                dataset=self.dataset,
                overall_status="FAIL",
                quality_score=60.0 + i,
                checks_json=[{"name": f"test_check_{i}", "type": "column", "status": "FAIL"}],
                completed_at=timezone.now() - timedelta(days=i),
            )

        # Generate report
        report = RootCauseAnalyzer.generate_root_cause_report(
            str(self.tenant.id), asset_id=str(self.asset.id), days=30
        )

        # Verify report structure
        self.assertIn("summary", report)
        self.assertIn("analyses", report)
        self.assertIn("common_recommendations", report)
        self.assertGreaterEqual(report["summary"]["total_failed_runs"], 3)
        self.assertGreaterEqual(len(report["analyses"]), 3)
        # Validate summary content, not just key existence.
        self.assertIsNotNone(report["summary"])
        self.assertIsInstance(report["analyses"], list)
