"""
Phase 277.B.048 — Records API StandardCursorPagination backward-compat tests.

Validates:
- New StandardCursorPagination cursor format works (base64-encoded JSON)
- Old plain-value cursor format accepted with Deprecation + Sunset headers
- New response shape uses ``results``, ``next_cursor``, ``previous_cursor``
- Old cursor returns correct next page
"""

from types import SimpleNamespace as _NS
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import Role, User, UserRole
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType


class MockConnector:
    """Simulates a warehouse connector for the LIVE_QUERY rows endpoint."""

    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        pass

    def close(self):
        pass

    def execute_query(self, sql):
        import re

        limit_match = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
        limit = int(limit_match.group(1)) if limit_match else 100
        cursor_match = re.search(r"WHERE id > '([^']*)'", sql)
        after_id = cursor_match.group(1) if cursor_match else None

        filtered = self._rows
        if after_id is not None:
            filtered = [r for r in self._rows if r[0] > after_id]
        rows = filtered[:limit]

        return _NS(
            rows=rows,
            columns=["id", "name", "value"],
            row_count=len(rows),
        )


class RecordsCursorBackwardCompatTests(TestCase):
    def setUp(self):
        super().setUp()
        import uuid as _uuid

        _uid = _uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Cursor Test {_uid}",
            slug=f"cursor-test-{_uid}",
            status=TenantStatus.ACTIVE,
        )
        self.platform_admin = User.objects.create_user(
            email=f"admin-{_uid}@cursor.test",
            password="testpass",
            tenant=self.tenant,
            status="ACTIVE",
        )
        admin_role, _ = Role.objects.get_or_create(
            name="PLATFORM_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Platform Administrator"},
        )
        UserRole.objects.create(user=self.platform_admin, role=admin_role)
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)

        self.wh_conn = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name=f"cursor-wh-{_uid}",
            warehouse_type=WarehouseType.SNOWFLAKE.value,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"cursor-asset-{_uid}",
            name="cursor-asset",
            data_strategy="LIVE_QUERY",
            warehouse_connection=self.wh_conn,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            format="CSV",
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.platform_admin)
        # 150 rows (id-000 through id-149)
        self.mock_rows = [[f"id-{i:03d}", f"name-{i}", str(i * 10)] for i in range(150)]
        self._connector = MockConnector(self.mock_rows)
        self._connector_patch = patch(
            "hub.apps.datasets.views.DatasetViewSet._resolve_connector",
            return_value=self._connector,
        )
        self._connector_patch.start()
        self.addCleanup(self._connector_patch.stop)
        self.url = reverse("dataset-rows", kwargs={"id": str(self.dataset.id)})

    # ── New cursor format ──────────────────────────────────────────

    def test_new_cursor_format_returns_results_and_next_cursor(self):
        resp = self.client.get(self.url, {"limit": 50})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 50)
        self.assertIn("next_cursor", data)
        self.assertIsNotNone(data["next_cursor"])
        self.assertIn("previous_cursor", data)
        self.assertIsNone(data["previous_cursor"])

    def test_new_cursor_paginates_correctly(self):
        """Second page with new cursor returns next 50 rows."""
        page1 = self.client.get(self.url, {"limit": 50}).json()
        cursor = page1["next_cursor"]

        page2 = self.client.get(self.url, {"limit": 50, "cursor": cursor}).json()
        self.assertEqual(len(page2["results"]), 50)
        self.assertEqual(page2["results"][0][0], "id-050")
        self.assertIsNotNone(page2["previous_cursor"])

    def test_new_cursor_third_page_returns_remaining(self):
        """Third page should have exactly 50 rows (150 total, 50/page)."""
        page1 = self.client.get(self.url, {"limit": 50}).json()
        page2 = self.client.get(
            self.url,
            {"limit": 50, "cursor": page1["next_cursor"]},
        ).json()
        page3 = self.client.get(
            self.url,
            {"limit": 50, "cursor": page2["next_cursor"]},
        ).json()
        self.assertEqual(len(page3["results"]), 50)
        self.assertEqual(page3["results"][0][0], "id-100")

    # ── Old cursor backward compatibility ──────────────────────────

    def test_old_cursor_format_accepted_with_deprecation_header(self):
        resp = self.client.get(self.url, {"limit": 50, "cursor": "id-049"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Deprecation", resp.headers)
        self.assertIn("Sunset", resp.headers)
        data = resp.json()
        self.assertEqual(data["results"][0][0], "id-050")

    def test_old_cursor_deprecation_header_value(self):
        resp = self.client.get(self.url, {"limit": 50, "cursor": "id-010"})
        deprecation = resp.headers.get("Deprecation", "")
        self.assertEqual(deprecation, "true")

    def test_old_cursor_sunset_header_is_present(self):
        resp = self.client.get(self.url, {"limit": 50, "cursor": "id-010"})
        sunset = resp.headers.get("Sunset", "")
        self.assertTrue(sunset, "Sunset header must be present")

    # ── Response shape ─────────────────────────────────────────────

    def test_response_includes_columns(self):
        resp = self.client.get(self.url, {"limit": 10})
        data = resp.json()
        self.assertIn("columns", data)
        self.assertIsInstance(data["columns"], list)

    def test_response_includes_page_size(self):
        resp = self.client.get(self.url, {"limit": 30})
        data = resp.json()
        self.assertIn("page_size", data)
        self.assertEqual(data["page_size"], 30)

    def test_new_cursor_no_deprecation_header(self):
        """New format cursor should NOT trigger deprecation warnings."""
        resp = self.client.get(self.url, {"limit": 50})
        self.assertNotIn("Deprecation", resp.headers)

    # ── Edge cases ─────────────────────────────────────────────────

    def test_empty_dataset_returns_zero_results(self):
        """Zero-row dataset returns empty result set."""
        empty_connector = MockConnector([])
        with patch(
            "hub.apps.datasets.views.DatasetViewSet._resolve_connector",
            return_value=empty_connector,
        ):
            resp = self.client.get(self.url, {"limit": 50})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["results"]), 0)
        self.assertIsNone(data["next_cursor"])

    def test_last_page_has_no_next_cursor(self):
        """Last page should have next_cursor=None."""
        page1 = self.client.get(self.url, {"limit": 100}).json()
        self.assertIsNotNone(page1["next_cursor"])

        page2 = self.client.get(
            self.url,
            {"limit": 100, "cursor": page1["next_cursor"]},
        ).json()
        # 150 rows, page_size=100: page2 has 50 rows, no more pages
        self.assertEqual(len(page2["results"]), 50)
        self.assertIsNone(page2["next_cursor"])
