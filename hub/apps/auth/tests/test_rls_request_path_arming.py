"""
W1.20 (oss-release-remediation, D2 / W1.4b) — the RLS arming
integration pins: an UNFILTERED queryset returns EMPTY when RLS is
armed.

The design contract (design.md R2-S1/D2): arming fails closed —
leaks become empty results, never cross-tenant rows.  These pins
prove that direction at the database:

* A planted unfiltered view (``Asset.objects.count()`` — deliberately
  NO tenant filter, the application-layer gap RLS exists to cover)
  returns ZERO for a foreign tenant when the middleware arms the
  tenant GUC, and the tenant's OWN rows when the tenant matches.
* Anonymous requests (no tenant) fail closed to zero.
* The master kill switch never leaks: disabled arming + an enforced
  (non-BYPASSRLS) role still hides everything; the leak baseline only
  exists on an RLS-exempt (superuser) connection — which is exactly
  why arming matters.

Enforcement reality: on a superuser test connection PostgreSQL
exempts the role from RLS, so policy-EXISTENCE proves nothing (the
``hub_rls_probe`` pattern from ``databricks_admin``'s UC isolation
suite — a NOSUPERUSER NOBYPASSRLS NOLOGIN role switched via
``SET ROLE`` — is the only honest way to exercise the policies).  On
a non-bypass connection the connection itself enforces and the probe
is skipped.

No mocks: real Postgres rows, real roles, real RLS, the real
middleware.
"""

import json
import uuid
from contextlib import contextmanager

import pytest
from django.db import connection
from django.http import JsonResponse
from django.test import RequestFactory, TransactionTestCase, override_settings
from django.urls import path

from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from tests.factories import AssetFactory

pytestmark = pytest.mark.django_db(transaction=True)

_RLS_PROBE_ROLE = "hub_rls_probe"


# ---------------------------------------------------------------------------
# Planted application-layer gap — an unfiltered view over a real RLS
# table.  The repo's own viewsets are all tenant-scoped (W1.4a / G3),
# so the honest pin for "RLS is the last line of defence" is a view
# that deliberately skips the filter.
# ---------------------------------------------------------------------------
def _unfiltered_assets(request):
    from hub.apps.assets.models import Asset

    return JsonResponse({"count": Asset.objects.count()})


def _echo_tenant_guc(request):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
        row = cursor.fetchone()
    # '' (the placeholder default) ≡ NULL ≡ "no tenant" — see the
    # normalization note in test_rls_middleware_guc.
    return JsonResponse({"tenant_guc": (row[0] if row else None) or None})


# The full-stack pins mount these via override_settings(ROOT_URLCONF=__name__).
urlpatterns = [
    path("api/v1/_w120_unfiltered_assets/", _unfiltered_assets),
    path("api/v1/_w120_echo_tenant_guc/", _echo_tenant_guc),
]


