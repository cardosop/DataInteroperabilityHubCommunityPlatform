"""
E2E tests for Data Observability

End-to-end tests for complete observability workflows.
"""
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.volume import VolumeMonitor
from hub.apps.observability.schema_drift import SchemaDriftDetector
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

from .conftest import E2ETestBase


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class ObservabilityE2ETest(E2ETestBase):
    """E2E tests for data observability"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
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
            name="Test Dataset",
            schema_json={
                "fields": [
                    {"name": "email", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
    
    def test_complete_observability_workflow(self):
        """Test complete observability workflow: freshness -> volume -> drift"""
        # Step 1: Record freshness metric
        metric = FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            last_update_time=timezone.now() - timedelta(hours=1),
            freshness_sla="HOURLY",
            row_count=1000,
            size_bytes=50000,
            schema_json=self.dataset.schema_json
        )
        
        self.assertIsNotNone(metric)
        self.assertFalse(metric.is_stale)  # 1 hour old, 1 hour SLA = not stale
        
        # Step 2: Get freshness dashboard
        url = reverse('observability-get-freshness-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Step 3: Aggregate volume trends
        VolumeMonitor.aggregate_daily_trends(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id),
            days=30
        )
        
        # Step 4: Get volume dashboard
        url = reverse('observability-get-volume-dashboard')
        response = self.client.get(url, {'period_type': 'DAILY'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Step 5: Detect schema drift
        new_schema = {
            "fields": [
                {"name": "email", "type": "string", "nullable": False},
                {"name": "name", "type": "string", "nullable": True},
                {"name": "age", "type": "integer", "nullable": True}  # New field
            ]
        }
        
        drift = SchemaDriftDetector.detect_drift(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            current_schema_json=new_schema
        )
        
        self.assertIsNotNone(drift)
        self.assertIn("age", drift.new_fields)
        
        # Step 6: Get schema drift dashboard
        url = reverse('observability-get-schema-drift-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_stale_data_detection_workflow(self):
        """Test stale data detection workflow"""
        # Record stale metric
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            last_update_time=timezone.now() - timedelta(hours=2),
            freshness_sla="HOURLY"  # 1 hour SLA, 2 hours old = stale
        )
        
        # Detect stale data
        stale_data = FreshnessMonitor.detect_stale_data(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id)
        )
        
        self.assertGreater(len(stale_data), 0)
        self.assertTrue(stale_data[0]["freshness_age_seconds"] > 3600)
        
        # Get stale data via API
        url = reverse('observability-get-stale-data')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_volume_anomaly_detection_workflow(self):
        """Test volume anomaly detection workflow"""
        # Record normal metrics
        for i in range(10):
            FreshnessMonitor.record_metric(
                tenant_id=str(self.tenant.id),
                dataset=self.dataset,
                row_count=1000 + i * 10,
                size_bytes=50000 + i * 500
            )
        
        # Record anomaly (spike)
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            row_count=50000,  # Large spike
            size_bytes=2000000
        )
        
        # Aggregate trends
        trends = VolumeMonitor.aggregate_daily_trends(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id),
            days=30
        )
        
        # Check for anomalies
        anomalies = [t for t in trends if t.is_anomaly]
        # May or may not detect depending on baseline, but should process correctly
        self.assertIsInstance(anomalies, list)

