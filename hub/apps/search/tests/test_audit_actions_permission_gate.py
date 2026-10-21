"""
close-test-coverage-gaps 3.x review — the search AUDITOR-surface permission gate.

Review of the 3.0 checkpoint initially flagged these actions for the DRF
3.16 action-kwarg trap — but verification shows the gate IS enforced:
``SimpleRouter`` forwards ``@action`` kwargs as ``as_view`` initkwargs
(``routers.py: initkwargs.update(action.kwargs)``) and the view instance
is constructed with them (``cls(**initkwargs)`` → Django's ``View.__init__``
setattr), so ``self.permission_classes`` carries IsAuditor at request time.
The trap is NARROWER than first stated: it only bites MANUALLY-REGISTERED
``ViewSet.as_view({"post": action})`` routes (the tenants onboarding
endpoint — fixed in 3.0 with a ``get_permissions()`` branch). Router-
registered actions are safe.

This suite pins the enforced contract + the mechanism it depends on:

1.  The ROUTE carries the action kwargs in its initkwargs (a regression
    that re-registers these actions manually — the onboarding-class bug —
    must fail here BEFORE it opens the surface).
2.  P3-1 (sunset 2026-08-10): the deprecated search surface 410s via
    APIVersionMiddleware BEFORE any permission/view code — the
    pre-sunset 401/403/200 enforcement behaviors are dead with the
    surface; the remaining tests pin the SUNSET contract itself (the
    behavioral migration to /api/search/ is recorded for the search
    owning lane).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import permissions
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _make_tenant(prefix: str) -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{prefix}-{suffix}",
        slug=f"{prefix}-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    # The /api/v1/search/ subtree is subscription-gated by middleware —
    # without an active subscription every request 403s with
    # subscription_inactive and the auditor-gate pin becomes vacuous.
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_auditor(tenant: Tenant):
    suffix = uuid.uuid4().hex[:8]
    user = User.objects.create(
        email=f"auditor-{suffix}@example.com",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="AUDITOR",
        defaults={"description": "Auditor"},
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
    return user


def _make_regular(tenant: Tenant):
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create(
        email=f"regular-{suffix}@example.com",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _analytics_url() -> str:
    return reverse("search-analytics")


def _rebuild_url() -> str:
    return reverse("search-rebuild-index")


class TestAuditActionPermissionLayer:
    def test_router_forwards_auditor_kwargs_to_the_route(self):
        """The enforcement mechanism: SimpleRouter forwards the action
        kwargs as as_view initkwargs (routers.py: initkwargs.update(
        action.kwargs)), and the view instance is constructed with them.
        A manual re-registration of these actions would drop IsAuditor
        exactly like the tenants onboarding endpoint did pre-3.0 — this
        pin must fail first."""
        from django.urls import resolve, reverse

        from hub.apps.search.views import IsAuditor

        for url_name in ("search-analytics", "search-rebuild-index"):
            resolved = resolve(reverse(url_name))
            initkwargs = getattr(resolved.func, "initkwargs", {})
            perms = initkwargs.get("permission_classes", [])
            assert IsAuditor in perms, f"{url_name} route lost its IsAuditor kwarg"
            assert permissions.IsAuthenticated in perms


class TestAuditActionPermissionEnforcement:
    def _make_unauth_client(self) -> APIClient:
        return APIClient()

    def _make_non_auditor_client(self) -> APIClient:
        tenant = _make_tenant("search-gate")
        regular = _make_regular(tenant)
        client = APIClient()
        client.force_authenticate(user=regular)
        return client

    def _make_auditor_client(self) -> APIClient:
        tenant = _make_tenant("search-gate")
        auditor = _make_auditor(tenant)
        client = APIClient()
        client.force_authenticate(user=auditor)
        return client

    def _assert_sunset(self, resp: Any, replacement: str) -> None:
        """P3-1 (the sunset cleanup): the deprecated search surface
        (sunset 2026-08-10) 410s via APIVersionMiddleware BEFORE any
        permission/view code — the enforcement tests below now pin the
        SUNSET contract itself (the pre-sunset 401/403/200 behaviors
        are dead with the surface). The behavioral migration to
        ``/api/search/`` (UnifiedSearchView) is recorded for the search
        owning lane."""
        assert resp.status_code == 410, resp.content
        body = resp.json()
        assert body.get("code") == "ENDPOINT_SUNSET", resp.content
        assert body.get("details", {}).get("replacement") == replacement, resp.content

    def test_analytics_sunset_contract(self):
        resp: Any = self._make_unauth_client().get(_analytics_url())
        self._assert_sunset(resp, "/api/search/")

    def test_rebuild_sunset_contract(self):
        resp: Any = self._make_unauth_client().post(_rebuild_url(), {}, format="json")
        self._assert_sunset(resp, "/api/search/")

    def test_analytics_sunset_contract_regardless_of_auth(self):
        """The 410 fires BEFORE permissions — an AUDITOR gets the same
        sunset refusal (the surface is gone for everyone)."""
        resp: Any = self._make_auditor_client().get(_analytics_url())
        self._assert_sunset(resp, "/api/search/")

    def test_rebuild_sunset_contract_regardless_of_auth(self):
        resp: Any = self._make_auditor_client().post(_rebuild_url(), {}, format="json")
        self._assert_sunset(resp, "/api/search/")
