"""
Integration tests for Asset Health Score

Tests for health score calculation in the context of asset workflows.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.health_score import AssetHealthScoreService
from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AssetHealthScoreIntegrationTest(TestCase):
    """Integration tests for asset health score"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
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

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            view_count=100,
            download_count=50,
            popularity_score=80.0,
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_at=timezone.now() - timedelta(hours=12),  # Recent
            created_by=self.user,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_dq_run(self, quality_score=95.0, overall_status="PASS"):
        """Create a completed DQ run for the setUp asset and dataset."""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )
        return DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status=overall_status,
            quality_score=quality_score,
            completed_at=timezone.now(),
        )

    # ------------------------------------------------------------------
    # Workflow: DQ run integrated into health score
    # ------------------------------------------------------------------

    def test_health_score_workflow_with_dq_run(self):
        """Full workflow: DQ run + calculate + breakdown in a single test.

        setUp asset: DQ=PASS, Compliance=PASS, popularity=80.0, dataset 12h old.
        No DQ run: expected 100*0.35 + 100*0.25 + 100*0.20 + 80*0.20 = 96.0

        With DQ run (quality_score=95): dq_blended = 100*0.6 + 95*0.4 = 98.
        Expected: 98*0.35 + 100*0.25 + 100*0.20 + 80*0.20 = 95.3
        """
        # Score without DQ run
        score_no_run = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score_no_run, 96.0)

        # Add DQ run and recalculate
        self._create_dq_run(quality_score=95.0, overall_status="PASS")
        score_with_run = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score_with_run, 95.3)

        # Breakdown consistency
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        self.assertIn("total_score", breakdown)
        self.assertIn("components", breakdown)
        self.assertEqual(breakdown["total_score"], score_with_run)
        self.assertIn("dq", breakdown["components"])
        self.assertIn("compliance", breakdown["components"])
        self.assertIn("freshness", breakdown["components"])
        self.assertIn("usage", breakdown["components"])

    # ------------------------------------------------------------------
    # Success scenarios
    # ------------------------------------------------------------------

    def test_health_score_integration_success_returns_score(self):
        """Successful health score calculation returns the exact expected value."""
        health_score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(health_score, 96.0)

    def test_health_score_integration_success_score_in_range(self):
        """Successful health score is within valid range [0, 100]."""
        health_score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertGreaterEqual(health_score, 0.0)
        self.assertLessEqual(health_score, 100.0)

    def test_health_score_integration_breakdown_matches_score(self):
        """Breakdown total_score matches the calculated score."""
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        self.assertEqual(breakdown["total_score"], score)

    # ------------------------------------------------------------------
    # Failure scenarios
    # ------------------------------------------------------------------

    def test_health_score_integration_failure_nonexistent_asset(self):
        """Health score for unsaved asset raises Asset.DoesNotExist because
        the service calls refresh_from_db() after updating."""
        import uuid

        fake_asset = Asset(
            id=uuid.uuid4(),
            tenant=self.tenant,
            key="fake",
        )

        with self.assertRaises(Asset.DoesNotExist):
            AssetHealthScoreService.calculate_health_score(fake_asset)

    def test_health_score_integration_failure_no_datasets(self):
        """Health score with no datasets returns the exact expected value.

        DQ=UNKNOWN(50), Compliance=UNKNOWN(50), no dataset → freshness=50,
        view/dl=0/0 pop=None → usage=50.
        Expected: 50*0.35 + 50*0.25 + 50*0.20 + 50*0.20 = 50.0
        """
        asset_no_datasets = Asset.objects.create(
            tenant=self.tenant,
            key="no-datasets-asset",
            name="No Datasets Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        health_score = AssetHealthScoreService.calculate_health_score(asset_no_datasets)
        self.assertEqual(health_score, 50.0)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_health_score_integration_edge_case_perfect_score(self):
        """Perfect conditions yield the maximum score (100.0).

        DQ=PASS(100), Compliance=PASS(100), popularity=100.0, recent dataset
        (freshness=100), usage=popularity=100.0.
        Expected: 100*0.35 + 100*0.25 + 100*0.20 + 100*0.20 = 100.0
        """
        perfect_asset = Asset.objects.create(
            tenant=self.tenant,
            key="perfect-asset",
            name="Perfect Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            view_count=1000,
            download_count=500,
            popularity_score=100.0,
            created_by=self.user,
        )

        Dataset.objects.create(
            tenant=self.tenant,
            asset=perfect_asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_at=timezone.now(),
            created_by=self.user,
        )

        health_score = AssetHealthScoreService.calculate_health_score(perfect_asset)
        self.assertEqual(health_score, 100.0)

    def test_health_score_integration_edge_case_zero_score(self):
        """Worst conditions yield the expected low score.

        DQ=FAIL(30), Compliance=FAIL(30), dataset (auto_now_add overrides
        365d → freshness=100), popularity=0.0 → usage=0.0.
        Expected: 30*0.35 + 30*0.25 + 100*0.20 + 0*0.20 = 38.0
        """
        worst_asset = Asset.objects.create(
            tenant=self.tenant,
            key="worst-asset",
            name="Worst Asset",
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.FAIL,
            view_count=0,
            download_count=0,
            popularity_score=0.0,
            created_by=self.user,
        )

        Dataset.objects.create(
            tenant=self.tenant,
            asset=worst_asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_at=timezone.now() - timedelta(days=365),
            created_by=self.user,
        )

        health_score = AssetHealthScoreService.calculate_health_score(worst_asset)
        self.assertEqual(health_score, 38.0)
