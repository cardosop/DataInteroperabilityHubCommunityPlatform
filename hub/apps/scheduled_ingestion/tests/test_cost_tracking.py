"""
Unit tests for Cost Tracking
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    IngestionCost
)
from hub.apps.scheduled_ingestion.cost_tracking import CostTrackingManager
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset


pytestmark = pytest.mark.django_db(transaction=True)


class CostTrackingTest(TestCase):
    """Test Cost Tracking"""
    
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
        
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type="S3",
            source_config={"bucket": "test-bucket"},
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user
        )
    
    def test_calculate_run_costs(self):
        """Test calculating costs for a run"""
        # Create run
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            files_found=10,
            files_processed=10,
            datasets_created=10,
            result_json={
                "files_processed": [
                    {"file_path": "file1.csv", "size_bytes": 1024 * 1024},  # 1MB
                    {"file_path": "file2.csv", "size_bytes": 2 * 1024 * 1024}  # 2MB
                ]
            }
        )
        
        # Calculate costs
        cost = CostTrackingManager.calculate_run_costs(str(run.id))
        
        self.assertIsNotNone(cost)
        self.assertEqual(cost.run, run)
        self.assertEqual(cost.scheduled_ingestion, self.scheduled_ingestion)
        self.assertGreater(cost.total_cost_usd, Decimal('0.0'))
        self.assertGreater(cost.storage_cost_usd, Decimal('0.0'))
        self.assertGreater(cost.compute_cost_usd, Decimal('0.0'))
        self.assertGreater(cost.network_cost_usd, Decimal('0.0'))
        self.assertIn('cost_breakdown_json', cost.cost_breakdown_json)
    
    def test_get_cost_report(self):
        """Test getting cost report"""
        # Create runs with costs
        run1 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(days=2),
            completed_at=timezone.now() - timedelta(days=2) + timedelta(hours=1),
            files_processed=10,
            datasets_created=10
        )
        
        run2 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(days=1),
            completed_at=timezone.now() - timedelta(days=1) + timedelta(hours=1),
            files_processed=5,
            datasets_created=5
        )
        
        # Calculate costs for runs
        cost1 = CostTrackingManager.calculate_run_costs(str(run1.id))
        cost2 = CostTrackingManager.calculate_run_costs(str(run2.id))
        
        # Get cost report
        report = CostTrackingManager.get_cost_report(
            tenant_id=str(self.tenant.id),
            start_date=timezone.now() - timedelta(days=3),
            end_date=timezone.now()
        )
        
        self.assertIn('summary', report)
        self.assertGreater(report['summary']['total_cost_usd'], 0.0)
        self.assertEqual(report['summary']['total_runs'], 2)
        self.assertIn('cost_by_ingestion', report)
        self.assertIn('daily_trends', report)

