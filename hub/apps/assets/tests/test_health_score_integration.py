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
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
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

    def test_health_score_workflow_calculates_score(self):
        """Test complete health score workflow calculates score."""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            completed_at=timezone.now(),
        )

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertIsNotNone(score)

    def test_health_score_workflow_score_in_range(self):
        """Test complete health score workflow score is in range."""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            completed_at=timezone.now(),
        )

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_health_score_workflow_breakdown_has_total_score(self):
        """Test complete health score workflow breakdown has total_score."""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            completed_at=timezone.now(),
        )

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        self.assertIn("total_score", breakdown)

    def test_health_score_workflow_breakdown_has_components(self):
        """Test complete health score workflow breakdown has components."""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            completed_at=timezone.now(),
        )

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        self.assertIn("components", breakdown)

    def test_health_score_workflow_breakdown_matches_score(self):
        """Test complete health score workflow breakdown total_score matches calculated score."""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            completed_at=timezone.now(),
        )

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        self.assertEqual(breakdown["total_score"], score)

    # ========== SUCCESS SCENARIOS ==========

    def test_health_score_integration_success_returns_score(self):
        """Test successful health score calculation integration returns score."""
        health_score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertIsNotNone(health_score)

    def test_health_score_integration_success_score_in_range(self):
        """Test successful health score calculation integration score is in range."""
        health_score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertGreaterEqual(health_score, 0.0)
        self.assertLessEqual(health_score, 100.0)

    # ========== FAILURE SCENARIOS ==========

    def test_health_score_integration_failure_nonexistent_asset(self):
        """Health score for unsaved asset raises because the service
        persists the computed score via asset.save()."""
        import uuid

        fake_asset = Asset(
            id=uuid.uuid4(), tenant=self.tenant, key="fake",
        )

        # The service calls asset.save() to persist health_score,
        # which fails for an unsaved object with a fabricated PK.
        with self.assertRaises(Exception):
            AssetHealthScoreService.calculate_health_score(fake_asset)

    def test_health_score_integration_failure_no_datasets(self):
        """Test health score calculation with no datasets (failure scenario)"""
        asset_no_datasets = Asset.objects.create(
            tenant=self.tenant,
            key="no-datasets-asset",
            name="No Datasets Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Should handle no datasets gracefully
        health_score = AssetHealthScoreService.calculate_health_score(asset_no_datasets)

        # Should return score (may be lower without datasets)
        self.assertIsNotNone(health_score)
        self.assertGreaterEqual(health_score, 0.0)

    # ========== EDGE CASES ==========

    def test_health_score_integration_edge_case_perfect_score(self):
        """Test health score calculation with perfect conditions (edge case)"""
        # Create asset with perfect conditions
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

        # Create recent dataset
        recent_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=perfect_asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_at=timezone.now(),  # Very recent
            created_by=self.user,
        )

        health_score = AssetHealthScoreService.calculate_health_score(perfect_asset)

        # Should return high score
        self.assertGreaterEqual(health_score, 80.0)

    def test_health_score_integration_edge_case_zero_score(self):
        """Test health score calculation with worst conditions (edge case)"""
        # Create asset with worst conditions
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

        # Create old dataset
        old_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=worst_asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_at=timezone.now() - timedelta(days=365),  # Very old
            created_by=self.user,
        )

        health_score = AssetHealthScoreService.calculate_health_score(worst_asset)

        # Should return low score
        self.assertLessEqual(health_score, 50.0)

    # ========== ERROR HANDLING ==========

    def test_health_score_integration_error_handling(self):
        """Test error handling in health score calculation integration"""
        # Use valid asset
        try:
            health_score = AssetHealthScoreService.calculate_health_score(self.asset)
            # Should return score
            self.assertIsNotNone(health_score)
            self.assertGreaterEqual(health_score, 0.0)
            self.assertLessEqual(health_score, 100.0)
        except Exception:
            # If raises exception, that's a problem
            self.fail("calculate_health_score should handle errors gracefully")
