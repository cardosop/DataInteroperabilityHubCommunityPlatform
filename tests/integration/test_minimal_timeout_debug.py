"""
Minimal test to debug timeout issues
"""
import json
import time
from django.test import TransactionTestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import User, Role, UserRole
from hub.apps.contracts.models import Contract, OriginalFormat
from hub.apps.assets.models import Asset, AssetStatus
from tests.fixtures.test_data_factories import TenantFactory, UserFactory
from django.db.models.signals import post_save
from hub.apps.semantic.signals import contract_saved, asset_saved
from hub.apps.tenants.signals import create_default_roles

# Disconnect signals
post_save.disconnect(contract_saved, sender=Contract)
post_save.disconnect(asset_saved, sender=Asset)
post_save.disconnect(create_default_roles, sender=Tenant)


class MinimalTimeoutTest(TransactionTestCase):
    """Minimal test to debug timeout"""

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""
        # Don't flush - transactions are rolled back which provides isolation
        pass

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        print(f"[{time.time()}] Starting setUp...")

        print(f"[{time.time()}] Creating tenant...")
        start = time.time()
        # Use unique name/slug to avoid conflicts
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = TenantFactory.create_tenant(
            name=f"Minimal Test Tenant {unique_id}",
            slug=f"minimal-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        print(f"[{time.time()}] Tenant created in {time.time() - start:.3f}s")

        print(f"[{time.time()}] Creating role...")
        start = time.time()
        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        print(f"[{time.time()}] Role created in {time.time() - start:.3f}s")

        print(f"[{time.time()}] Creating user...")
        start = time.time()
        self.user = UserFactory.create_user(tenant=self.tenant, email=f"minimal-{unique_id}@test.com")
        UserRole.objects.get_or_create(user=self.user, role=self.role)
        print(f"[{time.time()}] User created in {time.time() - start:.3f}s")

        print(f"[{time.time()}] Authenticating client...")
        start = time.time()
        self.client.force_authenticate(user=self.user)
        print(f"[{time.time()}] Client authenticated in {time.time() - start:.3f}s")

        print(f"[{time.time()}] setUp complete")

    def test_minimal_asset_creation(self):
        """Test minimal asset creation"""
        print(f"[{time.time()}] Starting test...")

        print(f"[{time.time()}] Creating asset...")
        start = time.time()
        asset_data = {
            "key": "minimal-asset",
            "name": "Minimal Asset",
            "description": "Test",
            "domain": "sales",
        }
        asset_response = self.client.post(reverse("asset-list"), asset_data, format="json")
        elapsed = time.time() - start
        print(f"[{time.time()}] Asset creation took {elapsed:.3f}s, status: {asset_response.status_code}")

        if asset_response.status_code != 201:
            print(f"Error: {asset_response.data}")
            return

        asset_id = asset_response.data["id"]
        print(f"[{time.time()}] Asset created: {asset_id}")

        print(f"[{time.time()}] Creating contract...")
        start = time.time()
        sample_contract = {
            "id": "orders",
            "info": {
                "name": "Customer Orders",
                "title": "Customer Orders",
                "owners": [{"name": "Data Platform Team", "email": "dataplatform@example.com"}],
                "tags": ["analytics", "sales"],
            },
            "schema": {
                "fields": [
                    {"name": "order_id", "type": "string", "required": True},
                ]
            },
        }
        contract_data = {
            "original_raw": json.dumps(sample_contract),
            "original_format": OriginalFormat.JSON.value,
            "asset_id": asset_id,
        }
        contract_response = self.client.post(reverse("contract-list"), contract_data, format="json")
        elapsed = time.time() - start
        print(f"[{time.time()}] Contract creation took {elapsed:.3f}s, status: {contract_response.status_code}")

        if contract_response.status_code != 201:
            print(f"Error: {contract_response.data}")
            return

        contract_id = contract_response.data["id"]
        print(f"[{time.time()}] Contract created: {contract_id}")

        print(f"[{time.time()}] Test complete")
