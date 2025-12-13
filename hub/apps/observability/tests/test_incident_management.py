"""
Unit tests for Data Incident Management service.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from hub.apps.observability.models import DataIncident
from hub.apps.observability.incident_management import IncidentManager
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset


pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class IncidentManagerTest(TestCase):
    """Test Data Incident Management service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            description="Test asset description"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        if hasattr(self.user, 'tenant'):
            self.user.tenant = self.tenant
            self.user.save()
    
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
            detected_by_id=str(self.user.id)
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
            incident_type="QUALITY_VIOLATION"
        )
        
        # Update to TRIAGED
        updated = IncidentManager.update_incident_status(
            incident_id=str(incident.id),
            status="TRIAGED"
        )
        
        self.assertEqual(updated.status, "TRIAGED")
        self.assertIsNotNone(updated.triaged_at)
        
        # Update to IN_PROGRESS
        updated = IncidentManager.update_incident_status(
            incident_id=str(incident.id),
            status="IN_PROGRESS",
            assigned_to_id=str(self.user.id)
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
            resolved_by_id=str(self.user.id)
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
            incident_type="PIPELINE_FAILURE"
        )
        
        assigned = IncidentManager.assign_incident(
            incident_id=str(incident.id),
            assigned_to_id=str(self.user.id)
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
            incident_type="SCHEMA_DRIFT"
        )
        
        resolved = IncidentManager.resolve_incident(
            incident_id=str(incident.id),
            resolution_notes="Fixed schema drift",
            root_cause="Schema changed unexpectedly",
            resolved_by_id=str(self.user.id)
        )
        
        self.assertEqual(resolved.status, "RESOLVED")
        self.assertEqual(resolved.resolution_notes, "Fixed schema drift")
        self.assertEqual(resolved.root_cause, "Schema changed unexpectedly")
        self.assertEqual(resolved.resolved_by, self.user)
    
    def test_get_incidents_dashboard(self):
        """Test getting incidents dashboard"""
        # Create incidents
        IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 1",
            description="Description 1",
            incident_type="FRESHNESS_VIOLATION",
            status="DETECTED"
        )
        
        IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 2",
            description="Description 2",
            incident_type="QUALITY_VIOLATION",
            status="RESOLVED"
        )
        
        dashboard = IncidentManager.get_incidents_dashboard(
            tenant_id=str(self.tenant.id),
            limit=10
        )
        
        self.assertIn('results', dashboard)
        self.assertIn('summary', dashboard)
        self.assertEqual(len(dashboard['results']), 2)
        self.assertEqual(dashboard['summary']['total_incidents'], 2)
        self.assertEqual(dashboard['summary']['detected_incidents'], 1)
        self.assertEqual(dashboard['summary']['resolved_incidents'], 1)
    
    def test_get_incidents_dashboard_with_filters(self):
        """Test getting incidents dashboard with filters"""
        # Create incidents with different statuses
        IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 1",
            description="Description 1",
            incident_type="FRESHNESS_VIOLATION"
        )
        
        incident2 = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Incident 2",
            description="Description 2",
            incident_type="QUALITY_VIOLATION"
        )
        
        # Resolve one incident
        IncidentManager.update_incident_status(
            incident_id=str(incident2.id),
            status="RESOLVED"
        )
        
        # Filter by status
        dashboard = IncidentManager.get_incidents_dashboard(
            tenant_id=str(self.tenant.id),
            status="RESOLVED",
            limit=10
        )
        
        self.assertEqual(len(dashboard['results']), 1)
        self.assertEqual(dashboard['results'][0]['status'], "RESOLVED")

