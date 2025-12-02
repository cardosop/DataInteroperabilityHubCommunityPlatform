"""
Unit tests for tenant signals.
"""
import pytest
from django.test import TestCase
from hub.apps.tenants.models import Tenant



pytestmark = pytest.mark.django_db(transaction=True)
class TenantSignalsTest(TestCase):
    """Test tenant signals"""
    
    def test_default_roles_created_on_tenant_creation(self):
        """Test that default roles are created when tenant is created"""
        # Import here to avoid circular import if Role model doesn't exist yet
        try:
            from hub.apps.users.models import Role
            
            tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
            
            # Check that default roles were created
            roles = Role.objects.filter(tenant=tenant)
            role_names = [role.name for role in roles]
            
            self.assertIn("TENANT_ADMIN", role_names)
            self.assertIn("DATA_PROVIDER", role_names)
            self.assertIn("DATA_CONSUMER", role_names)
            self.assertIn("AUDITOR", role_names)
            self.assertEqual(len(roles), 4)
        except ImportError:
            # Role model doesn't exist yet, skip this test
            self.skipTest("Role model not yet implemented")

