"""
Tests for warehouse ViewSets.

Tests CRUD, feature gates, tenant isolation, custom actions, and
error paths for all 4 ViewSets.  Connector calls are mocked at the
import boundary so no real warehouse credentials are needed.
"""

from unittest import mock

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.warehouses.models import WarehouseConnection, WarehouseConnectionACL

# ── Helpers ──────────────────────────────────────────────────────────

_tenant_counter = 0
_user_counter = 0

SAMPLE_UUID = "00000000-0000-0000-0000-000000000000"


def _create_tenant(**overrides):
    """Create a tenant with warehouse_connectivity_enabled and an active
    BASE subscription (required for POST/PATCH/DELETE operations)."""
    global _tenant_counter
    _tenant_counter += 1
    defaults = {
        "name": f"test-wh-tenant-{_tenant_counter}",
        "slug": f"test-wh-{_tenant_counter}",
        "warehouse_connectivity_enabled": True,
    }
    defaults.update(overrides)
    tenant = Tenant.objects.create(**defaults)

    # Ensure tenant has an active BASE subscription so the billing
    # middleware allows POST/PATCH/DELETE (skipped for GET/HEAD/OPTIONS).
    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.tenants.models import TenantConfig, TenantPlan

    TenantConfig.objects.get_or_create(tenant=tenant)
    plan = TenantPlan.objects.filter(slug="free", is_active=True).first()
    if plan and not Subscription.objects.filter(tenant=tenant, category="BASE").exists():
        Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            category="BASE",
            status=SubscriptionStatus.ACTIVE,
        )

    return tenant


def _create_user(tenant, is_admin=False):
    global _user_counter
    _user_counter += 1
    email = f"wh-test-{_user_counter}@test.com"
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        tenant=tenant,
    )
    if is_admin:
        user.is_platform_admin = True
        user.save()
    return user


def _create_connection(tenant, **overrides):
    return WarehouseConnection.objects.create(
        tenant=tenant,
        name="test-connection",
        warehouse_type="SNOWFLAKE",
        config={"account": "test", "database": "test_db"},
        is_active=True,
        **overrides,
    )


# ── WarehouseConnectionViewSet ───────────────────────────────────────


