"""
Simple test to verify infrastructure works without file operations
"""
import sys
import os
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    class DummyPytest:
        class mark:
            @staticmethod
            def django_db(**kwargs):
                return lambda f: f
            @staticmethod
            def integration(f):
                return f
    pytest = DummyPytest()

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import User, Role, UserRole
from tests.fixtures.test_data_factories import TenantFactory, UserFactory
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from django.db.models.signals import post_save
from hub.apps.semantic.signals import contract_saved, asset_saved
from hub.apps.tenants.signals import create_default_roles

# Use default transaction=False so TenantSuspensionMiddleware sees subscription from setUp
if HAS_PYTEST:
    pytestmark = [pytest.mark.django_db, pytest.mark.integration]


class SimpleAssetCreationTest(TestCase):
    """Simple test to verify basic infrastructure"""

    def setUp(self):
        super().setUp()
        # Disconnect signals
        post_save.disconnect(contract_saved, sender=None)
        post_save.disconnect(asset_saved, sender=None)
        post_save.disconnect(create_default_roles, sender=None)

        self.client = APIClient()

        # Create tenant (use unique name/slug to avoid conflicts)
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = TenantFactory.create_tenant(
            name=f"Simple Test Tenant {unique_id}",
            slug=f"simple-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create role
        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )

        # Create user (use unique email to avoid conflicts)
        self.user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"simple-{unique_id}@test.com",
        )
        UserRole.objects.get_or_create(user=self.user, role=self.role)

        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        post_save.connect(contract_saved, sender=None)
        post_save.connect(asset_saved, sender=None)
        post_save.connect(create_default_roles, sender=None)
        super().tearDown()

    def test_simple_asset_creation(self):
        """Test simple asset creation without file operations"""
        print("\n[TEST] Starting simple asset creation test")

        asset_data = {
            "key": "simple-test-asset",
            "name": "Simple Test Asset",
            "description": "Test",
            "domain": "sales",
        }

        response = self.client.post(reverse("asset-list"), asset_data, format="json")
        print(f"[TEST] Asset creation response: status={response.status_code}")

        if response.status_code != status.HTTP_201_CREATED:
            print(f"[TEST] Error: {response.data if hasattr(response, 'data') else response.content}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        print(f"[TEST] Asset created successfully: {response.data['id']}")
