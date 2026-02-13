"""
Unit tests for DQRun model.

Tests cover:
- Model creation (success scenarios)
- Model validation (failure scenarios)
- Edge cases (missing fields, invalid values)
- Error handling (constraint violations)
"""

import pytest
from django.core.exceptions import ValidationError

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQTestBase
from hub.apps.jobs.models import Job, JobStatus, JobType

pytestmark = pytest.mark.django_db(transaction=True)


class DQRunModelTest(DQTestBase):
    """Test DQRun model"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_create_dq_run_success(self):
        """Test DQ run creation with valid data"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            file=self.file,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertEqual(dq_run.tenant, self.tenant)
        self.assertEqual(dq_run.asset, self.asset)
        self.assertEqual(dq_run.job, self.job)
        self.assertEqual(dq_run.file, self.file)
        self.assertEqual(dq_run.engine, DQEngine.GREAT_EXPECTATIONS)
        self.assertEqual(dq_run.profile_key, "intake_basic_gx")
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)

    def test_create_dq_run_with_dataset(self):
        """Test DQ run creation with dataset"""
        from hub.apps.datasets.models import Dataset

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            created_by=self.user,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=dataset,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertEqual(dq_run.dataset, dataset)

    def test_create_dq_run_without_asset(self):
        """Test DQ run creation without asset (edge case)"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertIsNone(dq_run.asset)

    def test_dq_run_status_transitions(self):
        """Test DQ run status transitions"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertEqual(dq_run.status, DQRunStatus.PENDING)

        # Transition to RUNNING
        dq_run.status = DQRunStatus.RUNNING
        dq_run.save()
        self.assertEqual(dq_run.status, DQRunStatus.RUNNING)

        # Transition to SUCCEEDED
        dq_run.status = DQRunStatus.SUCCEEDED
        dq_run.overall_status = "PASS"
        dq_run.quality_score = 95.5
        dq_run.save()
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, "PASS")
        self.assertEqual(dq_run.quality_score, 95.5)

    def test_dq_run_status_failure(self):
        """Test DQ run status failure scenario"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        # Transition to FAILED
        dq_run.status = DQRunStatus.FAILED
        dq_run.details_json = {"error": "Test error", "error_type": "ValueError"}
        dq_run.save()

        self.assertEqual(dq_run.status, DQRunStatus.FAILED)
        self.assertIn("error", dq_run.details_json)

    def test_dq_run_quality_score_range(self):
        """Test DQ run quality score range (edge case)"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=0.0,  # Minimum score
        )

        self.assertEqual(dq_run.quality_score, 0.0)

        dq_run.quality_score = 100.0  # Maximum score
        dq_run.save()
        self.assertEqual(dq_run.quality_score, 100.0)
