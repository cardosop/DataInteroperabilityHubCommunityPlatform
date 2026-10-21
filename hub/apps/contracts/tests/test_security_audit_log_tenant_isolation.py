from __future__ import annotations

import uuid

import pytest
from rest_framework import status

from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.models import SecurityAuditLog
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.observability.cross_tenant_metrics import (
    cross_tenant_denied_total,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SecurityAuditLogTenantIsolationTests(ContractsAPITestBase):
    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uid}",
            slug=f"other-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        SecurityAuditLog.objects.create(
            event_type="SECURITY_VIOLATION",
            tenant=self.tenant,
            user=self.user,
            description="own tenant log",
        )
        SecurityAuditLog.objects.create(
            event_type="SECURITY_VIOLATION",
            tenant=self.other_tenant,
            user=None,
            description="other tenant log",
        )

    @staticmethod
    def _counter_value() -> float:
        labeled = cross_tenant_denied_total.labels(
            endpoint="contracts.security_audit_logs",
            reason="query_tenant_mismatch",
        )
        value = getattr(labeled, "_value", None)
        if value is None or not hasattr(value, "get"):
            return 0.0
        return float(value.get())

    def test_cross_tenant_query_is_denied_with_audit_and_counter(self):
        before_audit = AuditEvent.objects.filter(
            tenant=self.tenant,
            action=event_types.CROSS_TENANT_DENIED,
        ).count()
        before_counter = self._counter_value()

        response = self.client.get(f"/api/v1/security/audit-logs/?tenant_id={self.other_tenant.id}")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "AUTH_FORBIDDEN")
        self.assertEqual(
            payload["error"]["details"]["code"],
            "CROSS_TENANT_FORBIDDEN",
        )
        self.assertEqual(
            payload["error"]["details"]["detail"],
            "tenant_id query parameter does not match request tenant",
        )
        after_audit = AuditEvent.objects.filter(
            tenant=self.tenant,
            action=event_types.CROSS_TENANT_DENIED,
        ).count()
        self.assertEqual(after_audit - before_audit, 1)
        after_counter = self._counter_value()
        self.assertGreaterEqual(
            after_counter - before_counter,
            1.0,
        )

    def test_happy_path_filters_to_request_tenant(self):
        response = self.client.get("/api/v1/security/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json().get("results", [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("tenant_id"), str(self.tenant.id))

    def test_matching_tenant_query_is_accepted_and_scoped(self):
        response = self.client.get(f"/api/v1/security/audit-logs/?tenant_id={self.tenant.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json().get("results", [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("tenant_id"), str(self.tenant.id))
