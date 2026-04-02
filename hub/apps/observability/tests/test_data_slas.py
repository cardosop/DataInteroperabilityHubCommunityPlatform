"""
Unit tests for Data SLA service.

Comprehensive tests without mocks/stubs, following engineering best practices and TDD principles.
"""

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.observability.data_slas import DataSLAMonitor
from hub.apps.observability.models import DataObservabilityMetric, DataSLA
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class DataSLAMonitorTest(TestCase):
    """Test Data SLA Monitoring service"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_create_sla(self):
        """Test creating a data SLA"""
        sla = DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test Freshness SLA",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=86400,  # 24 hours
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
            freshness_sla_seconds=3600,  # 1 hour
        )

        # Create metric with stale data
        DataObservabilityMetric.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            freshness_age_seconds=7200,  # 2 hours (violates SLA)
            recorded_at=timezone.now(),
        )

        # Check compliance
        result = DataSLAMonitor.check_compliance(str(sla.id))

        self.assertIsNotNone(result)
        self.assertIn("is_compliant", result)
        self.assertIn("compliance_percent", result)

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
            freshness_sla_seconds=86400,
        )

        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Quality SLA",
            sla_type="QUALITY",
            asset_id=str(self.asset.id),
            quality_target_score=0.95,
        )

        dashboard = DataSLAMonitor.get_slas_dashboard(tenant_id=str(self.tenant.id), limit=10)

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertEqual(len(dashboard["results"]), 2)
        self.assertEqual(dashboard["summary"]["total_slas"], 2)
        self.assertEqual(dashboard["summary"]["active_slas"], 2)

    def test_check_all_compliance(self):
        """Test checking compliance for all active SLAs"""
        # Create SLAs
        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test SLA 1",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=3600,
        )

        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test SLA 2",
            sla_type="QUALITY",
            asset_id=str(self.asset.id),
            quality_target_score=0.9,
        )

        results = DataSLAMonitor.check_all_compliance(tenant_id=str(self.tenant.id))

        self.assertIn("checked_count", results)
        self.assertIn("compliant_count", results)
        self.assertIn("violated_count", results)
        self.assertEqual(results["checked_count"], 2)


class DataSLAMonitorFailureTest(TestCase):
    """Test DataSLAMonitor failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_create_sla_invalid_tenant_id(self):
        """Test creating SLA with invalid tenant ID"""
        with self.assertRaises(Exception):  # NotFoundError or ValidationError
            DataSLAMonitor.create_sla(
                tenant_id=str(uuid.uuid4()),  # Non-existent tenant
                name="Test SLA",
                sla_type="FRESHNESS",
                asset_id=str(self.asset.id),
                freshness_sla_seconds=3600,
            )

    def test_create_sla_invalid_sla_type(self):
        """Test creating SLA with invalid SLA type"""
        with self.assertRaises(Exception):  # ValidationError
            DataSLAMonitor.create_sla(
                tenant_id=str(self.tenant.id),
                name="Test SLA",
                sla_type="INVALID_TYPE",
                asset_id=str(self.asset.id),
            )

    def test_create_sla_missing_required_fields(self):
        """Test creating SLA with missing required fields"""
        with self.assertRaises(Exception):  # ValidationError or TypeError
            DataSLAMonitor.create_sla(
                tenant_id=str(self.tenant.id),
                # Missing name, sla_type
            )

    def test_check_compliance_invalid_sla_id(self):
        """Test checking compliance with invalid SLA ID"""
        with self.assertRaises(Exception):  # NotFoundError
            DataSLAMonitor.check_compliance(str(uuid.uuid4()))  # Non-existent SLA


class DataSLAMonitorEdgeCasesTest(TestCase):
    """Test DataSLAMonitor edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_create_sla_with_all_types(self):
        """Test creating SLA with all SLA types"""
        sla_types = ["AVAILABILITY", "FRESHNESS", "QUALITY"]

        for sla_type in sla_types:
            if sla_type == "AVAILABILITY":
                sla = DataSLAMonitor.create_sla(
                    tenant_id=str(self.tenant.id),
                    name=f"Test {sla_type} SLA",
                    sla_type=sla_type,
                    asset_id=str(self.asset.id),
                    availability_target_percent=99.9,
                )
            elif sla_type == "FRESHNESS":
                sla = DataSLAMonitor.create_sla(
                    tenant_id=str(self.tenant.id),
                    name=f"Test {sla_type} SLA",
                    sla_type=sla_type,
                    asset_id=str(self.asset.id),
                    freshness_sla_seconds=3600,
                )
            else:  # QUALITY
                sla = DataSLAMonitor.create_sla(
                    tenant_id=str(self.tenant.id),
                    name=f"Test {sla_type} SLA",
                    sla_type=sla_type,
                    asset_id=str(self.asset.id),
                    quality_target_score=0.95,
                )

            self.assertEqual(sla.sla_type, sla_type)

    def test_get_slas_dashboard_empty(self):
        """Test getting SLAs dashboard when empty"""
        dashboard = DataSLAMonitor.get_slas_dashboard(tenant_id=str(self.tenant.id), limit=10)

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertEqual(len(dashboard["results"]), 0)

    def test_get_slas_dashboard_with_large_limit(self):
        """Test getting SLAs dashboard with large limit"""
        # Create multiple SLAs
        for i in range(50):
            DataSLAMonitor.create_sla(
                tenant_id=str(self.tenant.id),
                name=f"SLA {i}",
                sla_type="FRESHNESS",
                asset_id=str(self.asset.id),
                freshness_sla_seconds=3600,
            )

        dashboard = DataSLAMonitor.get_slas_dashboard(tenant_id=str(self.tenant.id), limit=1000)

        self.assertGreaterEqual(len(dashboard["results"]), 50)


class DataSLAMonitorErrorHandlingTest(TestCase):
    """Test DataSLAMonitor error handling"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_check_compliance_handles_no_metrics(self):
        """Test checking compliance handles no metrics"""
        sla = DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Test SLA",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=3600,
        )

        # Check compliance when no metrics exist
        result = DataSLAMonitor.check_compliance(str(sla.id))

        # Should handle gracefully
        self.assertIsNotNone(result)
        self.assertIn("is_compliant", result)

    def test_check_all_compliance_handles_empty(self):
        """Test checking all compliance handles empty SLAs"""
        results = DataSLAMonitor.check_all_compliance(tenant_id=str(self.tenant.id))

        # Should return empty results structure
        self.assertIn("checked_count", results)
        self.assertEqual(results["checked_count"], 0)
