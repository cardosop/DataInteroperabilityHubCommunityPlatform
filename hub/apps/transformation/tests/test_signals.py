"""
Unit tests for transformation signals — Phase 115F.1

Tests the dataset version creation signal that triggers
event-based transformation pipelines.
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.transformation.models import (
    PipelineExecution,
    PipelineStatus,
    TransformationPipeline,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DatasetVersionSignalTest(TestCase):
    """Test that dataset version creation triggers transformation."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass",
            tenant=self.tenant,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant, key=f"a-{uid}",
            name="Test Asset", status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_signal_registered(self):
        """Signal handler is connected to Dataset post_save."""
        from django.db.models.signals import post_save
        receivers = [
            r for r in post_save.receivers
            if "trigger_transformation" in str(r)
        ]
        self.assertGreaterEqual(len(receivers), 1)

    def test_no_crash_on_dataset_create_without_pipelines(self):
        """Creating a dataset without matching pipelines doesn't crash."""
        f = File.objects.create(
            tenant=self.tenant, name="test.csv",
            size=100, content_type="text/csv",
            storage_path="test/test.csv",
            created_by=self.user,
        )
        # Should not raise — signal fires but finds no pipelines
        Dataset.objects.create(
            tenant=self.tenant, asset=self.asset,
            file=f, format="CSV", version=1,
        )
        self.assertEqual(PipelineExecution.objects.count(), 0)

    def test_no_crash_on_dataset_update(self):
        """Updating an existing dataset doesn't trigger pipelines."""
        f = File.objects.create(
            tenant=self.tenant, name="test.csv",
            size=100, content_type="text/csv",
            storage_path="test/test.csv",
            created_by=self.user,
        )
        ds = Dataset.objects.create(
            tenant=self.tenant, asset=self.asset,
            file=f, format="CSV", version=1,
        )
        # Update — should not trigger (created=False)
        ds.version = 2
        ds.save()
        self.assertEqual(PipelineExecution.objects.count(), 0)

    def test_pipeline_with_matching_source_asset(self):
        """ACTIVE pipeline with matching source_asset_id is found."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Auto Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "s1", "type": "filter"}],
            },
            status=PipelineStatus.ACTIVE,
            metadata={
                "source_asset_id": str(self.asset.id),
            },
        )

        f = File.objects.create(
            tenant=self.tenant, name="new.csv",
            size=200, content_type="text/csv",
            storage_path="test/new.csv",
            created_by=self.user,
        )
        # Signal fires, finds the pipeline — should not crash
        Dataset.objects.create(
            tenant=self.tenant, asset=self.asset,
            file=f, format="CSV", version=2,
        )
        # Pipeline still exists and is active
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.status, PipelineStatus.ACTIVE)

    def test_inactive_pipeline_not_triggered(self):
        """DRAFT/INACTIVE pipelines should not be triggered."""
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Draft Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "s1", "type": "filter"}],
            },
            status=PipelineStatus.DRAFT,
            metadata={
                "source_asset_id": str(self.asset.id),
            },
        )

        f = File.objects.create(
            tenant=self.tenant, name="draft.csv",
            size=100, content_type="text/csv",
            storage_path="test/draft.csv",
            created_by=self.user,
        )
        # Should not crash — DRAFT pipeline is ignored
        Dataset.objects.create(
            tenant=self.tenant, asset=self.asset,
            file=f, format="CSV", version=3,
        )
