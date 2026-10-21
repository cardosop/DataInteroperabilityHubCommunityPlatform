"""
pilot-readiness 4.1 — API-key scope enforcement matrix.

``ROLE_SCOPE_MAP`` scopes x the endpoints that enforce them
(``HasScope``/``HasAnyScope``), over the REAL HTTP surface with the
real ``ApiKey`` header authentication — no mocks, no force_auth.

Each matrix cell asserts:
- the in-scope key reaches the endpoint (its response is NOT a 403
  permission denial — the endpoint's own validation may still refuse
  the payload, but never on scope grounds);
- the out-of-scope key gets 403 with the account-plane envelope code
  (``AUTH_FORBIDDEN`` — the 8.x PermissionDenied envelope contract);
- the wildcard ("*") key passes every surface;
- an empty-scopes key is denied everywhere it requires a scope.

The enforcement surface is REAL: assets (all non-safe methods require
``assets:write``), ml (``ml:read`` for safe / ``ml:write`` for
mutations — write does NOT imply read), virtualization
(``virtualization:write`` for query creation). A key with a scope the
endpoint does not require is unaffected.
"""

import hashlib
import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.security

_ENVELOPE_CODE = "AUTH_FORBIDDEN"


def _raw_key():
    return uuid.uuid4().hex


def _make_key(tenant, user, scopes):
    raw = _raw_key()
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        name=f"scopes-{uuid.uuid4().hex[:8]}",
        scopes=scopes,
    )
    return raw


def _client_for(raw_key):
    client = APIClient()
    # The real header contract is ``X-Api-Key`` (read as
    # HTTP_X_API_KEY by the auth class) or ``Authorization: ApiKey …``
    # — an ``Api-Key`` header is never read (the pre-fix tests silently
    # sent that and every cell 401'd).
    client.credentials(HTTP_X_API_KEY=raw_key)
    return client


