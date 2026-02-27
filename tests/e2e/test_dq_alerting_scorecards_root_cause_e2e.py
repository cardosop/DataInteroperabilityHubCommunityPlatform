"""
E2E tests for DQ Alerting Rules, Scorecards, and Root Cause Analysis

End-to-end tests for complete workflows.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.dq.models import (
    DQRun, DQRunStatus, DQEngine, DQAlertingRule, DQAnomalySeverity, DQAlertChannel,
    DQTrend, DQTrendDirection, DQAnomaly
)
from hub.apps.dq.alerting import DQAlertingService
from hub.apps.dq.scorecards import DQScorecardService
from hub.apps.dq.root_cause_analysis import RootCauseAnalyzer
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class DQAlertingE2ETest(TestCase):
    """E2E tests for DQ alerting rules"""
    
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
    
    def test_complete_alerting_workflow(self):
        """
        Test complete alerting workflow:
        1. Create alerting rule
        2. Create DQ run that triggers alert
        3. Evaluate rules
        4. Verify alert delivery
        """
        # Step 1: Create alerting rule
        rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Quality Threshold Alert",
            description="Alert when quality score drops below 80",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=[DQAlertChannel.EMAIL, DQAlertChannel.WEBHOOK],
            channel_config={
                "emails": ["ops@example.com"],
                "url": "https://webhook.example.com/alerts"
            },
            enabled=True,
            created_by=self.user
        )
        
        # Step 2: Create DQ run that triggers alert
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
            status=JobStatus.COMPLETED,
            created_by=self.user
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=70.0,  # Below threshold
            completed_at=timezone.now()
        )
        
        # Step 3: Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        # Step 4: Verify alert delivery
        self.assertGreater(len(alerts), 0)
        alert = alerts[0]
        self.assertEqual(alert["rule_id"], str(rule.id))
        self.assertEqual(alert["severity"], DQAnomalySeverity.HIGH)
        self.assertEqual(alert["metric_value"], 70.0)
        self.assertIn("triggered_at", alert)


class DQScorecardsE2ETest(TestCase):
    """E2E tests for DQ scorecards"""
    
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
    
    def test_complete_scorecard_workflow(self):
        """
        Test complete scorecard workflow:
        1. Create DQ runs over time
        2. Create trends
        3. Generate executive dashboard
        4. Generate asset scorecard
        5. Test drill-down
        """
        # Step 1: Create DQ runs
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
                overall_status="PASS" if i % 3 != 0 else "FAIL",
                quality_score=85.0 + (i * 0.5),
                completed_at=timezone.now() - timedelta(days=20-i)
            )
        
        # Step 2: Create trends
        for i in range(10):
            DQTrend.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                metric_type="quality_score",
                period_start=timezone.now() - timedelta(days=10-i),
                period_end=timezone.now() - timedelta(days=9-i),
                period_type="DAILY",
                current_value=85.0 + (i * 1.0),
                previous_value=84.0 + (i * 1.0),
                change_amount=1.0,
                change_percent=1.2,
                direction=DQTrendDirection.IMPROVING
            )
        
        # Step 3: Generate executive dashboard
        dashboard = DQScorecardService.get_executive_dashboard(
            str(self.tenant.id),
            days=30
        )
        
        self.assertIn("summary", dashboard)
        self.assertIn("score_distribution", dashboard)
        self.assertIn("trend_summary", dashboard)
        self.assertEqual(dashboard["summary"]["total_runs"], 20)
        
        # Step 4: Generate asset scorecard
        scorecard = DQScorecardService.get_asset_scorecard(
            str(self.asset.id),
            str(self.tenant.id),
            days=30
        )
        
        self.assertIn("metrics", scorecard)
        self.assertIn("recent_runs", scorecard)
        self.assertIn("trends", scorecard)
        
        # Step 5: Test drill-down
        drill_down = DQScorecardService.drill_down(
            str(self.tenant.id),
            asset_id=str(self.asset.id),
            days=30
        )
        
        self.assertIn("metrics", drill_down)
        self.assertIn("run_history", drill_down)
        self.assertEqual(drill_down["metrics"]["total_runs"], 20)


class DQRootCauseE2ETest(TestCase):
    """E2E tests for DQ root cause analysis"""
    
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
            schema_json={"fields": [{"name": "col1", "type": "string", "data_type": "string", "nullable": True}]},
            format="CSV",
            version=1,
            row_count=1000,
            created_by=self.user
        )
    
    def test_complete_root_cause_analysis_workflow(self):
        """
        Test complete root cause analysis workflow:
        1. Create historical DQ runs
        2. Create anomalies
        3. Create failed DQ run
        4. Analyze root cause
        5. Generate report
        """
        # Step 1: Create historical runs (each dataset must have unique version per asset)
        for i in range(10):
            historical_file = File.objects.create(
                tenant=self.tenant,
                name=f"hist{i}.csv",
                content_type="text/csv",
                size=1000,
                status=FileStatus.ACTIVE,
                storage_path=f"test/hist{i}.csv",
                content_sha256=f"hist{i}",
                created_by=self.user
            )
            # Use version=2+i so (tenant, asset, version) is unique (version=1 used by self.dataset)
            historical_dataset = Dataset.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                file=historical_file,
                schema_json={"fields": [{"name": "col1", "type": "string", "data_type": "string"}]},
                format="CSV",
                version=2 + i,
                row_count=1000,
                created_by=self.user
            )
            
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=historical_dataset.id,
                status=JobStatus.COMPLETED,
                created_by=self.user
            )

            DQRun.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                dataset=historical_dataset,
                job=job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
                overall_status="PASS",
                quality_score=90.0,
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Step 2: Create anomalies
        for i in range(3):
            DQAnomaly.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                metric_type="quality_score",
                expected_value=90.0,
                actual_value=70.0,
                deviation=-20.0,
                severity=DQAnomalySeverity.HIGH,
                anomaly_type="sudden_drop",
                detected_at=timezone.now() - timedelta(days=i)
            )
        
        # Step 3: Create failed DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
            status=JobStatus.COMPLETED,
            created_by=self.user
        )
        
        failed_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="FAIL",
            quality_score=60.0,
            checks_json=[
                {
                    "name": "expect_column_values_to_not_be_null",
                    "type": "column",
                    "status": "FAIL",
                    "result": False,
                    "message": "Column has null values"
                }
            ],
            completed_at=timezone.now()
        )
        
        # Step 4: Analyze root cause
        analysis = RootCauseAnalyzer.analyze_root_cause(failed_run)
        
        self.assertIn("root_causes", analysis)
        self.assertIn("primary_cause", analysis)
        self.assertIn("recommendations", analysis)
        self.assertGreater(len(analysis["root_causes"]), 0)
        
        # Step 5: Generate report
        report = RootCauseAnalyzer.generate_root_cause_report(
            str(self.tenant.id),
            asset_id=str(self.asset.id),
            days=30
        )
        
        self.assertIn("summary", report)
        self.assertIn("analyses", report)
        self.assertIn("common_recommendations", report)
        self.assertGreater(report["summary"]["total_failed_runs"], 0)

