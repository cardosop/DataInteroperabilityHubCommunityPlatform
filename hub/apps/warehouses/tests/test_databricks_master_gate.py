"""P0 (openspec add-databricks-control-plane task 0.12) — warehouses master gate.

The pre-existing-but-unused ``Tenant.warehouse_databricks_enabled`` now
gates the warehouses app's Databricks path: creating a DATABRICKS
connection requires the flag (``WAREHOUSE_TYPE_DISABLED_FOR_TENANT``).
Real DB, real flags, real 403s.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.users.models import Role, User, UserRole
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _activate_billing(tenant):
    """Active BASE subscription — the billing middleware gates POST/PATCH/DELETE.

    Delegates to the shared helper in tenants' test factories: importing
    billing directly here was a GATE-29 boundary violation (the billing
    import lives at the ONE allowlisted + guarded site, 313.H.3 — 1.3
    review fix).
    """
    from hub.apps.tenants.tests.factories import activate_billing

    activate_billing(tenant)


def _make_admin(tenant):
    email = f"{uuid.uuid4().hex[:8]}-wh-gate-admin@test.com"
    user = User.objects.create_user(email=email, password="testpass123", tenant=tenant)
    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, role=role)
    return user


def _api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _payload():
    return {
        "name": "db-conn",
        "warehouse_type": "DATABRICKS",
        "config": {
            "host": REAL_HOST,
            "http_path": "/sql/1.0/warehouses/wh-1",
            "pat_token": "dapi-gate-token",
        },
        "region": "us-east-1",
    }


class WarehousesDatabricksMasterGateTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        # The warehouses app's own feature gate requires connectivity.
        self.tenant.warehouse_connectivity_enabled = True
        self.tenant.save(update_fields=["warehouse_connectivity_enabled"])
        self.admin = _make_admin(self.tenant)

    def test_databricks_connection_requires_flag(self):
        response = _api_client(self.admin).post(
            "/api/v1/warehouses/connections/", _payload(), format="json"
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "WAREHOUSE_TYPE_DISABLED_FOR_TENANT"

    def test_databricks_connection_allowed_with_flag(self):
        self.tenant.warehouse_databricks_enabled = True
        self.tenant.save(update_fields=["warehouse_databricks_enabled"])
        response = _api_client(self.admin).post(
            "/api/v1/warehouses/connections/", _payload(), format="json"
        )
        assert response.status_code == 201, response.content


class DatabricksMasterGateUpdateTests(TestCase):
    """0.12 review — the master gate runs on create only; a PATCH that flips
    warehouse_type to DATABRICKS would bypass it entirely."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.tenant.warehouse_connectivity_enabled = True
        self.tenant.save(update_fields=["warehouse_connectivity_enabled"])
        self.admin = _make_admin(self.tenant)
        # warehouse_databricks_enabled stays False — the flag under test.
        from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

        self.connection = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="legacy-snowflake",
            warehouse_type=WarehouseType.SNOWFLAKE,
            config={"host": "snowflake.example", "http_path": "/x", "pat_token": "t"},
        )

    def test_patch_flipping_type_to_databricks_is_gated(self):
        response = _api_client(self.admin).patch(
            f"/api/v1/warehouses/connections/{self.connection.id}/",
            {"warehouse_type": "DATABRICKS"},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "WAREHOUSE_TYPE_DISABLED_FOR_TENANT"
        self.connection.refresh_from_db()
        assert self.connection.warehouse_type != "DATABRICKS", "the flip must not persist"
