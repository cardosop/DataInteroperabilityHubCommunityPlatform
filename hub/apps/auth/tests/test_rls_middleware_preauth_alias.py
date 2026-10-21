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
        cursor.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{_PREAUTH_ADMIN_ROLE}"')
        # Phase U.6 mirror (P0-1 battery finding, 2026-10-18): the
        # production admin alias role carries FULL DML — cross-tenant /
        # pre-tenant flows (login-attempt recording, the refresh mint)
        # write through it (scripts/init-db.sql U.6). The SELECT-only
        # grants above predate the U.6 write contract and made every
        # alias-routed write fail with permission denied — the pins
        # went RED when post-W10.2 features (the W11.2 lockout writes)
        # started exercising the alias-write path.
        cursor.execute(
            f"GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            f'TO "{_PREAUTH_ADMIN_ROLE}"'
        )


def _ensure_rls_probe_role():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [_RLS_PROBE_ROLE])
        if cursor.fetchone() is None:
            cursor.execute(f"CREATE ROLE {_RLS_PROBE_ROLE} NOSUPERUSER NOBYPASSRLS NOLOGIN")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {_RLS_PROBE_ROLE}")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_RLS_PROBE_ROLE}")
        # The enforced app role writes tenant-scoped audit rows on the
        # default connection (create_audit_event's tenant_context path —
        # e.g. the login audit). Production grants it INSERT on
        # audit_events; mirror that so the enforcement pins exercise the
        # real write path (the RLS WITH CHECK is still enforced — this
        # role is NOBYPASSRLS). UPDATE too: AuditEvent.save() locks the
        # chain predecessor with SELECT ... FOR UPDATE, which requires
        # the UPDATE privilege on the table.
        cursor.execute(f"GRANT INSERT, UPDATE ON audit_events TO {_RLS_PROBE_ROLE}")


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
        request = self.factory.get("/api/v1/assets/", HTTP_X_TENANT_ID=str(self.tenant_b.id))
        request.user = self.user_a

        response = self._run(request, _echo_tenant_guc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._json(response)["tenant_guc"], str(self.tenant_b.id))

    @pytest.mark.integration
    def test_non_member_x_tenant_id_still_403_under_enforcement(self):
        request = self.factory.get("/api/v1/assets/", HTTP_X_TENANT_ID=str(self.tenant_c.id))
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
        request = self.factory.get("/api/v1/assets/", HTTP_X_TENANT_ID=str(self.tenant_b.id))
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


