"""
Profile contract creation to identify bottlenecks
"""
import os
import sys
import time
import traceback

import sys
sys.path.insert(0, '/app')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import User, Role, UserRole
from hub.apps.contracts.models import Contract, OriginalFormat
from tests.fixtures.test_data_factories import TenantFactory, UserFactory

# Disconnect signals to prevent semantic service calls
from django.db.models.signals import post_save
from hub.apps.semantic.signals import contract_saved, asset_saved
from hub.apps.assets.models import Asset

post_save.disconnect(contract_saved, sender=Contract)
post_save.disconnect(asset_saved, sender=Asset)

print("=" * 80)
print("PROFILING CONTRACT CREATION")
print("=" * 80)

# Create test data
print("\n1. Creating tenant...")
start = time.time()
tenant = TenantFactory.create_tenant(
    name="Profile Test Tenant",
    slug="profile-test-tenant",
    status=TenantStatus.ACTIVE,
    kyc_status=KYCStatus.VERIFIED,
)
print(f"   ✓ Tenant created in {time.time() - start:.3f}s")

print("\n2. Creating roles...")
start = time.time()
role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name="DATA_PROVIDER",
    defaults={"description": "Data Provider"},
)
print(f"   ✓ Role created in {time.time() - start:.3f}s")

print("\n3. Creating user...")
start = time.time()
user = UserFactory.create_user(tenant=tenant, email="profile@test.com")
UserRole.objects.get_or_create(user=user, role=role)
print(f"   ✓ User created in {time.time() - start:.3f}s")

# Create asset
print("\n4. Creating asset...")
start = time.time()
from hub.apps.assets.models import Asset, AssetStatus
asset = Asset.objects.create(
    tenant=tenant,
    key="profile-test-asset",
    name="Profile Test Asset",
    domain="test",
    status=AssetStatus.DRAFT,
    created_by=user,
)
print(f"   ✓ Asset created in {time.time() - start:.3f}s")

# Sample ODCS contract
sample_contract = {
    "id": "orders",
    "info": {
        "title": "Customer Orders",
        "owners": [{"name": "Data Platform Team", "email": "dataplatform@example.com"}],
        "tags": ["analytics", "sales"],
    },
    "schema": {
        "fields": [
            {"name": "order_id", "type": "string", "required": True},
            {"name": "customer_id", "type": "string", "required": True},
            {"name": "order_date", "type": "date", "required": True},
            {"name": "total_amount", "type": "number", "required": True},
        ]
    },
}

print("\n5. Creating contract via API...")
client = APIClient()
client.force_authenticate(user=user)

contract_data = {
    "asset_id": str(asset.id),
    "original_raw": str(sample_contract).replace("'", '"'),
    "original_format": OriginalFormat.JSON.value,
}

start = time.time()
try:
    response = client.post(reverse("contract-list"), contract_data, format="json")
    elapsed = time.time() - start

    if response.status_code == status.HTTP_201_CREATED:
        print(f"   ✓ Contract created successfully in {elapsed:.3f}s")
        print(f"   Contract ID: {response.data.get('id')}")
    else:
        print(f"   ✗ Contract creation failed: {response.status_code}")
        print(f"   Response: {response.data}")
        print(f"   Time taken: {elapsed:.3f}s")
except Exception as e:
    elapsed = time.time() - start
    print(f"   ✗ Exception during contract creation: {e}")
    print(f"   Time taken: {elapsed:.3f}s")
    traceback.print_exc()

print("\n" + "=" * 80)
print("PROFILING COMPLETE")
print("=" * 80)
