"""
Profile contract creation to identify bottlenecks.

Runs as a pytest test so database access is properly enabled during collection.
"""

import time
import traceback

import pytest
from django.db.models.signals import post_save
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, OriginalFormat
from hub.apps.tenants.models import KYCStatus, TenantStatus
from hub.apps.users.models import Role, UserRole
from tests.fixtures.test_data_factories import TenantFactory, UserFactory

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


def _run_profiling():
    """Execute profiling logic (no DB access at import time)."""
    from django.urls import reverse

    from hub.apps.semantic.signals import asset_saved, contract_saved

    # Disconnect signals to prevent semantic service calls during profiling
    post_save.disconnect(contract_saved, sender=Contract)
    post_save.disconnect(asset_saved, sender=Asset)

    print("=" * 80)
    print("PROFILING CONTRACT CREATION")
    print("=" * 80)

    # Create test data
    print("\n1. Creating tenant...")
    start = time.time()
    tenant = TenantFactory.create_tenant(
        name=f"Profile Test Tenant {int(time.time())}",
        slug=f"profile-test-tenant-{int(time.time())}",
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
    user = UserFactory.create_user(
        tenant=tenant,
        email=f"profile-{int(time.time())}@test.com",
    )
    UserRole.objects.get_or_create(user=user, role=role)
    print(f"   ✓ User created in {time.time() - start:.3f}s")

    print("\n4. Creating asset...")
    start = time.time()
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"profile-test-asset-{int(time.time())}",
        name="Profile Test Asset",
        domain="test",
        status=AssetStatus.DRAFT,
        created_by=user,
    )
    print(f"   ✓ Asset created in {time.time() - start:.3f}s")

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


def test_profile_contract_creation():
    """Profile contract creation to identify bottlenecks."""
    _run_profiling()
