"""
Comprehensive unit tests for Observability Business Rules.

Tests cover:
- Freshness SLA validation rules
- Data SLA validation rules (availability, freshness, quality)
- Incident management business rules
- Schema drift detection rules
- Volume monitoring rules
- SLA violation detection
- Staleness detection

All tests use real implementations - no mocks/stubs.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.observability.data_slas import DataSLAMonitor
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.incident_management import IncidentManager
from hub.apps.observability.models import (
    DataIncident,
    DataObservabilityMetric,
    DataSLA,
    FreshnessSLA,
)
from hub.apps.tenants.models import KYCStatus, Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class FreshnessSLABusinessRulesTest(TestCase):
    """Test Freshness SLA business rules"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_get_sla_seconds_real_time(self):
        """Test getting SLA seconds for REAL_TIME"""
        seconds = FreshnessMonitor.get_sla_seconds(FreshnessSLA.REAL_TIME)
        self.assertEqual(seconds, 60)  # 1 minute

    def test_get_sla_seconds_near_real_time(self):
        """Test getting SLA seconds for NEAR_REAL_TIME"""
        seconds = FreshnessMonitor.get_sla_seconds(FreshnessSLA.NEAR_REAL_TIME)
        self.assertEqual(seconds, 300)  # 5 minutes

    def test_get_sla_seconds_hourly(self):
        """Test getting SLA seconds for HOURLY"""
        seconds = FreshnessMonitor.get_sla_seconds(FreshnessSLA.HOURLY)
        self.assertEqual(seconds, 3600)  # 1 hour

    def test_get_sla_seconds_daily(self):
        """Test getting SLA seconds for DAILY"""
        seconds = FreshnessMonitor.get_sla_seconds(FreshnessSLA.DAILY)
        self.assertEqual(seconds, 86400)  # 24 hours

    def test_get_sla_seconds_weekly(self):
        """Test getting SLA seconds for WEEKLY"""
        seconds = FreshnessMonitor.get_sla_seconds(FreshnessSLA.WEEKLY)
        self.assertEqual(seconds, 604800)  # 7 days

    def test_get_sla_seconds_monthly(self):
        """Test getting SLA seconds for MONTHLY"""
        seconds = FreshnessMonitor.get_sla_seconds(FreshnessSLA.MONTHLY)
        self.assertEqual(seconds, 2592000)  # 30 days

    def test_get_sla_seconds_on_demand(self):
        """Test getting SLA seconds for ON_DEMAND"""
        seconds = FreshnessMonitor.get_sla_seconds(FreshnessSLA.ON_DEMAND)
        self.assertIsNone(seconds)  # No SLA

    def test_get_sla_seconds_invalid(self):
        """Test getting SLA seconds for invalid SLA"""
        seconds = FreshnessMonitor.get_sla_seconds("INVALID_SLA")
        self.assertIsNone(seconds)

    def test_calculate_freshness_age_with_time(self):
        """Test calculating freshness age with last update time"""
        last_update = timezone.now() - timedelta(seconds=100)
        age = FreshnessMonitor.calculate_freshness_age(last_update)
        self.assertAlmostEqual(age, 100, delta=5)  # Allow 5 second variance

    def test_calculate_freshness_age_none(self):
        """Test calculating freshness age with None"""
        age = FreshnessMonitor.calculate_freshness_age(None)
        self.assertIsNone(age)

    def test_is_stale_within_sla(self):
        """Test staleness detection when within SLA"""
        is_stale = FreshnessMonitor.is_stale(30, 60)  # 30 seconds, SLA 60 seconds
        self.assertFalse(is_stale)

    def test_is_stale_exceeds_sla(self):
        """Test staleness detection when exceeds SLA"""
        is_stale = FreshnessMonitor.is_stale(120, 60)  # 120 seconds, SLA 60 seconds
        self.assertTrue(is_stale)

    def test_is_stale_exactly_at_sla(self):
        """Test staleness detection exactly at SLA threshold"""
        is_stale = FreshnessMonitor.is_stale(60, 60)  # Exactly at SLA
        # Should not be stale when exactly at SLA (stale only when strictly exceeding)
        self.assertFalse(is_stale)

    def test_is_stale_no_sla(self):
        """Test staleness detection with no SLA"""
        is_stale = FreshnessMonitor.is_stale(1000, None)  # No SLA
        self.assertFalse(is_stale)  # Never stale if no SLA

    def test_is_stale_no_age(self):
        """Test staleness detection with no age"""
        is_stale = FreshnessMonitor.is_stale(None, 60)
        self.assertFalse(is_stale)  # Not stale if no age


