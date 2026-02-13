"""
Unit tests for DQ Anomaly Detection

Tests for automatic anomaly detection in data quality metrics.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine, DQAnomaly, DQAnomalySeverity
from hub.apps.dq.anomaly_detection import AnomalyDetector
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AnomalyDetectorTest(TestCase):
    """Test AnomalyDetector"""
    
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
    
    def _create_dq_run(self, quality_score: float, completed_at: timezone.datetime = None) -> DQRun:
        """Helper to create DQ run"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
            created_by=self.user
        )
        
        return DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=quality_score,
            completed_at=completed_at or timezone.now()
        )
    
    def test_detect_z_score_anomaly(self):
        """Test z-score anomaly detection"""
        # Create baseline runs (normal values around 90)
        for i in range(10):
            self._create_dq_run(
                quality_score=90.0 + (i * 0.5),
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Create anomalous run (very low score)
        anomalous_run = self._create_dq_run(
            quality_score=50.0,  # Way below baseline
            completed_at=timezone.now()
        )
        
        # Detect anomalies
        anomalies = AnomalyDetector.detect_anomalies(anomalous_run)
        
        self.assertGreater(len(anomalies), 0)
        z_score_anomalies = [a for a in anomalies if a.anomaly_type == "z_score_outlier"]
        self.assertGreater(len(z_score_anomalies), 0)
    
    def test_detect_iqr_anomaly(self):
        """Test IQR-based anomaly detection"""
        # Create baseline runs
        for i in range(10):
            self._create_dq_run(
                quality_score=85.0 + (i * 1.0),
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Create outlier run
        outlier_run = self._create_dq_run(
            quality_score=30.0,  # Extreme outlier
            completed_at=timezone.now()
        )
        
        # Detect anomalies
        anomalies = AnomalyDetector.detect_anomalies(outlier_run)
        
        self.assertGreater(len(anomalies), 0)
        iqr_anomalies = [a for a in anomalies if a.anomaly_type == "iqr_outlier"]
        self.assertGreater(len(iqr_anomalies), 0)
    
    def test_detect_sudden_drop(self):
        """Test sudden drop detection"""
        # Create baseline runs (high scores)
        for i in range(10):
            self._create_dq_run(
                quality_score=95.0,
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Create run with sudden drop
        drop_run = self._create_dq_run(
            quality_score=70.0,  # Significant drop
            completed_at=timezone.now()
        )
        
        # Detect anomalies
        anomalies = AnomalyDetector.detect_anomalies(drop_run)
        
        self.assertGreater(len(anomalies), 0)
        drop_anomalies = [a for a in anomalies if a.anomaly_type == "sudden_drop"]
        self.assertGreater(len(drop_anomalies), 0)
    
    def test_anomaly_severity_calculation(self):
        """Test anomaly severity calculation"""
        # Create baseline
        for i in range(10):
            self._create_dq_run(
                quality_score=90.0,
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Create critical anomaly (very extreme)
        critical_run = self._create_dq_run(
            quality_score=20.0,  # Extreme outlier
            completed_at=timezone.now()
        )
        
        anomalies = AnomalyDetector.detect_anomalies(critical_run)
        
        # Should have at least one high or critical severity
        high_severity = [a for a in anomalies if a.severity in [DQAnomalySeverity.HIGH, DQAnomalySeverity.CRITICAL]]
        self.assertGreater(len(high_severity), 0)
    
    def test_detect_anomalies_for_asset(self):
        """Test anomaly detection for asset"""
        # Create baseline runs
        for i in range(10):
            self._create_dq_run(
                quality_score=90.0,
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Create anomalous run
        anomalous_run = self._create_dq_run(
            quality_score=50.0,
            completed_at=timezone.now()
        )
        
        # Detect anomalies for asset
        anomalies = AnomalyDetector.detect_anomalies_for_asset(
            str(self.asset.id),
            str(self.tenant.id)
        )
        
        self.assertGreater(len(anomalies), 0)
    
    def test_detect_anomalies_for_dataset(self):
        """Test anomaly detection for dataset"""
        # Create baseline runs
        for i in range(10):
            self._create_dq_run(
                quality_score=90.0,
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Create anomalous run
        anomalous_run = self._create_dq_run(
            quality_score=50.0,
            completed_at=timezone.now()
        )
        
        # Detect anomalies for dataset
        anomalies = AnomalyDetector.detect_anomalies_for_dataset(
            str(self.dataset.id),
            str(self.tenant.id)
        )
        
        self.assertGreater(len(anomalies), 0)
    
    def test_no_anomalies_with_insufficient_data(self):
        """Test that no anomalies are detected with insufficient data"""
        # Create only 2 runs (not enough for baseline)
        self._create_dq_run(quality_score=90.0, completed_at=timezone.now() - timedelta(days=2))
        self._create_dq_run(quality_score=50.0, completed_at=timezone.now())
        
        latest_run = DQRun.objects.filter(
            tenant=self.tenant,
            asset=self.asset
        ).order_by('-completed_at').first()
        
        anomalies = AnomalyDetector.detect_anomalies(latest_run)
        
        # Should return empty list (not enough data)
        self.assertEqual(len(anomalies), 0)

