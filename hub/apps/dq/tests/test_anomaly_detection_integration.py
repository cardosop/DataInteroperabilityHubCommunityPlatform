"""
Integration tests for DQ Anomaly Detection

Tests for anomaly detection in the context of DQ run workflows.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine, DQAnomaly
from hub.apps.dq.anomaly_detection import AnomalyDetector
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AnomalyDetectionIntegrationTest(TestCase):
    """Integration tests for anomaly detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
    
    def test_anomaly_detection_workflow(self):
        """Test complete anomaly detection workflow"""
        # Create baseline DQ runs
        for i in range(15):
            job = Job.objects.create(
                tenant=self.tenant,
                job_type=JobType.DQ_CHECK,
                status=JobStatus.COMPLETED,
                created_by=self.user
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
                completed_at=timezone.now() - timedelta(days=15-i)
            )
        
        # Create anomalous DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            job_type=JobType.DQ_CHECK,
            status=JobStatus.COMPLETED,
            created_by=self.user
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
            completed_at=timezone.now()
        )
        
        # Detect anomalies
        anomalies = AnomalyDetector.detect_anomalies(anomalous_run)
        
        # Save anomalies
        for anomaly in anomalies:
            anomaly.save()
        
        # Verify anomalies were created
        saved_anomalies = DQAnomaly.objects.filter(
            tenant=self.tenant,
            asset=self.asset
        )
        self.assertGreater(saved_anomalies.count(), 0)
        
        # Verify anomaly details
        anomaly = saved_anomalies.first()
        self.assertEqual(anomaly.metric_type, "quality_score")
        self.assertIsNotNone(anomaly.expected_value)
        self.assertIsNotNone(anomaly.actual_value)
        self.assertIsNotNone(anomaly.deviation)