@override_settings(
    DATABASES=_databases_with_preauth_admin(),
    RLS_ADMIN_ALIAS_IN_TESTS=True,
)
class W102RefreshTokenLifecycleUnderEnforcement(_PreauthEnforcementBase):
    """W10.2 (oss-release-remediation) — the live staging role flip
    (api-service → the RLS-enforced meshant_app) surfaced REAL
    pre-tenant violations in the refresh-token lifecycle: the login
    mint, the refresh rotation and the switch-tenant mint all INSERT
    into ``refresh_tokens`` on the armed default connection whose
    WITH CHECK policy rejects NULL-tenant rows (fail-closed), and the
    refresh read + the switch-tenant membership check see nothing
    through the armed current-tenant GUC.

    These pins run the REAL auth views under the enforced role with
    the BYPASSRLS alias — RED against the pre-fix views
    (live-staging-proven: login 500ed with "new row violates
    row-level security policy for table refresh_tokens")."""

    def _login_request(self, email=None):
        email = email or self.user_a.email
        return self.factory.post(
            "/api/v1/auth/login/",
            data=json.dumps({"email": email, "password": "testpass123"}),
            content_type="application/json",
        )

    def _mint(self, tenant, token_str=None, family_id=None, sequence=0):
        from django.utils import timezone

        from hub.apps.auth.models import RefreshToken

        token_str = token_str or RefreshToken.generate_token()
        return (
            RefreshToken.objects.using("admin").create(
                user=self.user_a,
                tenant_id=tenant.id,
                token_hash=RefreshToken.hash_token(token_str),
                expires_at=timezone.now() + timezone.timedelta(hours=1),
                # family_id is NOT NULL since the refresh-family migration —
                # a family-less mint violates the constraint at rotation.
                family_id=family_id or str(uuid.uuid4()),
                sequence_number=sequence,
            ),
            token_str,
        )

    @pytest.mark.integration
    def test_login_mints_refresh_token_under_enforcement(self):
        from django.db import transaction

        from hub.apps.auth.models import RefreshToken
        from hub.apps.auth.views import login

        # The production request shape: the view runs inside the request
        # transaction — the login audit's transaction-local tenant GUC
        # must survive to the INSERT (in autocommit it evaporates after
        # the set_config statement and the RLS WITH CHECK fails).
        with transaction.atomic(), self._enforced_connection():
            response = login(self._login_request())

        self.assertEqual(response.status_code, 200, response.data)
        row = RefreshToken.objects.using("admin").get(user=self.user_a)
        self.assertEqual(row.tenant_id, self.tenant_a.id)

    @pytest.mark.integration
    def test_refresh_rotates_under_enforcement(self):
        from django.db import transaction

        from hub.apps.auth.models import RefreshToken
        from hub.apps.auth.views import refresh_token

        old, token_str = self._mint(self.tenant_a)
        request = self.factory.post(
            "/api/v1/auth/refresh/",
            data=json.dumps({"refresh_token": token_str}),
            content_type="application/json",
        )

        # Same production request-transaction shape as the login pin.
        with transaction.atomic(), self._enforced_connection():
            response = refresh_token(request)

        self.assertEqual(response.status_code, 200, response.data)
        old.refresh_from_db(using="admin")
        self.assertIsNotNone(old.revoked_at)
        sibling = RefreshToken.objects.using("admin").get(
            family_id=old.family_id, revoked_at__isnull=True
        )
        self.assertEqual(sibling.sequence_number, old.sequence_number + 1)

    @pytest.mark.integration
    def test_refresh_rejects_unknown_token_under_enforcement(self):
        from django.db import transaction

        from hub.apps.auth.views import refresh_token

        request = self.factory.post(
            "/api/v1/auth/refresh/",
            data=json.dumps({"refresh_token": "not-a-real-token"}),
            content_type="application/json",
        )

        # Same production request-transaction shape as the login pin.
        with transaction.atomic(), self._enforced_connection():
            response = refresh_token(request)

        self.assertEqual(response.status_code, 400, response.data)

    @pytest.mark.integration
    def test_switch_tenant_mints_cross_tenant_row_under_enforcement(self):
        from django.db import transaction

        from hub.apps.auth.jwt_utils import JWTTokenGenerator
        from hub.apps.auth.models import RefreshToken
        from hub.apps.auth.views import switch_tenant

        # The W10.3 impersonation work made switch_tenant a DRF
        # @api_view — a manually-assigned request.user is no longer
        # honoured; the pin carries a REAL access token (the production
        # shape). JWTAuthentication resolves the user on the default
        # connection, which works because the GUC below is armed for
        # the caller's own tenant (exactly what the middleware does in
        # the real request cycle).
        token = JWTTokenGenerator.generate_access_token(self.user_a)
        request = self.factory.post(
            "/api/v1/auth/switch-tenant/",
            data=json.dumps({"tenant_id": str(self.tenant_b.id)}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        # The middleware would arm the CURRENT tenant (tenant_a) for an
        # authenticated request — transaction-local, the production shape.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    [str(self.tenant_a.id)],
                )
            with self._enforced_connection():
                response = switch_tenant(request)

        self.assertEqual(response.status_code, 200, response.data)
        row = (
            RefreshToken.objects.using("admin")
            .filter(user=self.user_a)
            .order_by("-created_at")
            .first()
        )
        self.assertEqual(row.tenant_id, self.tenant_b.id)