def _ensure_rls_probe_role():
    """Idempotently create the non-superuser probe role with SELECT on
    every public table (the init-db.sql ``meshant_app`` grant shape —
    the middleware chain under the probe role may only read)."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [_RLS_PROBE_ROLE])
        if cursor.fetchone() is None:
            cursor.execute(f"CREATE ROLE {_RLS_PROBE_ROLE} NOSUPERUSER NOBYPASSRLS NOLOGIN")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {_RLS_PROBE_ROLE}")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_RLS_PROBE_ROLE}")


def _connection_bypasses_rls():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('is_superuser')")
        if cursor.fetchone()[0] == "on":
            return True
        cursor.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        return bool(cursor.fetchone()[0])


def _visible_count_as(role_or_none, tenant_id, table):
    """Direct SQL control: rows visible on *table* under *tenant_id*'s
    GUC.  The probe sequence runs inside ``transaction.atomic()`` —
    in an autocommit world (TransactionTestCase) a bare
    ``set_config(..., is_local=true)`` dies with its own implicit
    commit and the count reads NO tenant context (the 1.12 RLS probe
    autocommit trap), proving nothing.  The atomic also reverts the
    SET ROLE + GUC atomically at commit."""
    from django.db import connection
    from django.db import transaction as db_transaction

    with db_transaction.atomic(), connection.cursor() as cursor:
        if role_or_none:
            cursor.execute(f"SET ROLE {role_or_none}")
        cursor.execute("SELECT set_config('app.current_tenant_id', %s, true)", [str(tenant_id)])
        cursor.execute(f"SELECT count(*) FROM {table}")
        return cursor.fetchone()[0]


class ArmedRequestPathEnforcementPins(TransactionTestCase):
    """The evidence pin: unfiltered queryset → EMPTY with RLS armed."""

    def setUp(self):
        self.factory = RequestFactory()
        uid = uuid.uuid4().hex[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"W120 Arm A {uid}", slug=f"w120-arm-a-{uid}", status="ACTIVE"
        )
        self.tenant_b = Tenant.objects.create(
            name=f"W120 Arm B {uid}", slug=f"w120-arm-b-{uid}", status="ACTIVE"
        )
        self.user_a = User.objects.create_user(
            email=f"w120-arm-a-{uid}@example.com", password="testpass123", tenant=self.tenant_a
        )
        self.user_b = User.objects.create_user(
            email=f"w120-arm-b-{uid}@example.com", password="testpass123", tenant=self.tenant_b
        )
        # The row the unfiltered queryset would leak to tenant B.
        self.asset_a = AssetFactory.create(tenant=self.tenant_a)
        _ensure_rls_probe_role()

    def _probe_role(self):
        """The probe role when the test connection is RLS-exempt, else
        None (the connection itself is the enforcement subject)."""
        _ensure_rls_probe_role()
        return _RLS_PROBE_ROLE if _connection_bypasses_rls() else None

    @contextmanager
    def _enforced_connection(self):
        probe = self._probe_role()
        with connection.cursor() as cursor:
            if probe:
                cursor.execute(f"SET ROLE {probe}")
        try:
            yield probe
        finally:
            if probe:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")

    def _run_request(self, user, get_response):
        with self._enforced_connection() as probe:
            request = self.factory.get("/api/v1/assets/")
            if user is not None:
                request.user = user
            response = TenantScopingMiddleware(get_response)(request)
        return probe, response

    def _json(self, response):
        return json.loads(response.content.decode("utf-8"))

    @pytest.mark.integration
    def test_unfiltered_queryset_returns_empty_for_foreign_tenant_when_armed(self):
        # Control first: the row EXISTS and the policies pass it only
        # under its owner's context — the pin below is not vacuous.
        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "assets") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "assets") == 0

        _probe, response = self._run_request(self.user_b, _unfiltered_assets)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["count"], 0)

    @pytest.mark.integration
    def test_own_tenant_rows_visible_when_armed(self):
        _probe, response = self._run_request(self.user_a, _unfiltered_assets)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["count"], 1)

    @pytest.mark.integration
    def test_anonymous_request_fails_closed_to_empty_when_armed(self):
        _probe, response = self._run_request(None, _unfiltered_assets)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["count"], 0)

    @pytest.mark.integration
    def test_armed_request_runs_with_the_tenant_guc_in_the_database(self):
        _probe, response = self._run_request(self.user_b, _echo_tenant_guc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["tenant_guc"], str(self.tenant_b.id))

    @override_settings(RLS_REQUEST_PATH_ENABLED=False)
    @pytest.mark.integration
    def test_kill_switch_disabled_is_fail_closed_never_leaky(self):
        # With arming disabled the GUC is unset, so the policies hide
        # EVERYTHING on an enforced connection — the kill switch can
        # empty results, it can never leak them.
        _probe, response = self._run_request(self.user_a, _unfiltered_assets)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["count"], 0)

    @override_settings(RLS_REQUEST_PATH_ENABLED=False)
    @pytest.mark.integration
    def test_unarmed_baseline_documents_the_leak_arming_prevents(self):
        # The negative control: with arming disabled, the planted
        # unfiltered queryset returns the FULL cross-tenant inventory
        # on an RLS-exempt (superuser) connection — the exact leak
        # class arming exists to close.  On an enforcing connection
        # the policies hide everything even unarmed (fail-closed).
        # The assertion is residue-proof: the full inventory is read
        # from the same connection, so shared-DB residue from other
        # suites cannot fake either branch.
        from hub.apps.assets.models import Asset

        full_inventory = Asset.objects.count()
        self.assertGreater(full_inventory, 0)  # our row is in there

        request = self.factory.get("/api/v1/assets/")
        request.user = self.user_b
        response = TenantScopingMiddleware(_unfiltered_assets)(request)
        expected = full_inventory if _connection_bypasses_rls() else 0
        self.assertEqual(self._json(response)["count"], expected)

    @pytest.mark.integration
    def test_guc_does_not_leak_onto_the_connection_after_request(self):
        _, response = self._run_request(self.user_a, _unfiltered_assets)
        self.assertEqual(response.status_code, 200)

        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
            row = cursor.fetchone()
        # '' (the placeholder default) ≡ NULL ≡ "no tenant" — either
        # proves the transaction-local value evaporated.
        self.assertIsNone(row[0] or None)


class FullStackRequestPathArmingPins(TransactionTestCase):
    """The same pins through the REAL middleware chain (ROOT_URLCONF
    override mounts the planted views; APIClient drives the request)."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"W120 FS A {uid}", slug=f"w120-fs-a-{uid}", status="ACTIVE"
        )
        self.tenant_b = Tenant.objects.create(
            name=f"W120 FS B {uid}", slug=f"w120-fs-b-{uid}", status="ACTIVE"
        )
        self.user_a = User.objects.create_user(
            email=f"w120-fs-a-{uid}@example.com", password="testpass123", tenant=self.tenant_a
        )
        self.user_b = User.objects.create_user(
            email=f"w120-fs-b-{uid}@example.com", password="testpass123", tenant=self.tenant_b
        )
        self.asset_a = AssetFactory.create(tenant=self.tenant_a)
        _ensure_rls_probe_role()

    def _probe_role(self):
        _ensure_rls_probe_role()
        return _RLS_PROBE_ROLE if _connection_bypasses_rls() else None

    @contextmanager
    def _enforced_connection(self):
        probe = self._probe_role()
        with connection.cursor() as cursor:
            if probe:
                cursor.execute(f"SET ROLE {probe}")
        try:
            yield probe
        finally:
            if probe:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")

    @override_settings(ROOT_URLCONF=__name__, MVP_MODE=False)
    @pytest.mark.integration
    def test_full_stack_unfiltered_endpoint_empty_for_foreign_tenant(self):
        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "assets") == 1

        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user_b)

        with self._enforced_connection():
            response = client.get("/api/v1/_w120_unfiltered_assets/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["count"], 0)

    @override_settings(ROOT_URLCONF=__name__, MVP_MODE=False)
    @pytest.mark.integration
    def test_full_stack_echo_shows_the_tenant_guc(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user_a)

        with self._enforced_connection():
            response = client.get("/api/v1/_w120_echo_tenant_guc/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["tenant_guc"], str(self.tenant_a.id))
