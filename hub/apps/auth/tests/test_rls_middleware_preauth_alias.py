"""
W1.20 (oss-release-remediation, D2 / W1.4b) — pre-tenant identity
resolution must survive RLS enforcement.

In the production role shape the ``default`` connection runs as
``meshant_app`` (RLS-enforced) and the ``admin`` alias as
``meshant_admin`` (BYPASSRLS).  The middleware resolves identity
(API key, JWT user, membership) BEFORE a tenant GUC exists, and the
identity tables (``api_keys``, ``users``,
``user_tenant_memberships``) all carry RLS policies — so those
lookups MUST route through the BYPASSRLS seam or arming would lock
every request out (fail-closed to empty).

This module realizes the canonical
``RLSBypassPreAuthTransactionTest`` promised by the
``_user_lookup_alias`` docstring in ``hub/apps/auth/views.py``: a
TransactionTestCase (committed fixtures are visible to the parallel
admin connection — the TestCase MVCC trap is exactly why the helper
defaults to ``"default"`` under pytest), a REAL second role
(BYPASSRLS + LOGIN) on the test server, and the enforced default
connection exercised via the ``hub_rls_probe`` SET ROLE pattern.

No mocks: real roles, real connections, real RLS.
"""

import copy
import json
import uuid
from contextlib import contextmanager

import pytest
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.test import RequestFactory, TransactionTestCase, override_settings

from hub.apps.auth.db_aliases import _alias_differs, user_lookup_alias
from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.users.services import UserTenantMembershipService
from tests.factories import AssetFactory

pytestmark = pytest.mark.django_db(transaction=True)

_PREAUTH_ADMIN_ROLE = "w120_preauth_admin"
_PREAUTH_ADMIN_PASSWORD = "w120-preauth-admin-pw"  # test-only role credential
_RLS_PROBE_ROLE = "hub_rls_probe"


def _unfiltered_assets(request):
    from hub.apps.assets.models import Asset

    return JsonResponse({"count": Asset.objects.count()})


def _echo_tenant_guc(request):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
        row = cursor.fetchone()
    return JsonResponse({"tenant_guc": row[0] if row else None})


