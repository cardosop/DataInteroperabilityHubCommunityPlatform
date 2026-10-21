"""
Integration tests for DQ Anomaly Detection

Tests for anomaly detection in the context of DQ run workflows.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.dq.anomaly_detection import AnomalyDetector
from hub.apps.dq.models import DQAnomaly, DQEngine, DQRun, DQRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AnomalyDetectionIntegrationTest(TestCase):
    """Integration tests for anomaly detection"""

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
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

    def test_anomaly_detection_workflow(self):
        """Test complete anomaly detection workflow"""
        # Create baseline DQ runs
        for i in range(15):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
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
                quality_score=90.0,
                completed_at=timezone.now() - timedelta(days=15 - i),
            )

        # Create anomalous DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        anomalous_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=40.0,  # Anomalous
            completed_at=timezone.now(),
        )

        # Detect anomalies
        anomalies = AnomalyDetector.detect_anomalies(anomalous_run)

        # Save anomalies
        for anomaly in anomalies:
            anomaly.save()

        # Verify anomalies were created — exactly 1 anomaly for the
        # single outlier run (quality_score 40 vs baseline 90).
        saved_anomalies = DQAnomaly.objects.filter(
            tenant=self.tenant,
            asset=self.asset,
        )
        self.assertEqual(saved_anomalies.count(), 1)

        # Verify anomaly properties carry meaningful computed values,
        # not just is-not-None vacuously passing placeholders.
        anomaly = saved_anomalies.first()
        self.assertEqual(anomaly.metric_type, "quality_score")
        self.assertIsNotNone(anomaly.expected_value)
        self.assertIsNotNone(anomaly.actual_value)
        self.assertIsNotNone(anomaly.deviation)
        # The outlier value (40.0) should be reflected.
        self.assertAlmostEqual(anomaly.actual_value, 40.0, places=1)
        # Severity must be high for a 90→40 drop.
        self.assertIn(anomaly.severity, ["HIGH", "CRITICAL"])
        # Anomaly type must be set to a meaningful value.
        self.assertIsNotNone(anomaly.anomaly_type)
        self.assertGreater(len(anomaly.anomaly_type), 0)
        # Deviation should be non-zero (the drop magnitude, negative for a fall).
        self.assertNotEqual(anomaly.deviation, 0)
