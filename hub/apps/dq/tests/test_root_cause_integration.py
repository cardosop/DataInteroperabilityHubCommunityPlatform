"""
Integration tests for DQ Root Cause Analysis

Tests for root cause analysis in the context of DQ workflows.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine, DQAnomaly, DQAnomalySeverity
from hub.apps.dq.root_cause_analysis import RootCauseAnalyzer
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class RootCauseAnalysisIntegrationTest(TestCase):
    """Integration tests for root cause analysis"""
    
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
    
    def test_root_cause_analysis_workflow(self):
        """Test complete root cause analysis workflow"""
        # Create historical runs
        for i in range(5):
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
            
            # Use version=i+2 so (tenant, asset, version) is unique per iteration
            # (version=1 is already used by self.dataset in setUp)
            historical_dataset = Dataset.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                file=historical_file,
                schema_json={"fields": [{"name": "col1", "type": "string", "data_type": "string"}]},
                format="CSV",
                version=i + 2,
                row_count=1000,
                created_by=self.user
            )
            
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
                resource_id=historical_dataset.id,
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
                completed_at=timezone.now() - timedelta(days=5-i)
            )
        
        # Create failed run with check failures
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
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
        
        # Analyze root cause
        analysis = RootCauseAnalyzer.analyze_root_cause(failed_run)
        
        # Verify analysis structure
        self.assertIn("root_causes", analysis)
        self.assertIn("primary_cause", analysis)
        self.assertIn("recommendations", analysis)
        self.assertGreater(len(analysis["root_causes"]), 0)
        
        # Should have check failure
        check_failures = [c for c in analysis["root_causes"] if c["type"] == "CHECK_FAILURE"]
        self.assertGreater(len(check_failures), 0)
    
    def test_root_cause_report_generation(self):
        """Test root cause report generation"""
        # Create multiple failed runs
        for i in range(3):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
                resource_id=self.dataset.id,
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
                overall_status="FAIL",
                quality_score=60.0 + i,
                checks_json=[
                    {
                        "name": f"test_check_{i}",
                        "type": "column",
                        "status": "FAIL"
                    }
                ],
                completed_at=timezone.now() - timedelta(days=i)
            )
        
        # Generate report
        report = RootCauseAnalyzer.generate_root_cause_report(
            str(self.tenant.id),
            asset_id=str(self.asset.id),
            days=30
        )
        
        # Verify report structure
        self.assertIn("summary", report)
        self.assertIn("analyses", report)
        self.assertIn("common_recommendations", report)
        self.assertGreater(report["summary"]["total_failed_runs"], 0)
        self.assertGreater(len(report["analyses"]), 0)