def _ensure_preauth_admin_role():
    """Idempotently create the BYPASSRLS pre-auth role the production
    ``meshant_admin`` shape stands in for (the init-db.sql DO $$
    pattern)."""
    from django.db import connection

    # CREATE ROLE takes an identifier — the role name is a fixed test
    # constant, quoted as an identifier (psycopg2's client-side %s
    # binding produces a string literal, which CREATE ROLE rejects).
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = %s
                ) THEN
                    CREATE ROLE "{_PREAUTH_ADMIN_ROLE}" WITH LOGIN BYPASSRLS PASSWORD %s;
                END IF;
            END
            $$;
            """,
            [_PREAUTH_ADMIN_ROLE, _PREAUTH_ADMIN_PASSWORD],
        )
        cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{_PREAUTH_ADMIN_ROLE}"')
        cursor.execute(
            f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{_PREAUTH_ADMIN_ROLE}"'
        )


def _ensure_rls_probe_role():
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


def _databases_with_preauth_admin():
    databases = copy.deepcopy(settings.DATABASES)
    admin_cfg = dict(databases["admin"])
    admin_cfg["USER"] = _PREAUTH_ADMIN_ROLE
    admin_cfg["PASSWORD"] = _PREAUTH_ADMIN_PASSWORD
    # The admin alias is the SAME physical database as default (a
    # different ROLE, not a different database) — mark it a MIRROR so
    # TransactionTestCase does not flush it separately (two connections
    # TRUNCATE-ing the same tables deadlock/timeout — the exact trap
    # the 'baas' alias's MIRROR comment in settings.py documents).
    # Copy the TEST sub-dict before mutating: settings may share it
    # with the default alias's config via a shallow copy.
    admin_cfg["TEST"] = dict(admin_cfg.get("TEST") or {})
    admin_cfg["TEST"]["MIRROR"] = "default"
    databases["admin"] = admin_cfg
    return databases


class TestAliasDiscriminator:
    """The pure discriminator logic — the only test-visible branch in
    pytest without the canonical override."""

    def test_alias_differs_when_admin_uses_a_different_role(self):
        assert _alias_differs(
            {
                "default": {"USER": "meshant_app"},
                "admin": {"USER": "meshant_admin"},
            }
        )

    def test_alias_does_not_differ_when_roles_match(self):
        assert not _alias_differs({"default": {"USER": "hub"}, "admin": {"USER": "hub"}})

    def test_alias_does_not_differ_when_admin_missing(self):
        assert not _alias_differs({"default": {"USER": "hub"}})

    def test_pytest_runs_default_to_default_alias(self):
        # The MVCC guard: in pytest the admin alias is a SEPARATE
        # connection whose snapshot predates TestCase fixtures, so the
        # helper must resolve to "default" (same connection).
        assert user_lookup_alias() == "default"

    @override_settings(RLS_ADMIN_ALIAS_IN_TESTS=True)
    def test_test_override_selects_admin_when_roles_differ(self):
        databases = _databases_with_preauth_admin()
        with override_settings(DATABASES=databases):
            assert user_lookup_alias() == "admin"

    @override_settings(RLS_ADMIN_ALIAS_IN_TESTS=True)
    def test_test_override_stays_default_when_roles_match(self):
        with override_settings(DATABASES=copy.deepcopy(settings.DATABASES)):
            assert user_lookup_alias() == "default"


class _PreauthEnforcementBase(TransactionTestCase):
    """Shared fixtures + the enforcement-world request helper."""

    # The middleware routes pre-tenant identity reads through the
    # 'admin' alias — Django forbids queries to undeclared aliases in
    # TransactionTestCase, and the alias is declared here with MIRROR
    # so the shared physical database is not flushed twice.
    databases = frozenset({"default", "admin"})

    def setUp(self):
        _ensure_preauth_admin_role()
        _ensure_rls_probe_role()
        self.factory = RequestFactory()
        uid = uuid.uuid4().hex[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"W120 PreA A {uid}", slug=f"w120-prea-a-{uid}", status="ACTIVE"
        )
        self.tenant_b = Tenant.objects.create(
            name=f"W120 PreA B {uid}", slug=f"w120-prea-b-{uid}", status="ACTIVE"
        )
        self.tenant_c = Tenant.objects.create(
            name=f"W120 PreA C {uid}", slug=f"w120-prea-c-{uid}", status="ACTIVE"
        )
        # status=ACTIVE matters: the middleware's JWT/worker paths call
        # user.is_active(), which compares the status enum.
        self.user_a = User.objects.create_user(
            email=f"w120-prea-a-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        self.asset_a = AssetFactory.create(tenant=self.tenant_a)
        UserTenantMembershipService().add_membership(self.user_a, self.tenant_a)
        UserTenantMembershipService().add_membership(self.user_a, self.tenant_b)

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

    def _run(self, request, get_response):
        with self._enforced_connection():
            return TenantScopingMiddleware(get_response)(request)

    def _json(self, response):
        return json.loads(response.content.decode("utf-8"))


@override_settings(
    DATABASES=_databases_with_preauth_admin(),
    RLS_ADMIN_ALIAS_IN_TESTS=True,
)
class RLSBypassPreAuthTransactionTest(_PreauthEnforcementBase):
    """The canonical pattern: pre-auth identity reads on the BYPASSRLS
    alias while the default connection enforces RLS."""

    @pytest.mark.integration
    def test_api_key_extraction_survives_enforcement_via_bypassrls_alias(self):
        from hub.apps.auth.models import APIKey

        # Unique plaintext per run: the shared test DB accumulates
        # residue (its flush times out), and api_keys_key_hash is
        # unique — a fixed key collides with earlier runs.
        plaintext = f"w120-pre-auth-key-{uuid.uuid4().hex}"
        APIKey.objects.create(
            tenant=self.tenant_a,
            name="w120 pre-auth key",
            key_hash=APIKey.hash_key(plaintext),
            user=self.user_a,
        )
        request = self.factory.get("/api/v1/assets/", HTTP_AUTHORIZATION=f"ApiKey {plaintext}")

        response = self._run(request, _unfiltered_assets)

        self.assertEqual(response.status_code, 200, response.content)
        # Tenant resolved through the BYPASSRLS connection, armed on the
        # enforced one — the owner sees their own row.
        self.assertEqual(self._json(response)["count"], 1)

    @pytest.mark.integration
    def test_x_tenant_id_membership_resolved_through_bypassrls_alias(self):
        request = self.factory.get(
            "/api/v1/assets/", HTTP_X_TENANT_ID=str(self.tenant_b.id)
        )
        request.user = self.user_a

        response = self._run(request, _echo_tenant_guc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["tenant_guc"], str(self.tenant_b.id))

    @pytest.mark.integration
    def test_non_member_x_tenant_id_still_403_under_enforcement(self):
        request = self.factory.get(
            "/api/v1/assets/", HTTP_X_TENANT_ID=str(self.tenant_c.id)
        )
        request.user = self.user_a

        with self._enforced_connection():
            response = TenantScopingMiddleware(_unfiltered_assets)(request)

        self.assertEqual(response.status_code, 403)

    @pytest.mark.integration
    def test_jwt_user_resolution_survives_enforcement_via_bypassrls_alias(self):
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        token = JWTTokenGenerator.generate_access_token(
            user=self.user_a, tenant_id=str(self.tenant_a.id)
        )
        request = self.factory.get(
            "/api/v1/assets/", HTTP_X_TENANT_ID=str(self.tenant_b.id)
        )
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        with self._enforced_connection():
            response = TenantScopingMiddleware(_echo_tenant_guc)(request)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["tenant_guc"], str(self.tenant_b.id))


@override_settings(
    DATABASES=_databases_with_preauth_admin(),
    RLS_ADMIN_ALIAS_IN_TESTS=False,
)
class PreauthWithoutAliasFailsClosed(_PreauthEnforcementBase):
    """The control: without the BYPASSRLS routing the enforced
    connection hides the identity rows — fail-closed, never leaky."""

    @pytest.mark.integration
    def test_api_key_rows_hidden_without_alias_routing(self):
        from hub.apps.auth.models import APIKey

        plaintext = f"w120-pre-auth-key-{uuid.uuid4().hex}"
        APIKey.objects.create(
            tenant=self.tenant_a,
            name="w120 pre-auth key (control)",
            key_hash=APIKey.hash_key(plaintext),
            user=self.user_a,
        )
        request = self.factory.get("/api/v1/assets/", HTTP_AUTHORIZATION=f"ApiKey {plaintext}")

        response = self._run(request, _unfiltered_assets)

        self.assertEqual(response.status_code, 200, response.content)
        # The key lookup sees nothing under the enforced role (RLS on
        # api_keys, no tenant GUC yet) → no tenant resolved → the
        # unfiltered queryset fails closed to zero.  The alias routing
        # is what makes the production shape work.
        self.assertEqual(self._json(response)["count"], 0)