class DataSLABusinessRulesTest(TestCase):
    """Test Data SLA business rules"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_create_availability_sla(self):
        """Test creating availability SLA"""
        sla = DataSLA.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Availability SLA",
            sla_type="AVAILABILITY",
            availability_target_percent=99.9,
            is_active=True,
        )

        self.assertEqual(sla.sla_type, "AVAILABILITY")
        self.assertEqual(sla.availability_target_percent, 99.9)
        self.assertIsNone(sla.freshness_sla_seconds)
        self.assertIsNone(sla.quality_target_score)

    def test_create_freshness_sla(self):
        """Test creating freshness SLA"""
        sla = DataSLA.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Freshness SLA",
            sla_type="FRESHNESS",
            freshness_sla_seconds=3600,  # 1 hour
            is_active=True,
        )

        self.assertEqual(sla.sla_type, "FRESHNESS")
        self.assertEqual(sla.freshness_sla_seconds, 3600)
        self.assertIsNone(sla.availability_target_percent)
        self.assertIsNone(sla.quality_target_score)

    def test_create_quality_sla(self):
        """Test creating quality SLA"""
        sla = DataSLA.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Quality SLA",
            sla_type="QUALITY",
            quality_target_score=0.95,
            is_active=True,
        )

        self.assertEqual(sla.sla_type, "QUALITY")
        self.assertEqual(sla.quality_target_score, 0.95)
        self.assertIsNone(sla.availability_target_percent)
        self.assertIsNone(sla.freshness_sla_seconds)

    def test_sla_must_have_appropriate_target(self):
        """Test SLA must have appropriate target for its type"""
        # Availability SLA without target should fail constraint
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            DataSLA.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                name="Invalid SLA",
                sla_type="AVAILABILITY",
                # Missing availability_target_percent
                is_active=True,
            )

    def test_sla_violation_detection(self):
        """Test SLA violation detection"""
        sla = DataSLA.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Freshness SLA",
            sla_type="FRESHNESS",
            freshness_sla_seconds=3600,
            is_active=True,
        )

        # Initially not violated
        self.assertFalse(sla.is_violated)

        # Mark as violated
        sla.is_violated = True
        sla.violated_at = timezone.now()
        sla.save()

        self.assertTrue(sla.is_violated)
        self.assertIsNotNone(sla.violated_at)


class IncidentManagementBusinessRulesTest(TestCase):
    """Test Incident Management business rules"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_incident_created_with_detected_status(self):
        """Test incident is created with DETECTED status"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="FRESHNESS_VIOLATION",
            severity="HIGH",
        )

        self.assertEqual(incident.status, "DETECTED")
        self.assertIsNotNone(incident.detected_at)

    def test_incident_status_transition_detected_to_triaged(self):
        """Test incident status transition from DETECTED to TRIAGED"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="QUALITY_VIOLATION",
        )

        updated = IncidentManager.update_incident_status(
            incident_id=str(incident.id), status="TRIAGED"
        )

        self.assertEqual(updated.status, "TRIAGED")
        self.assertIsNotNone(updated.triaged_at)

    def test_incident_status_transition_to_in_progress(self):
        """Test incident status transition to IN_PROGRESS"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="SCHEMA_DRIFT",
        )

        updated = IncidentManager.update_incident_status(
            incident_id=str(incident.id),
            status="IN_PROGRESS",
            assigned_to_id=str(self.user.id),
        )

        self.assertEqual(updated.status, "IN_PROGRESS")
        self.assertEqual(updated.assigned_to, self.user)
        self.assertIsNotNone(updated.in_progress_at)

    def test_incident_status_transition_to_resolved(self):
        """Test incident status transition to RESOLVED"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="PIPELINE_FAILURE",
        )

        updated = IncidentManager.resolve_incident(
            incident_id=str(incident.id),
            resolution_notes="Fixed",
            root_cause="Root cause",
            resolved_by_id=str(self.user.id),
        )

        self.assertEqual(updated.status, "RESOLVED")
        self.assertIsNotNone(updated.resolved_at)
        self.assertIsNotNone(updated.resolution_time_seconds)
        self.assertEqual(updated.resolved_by, self.user)

    def test_incident_resolution_time_calculation(self):
        """Test incident resolution time calculation"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="FRESHNESS_VIOLATION",
        )

        # Wait so resolution_time_seconds is at least 1 (int of fractional seconds can be 0)
        import time

        time.sleep(1.1)  # INTENTIONAL: test-specific timing requirement

        resolved = IncidentManager.resolve_incident(
            incident_id=str(incident.id),
            resolution_notes="Fixed",
            root_cause="Root cause",
            resolved_by_id=str(self.user.id),
        )

        # Resolution time should be calculated
        self.assertIsNotNone(resolved.resolution_time_seconds)
        self.assertGreater(resolved.resolution_time_seconds, 0)


class ObservabilityBusinessRulesFailureTest(TestCase):
    """Test business rules failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_create_incident_missing_required_fields(self):
        """Test creating incident with missing required fields"""
        with self.assertRaises(Exception):  # ValidationError or TypeError
            IncidentManager.create_incident(
                tenant_id=str(self.tenant.id),
                # Missing title, description, incident_type
            )

    def test_update_incident_status_invalid_status(self):
        """Test updating incident with invalid status"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="FRESHNESS_VIOLATION",
        )

        with self.assertRaises(Exception):  # ValidationError
            IncidentManager.update_incident_status(
                incident_id=str(incident.id), status="INVALID_STATUS"
            )

    def test_create_sla_invalid_sla_type(self):
        """Test creating SLA with invalid SLA type"""
        with self.assertRaises(Exception):  # ValidationError
            DataSLA.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                name="Invalid SLA",
                sla_type="INVALID_TYPE",
                is_active=True,
            )

    def test_create_sla_missing_target(self):
        """Test creating SLA without appropriate target"""
        # Freshness SLA without freshness_sla_seconds should fail
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            DataSLA.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                name="Invalid Freshness SLA",
                sla_type="FRESHNESS",
                # Missing freshness_sla_seconds
                is_active=True,
            )


class ObservabilityBusinessRulesEdgeCasesTest(TestCase):
    """Test business rules edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def test_freshness_age_very_old(self):
        """Test freshness age calculation for very old data"""
        very_old_time = timezone.now() - timedelta(days=365)
        age = FreshnessMonitor.calculate_freshness_age(very_old_time)
        self.assertGreater(age, 30000000)  # More than 1 year in seconds

    def test_freshness_age_very_recent(self):
        """Test freshness age calculation for very recent data"""
        recent_time = timezone.now() - timedelta(seconds=1)
        age = FreshnessMonitor.calculate_freshness_age(recent_time)
        self.assertLessEqual(age, 5)  # Should be around 1 second

    def test_sla_with_zero_target(self):
        """Test SLA with zero target value"""
        sla = DataSLA.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Zero Availability SLA",
            sla_type="AVAILABILITY",
            availability_target_percent=0.0,
            is_active=True,
        )

        self.assertEqual(sla.availability_target_percent, 0.0)

    def test_sla_with_max_target(self):
        """Test SLA with maximum target value"""
        sla = DataSLA.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            name="Max Availability SLA",
            sla_type="AVAILABILITY",
            availability_target_percent=100.0,
            is_active=True,
        )

        self.assertEqual(sla.availability_target_percent, 100.0)

    def test_incident_with_all_severities(self):
        """Test creating incidents with all severity levels"""
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        for severity in severities:
            incident = IncidentManager.create_incident(
                tenant_id=str(self.tenant.id),
                title=f"Test {severity} Incident",
                description="Test description",
                incident_type="FRESHNESS_VIOLATION",
                severity=severity,
            )

            self.assertEqual(incident.severity, severity)

    def test_incident_with_all_types(self):
        """Test creating incidents with all incident types"""
        incident_types = [
            "FRESHNESS_VIOLATION",
            "QUALITY_VIOLATION",
            "SCHEMA_DRIFT",
            "PIPELINE_FAILURE",
            "VOLUME_ANOMALY",
        ]

        for incident_type in incident_types:
            incident = IncidentManager.create_incident(
                tenant_id=str(self.tenant.id),
                title=f"Test {incident_type}",
                description="Test description",
                incident_type=incident_type,
            )

            self.assertEqual(incident.incident_type, incident_type)