@pytest.mark.django_db(transaction=True)
class WarehouseConnectionViewSetTests(TestCase):
    """Tests for WarehouseConnectionViewSet CRUD and custom actions."""

    def setUp(self):
        self.tenant = _create_tenant()
        self.other_tenant = _create_tenant(name="other-tenant")
        self.user = _create_user(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    # ── List ────────────────────────────────────────────────────────

    def test_list_connections_empty(self):
        url = reverse("warehouse-connection-list")
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["results"] == []

    def test_list_connections_tenant_scoped(self):
        _create_connection(self.tenant)
        _create_connection(self.other_tenant)
        url = reverse("warehouse-connection-list")
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 1

    # ── Create ──────────────────────────────────────────────────────

    def test_create_connection_success(self):
        url = reverse("warehouse-connection-list")
        resp = self.client.post(
            url,
            {
                "name": "new-conn",
                "warehouse_type": "BIGQUERY",
                "config": {"project": "p", "dataset": "d"},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["name"] == "new-conn"

    def test_create_connection_feature_disabled(self):
        self.tenant.warehouse_connectivity_enabled = False
        self.tenant.save()
        url = reverse("warehouse-connection-list")
        resp = self.client.post(
            url,
            {
                "name": "nope",
                "warehouse_type": "SNOWFLAKE",
                "config": {"account": "a"},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_connection_invalid_type(self):
        url = reverse("warehouse-connection-list")
        resp = self.client.post(
            url,
            {
                "name": "bad",
                "warehouse_type": "invalid",
                "config": {},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ── Retrieve ────────────────────────────────────────────────────

    def test_retrieve_connection(self):
        conn = _create_connection(self.tenant)
        url = reverse("warehouse-connection-detail", kwargs={"id": conn.id})
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["name"] == "test-connection"

    def test_retrieve_cross_tenant_blocked(self):
        conn = _create_connection(self.other_tenant)
        url = reverse("warehouse-connection-detail", kwargs={"id": conn.id})
        resp = self.client.get(url)
        assert resp.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)

    # ── Update ──────────────────────────────────────────────────────

    def test_update_connection(self):
        conn = _create_connection(self.tenant)
        url = reverse("warehouse-connection-detail", kwargs={"id": conn.id})
        resp = self.client.patch(url, {"name": "renamed"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["name"] == "renamed"

    # ── Delete ──────────────────────────────────────────────────────

    def test_delete_connection(self):
        conn = _create_connection(self.tenant)
        url = reverse("warehouse-connection-detail", kwargs={"id": conn.id})
        resp = self.client.delete(url)
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not WarehouseConnection.objects.filter(id=conn.id).exists()

    # ── Test connection ─────────────────────────────────────────────

    def _mock_connector_cls(self, mock_get_connector):
        """Set up the connector-class mock chain so that
        get_connector_for_connection → mock class → mock instance."""
        mock_instance = mock.MagicMock()
        mock_cls = mock.MagicMock(return_value=mock_instance)
        mock_get_connector.return_value = mock_cls
        return mock_instance

    @mock.patch("hub.apps.warehouses.base.get_connector_for_connection")
    def test_test_connection_success(self, mock_get_connector):
        conn = _create_connection(self.tenant)
        self._mock_connector_cls(mock_get_connector)

        url = reverse("warehouse-connection-test-connection", kwargs={"id": conn.id})
        resp = self.client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["success"] is True
        assert "latency_ms" in resp.data

    @mock.patch("hub.apps.warehouses.base.get_connector_for_connection")
    def test_test_connection_failure(self, mock_get_connector):
        conn = _create_connection(self.tenant)
        mock_instance = self._mock_connector_cls(mock_get_connector)
        mock_instance.connect.side_effect = RuntimeError("connection refused")

        url = reverse("warehouse-connection-test-connection", kwargs={"id": conn.id})
        resp = self.client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["success"] is False
        assert "connection refused" in resp.data["error"]

    def test_test_connection_feature_disabled(self):
        self.tenant.warehouse_connectivity_enabled = False
        self.tenant.save()
        conn = _create_connection(self.tenant)
        url = reverse("warehouse-connection-test-connection", kwargs={"id": conn.id})
        resp = self.client.post(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    # ── Schema reflection ───────────────────────────────────────────

    def test_reflect_schema_missing_table_param(self):
        conn = _create_connection(self.tenant)
        url = reverse("warehouse-connection-reflect-schema", kwargs={"id": conn.id})
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "table" in str(resp.data)

    @mock.patch("hub.apps.warehouses.base.get_connector_for_connection")
    def test_reflect_schema_success(self, mock_get_connector):
        conn = _create_connection(self.tenant)
        from collections import namedtuple

        Col = namedtuple("Col", ["name", "data_type", "nullable", "comment"])
        mock_instance = self._mock_connector_cls(mock_get_connector)
        mock_instance.reflect_schema.return_value = [
            Col("id", "INTEGER", False, "Primary key"),
            Col("name", "VARCHAR", True, "Name column"),
        ]

        url = reverse("warehouse-connection-reflect-schema", kwargs={"id": conn.id})
        resp = self.client.get(url, {"table": "users"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["columns"]) == 2
        assert resp.data["table"] == "users"

    @mock.patch("hub.apps.warehouses.base.get_connector_for_connection")
    def test_reflect_schema_connector_error(self, mock_get_connector):
        conn = _create_connection(self.tenant)
        mock_instance = self._mock_connector_cls(mock_get_connector)
        mock_instance.connect.side_effect = RuntimeError("timeout")

        url = reverse("warehouse-connection-reflect-schema", kwargs={"id": conn.id})
        resp = self.client.get(url, {"table": "users"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ── Residency mismatches ────────────────────────────────────────

    def test_residency_mismatches_feature_disabled(self):
        self.tenant.warehouse_connectivity_enabled = False
        self.tenant.save()
        url = reverse("warehouse-connection-residency-mismatches")
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @mock.patch("hub.apps.warehouses.residency_validator.find_residency_mismatches")
    def test_residency_mismatches_tenant_scoped(self, mock_find):
        mock_find.return_value = [
            {"tenant_id": str(self.tenant.id), "asset": "a1"},
            {"tenant_id": str(self.other_tenant.id), "asset": "a2"},
        ]
        url = reverse("warehouse-connection-residency-mismatches")
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1  # Only own tenant's

    # ── Platform admin bypass ───────────────────────────────────────

    def test_platform_admin_sees_all_connections(self):
        admin = _create_user(self.tenant, is_admin=True)
        _create_connection(self.tenant)
        _create_connection(self.other_tenant)

        self.client.force_authenticate(user=admin)
        url = reverse("warehouse-connection-list")
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2


# ── LiveQueryViewSet ─────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
class LiveQueryViewSetTests(TestCase):
    """Tests for LiveQueryViewSet — LIVE_QUERY asset query endpoint."""

    def setUp(self):
        self.tenant = _create_tenant()
        self.user = _create_user(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_query_missing_asset_id(self):
        url = reverse("livequery-list")
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "asset_id" in str(resp.data)

    def test_query_asset_not_found(self):
        url = reverse("livequery-list")
        resp = self.client.get(url, {"asset_id": "00000000-0000-0000-0000-000000000000"})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_rejected(self):
        client = APIClient()  # no auth
        url = reverse("livequery-list")
        resp = client.get(url, {"asset_id": SAMPLE_UUID})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── DeltaShareView ───────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
class DeltaShareViewTests(TestCase):
    """Tests for DeltaShareView — Delta Sharing protocol endpoint."""

    def setUp(self):
        self.tenant = _create_tenant()
        self.user = _create_user(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_tables_asset_not_found(self):
        url = reverse(
            "deltashare-list-tables", kwargs={"asset_id": "00000000-0000-0000-0000-000000000000"}
        )
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_rejected(self):
        client = APIClient()
        url = reverse("deltashare-list-tables", kwargs={"asset_id": SAMPLE_UUID})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── WarehouseConnectionACLViewSet ────────────────────────────────────


@pytest.mark.django_db(transaction=True)
class WarehouseConnectionACLViewSetTests(TestCase):
    """Tests for WarehouseConnectionACLViewSet CRUD."""

    def setUp(self):
        self.tenant = _create_tenant()
        self.other_tenant = _create_tenant(name="other-acl-tenant")
        self.user = _create_user(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_acls_empty(self):
        url = reverse("warehouse-acl-list")
        resp = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["results"] == []

    def test_unauthenticated_rejected(self):
        client = APIClient()
        url = reverse("warehouse-acl-list")
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_acl(self):
        conn = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="acl-conn",
            warehouse_type="SNOWFLAKE",
        )
        before = WarehouseConnectionACL.objects.count()
        url = reverse("warehouse-acl-list")
        payload = {
            "connection": str(conn.id),
            "user": str(self.user.id),
            "role": "VIEWER",
        }
        resp = self.client.post(url, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert WarehouseConnectionACL.objects.count() == before + 1
        assert resp.data["role"] == "VIEWER"
        assert str(resp.data["connection"]) == str(conn.id)

    def test_cross_tenant_isolation(self):
        conn_a = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="acl-iso-a",
            warehouse_type="SNOWFLAKE",
        )
        WarehouseConnectionACL.objects.create(
            tenant=self.tenant,
            connection=conn_a,
            user=self.user,
            role="ADMIN",
        )
        # Tenant B user authenticates and should see zero ACLs
        other_user = _create_user(self.other_tenant)
        other_client = APIClient()
        other_client.force_authenticate(user=other_user)
        url = reverse("warehouse-acl-list")
        resp = other_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["results"] == []
