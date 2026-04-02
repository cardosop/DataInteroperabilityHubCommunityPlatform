"""
Unit tests for Data Incident Management service.

Comprehensive tests without mocks/stubs, following engineering best practices and TDD principles.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.observability.incident_management import IncidentManager
from hub.apps.observability.models import DataIncident
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class IncidentManagerTest(TestCase):
    """Test Data Incident Management service"""

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

    def test_create_incident(self):
        """Test creating a data incident"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test incident description",
            incident_type="FRESHNESS_VIOLATION",
            severity="HIGH",
            resource_type="ASSET",
            resource_id=str(self.asset.id),
            detected_by_id=str(self.user.id),
        )

        self.assertIsNotNone(incident.id)
        self.assertEqual(incident.title, "Test Incident")
        self.assertEqual(incident.status, "DETECTED")
        self.assertEqual(incident.severity, "HIGH")
        self.assertIsNotNone(incident.detected_at)

    def test_update_incident_status(self):
        """Test updating incident status"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="QUALITY_VIOLATION",
        )

        # Update to TRIAGED
        updated = IncidentManager.update_incident_status(
            incident_id=str(incident.id), status="TRIAGED"
        )

        self.assertEqual(updated.status, "TRIAGED")
        self.assertIsNotNone(updated.triaged_at)

        # Update to IN_PROGRESS
        updated = IncidentManager.update_incident_status(
            incident_id=str(incident.id), status="IN_PROGRESS", assigned_to_id=str(self.user.id)
        )

        self.assertEqual(updated.status, "IN_PROGRESS")
        self.assertIsNotNone(updated.in_progress_at)
        self.assertEqual(updated.assigned_to, self.user)

        # Update to RESOLVED
        updated = IncidentManager.update_incident_status(
            incident_id=str(incident.id),
            status="RESOLVED",
            resolution_notes="Issue resolved",
            root_cause="Root cause identified",
            resolved_by_id=str(self.user.id),
        )

        self.assertEqual(updated.status, "RESOLVED")
        self.assertIsNotNone(updated.resolved_at)
        self.assertIsNotNone(updated.resolution_time_seconds)
        self.assertEqual(updated.resolution_notes, "Issue resolved")

    def test_assign_incident(self):
        """Test assigning incident to a user"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="PIPELINE_FAILURE",
        )

        assigned = IncidentManager.assign_incident(
            incident_id=str(incident.id), assigned_to_id=str(self.user.id)
        )

        self.assertEqual(assigned.assigned_to, self.user)
        self.assertEqual(assigned.status, "IN_PROGRESS")
        self.assertIsNotNone(assigned.in_progress_at)

    def test_resolve_incident(self):
        """Test resolving an incident"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="SCHEMA_DRIFT",
        )

        resolved = IncidentManager.resolve_incident(
            incident_id=str(incident.id),
            resolution_notes="Fixed schema drift",
            root_cause="Schema changed unexpectedly",
            resolved_by_id=str(self.user.id),
        )

        self.assertEqual(resolved.status, "RESOLVED")
        self.assertEqual(resolved.resolution_notes, "Fixed schema drift")
        self.assertEqual(resolved.root_cause, "Schema changed unexpectedly")
        self.assertEqual(resolved.resolved_by, self.user)

    def test_get_incidents_dashboard(self):
        """Test getting incidents dashboard"""
        # Create incidents (create_incident does not accept status; status is DETECTED by default)
        IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 1",
            description="Description 1",
            incident_type="FRESHNESS_VIOLATION",
        )

        incident2 = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 2",
            description="Description 2",
            incident_type="QUALITY_VIOLATION",
        )
        # Resolve the second incident so summary counts are correct
        IncidentManager.update_incident_status(
            incident_id=str(incident2.id),
            status="RESOLVED",
            resolution_notes="Resolved",
            resolved_by_id=str(self.user.id),
        )

        dashboard = IncidentManager.get_incidents_dashboard(tenant_id=str(self.tenant.id), limit=10)

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertEqual(len(dashboard["results"]), 2)
        self.assertEqual(dashboard["summary"]["total_incidents"], 2)
        self.assertEqual(dashboard["summary"]["detected_incidents"], 1)
        self.assertEqual(dashboard["summary"]["resolved_incidents"], 1)

    def test_get_incidents_dashboard_with_filters(self):
        """Test getting incidents dashboard with filters"""
        # Create incidents with different statuses
        IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 1",
            description="Description 1",
            incident_type="FRESHNESS_VIOLATION",
        )

        incident2 = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 2",
            description="Description 2",
            incident_type="QUALITY_VIOLATION",
        )

        # Resolve one incident
        IncidentManager.update_incident_status(incident_id=str(incident2.id), status="RESOLVED")

        # Filter by status
        dashboard = IncidentManager.get_incidents_dashboard(
            tenant_id=str(self.tenant.id), status="RESOLVED", limit=10
        )

        self.assertEqual(len(dashboard["results"]), 1)
        self.assertEqual(dashboard["results"][0]["status"], "RESOLVED")


class IncidentManagerSuccessTest(TestCase):
    """Test IncidentManager success scenarios"""

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

    def test_create_incident_success_all_fields(self):
        """Test creating incident with all fields"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Complete Incident",
            description="Full description",
            incident_type="FRESHNESS_VIOLATION",
            severity="CRITICAL",
            resource_type="ASSET",
            resource_id=str(self.asset.id),
            detected_by_id=str(self.user.id),
        )

        self.assertIsNotNone(incident.id)
        self.assertEqual(incident.title, "Complete Incident")
        self.assertEqual(incident.severity, "CRITICAL")
        self.assertEqual(incident.resource_type, "ASSET")
        self.assertEqual(incident.resource_id, str(self.asset.id))

    def test_get_incidents_dashboard_empty(self):
        """Test getting incidents dashboard when empty"""
        dashboard = IncidentManager.get_incidents_dashboard(tenant_id=str(self.tenant.id), limit=10)

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertEqual(len(dashboard["results"]), 0)
        self.assertEqual(dashboard["summary"]["total_incidents"], 0)


