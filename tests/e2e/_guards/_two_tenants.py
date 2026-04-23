"""`two_tenants` pytest fixture for tenant-isolation tests.

Creating two tenants manually in a test is five-plus lines of boilerplate that
invariably drifts between tests — different role assignments, different
auth styles, subtle mutations that make one test's setup incompatible with
another's. This fixture captures the canonical "two tenants, two users, two
authenticated DRF clients" idiom so every isolation test uses the same
fixtures.

Usage (after PR 6b migrates `test_multi_tenant_isolation.py`):

    def test_asset_cannot_leak_across_tenants(two_tenants):
        # Tenant A creates an asset via its own client.
        resp = two_tenants.a.client.post("/api/v1/assets/", {...}, format="json")
        asset_id = resp.json()["id"]
        # Tenant B hitting the same ID must get 404, not 200.
        resp = two_tenants.b.client.get(f"/api/v1/assets/{asset_id}/")
        assert resp.status_code == 404

The fixture also exposes `.a.tenant` / `.a.user` for tests that want to
assert at the ORM layer (the other half of the dual-channel idiom).

Intentionally kept simple: no role/permission mutations, no organization
seeding, no custom kwargs. Tests that need richer setup build on top rather
than forcing them into this fixture's API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass(frozen=True)
class TenantBundle:
    """One tenant + one user + one authenticated DRF APIClient."""

    tenant: Any
    user: Any
    client: Any


@dataclass(frozen=True)
class TwoTenants:
    a: TenantBundle
    b: TenantBundle


def _make_bundle(suffix: str) -> TenantBundle:
    # Imports are deferred so the module is safe to import before Django
    # apps are loaded (e.g. during test collection in a non-Django context).
    from rest_framework.test import APIClient

    from tests.factories import TenantFactory, UserFactory

    tenant = TenantFactory(name=f"Isolation-{suffix}-tenant", slug=f"iso-{suffix.lower()}")
    user = UserFactory(tenant=tenant, email=f"iso-{suffix.lower()}@example.com")
    client = APIClient()
    client.force_authenticate(user=user)
    return TenantBundle(tenant=tenant, user=user, client=client)


@pytest.fixture
def two_tenants(db) -> TwoTenants:
    """Two fully-isolated tenants with authenticated DRF clients.

    Depends on pytest-django's `db` fixture so the Django test database is
    provisioned. Each call produces fresh tenants — pytest-django rolls back
    the transaction between tests so there is no cross-test leakage.
    """
    return TwoTenants(
        a=_make_bundle("A"),
        b=_make_bundle("B"),
    )
