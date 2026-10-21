"""W8.3 — audit-event CSV export: formula-injection neutralisation.

The export writes tenant name, actor email, resource identifiers and
the details JSON verbatim (CWE-1236): tenant names and emails are
user-controlled strings that may begin with a spreadsheet formula
trigger, and ``details_json`` embeds arbitrary caller-supplied values.
These pins exercise the REAL endpoint (DB + APIClient, no mocks) and
assert every exported cell is spreadsheet-safe.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _grant_role(user, tenant, name):
    role, _ = Role.objects.get_or_create(tenant=tenant, name=name, defaults={"description": name})
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


class AuditExportCsvOutputSafetyTests(TestCase):
    """The exported CSV neutralises formula-triggering cells."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name="=2+5+cmd|' /C calc'!A0",
            slug=f"csv-safe-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"@SUM(1,1)-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        _grant_role(self.user, self.tenant, "AUDITOR")
        self.event = create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=uuid.uuid4(),
            details={"asset_name": '=HYPERLINK("http://evil.example")'},
        )

    def _get_export_rows(self) -> tuple[int, list[list[str]]]:
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content[:500])
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
        return response.status_code, rows

    def test_exported_cells_are_spreadsheet_safe(self):
        _, rows = self._get_export_rows()
        self.assertEqual(rows[0][0], "ID")
        self.assertGreaterEqual(len(rows), 2)
        triggers = ("=", "+", "-", "@", "\t", "\r")
        for row in rows[1:]:
            for cell in row:
                self.assertFalse(
                    cell.startswith(triggers),
                    f"un-neutralised formula cell: {cell!r}",
                )

    def test_tenant_name_cell_is_guarded(self):
        _, rows = self._get_export_rows()
        tenant_cells = [row[2] for row in rows[1:]]
        self.assertIn("'=2+5+cmd|' /C calc'!A0", tenant_cells)

    def test_actor_email_cell_is_guarded(self):
        _, rows = self._get_export_rows()
        email_cells = [row[3] for row in rows[1:]]
        self.assertTrue(any(cell.startswith("'@SUM(1,1)") for cell in email_cells))

    def test_details_json_cell_is_guarded(self):
        _, rows = self._get_export_rows()
        details_cells = [row[8] for row in rows[1:]]
        # The JSON blob starts with '{' (not a trigger) so the cell
        # itself is text — pin that the hostile payload is NOT emitted
        # as a leading formula and that the blob is present.
        self.assertTrue(any('"asset_name": "=HYPERLINK' in cell for cell in details_cells))
        self.assertTrue(all(not cell.startswith(("=", "+", "-", "@")) for cell in details_cells))

    def test_id_column_stays_numeric(self):
        _, rows = self._get_export_rows()
        self.assertEqual(rows[1][0], str(self.event.id))

    def test_csv_content_type_and_disposition(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", response["Content-Disposition"])
