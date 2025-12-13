"""
Unit tests for Data SLA service.
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.observability.models import DataSLA, DataObservabilityMetric
from hub.apps.observability.data_slas import DataSLAMonitor
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset


pytestmark = pytest.mark.django_db(transaction=True)


class DataSLAMonitorTest(TestCase):
    """Test Data SLA Monitoring service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            description="Test asset description"
        )
    
    def test_create_sla(self):
        """Test creating a data SLA"""
        sla = DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test Freshness SLA",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=86400  # 24 hours
        )
        
        self.assertIsNotNone(sla.id)
        self.assertEqual(sla.name, "Test Freshness SLA")
        self.assertEqual(sla.sla_type, "FRESHNESS")
        self.assertEqual(sla.freshness_sla_seconds, 86400)
        self.assertTrue(sla.is_active)
    
    def test_check_compliance_freshness(self):
        """Test checking freshness SLA compliance"""
        # Create SLA
        sla = DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test Freshness SLA",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=3600  # 1 hour
        )
        
        # Create metric with stale data
        DataObservabilityMetric.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            freshness_age_seconds=7200,  # 2 hours (violates SLA)
            recorded_at=timezone.now()
        )
        
        # Check compliance
        result = DataSLAMonitor.check_compliance(str(sla.id))
        
        self.assertIsNotNone(result)
        self.assertIn('is_compliant', result)
        self.assertIn('compliance_percent', result)
        
        # Refresh SLA
        sla.refresh_from_db()
        self.assertTrue(sla.is_violated)
    
    def test_get_slas_dashboard(self):
        """Test getting SLAs dashboard"""
        # Create SLAs
        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Freshness SLA",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=86400
        )
        
        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Quality SLA",
            sla_type="QUALITY",
            asset_id=str(self.asset.id),
            quality_target_score=0.95
        )
        
        dashboard = DataSLAMonitor.get_slas_dashboard(
            tenant_id=str(self.tenant.id),
            limit=10
        )
        
        self.assertIn('results', dashboard)
        self.assertIn('summary', dashboard)
        self.assertEqual(len(dashboard['results']), 2)
        self.assertEqual(dashboard['summary']['total_slas'], 2)
        self.assertEqual(dashboard['summary']['active_slas'], 2)
    
    def test_check_all_compliance(self):
        """Test checking compliance for all active SLAs"""
        # Create SLAs
        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test SLA 1",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=3600
        )
        
        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test SLA 2",
            sla_type="QUALITY",
            asset_id=str(self.asset.id),
            quality_target_score=0.9
        )
        
        results = DataSLAMonitor.check_all_compliance(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn('checked_count', results)
        self.assertIn('compliant_count', results)
        self.assertIn('violated_count', results)
        self.assertEqual(results['checked_count'], 2)

