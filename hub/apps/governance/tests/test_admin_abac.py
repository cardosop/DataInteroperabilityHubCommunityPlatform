"""
Phase 277.B.092 — ABAC enforcement on admin endpoints tests.
"""

from unittest.mock import patch

import pytest
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import PermissionDenied

from hub.apps.governance.abac import ABACEngine
from hub.apps.governance.admin_abac import (
    _evaluate_admin_action,
    admin_abac_guard,
)
from hub.apps.governance.models import AccessPolicy
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import User


class TestAdminABACGuard(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(
            name="ABAC Admin",
            slug="abac-admin",
            status=TenantStatus.ACTIVE,
        )
        # User must have a tenant so real ABAC policies can match
        self.user = User.objects.create_user(
            email="admin@abac.test",
            password="testpass",
            tenant=self.tenant,
        )

    def _make_request(self, method="PATCH", user=None):
        req = getattr(self.factory, method.lower())("/api/v1/tenants/uuid/rate-limits/")
        req.user = user or self.user
        return req

    def test_allows_when_abac_result_is_allow(self):
        """Admin proceeds when ABAC returns allowed=True (real policy)."""
        # Create a real ALLOW policy with empty conditions → always matches
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Admin Config",
            conditions={},
            effect="ALLOW",
            priority=100,
            enabled=True,
        )

        req = self._make_request()
        # Should not raise — ABAC evaluates real policy and returns allowed=True
        _evaluate_admin_action(req, "TENANT_CONFIG", "ADMIN_WRITE")

    def test_blocks_when_abac_result_is_deny(self):
        """Admin is blocked when ABAC returns allowed=False (real DENY policy)."""
        # Create a real DENY policy with empty conditions → always matches
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Admin Config",
            conditions={},
            effect="DENY",
            priority=50,  # Higher priority (lower number) than any ALLOW
            enabled=True,
        )

        req = self._make_request()
        with pytest.raises(PermissionDenied) as ctx:
            _evaluate_admin_action(req, "TENANT_CONFIG", "ADMIN_WRITE")

        error = ctx.value.detail
        assert error["code"] == "ABAC_POLICY_DENIED"

    def test_fail_open_on_abac_evaluation_error(self):
        """Admin proceeds when ABAC evaluation raises an exception."""
        with patch.object(ABACEngine, "evaluate_access") as mock_eval:
            mock_eval.side_effect = RuntimeError("ABAC engine unavailable")

            req = self._make_request()
            # Should not raise — fail-open
            _evaluate_admin_action(req, "TENANT_CONFIG", "ADMIN_WRITE")

    def test_decorator_allows_when_abac_allow(self):
        """@admin_abac_guard lets the wrapped function execute when ABAC allows."""
        # Create a real ALLOW policy
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Admin Config Decorator",
            conditions={},
            effect="ALLOW",
            priority=100,
            enabled=True,
        )

        call_count = 0

        @admin_abac_guard("TENANT_CONFIG")
        def my_admin_view(request):
            nonlocal call_count
            call_count += 1
            from django.http import JsonResponse

            return JsonResponse({"ok": True})

        req = self._make_request()
        resp = my_admin_view(req)
        assert resp.status_code == 200
        assert call_count == 1

    def test_decorator_blocks_when_abac_deny(self):
        """@admin_abac_guard blocks when ABAC denies (real DENY policy)."""
        # Create a real DENY policy
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Admin Config Decorator",
            conditions={},
            effect="DENY",
            priority=50,
            enabled=True,
        )

        @admin_abac_guard("TENANT_CONFIG")
        def my_admin_view(request):
            return None

        req = self._make_request()
        resp = my_admin_view(req)
        assert resp.status_code == 403
        import json

        data = json.loads(resp.content)
        assert data["error"]["code"] == "ABAC_POLICY_DENIED"

    def test_decorator_returns_401_for_unauthenticated(self):
        """@admin_abac_guard returns 401 when user is not authenticated."""

        @admin_abac_guard("TENANT_CONFIG")
        def my_admin_view(request):
            return None

        req = self._make_request()
        req.user = type("Anon", (), {"is_authenticated": False})()
        resp = my_admin_view(req)
        assert resp.status_code == 401

    def test_decorator_preserves_function_metadata(self):
        """@admin_abac_guard preserves __name__ and __doc__."""

        @admin_abac_guard("TENANT_CONFIG")
        def documented_view(request, tenant_id):
            """Updates tenant configuration."""

        assert documented_view.__name__ == "documented_view"
        assert documented_view.__doc__ == "Updates tenant configuration."

    def test_read_operations_evaluated_by_abac_guard(self):
        """GET requests are evaluated by ABAC guard regardless of HTTP method."""
        # Create a real DENY policy — it blocks GET too
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Admin Reads",
            conditions={},
            effect="DENY",
            priority=50,
            enabled=True,
        )

        @admin_abac_guard("TENANT_CONFIG", action="ADMIN_READ")
        def read_view(request):
            from django.http import JsonResponse

            return JsonResponse({"data": []})

        req = self._make_request("GET")
        resp = read_view(req)
        # GET with DENY policy is still blocked by the guard itself
        # (ABAC is evaluated regardless of HTTP method)
        assert resp.status_code == 403
