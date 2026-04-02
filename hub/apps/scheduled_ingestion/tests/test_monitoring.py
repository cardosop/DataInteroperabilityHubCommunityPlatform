"""
Unit tests for Ingestion Monitoring Dashboard
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus
)
from hub.apps.scheduled_ingestion.monitoring import IngestionMonitoringDashboard
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class IngestionMonitoringDashboardTest(TestCase):
    """Test IngestionMonitoringDashboard"""
    
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
    
    def test_get_dashboard_summary(self):
        """Test getting dashboard summary"""
        # Create some runs
        run1 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=1),
            files_found=10,
            files_processed=9,
            files_failed=1,
            datasets_created=9
        )
        
        run2 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.FAILED,
            started_at=timezone.now() - timedelta(hours=3),
            completed_at=timezone.now() - timedelta(hours=2),
            files_found=5,
            files_processed=0,
            files_failed=5,
            datasets_created=0,
            error_message="Connection failed"
        )
        
        dashboard = IngestionMonitoringDashboard.get_dashboard(
            tenant_id=str(self.tenant.id),
            days=30
        )
        
        self.assertIn('summary', dashboard)
        self.assertEqual(dashboard['summary']['total_runs'], 2)
        self.assertEqual(dashboard['summary']['completed_runs'], 1)
        self.assertEqual(dashboard['summary']['failed_runs'], 1)
        self.assertEqual(dashboard['summary']['total_files_found'], 15)
        self.assertEqual(dashboard['summary']['total_files_processed'], 9)
        self.assertEqual(dashboard['summary']['total_files_failed'], 6)
        self.assertEqual(dashboard['summary']['total_datasets_created'], 9)
    
    def test_get_dashboard_health_status(self):
        """Test health status calculation"""
        # Create runs with different success rates
        for i in range(10):
            ScheduledIngestionRun.objects.create(
                scheduled_ingestion=self.scheduled_ingestion,
                status=ScheduledIngestionRunStatus.COMPLETED if i < 9 else ScheduledIngestionRunStatus.FAILED,
                started_at=timezone.now() - timedelta(days=i),
                completed_at=timezone.now() - timedelta(days=i) + timedelta(minutes=5),
                files_found=10,
                files_processed=9 if i < 9 else 0,
                files_failed=1 if i < 9 else 10,
                datasets_created=9 if i < 9 else 0
            )
        
        dashboard = IngestionMonitoringDashboard.get_dashboard(
            tenant_id=str(self.tenant.id),
            days=30
        )
        
        # 90% success rate (9 ok / 1 fail) should be DEGRADED
        self.assertIn('summary', dashboard)
        self.assertIn('health_status', dashboard['summary'])
        self.assertEqual(
            dashboard['summary']['health_status'], 'DEGRADED',
            f"90% success rate should be DEGRADED, got "
            f"{dashboard['summary']['health_status']}",
        )
    
    def test_get_dashboard_trends(self):
        """Test trend data generation"""
        # Create runs on different days
        for i in range(5):
            ScheduledIngestionRun.objects.create(
                scheduled_ingestion=self.scheduled_ingestion,
                status=ScheduledIngestionRunStatus.COMPLETED,
                started_at=timezone.now() - timedelta(days=i),
                completed_at=timezone.now() - timedelta(days=i) + timedelta(minutes=5),
                files_found=10,
                files_processed=10,
                datasets_created=10
            )
        
        dashboard = IngestionMonitoringDashboard.get_dashboard(
            tenant_id=str(self.tenant.id),
            days=7
        )
        
        self.assertIn('trends', dashboard)
        self.assertEqual(len(dashboard['trends']), 7)
    
    def test_get_dashboard_per_ingestion(self):
        """Test per-ingestion statistics"""
        # Create second ingestion
        ingestion2 = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion 2",
            source_type="GCS",
            source_config={"bucket": "test-bucket-2"},
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user
        )
        
        # Create runs for both ingestions
        ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            files_found=10,
            files_processed=10,
            datasets_created=10
        )
        
        ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion2,
            status=ScheduledIngestionRunStatus.COMPLETED,
            files_found=5,
            files_processed=5,
            datasets_created=5
        )
        
        dashboard = IngestionMonitoringDashboard.get_dashboard(
            tenant_id=str(self.tenant.id),
            days=30
        )
        
        self.assertIn('ingestions', dashboard)
        self.assertEqual(len(dashboard['ingestions']), 2)
        
        # Verify ingestion stats
        ingestion1_stats = next(
            (i for i in dashboard['ingestions'] if i['id'] == str(self.scheduled_ingestion.id)),
            None
        )
        self.assertIsNotNone(ingestion1_stats)
        self.assertEqual(ingestion1_stats['total_runs'], 1)
        self.assertEqual(ingestion1_stats['completed_runs'], 1)
        self.assertEqual(ingestion1_stats['success_rate'], 100.0)

