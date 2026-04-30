"""
Phase 227 Wave 1 (227.L9) — API endpoint tests.

Covers:

* **L9.2** — ``GET /api/v1/contracts/schema/json-schema/?spec=<odcs|odps>``
  returns the canonical HubContract JSON Schema with the
  ``application/schema+json`` content-type per IANA registration.

* **L9.3** — ``GET /api/v1/contracts/?filter=structureless`` is gated
  to TENANT_ADMIN. Non-admin users (DATA_PROVIDER / DATA_VIEWER /
  unauthenticated) get HTTP 403 / 401 respectively. The filter
  itself was shipped in 227.L5.8; this test pins the gate from L9.3.

L9.1 is intentionally NOT covered here — both flags
(``contracts.schema_editor.enabled`` and
``contracts.structural_floor.enabled``) were ungated per the
2026-04-30 directive that retired L3/L4/L5 flag-gating across the
board. Registering dead flags would create lint noise and a flaky
"the flag does nothing" expectation. See `tasks.md` 227.L9.1
closeout for the rationale.

L9.4 is an integration concern handled by the OpenAPI-drift
playwright spec — covered separately at PR-merge time, not in
this unit test.

No internal-code mocks. Real DB rows, real DRF ``APIClient``.
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient


def _make_tenant():
    from hub.apps.tenants.models import KYCStatus, Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"L9 Co {suffix}",
        slug=f"l9-co-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )


def _make_user(tenant):
    from django.contrib.auth import get_user_model
    from hub.apps.users.models import UserStatus

    suffix = uuid.uuid4().hex[:8]
    return get_user_model().objects.create_user(
        email=f"l9-{suffix}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _grant_role(user, tenant, role_name: str):
    """Grant a non-platform-admin role explicitly so ``has_role``
    returns True without short-circuiting via ``is_platform_admin``."""
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name=role_name,
        defaults={"description": f"{role_name} role for L9 tests"},
    )
    UserRole.objects.get_or_create(user=user, role=role)


def _authenticated_client(user) -> APIClient:
    """Return a force-authenticated APIClient. ``force_authenticate``
    bypasses CSRF and session lookup but DOES populate
    ``request.user`` with the supplied instance — enough to exercise
    ``user.has_role(...)`` against the real Role/UserRole rows."""
    client = APIClient()
    # Ensure the user is NOT a platform_admin (would short-circuit
    # has_role to True for every role check). The L9.3 spec is for
    # ROLE-gated tenant scoping, not platform-superuser bypass.
    if user.is_platform_admin:
        user.is_platform_admin = False
        user.save(update_fields=["is_platform_admin"])
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# 227.L9.2 — JSON Schema endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestJsonSchemaEndpoint(TestCase):
    """``GET /api/v1/contracts/schema/json-schema/?spec=<odcs|odps>``
    returns ``application/schema+json`` derived from
    ``HubContractModel.model_json_schema()``."""

    def test_returns_schema_json_content_type(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        client = _authenticated_client(user)

        response = client.get(
            "/api/v1/contracts/schema/json-schema/?spec=odcs",
        )
        assert response.status_code == 200
        # IANA-registered media type for JSON Schema documents.
        assert response["Content-Type"].startswith("application/schema+json"), (
            f"Expected application/schema+json content-type per IANA "
            f"registration; got {response['Content-Type']!r}"
        )

    def test_response_carries_schema_dict_and_spec(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        client = _authenticated_client(user)

        response = client.get(
            "/api/v1/contracts/schema/json-schema/?spec=odcs",
        )
        assert response.status_code == 200
        body = response.data
        assert body["spec"] == "odcs"
        schema = body["schema"]
        # Pydantic v2 model_json_schema emits a top-level
        # ``properties`` dict and ``$defs`` for nested classes.
        assert "properties" in schema, (
            f"Expected JSON Schema properties dict; got {list(schema.keys())!r}"
        )
        # Required fields per the L3 contract.
        for required_key in ("info", "schema"):
            assert required_key in schema["properties"], (
                f"Schema missing required key {required_key!r}"
            )

    def test_invalid_spec_returns_400(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        client = _authenticated_client(user)

        response = client.get(
            "/api/v1/contracts/schema/json-schema/?spec=avro",
        )
        assert response.status_code == 400
        assert response.data["code"] == "INVALID_SPEC"
        assert "odcs" in response.data["details"]["allowed"]
        assert "odps" in response.data["details"]["allowed"]

    def test_accept_application_json_does_not_406(self):
        """Phase 227 L9.2 audit follow-up — RFC 6839 +json suffix
        compatibility. A client sending ``Accept: application/json``
        (the most common JS fetch / curl default) MUST receive the
        schema, not a 406 Not Acceptable. The response Content-Type is
        STILL ``application/schema+json`` (the server upgrades the
        type per RFC 7231 §3.1.1.5)."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        client = _authenticated_client(user)

        response = client.get(
            "/api/v1/contracts/schema/json-schema/?spec=odcs",
            HTTP_ACCEPT="application/json",
        )
        assert response.status_code == 200, (
            f"Accept: application/json must NOT 406 against the "
            f"schema endpoint (RFC 6839 +json suffix); got "
            f"{response.status_code}: {response.data}"
        )
        # Server upgrades the response type to the IANA-preferred
        # form per RFC 7231 §3.1.1.5.
        assert response["Content-Type"].startswith(
            "application/schema+json"
        )

    def test_accept_application_schema_json_explicit(self):
        """Clients that explicitly ask for ``application/schema+json``
        get it. This is the documented happy path."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        client = _authenticated_client(user)

        response = client.get(
            "/api/v1/contracts/schema/json-schema/?spec=odcs",
            HTTP_ACCEPT="application/schema+json",
        )
        assert response.status_code == 200
        assert response["Content-Type"].startswith(
            "application/schema+json"
        )

    def test_accept_incompatible_returns_406(self):
        """Defensive: a truly-incompatible Accept header (e.g. ``text/html``,
        ``application/xml``) MUST 406. The +json suffix relaxation
        only fires for clients that asked for ``application/json`` or
        related — we don't relax to anything else."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        client = _authenticated_client(user)

        response = client.get(
            "/api/v1/contracts/schema/json-schema/?spec=odcs",
            HTTP_ACCEPT="text/html",
        )
        assert response.status_code == 406, (
            f"Accept: text/html must 406 against a JSON Schema "
            f"endpoint; got {response.status_code}: {response.data}"
        )

    def test_missing_spec_param_returns_canonical_schema(self):
        """``spec`` is optional per the L9.2 spec — its absence returns
        the canonical HubContract schema with ``spec: null``."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        client = _authenticated_client(user)

        response = client.get("/api/v1/contracts/schema/json-schema/")
        assert response.status_code == 200
        assert response.data["spec"] is None
        assert "properties" in response.data["schema"]


# ---------------------------------------------------------------------------
# 227.L9.3 — TENANT_ADMIN gate on ?filter=structureless
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestStructurelessFilterRoleGate(TestCase):
    """``GET /api/v1/contracts/?filter=structureless`` requires
    ``TENANT_ADMIN`` role per L9.3. Non-admins get 403; unauthenticated
    requests get 401. Platform admins bypass via ``has_role``'s built-
    in short-circuit."""

    def _seed_structureless_contract(self, tenant):
        from hub.apps.contracts.models import Contract

        return Contract.objects.create(
            tenant=tenant,
            version=1,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="YAML",
            original_raw="kind: DataContract\nname: bad",
            hub_contract_json={"models": [], "schema": {"fields": []}},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status="ACTIVE",
        )

    def test_tenant_admin_can_list_structureless_contracts(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        _grant_role(user, tenant, "TENANT_ADMIN")
        contract = self._seed_structureless_contract(tenant)

        client = _authenticated_client(user)
        response = client.get(
            "/api/v1/contracts/?filter=structureless",
        )
        assert response.status_code == 200, (
            f"TENANT_ADMIN must be able to list structureless contracts; "
            f"got {response.status_code}: {response.data}"
        )
        ids = {r["id"] for r in response.data["results"]}
        assert str(contract.id) in ids

    def test_data_provider_role_is_forbidden(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        _grant_role(user, tenant, "DATA_PROVIDER")
        self._seed_structureless_contract(tenant)

        client = _authenticated_client(user)
        response = client.get(
            "/api/v1/contracts/?filter=structureless",
        )
        assert response.status_code == 403, (
            f"DATA_PROVIDER must be 403'd from ?filter=structureless; "
            f"got {response.status_code}: {response.data}"
        )
        assert response.data["code"] == "PERMISSION_DENIED"
        assert "TENANT_ADMIN" in response.data["details"]["required_roles"]

    def test_data_viewer_role_is_forbidden(self):
        """A read-only viewer MUST NOT see other users' structureless
        contracts via this admin-triage filter."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        _grant_role(user, tenant, "DATA_VIEWER")
        self._seed_structureless_contract(tenant)

        client = _authenticated_client(user)
        response = client.get(
            "/api/v1/contracts/?filter=structureless",
        )
        assert response.status_code == 403

    def test_user_with_no_role_is_forbidden(self):
        """No assigned role at all → 403."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        # No _grant_role call.
        self._seed_structureless_contract(tenant)

        client = _authenticated_client(user)
        response = client.get(
            "/api/v1/contracts/?filter=structureless",
        )
        assert response.status_code == 403

    def test_unauthenticated_request_is_rejected(self):
        """No auth at all → 401 (DRF's IsAuthenticated default).

        Note: the DRF middleware chain applies BEFORE our role check,
        so the response code is whatever DRF produces for an
        unauthenticated user (typically 401 or 403 depending on the
        permission class set in settings).
        """
        tenant = _make_tenant()
        self._seed_structureless_contract(tenant)

        client = APIClient()  # no force_authenticate
        response = client.get(
            "/api/v1/contracts/?filter=structureless",
        )
        # Either 401 (auth required) or 403 (auth-but-not-allowed) is
        # acceptable per RFC 7235 / DRF defaults — what matters is
        # the request is REJECTED.
        assert response.status_code in (401, 403), (
            f"Unauthenticated structureless filter must be 401/403; "
            f"got {response.status_code}: {response.data}"
        )

    def test_platform_admin_bypasses_role_gate(self):
        """``user.has_role(...)`` short-circuits to True for
        ``is_platform_admin`` users — verified at the model level.
        Pin that the L9.3 endpoint inherits this."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)

        # Promote to platform admin.
        user.is_platform_admin = True
        user.save(update_fields=["is_platform_admin"])
        contract = self._seed_structureless_contract(tenant)

        # Don't use _authenticated_client — that demotes platform admin.
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(
            "/api/v1/contracts/?filter=structureless",
        )
        assert response.status_code == 200, (
            f"Platform admin must bypass TENANT_ADMIN gate; got "
            f"{response.status_code}: {response.data}"
        )
        ids = {r["id"] for r in response.data["results"]}
        assert str(contract.id) in ids

    def test_filter_does_not_apply_role_gate_when_absent(self):
        """The role gate ONLY fires when ``?filter=structureless`` is
        supplied. The standard list endpoint stays accessible to all
        authenticated users with whatever role they have."""
        tenant = _make_tenant()
        user = _make_user(tenant)
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        ensure_tenant_has_active_subscription(tenant)
        _grant_role(user, tenant, "DATA_VIEWER")

        client = _authenticated_client(user)
        # No ?filter=structureless.
        response = client.get("/api/v1/contracts/")
        assert response.status_code == 200, (
            f"Plain GET /contracts/ must remain accessible to any "
            f"authenticated tenant user; got {response.status_code}"
        )