class ApiKeyScopeMatrixTest(TestCase):
    """The endpoint x scope matrix (plan: ROLE_SCOPE_MAP scopes x
    endpoints, 403 out-of-scope / 200 in-scope)."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name=f"scopes-{uuid.uuid4().hex[:8]}",
            slug=f"scopes-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            ml_enabled=True,
            virtualization_enabled=True,
        )
        from django.utils import timezone

        cls.tenant.onboarding_completed_at = timezone.now()
        cls.tenant.save(update_fields=["onboarding_completed_at", "updated_at"])
        from hub.apps.tenants.models import TenantPlan
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        pro_plan = TenantPlan.objects.filter(slug="pro", is_active=True).first()
        if pro_plan:
            cls.tenant.plan = pro_plan
            cls.tenant.save(update_fields=["plan"])
        ensure_tenant_has_active_subscription(cls.tenant)
        cls.user = User.objects.create_user(
            email=f"scopes-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=cls.tenant,
            status=UserStatus.ACTIVE,
        )
        # The assets + virtualization write surfaces check ROLE as well
        # as scope (HasAnyRole + HasScope) — the real persona shape is a
        # user WITH a role whose API key carries the scope.
        from hub.apps.users.models import Role, UserRole

        role, _created = Role.objects.get_or_create(
            tenant=cls.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Matrix fixture role"},
        )
        UserRole.objects.get_or_create(user=cls.user, tenant=cls.tenant, role=role)

    def _request(self, client, method, path, data=None):
        kwargs = {"data": data} if data is not None else {}
        return getattr(client, method)(path, format="json", **kwargs)

    def _assert_permission_denied(self, response):
        assert response.status_code == 403, response.content[:300]
        body = response.json()
        code = (body.get("error") or {}).get("code")
        assert code == _ENVELOPE_CODE, f"envelope code {code!r} != {_ENVELOPE_CODE!r}"

    # ── assets:write (POST /api/v1/assets/) ───────────────────────────
    def test_assets_write_scope_reaches_create(self):
        client = _client_for(_make_key(self.tenant, self.user, ["assets:write"]))
        response = client.post(
            "/api/v1/assets/",
            {"name": "Scoped Asset", "key": f"scoped-{uuid.uuid4().hex[:8]}", "domain": "sales"},
            format="json",
        )
        # Not a 403: the payload/validation outcome is the endpoint's
        # business, the scope must not be the blocker.
        assert response.status_code not in (401, 403), response.content[:300]

    def test_assets_write_missing_scope_denied(self):
        client = _client_for(_make_key(self.tenant, self.user, ["contracts:write"]))
        response = client.post(
            "/api/v1/assets/",
            {"name": "Scoped Asset", "key": f"scoped-{uuid.uuid4().hex[:8]}", "domain": "sales"},
            format="json",
        )
        self._assert_permission_denied(response)

    def test_assets_write_empty_scopes_denied(self):
        client = _client_for(_make_key(self.tenant, self.user, []))
        response = client.post(
            "/api/v1/assets/",
            {"name": "Scoped Asset", "key": f"scoped-{uuid.uuid4().hex[:8]}", "domain": "sales"},
            format="json",
        )
        self._assert_permission_denied(response)

    # ── ml:read / ml:write (GET+POST /api/v1/ml/models/) ──────────────
    def test_ml_read_scope_reaches_list(self):
        client = _client_for(_make_key(self.tenant, self.user, ["ml:read"]))
        response = client.get("/api/v1/ml/models/")
        assert response.status_code not in (401, 403), response.content[:300]

    def test_ml_read_denied_without_read_scope(self):
        # ml:write does NOT imply ml:read — the write-only key must be
        # denied on the safe-method list (the matrix's write≠read cell).
        client = _client_for(_make_key(self.tenant, self.user, ["ml:write"]))
        response = client.get("/api/v1/ml/models/")
        self._assert_permission_denied(response)

    def test_ml_write_scope_reaches_create(self):
        client = _client_for(_make_key(self.tenant, self.user, ["ml:write"]))
        response = client.post(
            "/api/v1/ml/models/",
            {"name": "Scoped Model", "key": f"scoped-{uuid.uuid4().hex[:8]}"},
            format="json",
        )
        assert response.status_code not in (401, 403), response.content[:300]

    def test_ml_write_denied_without_write_scope(self):
        client = _client_for(_make_key(self.tenant, self.user, ["ml:read"]))
        response = client.post(
            "/api/v1/ml/models/",
            {"name": "Scoped Model", "key": f"scoped-{uuid.uuid4().hex[:8]}"},
            format="json",
        )
        self._assert_permission_denied(response)

    # ── virtualization:write (POST /api/v1/virtualization/datasets/) ──
    def test_virtualization_write_scope_reaches_create(self):
        client = _client_for(_make_key(self.tenant, self.user, ["virtualization:write"]))
        response = client.post(
            "/api/v1/virtualization/datasets/",
            {"name": "Scoped VD", "source": "source-1"},
            format="json",
        )
        assert response.status_code not in (401, 403), response.content[:300]

    def test_virtualization_write_missing_scope_denied(self):
        client = _client_for(_make_key(self.tenant, self.user, ["ml:write"]))
        response = client.post(
            "/api/v1/virtualization/datasets/",
            {"name": "Scoped VD", "source": "source-1"},
            format="json",
        )
        self._assert_permission_denied(response)

    # ── wildcard ──────────────────────────────────────────────────────
    def test_wildcard_scope_passes_every_surface(self):
        client = _client_for(_make_key(self.tenant, self.user, ["*"]))
        for method, path, data in (
            ("post", "/api/v1/assets/", {"name": "W", "key": f"w-{uuid.uuid4().hex[:8]}", "domain": "sales"}),
            ("get", "/api/v1/ml/models/", None),
            ("post", "/api/v1/ml/models/", {"name": "W", "key": f"w-{uuid.uuid4().hex[:8]}"}),
            ("post", "/api/v1/virtualization/datasets/", {"name": "W", "source": "s-1"}),
        ):
            response = self._request(client, method, path, data)
            assert response.status_code not in (401, 403), (method, path, response.content[:300])

    # ── tenant-scoped keys without a user are rejected ────────────────
    def test_tenant_key_without_user_rejected(self):
        raw = _raw_key()
        APIKey.objects.create(
            tenant=self.tenant,
            user=None,
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            name=f"scopes-{uuid.uuid4().hex[:8]}",
            scopes=["*"],
        )
        client = _client_for(raw)
        response = client.get("/api/v1/ml/models/")
        assert response.status_code in (401, 403), response.content[:300]
