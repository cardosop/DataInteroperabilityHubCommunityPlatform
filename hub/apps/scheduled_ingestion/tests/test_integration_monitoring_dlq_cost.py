"""
Integration tests for Monitoring, DLQ, and Cost Tracking
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    DeadLetterQueueItem,
    IngestionCost
)
from hub.apps.scheduled_ingestion.monitoring import IngestionMonitoringDashboard
from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager
from hub.apps.scheduled_ingestion.cost_tracking import CostTrackingManager
from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class MonitoringDLQCostIntegrationTest(TestCase):
    """Integration tests for monitoring, DLQ, and cost tracking"""
    
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
    
    def test_complete_workflow_monitoring_dlq_cost(self):
        """Test complete workflow: monitoring, DLQ sync, and cost tracking"""
        # Create runs
        run1 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=1),
            files_found=10,
            files_processed=8,
            files_failed=2,
            datasets_created=8,
            result_json={
                "files_processed": [
                    {"file_path": "file1.csv", "size_bytes": 1024 * 1024}
                ]
            }
        )
        
        run2 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            files_found=5,
            files_processed=5,
            files_failed=0,
            datasets_created=5
        )
        
        # Mark some files as permanently failed
        state_manager = IncrementalStateManager(self.scheduled_ingestion)
        for i in range(3):
            state_manager.mark_file_failed(
                file_path="failed_file.csv",
                error_message="Permanent error",
                error_code="PERMANENT_ERROR",
                retry_count=i,
                max_retries=3
            )
        
        # Sync DLQ
        DeadLetterQueueManager.sync_from_ingestion_state(str(self.scheduled_ingestion.id))
        
        # Calculate costs
        cost1 = CostTrackingManager.calculate_run_costs(str(run1.id))
        cost2 = CostTrackingManager.calculate_run_costs(str(run2.id))
        
        # Get monitoring dashboard
        dashboard = IngestionMonitoringDashboard.get_dashboard(
            tenant_id=str(self.tenant.id),
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            days=30
        )
        
        # Get DLQ dashboard
        dlq_dashboard = DeadLetterQueueManager.get_dlq_dashboard(
            tenant_id=str(self.tenant.id),
            scheduled_ingestion_id=str(self.scheduled_ingestion.id)
        )
        
        # Get cost report
        cost_report = CostTrackingManager.get_cost_report(
            tenant_id=str(self.tenant.id),
            scheduled_ingestion_id=str(self.scheduled_ingestion.id)
        )
        
        # Verify monitoring dashboard
        self.assertEqual(dashboard['summary']['total_runs'], 2)
        self.assertEqual(dashboard['summary']['completed_runs'], 2)
        
        # Verify DLQ dashboard
        self.assertEqual(dlq_dashboard['summary']['total_items'], 1)
        self.assertEqual(dlq_dashboard['summary']['pending_items'], 1)
        
        # Verify cost report
        self.assertGreater(cost_report['summary']['total_cost_usd'], 0.0)
        self.assertEqual(cost_report['summary']['total_runs'], 2)

