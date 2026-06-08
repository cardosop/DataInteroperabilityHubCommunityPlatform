"""
E2E tests for DQ Anomaly Detection and Trend Analysis

End-to-end tests for complete workflows including anomaly detection and trend analysis.
"""
import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine, DQAnomaly, DQAnomalySeverity, DQTrend
from hub.apps.dq.anomaly_detection import AnomalyDetector
from hub.apps.dq.trend_analysis import TrendAnalyzer
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
import uuid

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class DQAnomalyDetectionE2ETest(TestCase):
    """E2E tests for DQ anomaly detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        self.tenant = Tenant.objects.create(
            name=f"DQ Anomaly Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"dq-anomaly-test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"dq-anomaly-test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        self.user.status = UserStatus.ACTIVE
        self.user.save()
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)
        
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
    
    def test_complete_anomaly_detection_workflow(self):
        """
        Test complete anomaly detection workflow:
        1. Create baseline DQ runs
        2. Create anomalous DQ run
        3. Detect anomalies
        4. Save and verify anomalies
        """
        # Step 1: Create baseline DQ runs
        for i in range(20):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=self.dataset.id,
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
                completed_at=timezone.now() - timedelta(days=20-i)
            )
        
        # Step 2: Create anomalous DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
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
            quality_score=30.0,  # Extreme anomaly
            completed_at=timezone.now()
        )
        
        # Step 3: Detect anomalies
        anomalies = AnomalyDetector.detect_anomalies(anomalous_run)
        
        # Step 4: Save and verify anomalies
        for anomaly in anomalies:
            anomaly.save()
        
        saved_anomalies = DQAnomaly.objects.filter(
            tenant=self.tenant,
            asset=self.asset
        )
        self.assertGreater(saved_anomalies.count(), 0)
        
        # Verify anomaly details
        anomaly = saved_anomalies.first()
        self.assertEqual(anomaly.metric_type, "quality_score")
        # Expected value should approximate the baseline mean (~90.0)
        self.assertIsNotNone(anomaly.expected_value)
        self.assertGreater(anomaly.expected_value, 50.0,
                           "Expected value should reflect baseline (~90), not be near 0")
        self.assertEqual(anomaly.actual_value, 30.0)
        # Deviation should be negative (actual < expected)
        self.assertIsNotNone(anomaly.deviation)
        self.assertLess(anomaly.deviation, 0,
                        "Deviation should be negative when actual < expected")
        # Severity should be HIGH or CRITICAL for a 60-point drop
        self.assertIsNotNone(anomaly.severity)
        self.assertIn(anomaly.severity, ["HIGH", "CRITICAL", DQAnomalySeverity.HIGH, DQAnomalySeverity.CRITICAL],
                       "A 60-point quality drop should be HIGH or CRITICAL severity")


class DQTrendAnalysisE2ETest(TestCase):
    """E2E tests for DQ trend analysis"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
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
    
    def test_complete_trend_analysis_workflow(self):
        """
        Test complete trend analysis workflow:
        1. Create DQ runs over time
        2. Calculate trends
        3. Save trends
        4. Generate visualizations
        """
        # Step 1: Create DQ runs with improving trend
        for i in range(30):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=self.dataset.id,
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
                quality_score=70.0 + (i * 1.0),  # Improving trend
                completed_at=timezone.now() - timedelta(days=30-i)
            )
        
        # Step 2: Calculate trends
        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            period_type="DAILY",
            periods=30
        )
        
        # Step 3: Save trends
        for trend in trends:
            trend.save()
        
        saved_trends = DQTrend.objects.filter(
            tenant=self.tenant,
            asset=self.asset
        )
        self.assertGreater(saved_trends.count(), 0)

        # Verify trend data reflects the improving quality scores (70 → 99)
        first_trend = saved_trends.order_by('period_start').first()
        self.assertIsNotNone(first_trend.metric_type)
        self.assertIsNotNone(first_trend.current_value)

        # Step 4: Generate visualizations
        json_viz = TrendAnalyzer.get_trend_visualization(trends, format="json")
        chart_viz = TrendAnalyzer.get_trend_visualization(trends, format="chart_data")

        # Verify JSON visualization structure and content
        self.assertIsInstance(json_viz, list)
        self.assertGreater(len(json_viz), 0)

        # Verify chart visualization structure and content
        self.assertIsInstance(chart_viz, dict)
        self.assertIn("labels", chart_viz)
        self.assertIn("datasets", chart_viz)
        self.assertGreater(len(chart_viz["labels"]), 0)
        self.assertGreater(len(chart_viz["datasets"]), 0)
        # Datasets should contain actual data points
        first_dataset = chart_viz["datasets"][0]
        self.assertIn("data", first_dataset,
                       "Chart dataset should have a 'data' key with values")

