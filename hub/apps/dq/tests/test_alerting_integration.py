"""
Integration tests for DQ Alerting Rules

Tests for alerting in the context of DQ run workflows.
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
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class DQAlertingIntegrationTest(TestCase):
    """Integration tests for DQ alerting"""
    
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
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
    
    def test_alerting_workflow(self):
        """Test complete alerting workflow"""
        # Create alerting rule
        rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Quality Threshold Alert",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=[DQAlertChannel.EMAIL],
            channel_config={"emails": ["test@example.com"]},
            enabled=True,
            created_by=self.user
        )
        
        # Create DQ run that triggers alert
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
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
        
        # Evaluate rules
        alerts = DQAlertingService.evaluate_rules(dq_run)
        
        # Verify alert was triggered
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0]["rule_id"], str(rule.id))
        self.assertEqual(alerts[0]["severity"], DQAnomalySeverity.HIGH)
        self.assertEqual(alerts[0]["metric_value"], 70.0)

