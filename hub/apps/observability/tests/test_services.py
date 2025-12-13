"""
Unit tests for ObservabilityService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase

from hub.apps.observability.services import ObservabilityService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ObservabilityServiceTest(TestCase):
    """Test ObservabilityService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = ObservabilityService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
    
    def test_get_freshness_dashboard_success(self):
        """Test successful freshness dashboard retrieval"""
        # Use real implementation - should return empty dashboard if no data
        result = self.service.get_freshness_dashboard(
            tenant_id=str(self.tenant.id)
        )
        
        # Should return a dictionary with dashboard structure
        self.assertIsInstance(result, dict)
        # Dashboard should have standard keys: results and summary
        self.assertIn("results", result)
        self.assertIn("summary", result)
    
    def test_get_volume_dashboard_success(self):
        """Test successful volume dashboard retrieval"""
        # Use real implementation - should return empty dashboard if no data
        result = self.service.get_volume_dashboard(
            tenant_id=str(self.tenant.id)
        )
        
        # Should return a dictionary with dashboard structure
        self.assertIsInstance(result, dict)
        # Dashboard should have standard keys: results and summary
        self.assertIn("results", result)
        self.assertIn("summary", result)
    
    def test_get_schema_drift_dashboard_success(self):
        """Test successful schema drift dashboard retrieval"""
        # Use real implementation - should return empty dashboard if no data
        result = self.service.get_schema_drift_dashboard(
            tenant_id=str(self.tenant.id)
        )
        
        # Should return a dictionary with dashboard structure
        self.assertIsInstance(result, dict)
        # Dashboard should have standard keys: results and summary
        self.assertIn("results", result)
        self.assertIn("summary", result)

