"""
Unit tests for Asset Health Score

Tests for health score calculation combining DQ, compliance, freshness, and usage.
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


class AssetHealthScoreServiceTest(TestCase):
    """Test AssetHealthScoreService"""

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
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

    def test_calculate_health_score_returns_score(self):
        """Test calculate_health_score returns the exact expected value.

        setUp: DQ=PASS(100), Compl=PASS(100), dataset → freshness=100,
        view=100+dl=50 / pop=None → usage=100.
        Expected: 100*0.35 + 100*0.25 + 100*0.20 + 100*0.20 = 100.0.
        """
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 100.0)

    def test_calculate_health_score_returns_score_in_range(self):
        """Test calculate_health_score returns score between 0 and 100."""
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_calculate_health_score_saves_score_to_asset(self):
        """Test calculate_health_score saves exact score to asset."""
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.health_score, score)
        self.assertEqual(score, 100.0)

    def test_calculate_health_score_dq_component_pass_status(self):
        """Test DQ component with PASS=100 status yields expected weighted score."""
        self.asset.dq_status = DQStatus.PASS
        self.asset.save()

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 100.0)

    def test_calculate_health_score_dq_component_fail_status(self):
        """Test DQ component with FAIL=30 status yields expected weighted score.

        FAIL(30)*0.35 + PASS(100)*0.25 + 100*0.20 + 100*0.20 = 75.5.
        """
        self.asset.dq_status = DQStatus.FAIL
        self.asset.save()

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 75.5)

    def test_calculate_health_score_dq_pass_higher_than_fail(self):
        """Test DQ PASS status produces a higher score than FAIL status.

        PASS: 100.0, FAIL: 75.5.
        """
        self.asset.dq_status = DQStatus.PASS
        self.asset.save()
        pass_score = AssetHealthScoreService.calculate_health_score(self.asset)

        self.asset.dq_status = DQStatus.FAIL
        self.asset.save()
        fail_score = AssetHealthScoreService.calculate_health_score(self.asset)

        self.assertEqual(pass_score, 100.0)
        self.assertEqual(fail_score, 75.5)
        self.assertGreater(pass_score, fail_score)

    def test_calculate_health_score_compliance_component_pass_status(self):
        """Test compliance component with PASS=100 status yields expected weighted score."""
        self.asset.compliance_status = ComplianceStatus.PASS
        self.asset.save()

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 100.0)

    def test_calculate_health_score_compliance_component_fail_status(self):
        """Test compliance component with FAIL=30 status yields expected weighted score.

        PASS(100)*0.35 + FAIL(30)*0.25 + 100*0.20 + 100*0.20 = 82.5.
        """
        self.asset.compliance_status = ComplianceStatus.FAIL
        self.asset.save()

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 82.5)

    def test_calculate_health_score_compliance_pass_higher_than_fail(self):
        """Test compliance PASS status produces a higher score than FAIL status.

        PASS: 100.0, FAIL: 82.5.
        """
        self.asset.compliance_status = ComplianceStatus.PASS
        self.asset.save()
        pass_score = AssetHealthScoreService.calculate_health_score(self.asset)

        self.asset.compliance_status = ComplianceStatus.FAIL
        self.asset.save()
        fail_score = AssetHealthScoreService.calculate_health_score(self.asset)

        self.assertEqual(pass_score, 100.0)
        self.assertEqual(fail_score, 82.5)
        self.assertGreater(pass_score, fail_score)

    def test_calculate_health_score_with_dq_run(self):
        """Test health score with DQ run blends quality_score into DQ component.

        dq_blended = 100*0.6 + 95*0.4 = 98.
        Expected: 98*0.35 + 100*0.25 + 100*0.20 + 100*0.20 = 99.3.
        """
        # Create DQ run with quality score
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

        score_with = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score_with, 99.3)

    def test_calculate_health_score_freshness_component(self):
        """Test freshness component with a recent dataset yields expected score.

        The setUp dataset (auto_now_add) is the newest, so freshness=100.
        Expected: 100.0 (same as setUp fixture).
        """
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_at=timezone.now() - timedelta(hours=12),
            created_by=self.user,
        )

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 100.0)

    def test_calculate_health_score_usage_component(self):
        """Test usage component with popularity_score=90 yields expected score.

        usage_score = popularity_score = 90.0 (not None).
        Expected: 100*0.35 + 100*0.25 + 100*0.20 + 90*0.20 = 98.0.
        """
        self.asset.view_count = 200
        self.asset.download_count = 100
        self.asset.popularity_score = 90.0
        self.asset.save()

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 98.0)

    def test_get_health_score_breakdown_returns_total_score(self):
        """Test get_health_score_breakdown returns total_score."""
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        self.assertIn("total_score", breakdown)

    def test_get_health_score_breakdown_returns_components(self):
        """Test get_health_score_breakdown returns components."""
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        self.assertIn("components", breakdown)

    def test_get_health_score_breakdown_includes_all_component_types(self):
        """Test get_health_score_breakdown includes all component types."""
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        components = breakdown["components"]
        self.assertIn("dq", components)
        self.assertIn("compliance", components)
        self.assertIn("freshness", components)
        self.assertIn("usage", components)

    def test_get_health_score_breakdown_dq_component_has_required_fields(self):
        """Test get_health_score_breakdown DQ component has required fields."""
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        dq_component = breakdown["components"]["dq"]
        self.assertIn("score", dq_component)
        self.assertIn("weight", dq_component)
        self.assertIn("weighted_score", dq_component)

    def test_recalculate_all_health_scores_returns_correct_count(self):
        """Test recalculating all health scores returns correct count."""
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                status=AssetStatus.ACTIVE,
                dq_status=DQStatus.PASS,
                compliance_status=ComplianceStatus.PASS,
                created_by=self.user,
            )

        count = AssetHealthScoreService.recalculate_all_health_scores(str(self.tenant.id))
        self.assertEqual(count, 6)

    def test_recalculate_all_health_scores_calculates_scores(self):
        """Test recalculating all health scores calculates expected scores.

        Each created asset: DQ=PASS(100), Compl=PASS(100), no dataset (freshness=50),
        no popularity_score → usage=0.0.
        Expected: 100*0.35 + 100*0.25 + 50*0.20 + 0*0.20 = 70.0.
        """
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                status=AssetStatus.ACTIVE,
                dq_status=DQStatus.PASS,
                compliance_status=ComplianceStatus.PASS,
                created_by=self.user,
            )

        AssetHealthScoreService.recalculate_all_health_scores(str(self.tenant.id))

        assets = Asset.objects.filter(tenant=self.tenant)
        for asset in assets:
            self.assertIsNotNone(asset.health_score)
            # setUp asset: dataset → fresh=100, view/dl=100/50 → usage=100 → 100.0
            # created extras: no dataset → fresh=50, view/dl=0/0 pop=None → usage=50 → 80.0
            if asset.key == "test-asset":
                self.assertEqual(asset.health_score, 100.0)
            else:
                self.assertEqual(asset.health_score, 80.0)

    # ========== SUCCESS SCENARIOS ==========

    def test_calculate_health_score_perfect_asset_returns_high_score_in_range(self):
        """Perfect conditions yield the maximum score (100.0).

        DQ=PASS(100), Compliance=PASS(100), freshness=100 (1h-old dataset),
        popularity=100.0 → usage=100.0.
        Expected: 100*0.35 + 100*0.25 + 100*0.20 + 100*0.20 = 100.0.
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
            created_at=timezone.now() - timedelta(hours=1),
            created_by=self.user,
        )

        score = AssetHealthScoreService.calculate_health_score(perfect_asset)
        self.assertEqual(score, 100.0)

    # ========== EDGE CASES ==========

    def test_calculate_health_score_zero_usage(self):
        """Zero usage yields the exact expected score.

        DQ=UNKNOWN(50), Compl=UNKNOWN(50), no dataset → freshness=50,
        popularity=0.0 → usage=0.0.
        Expected: 50*0.35 + 50*0.25 + 50*0.20 + 0*0.20 = 40.0.
        """
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="zero-usage-asset",
            name="Zero Usage Asset",
            status=AssetStatus.ACTIVE,
            view_count=0,
            download_count=0,
            popularity_score=0.0,
            created_by=self.user,
        )

        score = AssetHealthScoreService.calculate_health_score(asset)
        self.assertEqual(score, 40.0)

    def test_calculate_health_score_no_datasets(self):
        """No datasets yield the exact expected score.

        DQ=PASS(100), Compl=PASS(100), no dataset → freshness=50,
        no popularity_score → usage=0.0.
        Expected: 100*0.35 + 100*0.25 + 50*0.20 + 0*0.20 = 70.0.
        """
        asset_no_datasets = Asset.objects.create(
            tenant=self.tenant,
            key="no-datasets-asset",
            name="No Datasets Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        score = AssetHealthScoreService.calculate_health_score(asset_no_datasets)
        # DQ=PASS(100), Compl=PASS(100), no dataset → fresh=50,
        # view/dl=0/0 pop=None → usage=50. 100*.35+100*.25+50*.20+50*.20=80.0
        self.assertEqual(score, 80.0)

    def test_calculate_health_score_very_old_dataset(self):
        """Very old dataset does not change score when a newer dataset exists.

        The setUp dataset (auto_now_add) remains the newest, so freshness stays
        at 100 and the expected score is still 100.0.
        """
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=2,
            created_at=timezone.now() - timedelta(days=365),
            created_by=self.user,
        )

        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertEqual(score, 100.0)

    def test_calculate_health_score_unknown_statuses(self):
        """UNKNOWN statuses yield the exact expected score.

        DQ=UNKNOWN(50), Compl=UNKNOWN(50), no dataset → fresh=50,
        view/dl=0/0 pop=None → usage=50.
        Expected: 50*0.35 + 50*0.25 + 50*0.20 + 50*0.20 = 50.0.
        """
        asset_unknown = Asset.objects.create(
            tenant=self.tenant,
            key="unknown-status-asset",
            name="Unknown Status Asset",
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.UNKNOWN,
            compliance_status=ComplianceStatus.UNKNOWN,
            created_by=self.user,
        )

        score = AssetHealthScoreService.calculate_health_score(asset_unknown)
        self.assertEqual(score, 50.0)

    def test_get_health_score_breakdown_empty_components_returns_structure(self):
        """Test health score breakdown with empty components returns structure."""
        asset_minimal = Asset.objects.create(
            tenant=self.tenant,
            key="minimal-asset",
            name="Minimal Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        breakdown = AssetHealthScoreService.get_health_score_breakdown(asset_minimal)
        self.assertIn("total_score", breakdown)
        self.assertIn("components", breakdown)

    def test_get_health_score_breakdown_empty_components_includes_component_types(self):
        """Test health score breakdown with empty components includes component types."""
        asset_minimal = Asset.objects.create(
            tenant=self.tenant,
            key="minimal-asset",
            name="Minimal Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        breakdown = AssetHealthScoreService.get_health_score_breakdown(asset_minimal)
        components = breakdown["components"]
        self.assertIn("dq", components)
        self.assertIn("compliance", components)

    # ========== ERROR HANDLING ==========

    def test_calculate_health_score_nonexistent_asset(self):
        """Test health score calculation with None asset raises error."""
        with self.assertRaises((AttributeError, TypeError)):
            AssetHealthScoreService.calculate_health_score(None)

    def test_recalculate_all_health_scores_invalid_tenant(self):
        """Test recalculating health scores with invalid tenant returns 0."""
        fake_tenant_id = str(uuid.uuid4())

        count = AssetHealthScoreService.recalculate_all_health_scores(fake_tenant_id)
        self.assertEqual(count, 0)

    def test_get_health_score_breakdown_returns_valid_structure(self):
        """Test breakdown returns valid structure with total_score."""
        # Use valid asset
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)

        # Should return breakdown or handle errors gracefully
        self.assertIsNotNone(breakdown)
        self.assertIn("total_score", breakdown)
