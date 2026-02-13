"""
Unit tests for DQ Alerting Rules

Tests for configurable alerting rules and threshold-based alerts.
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.dq.models import (
    DQRun, DQRunStatus, DQEngine, DQAlertingRule, DQAnomalySeverity, DQAlertChannel
)
from hub.apps.dq.alerting import DQAlertingService
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class DQAlertingServiceTest(TestCase):
    """Test DQAlertingService"""
    
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
    
    def _create_dq_run(self, quality_score: float) -> DQRun:
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
            completed_at=timezone.now()
        )
    
    def _create_alerting_rule(
        self,
        threshold: float,
        operator: str = "<",
        severity: str = DQAnomalySeverity.MEDIUM,
        asset=None
    ) -> DQAlertingRule:
        """Helper to create alerting rule"""
        return DQAlertingRule.objects.create(
            tenant=self.tenant,
            asset=asset,
            name=f"Test Rule {threshold}",
            metric_type="quality_score",
            threshold=threshold,
            comparison_operator=operator,
            severity=severity,
            alert_channels=[DQAlertChannel.EMAIL],
            channel_config={"emails": ["test@example.com"]},
            enabled=True,
            created_by=self.user
        )
    
    def test_evaluate_rules_threshold_met(self):
        """Test rule evaluation when threshold is met"""
        # Create rule: quality_score < 80
        rule = self._create_alerting_rule(80.0, operator="<")
        
        # Create DQ run with score below threshold
        dq_run = self._create_dq_run(quality_score=70.0)
        
        # Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["rule_id"], str(rule.id))
        self.assertEqual(alerts[0]["severity"], rule.severity)
        self.assertEqual(alerts[0]["metric_value"], 70.0)
    
    def test_evaluate_rules_threshold_not_met(self):
        """Test rule evaluation when threshold is not met"""
        # Create rule: quality_score < 80
        rule = self._create_alerting_rule(80.0, operator="<")
        
        # Create DQ run with score above threshold
        dq_run = self._create_dq_run(quality_score=90.0)
        
        # Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        self.assertEqual(len(alerts), 0)
    
    def test_evaluate_rules_multiple_rules(self):
        """Test evaluation with multiple rules"""
        # Create multiple rules
        rule1 = self._create_alerting_rule(80.0, operator="<", severity=DQAnomalySeverity.MEDIUM)
        rule2 = self._create_alerting_rule(70.0, operator="<", severity=DQAnomalySeverity.HIGH)
        
        # Create DQ run that triggers both
        dq_run = self._create_dq_run(quality_score=65.0)
        
        # Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        self.assertEqual(len(alerts), 2)
        alert_severities = [a["severity"] for a in alerts]
        self.assertIn(DQAnomalySeverity.MEDIUM, alert_severities)
        self.assertIn(DQAnomalySeverity.HIGH, alert_severities)
    
    def test_evaluate_rules_asset_specific(self):
        """Test asset-specific rules"""
        # Create asset-specific rule
        rule = self._create_alerting_rule(80.0, operator="<", asset=self.asset)
        
        # Create DQ run for this asset
        dq_run = self._create_dq_run(quality_score=70.0)
        
        # Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["rule_id"], str(rule.id))
    
    def test_evaluate_rules_global_and_asset_specific(self):
        """Test both global and asset-specific rules"""
        # Create global rule
        global_rule = self._create_alerting_rule(90.0, operator="<", asset=None)
        
        # Create asset-specific rule
        asset_rule = self._create_alerting_rule(80.0, operator="<", asset=self.asset)
        
        # Create DQ run that triggers both
        dq_run = self._create_dq_run(quality_score=75.0)
        
        # Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        self.assertEqual(len(alerts), 2)
        rule_ids = [a["rule_id"] for a in alerts]
        self.assertIn(str(global_rule.id), rule_ids)
        self.assertIn(str(asset_rule.id), rule_ids)
    
    def test_evaluate_rules_disabled_rule(self):
        """Test that disabled rules are not evaluated"""
        # Create disabled rule
        rule = self._create_alerting_rule(80.0, operator="<")
        rule.enabled = False
        rule.save()
        
        # Create DQ run that would trigger rule
        dq_run = self._create_dq_run(quality_score=70.0)
        
        # Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        self.assertEqual(len(alerts), 0)
    
    def test_rule_evaluate_method(self):
        """Test rule evaluate method"""
        rule = self._create_alerting_rule(80.0, operator="<")
        
        # Test threshold met
        self.assertTrue(rule.evaluate(70.0))
        
        # Test threshold not met
        self.assertFalse(rule.evaluate(90.0))
        
        # Test disabled rule
        rule.enabled = False
        self.assertFalse(rule.evaluate(70.0))
    
    def test_rule_comparison_operators(self):
        """Test all comparison operators"""
        # Less than
        rule_lt = self._create_alerting_rule(80.0, operator="<")
        self.assertTrue(rule_lt.evaluate(70.0))
        self.assertFalse(rule_lt.evaluate(80.0))
        self.assertFalse(rule_lt.evaluate(90.0))
        
        # Less than or equal
        rule_lte = self._create_alerting_rule(80.0, operator="<=")
        self.assertTrue(rule_lte.evaluate(70.0))
        self.assertTrue(rule_lte.evaluate(80.0))
        self.assertFalse(rule_lte.evaluate(90.0))
        
        # Greater than
        rule_gt = self._create_alerting_rule(80.0, operator=">")
        self.assertFalse(rule_gt.evaluate(70.0))
        self.assertFalse(rule_gt.evaluate(80.0))
        self.assertTrue(rule_gt.evaluate(90.0))
        
        # Greater than or equal
        rule_gte = self._create_alerting_rule(80.0, operator=">=")
        self.assertFalse(rule_gte.evaluate(70.0))
        self.assertTrue(rule_gte.evaluate(80.0))
        self.assertTrue(rule_gte.evaluate(90.0))