class IncidentManagerFailureTest(TestCase):
    """Test IncidentManager failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_create_incident_missing_required_fields(self):
        """Test creating incident with missing required fields"""
        with self.assertRaises(Exception):  # ValidationError or TypeError
            IncidentManager.create_incident(
                tenant_id=str(self.tenant.id),
                # Missing title, description, incident_type
            )

    def test_create_incident_invalid_tenant_id(self):
        """Test creating incident with invalid tenant ID"""
        with self.assertRaises(Exception):  # NotFoundError or ValidationError
            IncidentManager.create_incident(
                tenant_id=str(uuid.uuid4()),  # Non-existent tenant
                title="Test Incident",
                description="Test description",
                incident_type="FRESHNESS_VIOLATION",
            )

    def test_update_incident_status_invalid_incident_id(self):
        """Test updating incident with invalid incident ID"""
        with self.assertRaises(Exception):  # NotFoundError
            IncidentManager.update_incident_status(
                incident_id=str(uuid.uuid4()), status="TRIAGED"  # Non-existent incident
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

    def test_assign_incident_invalid_user_id(self):
        """Test assigning incident to invalid user"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="PIPELINE_FAILURE",
        )

        with self.assertRaises(Exception):  # NotFoundError
            IncidentManager.assign_incident(
                incident_id=str(incident.id), assigned_to_id=str(uuid.uuid4())  # Non-existent user
            )


class IncidentManagerEdgeCasesTest(TestCase):
    """Test IncidentManager edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_create_incident_with_very_long_title(self):
        """Test creating incident with very long title"""
        long_title = "A" * 1000
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title=long_title,
            description="Test description",
            incident_type="FRESHNESS_VIOLATION",
        )

        self.assertEqual(incident.title, long_title)

    def test_create_incident_with_special_characters(self):
        """Test creating incident with special characters"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test!@#$%^&*() Incident",
            description="Test description with special chars: !@#$%^&*()",
            incident_type="QUALITY_VIOLATION",
        )

        self.assertEqual(incident.title, "Test!@#$%^&*() Incident")
        self.assertEqual(incident.description, "Test description with special chars: !@#$%^&*()")

    def test_create_incident_with_unicode(self):
        """Test creating incident with unicode characters"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="测试事件",
            description="测试描述",
            incident_type="SCHEMA_DRIFT",
        )

        self.assertEqual(incident.title, "测试事件")

    def test_get_incidents_dashboard_with_large_limit(self):
        """Test getting incidents dashboard with large limit"""
        # Create multiple incidents
        for i in range(50):
            IncidentManager.create_incident(
                tenant_id=str(self.tenant.id),
                title=f"Incident {i}",
                description=f"Description {i}",
                incident_type="FRESHNESS_VIOLATION",
            )

        dashboard = IncidentManager.get_incidents_dashboard(
            tenant_id=str(self.tenant.id), limit=1000
        )

        self.assertEqual(len(dashboard["results"]), 50)

    def test_get_incidents_dashboard_with_small_limit(self):
        """Test getting incidents dashboard with small limit"""
        # Create multiple incidents
        for i in range(10):
            IncidentManager.create_incident(
                tenant_id=str(self.tenant.id),
                title=f"Incident {i}",
                description=f"Description {i}",
                incident_type="FRESHNESS_VIOLATION",
            )

        dashboard = IncidentManager.get_incidents_dashboard(tenant_id=str(self.tenant.id), limit=5)

        self.assertEqual(len(dashboard["results"]), 5)


class IncidentManagerErrorHandlingTest(TestCase):
    """Test IncidentManager error handling"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_resolve_incident_without_resolved_by(self):
        """Test resolving incident without resolved_by_id succeeds (it's optional)"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="FRESHNESS_VIOLATION",
        )

        resolved = IncidentManager.resolve_incident(
            incident_id=str(incident.id),
            resolution_notes="Fixed",
            root_cause="Root cause",
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.status, "RESOLVED")
        self.assertEqual(resolved.resolution_notes, "Fixed")
        self.assertEqual(resolved.root_cause, "Root cause")
        self.assertIsNone(resolved.resolved_by_id)
        self.assertIsNotNone(resolved.resolved_at)

    def test_update_incident_status_multiple_times(self):
        """Test updating incident status multiple times"""
        incident = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident",
            description="Test description",
            incident_type="QUALITY_VIOLATION",
        )

        # Update multiple times
        IncidentManager.update_incident_status(incident_id=str(incident.id), status="TRIAGED")
        IncidentManager.update_incident_status(
            incident_id=str(incident.id), status="IN_PROGRESS", assigned_to_id=str(self.user.id)
        )
        IncidentManager.update_incident_status(
            incident_id=str(incident.id), status="RESOLVED", resolved_by_id=str(self.user.id)
        )

        # Verify final status
        incident.refresh_from_db()
        self.assertEqual(incident.status, "RESOLVED")

    def test_get_incidents_dashboard_with_invalid_filters(self):
        """Test getting incidents dashboard with invalid filters"""
        # Should handle invalid filters gracefully
        dashboard = IncidentManager.get_incidents_dashboard(
            tenant_id=str(self.tenant.id), status="INVALID_STATUS", limit=10  # Invalid status
        )

        # Should return empty results or handle gracefully
        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertEqual(len(dashboard["results"]), 0,
            "Invalid status filter should return no matching incidents")
