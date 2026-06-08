"""
Unit tests for DQ Root Cause Analysis

Tests for root cause identification, correlation analysis, and reporting.
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
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class RootCauseAnalyzerTest(TestCase):
    """Test RootCauseAnalyzer"""
    
    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
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
    
    def _create_dq_run(
        self,
        quality_score: float,
        overall_status: str = "PASS",
        checks_json=None,
        completed_at=None
    ) -> DQRun:
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
            overall_status=overall_status,
            quality_score=quality_score,
            checks_json=checks_json or [],
            completed_at=completed_at or timezone.now()
        )
    
    def test_analyze_root_cause_check_failure(self):
        """Test root cause analysis for check failures"""
        # Create DQ run with check failures
        checks_json = [
            {
                "name": "expect_column_values_to_not_be_null",
                "type": "column",
                "status": "FAIL",
                "result": False,
                "message": "Column has null values"
            }
        ]
        
        dq_run = self._create_dq_run(
            quality_score=60.0,
            overall_status="FAIL",
            checks_json=checks_json
        )
        
        # Analyze root cause
        analysis = RootCauseAnalyzer.analyze_root_cause(dq_run)
        
        self.assertIn("root_causes", analysis)
        self.assertGreaterEqual(len(analysis["root_causes"]), 1)

        # Should have exactly 1 check failure root cause (1 FAIL check created).
        check_failures = [c for c in analysis["root_causes"] if c["type"] == "CHECK_FAILURE"]
        self.assertEqual(len(check_failures), 1)
        self.assertEqual(check_failures[0]["details"]["check_name"], "expect_column_values_to_not_be_null")
    
    def test_analyze_root_cause_schema_change(self):
        """Test root cause analysis for schema changes"""
        # Use a separate asset so (tenant, asset, version) stays unique (self.dataset uses self.asset v1)
        asset_schema = Asset.objects.create(
            tenant=self.tenant,
            key="schema-asset",
            name="Schema Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        parent_file = File.objects.create(
            tenant=self.tenant,
            name="parent.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/parent.csv",
            content_sha256="def456",
            created_by=self.user
        )
        
        parent_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset_schema,
            file=parent_file,
            schema_json={"fields": [{"name": "col1", "type": "string", "data_type": "string", "nullable": True}]},
            format="CSV",
            version=1,
            row_count=1000,
            created_by=self.user
        )
        
        # Create child dataset with schema change
        child_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset_schema,
            file=self.file,
            schema_json={"fields": [
                {"name": "col1", "type": "string", "data_type": "string", "nullable": True},
                {"name": "col2", "type": "integer", "data_type": "integer", "nullable": False}  # New field
            ]},
            format="CSV",
            version=2,
            row_count=1000,
            parent_version=parent_dataset,
            created_by=self.user
        )
        
        dq_run = self._create_dq_run(
            quality_score=70.0,
            overall_status="FAIL"
        )
        dq_run.dataset = child_dataset
        dq_run.save()
        
        # Analyze root cause
        analysis = RootCauseAnalyzer.analyze_root_cause(dq_run)
        
        # Should detect schema change
        schema_changes = [c for c in analysis["root_causes"] if c["type"] == "SCHEMA_CHANGE"]
        self.assertGreaterEqual(len(schema_changes), 1)
        details = schema_changes[0]["details"]
        self.assertEqual(details["added_fields"], ["col2"],
            "col2 was added in the child schema")
        self.assertTrue(details["has_changes"],
            "schema difference must set has_changes=True")
    
    def test_analyze_root_cause_volume_change(self):
        """Test root cause analysis for volume changes"""
        # Create historical runs with consistent volume (unique version per dataset)
        historical_datasets = []
        for i in range(5):
            historical_file = File.objects.create(
                tenant=self.tenant,
                name=f"historical{i}.csv",
                content_type="text/csv",
                size=1000,
                status=FileStatus.ACTIVE,
                storage_path=f"test/historical{i}.csv",
                content_sha256=f"hist{i}",
                created_by=self.user
            )
            # Use version=i+2 so (tenant, asset, version) is unique per iteration
            # (version=1 is already used by self.dataset in setUp)
            historical_dataset = Dataset.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                file=historical_file,
                schema_json={"fields": [{"name": "col1", "type": "string"}]},
                format="CSV",
                version=i + 2,
                row_count=1000,  # Consistent volume
                created_by=self.user
            )
            historical_datasets.append(historical_dataset)
            
            # Create DQ run associated with this historical dataset
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
        
        # Create current run with significant volume change
        self.dataset.row_count = 5000  # 5x increase
        self.dataset.save()
        
        dq_run = self._create_dq_run(
            quality_score=70.0,
            overall_status="FAIL"
        )
        
        # Analyze root cause
        analysis = RootCauseAnalyzer.analyze_root_cause(dq_run)
        
        # Should detect volume change
        volume_changes = [c for c in analysis["root_causes"] if c["type"] == "VOLUME_CHANGE"]
        self.assertGreaterEqual(len(volume_changes), 1)
        details = volume_changes[0]["details"]
        self.assertEqual(details["current_count"], 5000,
            "current row_count must be the updated 5000")
        self.assertEqual(details["average_count"], 1000,
            "historical average must be 1000 (all historical datasets have 1000 rows)")
        # H10: 1000→5000 is a 400% increase — assert exact value, not just >100.
        self.assertEqual(details["change_percent"], 400,
            f"1000→5000 is a 400%% increase, got {details['change_percent']}")
    
    def test_analyze_root_cause_anomaly_correlation(self):
        """Test root cause analysis for anomaly correlation"""
        # Create recent anomalies
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
        
        dq_run = self._create_dq_run(
            quality_score=70.0,
            overall_status="FAIL"
        )
        
        # Analyze root cause
        analysis = RootCauseAnalyzer.analyze_root_cause(dq_run)
        
        # Should detect anomaly correlation
        anomaly_correlations = [c for c in analysis["root_causes"] if c["type"] == "ANOMALY_CORRELATION"]
        self.assertGreaterEqual(len(anomaly_correlations), 1)
        details = anomaly_correlations[0]["details"]
        self.assertEqual(details["anomaly_count"], 3,
            "must report all 3 created anomalies")
        self.assertEqual(details["high_severity_count"], 3,
            "all 3 anomalies have HIGH severity")
    
    def test_analyze_root_cause_confidence_scores(self):
        """Test confidence score calculation"""
        checks_json = [
            {
                "name": "test_check",
                "type": "column",
                "status": "FAIL",
                "result": False
            }
        ]
        
        dq_run = self._create_dq_run(
            quality_score=60.0,
            overall_status="FAIL",
            checks_json=checks_json
        )
        
        analysis = RootCauseAnalyzer.analyze_root_cause(dq_run)
        
        # Check failures should have high confidence
        for cause in analysis["root_causes"]:
            self.assertIn("confidence", cause)
            if cause["type"] == "CHECK_FAILURE":
                self.assertGreater(cause["confidence"], 0.8)
    
    def test_analyze_root_cause_recommendations(self):
        """Test recommendation generation"""
        checks_json = [
            {
                "name": "expect_column_values_to_not_be_null",
                "type": "column",
                "status": "FAIL"
            }
        ]
        
        dq_run = self._create_dq_run(
            quality_score=60.0,
            overall_status="FAIL",
            checks_json=checks_json
        )
        
        analysis = RootCauseAnalyzer.analyze_root_cause(dq_run)
        
        self.assertIn("recommendations", analysis)
        self.assertGreaterEqual(len(analysis["recommendations"]), 1)
        # At least one recommendation must name the failing check
        self.assertTrue(
            any("expect_column_values_to_not_be_null" in r for r in analysis["recommendations"]),
            f"Recommendations must reference the failing check; got {analysis['recommendations']}")
    
    def test_generate_root_cause_report(self):
        """Test root cause report generation"""
        # Create failed runs
        for i in range(5):
            self._create_dq_run(
                quality_score=60.0 + i,
                overall_status="FAIL",
                completed_at=timezone.now() - timedelta(days=i)
            )
        
        # Generate report
        report = RootCauseAnalyzer.generate_root_cause_report(
            str(self.tenant.id),
            asset_id=str(self.asset.id),
            days=30
        )
        
        self.assertIn("summary", report)
        self.assertIn("analyses", report)
        self.assertIn("common_recommendations", report)
        self.assertGreater(report["summary"]["total_failed_runs"], 0)

