"""
W1.20 (oss-release-remediation, D2 / W1.4b) — the RLS request-path
arming GUC pins.

The TenantScopingMiddleware arms PostgreSQL Row-Level Security on the
HTTP path by setting, inside the request's transaction::

    app.current_tenant_id           — the resolved request tenant (NULL
                                      for anonymous requests — the
                                      fail-closed direction)
    app.rls_<table>_enabled         — one GUC per RLS policy, mapped
                                      from the paired RLS_<TABLE>_ENABLED
                                      settings kill switch

These pins assert the GUCs are REALLY SET in the database session
(``current_setting`` probes — no mocks, no request-attribute echoes),
that the per-table flags follow the settings, that the master kill
switch (``RLS_REQUEST_PATH_ENABLED``) disables arming entirely, and
that the GUCs are transaction-local — after the request they
evaporate, so a pooled/reused connection can never leak one tenant's
scope into the next request.

The class is a TransactionTestCase on purpose: the middleware wraps
the request in ``transaction.atomic()`` and sets the GUCs with
``SET LOCAL`` (transaction-scoped).  A TestCase's outer test
transaction would keep the GUC alive past the middleware's commit,
which is exactly the leakage these pins exist to disprove — only the
autocommit world of TransactionTestCase mirrors the production
request lifecycle.
"""

import json
import uuid

import pytest
from django.http import JsonResponse
from django.test import RequestFactory, TransactionTestCase, override_settings

from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.users.services import UserTenantMembershipService

pytestmark = pytest.mark.django_db(transaction=True)


def _normalize_guc(value):
    # PostgreSQL placeholder GUCs report '' (the placeholder default)
    # both when unset-and-read-with-missing-ok and when SET to NULL —
    # functionally identical to "no tenant" for the policies (no UUID
    # equals ''), so the pins treat both as unset.
    return value or None


def _guc_probe_response(request):
    """get_response that echoes the REAL database GUC values — not
    request attributes."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_setting('app.current_tenant_id', true), "
            "current_setting('app.rls_assets_enabled', true)"
        )
        tenant_guc, assets_guc = cursor.fetchone()
    return JsonResponse(
        {
            "tenant_guc": _normalize_guc(tenant_guc),
            "rls_assets_enabled": _normalize_guc(assets_guc),
        }
    )


def _current_tenant_guc():
    """Read the tenant GUC from the connection NOW (autocommit read —
    only sees session-level state, never a finished request's
    transaction-local value)."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
        row = cursor.fetchone()
        return _normalize_guc(row[0] if row else None)


class RLSMiddlewareGUCTest(TransactionTestCase):
    def setUp(self):
        self.factory = RequestFactory()

        uid = uuid.uuid4().hex[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"RLS Middleware A {uid}",
            slug=f"rls-mid-a-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"RLS Middleware B {uid}",
            slug=f"rls-mid-b-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"rls-mid-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
        )
        UserTenantMembershipService().add_membership(self.user, self.tenant_a)
        UserTenantMembershipService().add_membership(self.user, self.tenant_b)

    def _run(self, request):
        return TenantScopingMiddleware(_guc_probe_response)(request)

    def _json(self, response):
        return json.loads(response.content.decode("utf-8"))

    @pytest.mark.integration
    def test_authenticated_request_arms_tenant_guc_in_the_database(self):
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        response = self._run(request)

        payload = self._json(response)
        self.assertEqual(payload["tenant_guc"], str(self.tenant_a.id))

    @pytest.mark.integration
    def test_x_tenant_id_override_arms_header_tenant_guc(self):
        request = self.factory.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )
        request.user = self.user

        response = self._run(request)

        payload = self._json(response)
        self.assertEqual(payload["tenant_guc"], str(self.tenant_b.id))

    @pytest.mark.integration
    def test_anonymous_request_arms_flags_but_leaves_tenant_guc_null(self):
        # Fail-closed: an anonymous request gets the per-table flags
        # (kill switches still express) but NO tenant — so the RLS
        # policies hide every tenant row.
        request = self.factory.get("/api/v1/assets/")

        response = self._run(request)

        payload = self._json(response)
        self.assertIsNone(payload["tenant_guc"])
        self.assertEqual(payload["rls_assets_enabled"], "true")

    @override_settings(RLS_ASSETS_ENABLED=False)
    @pytest.mark.integration
    def test_rls_table_flag_reflects_the_settings_kill_switch(self):
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        response = self._run(request)

        payload = self._json(response)
        self.assertEqual(payload["tenant_guc"], str(self.tenant_a.id))
        self.assertEqual(payload["rls_assets_enabled"], "false")

    @override_settings(RLS_REQUEST_PATH_ENABLED=False)
    @pytest.mark.integration
    def test_master_kill_switch_disables_arming_entirely(self):
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        response = self._run(request)

        payload = self._json(response)
        self.assertIsNone(payload["tenant_guc"])
        self.assertIsNone(payload["rls_assets_enabled"])

    @pytest.mark.integration
    def test_guc_is_transaction_local_and_does_not_leak_after_request(self):
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        response = self._run(request)
        self.assertEqual(response.status_code, 200)

        # The middleware's transaction committed — the SET LOCAL GUC
        # evaporated with it.  A pooled connection handed to the next
        # request must never carry this tenant's scope.
        self.assertIsNone(_current_tenant_guc())

    @pytest.mark.integration
    def test_anonymous_guc_is_transaction_local_too(self):
        request = self.factory.get("/api/v1/assets/")

        response = self._run(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(_current_tenant_guc())
