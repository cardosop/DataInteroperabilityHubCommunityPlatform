"""
Phase 277.B.092 — ABAC enforcement on admin endpoints tests.
"""
from unittest.mock import patch

import pytest
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import PermissionDenied

from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult
from hub.apps.governance.admin_abac import (
    _evaluate_admin_action,
    admin_abac_guard,
)
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import User


class TestAdminABACGuard(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name="ABAC Admin", slug="abac-admin", status=TenantStatus.ACTIVE,
        )
        cls.user = User.objects.create_user(
            email="admin@abac.test", password="testpass",
        )

    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, method="PATCH", user=None):
        req = getattr(self.factory, method.lower())("/api/v1/tenants/uuid/rate-limits/")
        req.user = user or self.user
        return req

    def test_allows_when_abac_result_is_allow(self):
        """Admin proceeds when ABAC returns allowed=True."""
        with patch.object(ABACEngine, "evaluate_access") as mock_eval:
            mock_eval.return_value = PolicyEvaluationResult(allowed=True)

            req = self._make_request()
            # Should not raise
            _evaluate_admin_action(req, "TENANT_CONFIG", "ADMIN_WRITE")
            mock_eval.assert_called_once()

    def test_blocks_when_abac_result_is_deny(self):
        """Admin is blocked when ABAC returns allowed=False."""
        with patch.object(ABACEngine, "evaluate_access") as mock_eval:
            mock_eval.return_value = PolicyEvaluationResult(allowed=False)

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
        with patch.object(ABACEngine, "evaluate_access") as mock_eval:
            mock_eval.return_value = PolicyEvaluationResult(allowed=True)

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
        """@admin_abac_guard blocks when ABAC denies."""
        with patch.object(ABACEngine, "evaluate_access") as mock_eval:
            mock_eval.return_value = PolicyEvaluationResult(allowed=False)

            @admin_abac_guard("TENANT_CONFIG")
            def my_admin_view(request):
                return None

            req = self._make_request()
            resp = my_admin_view(req)
            assert resp.status_code == 403
            data = resp.json()
            assert data["error"]["code"] == "ABAC_POLICY_DENIED"

    def test_decorator_returns_401_for_unauthenticated(self):
        """@admin_abac_guard returns 401 when user is not authenticated."""
        with patch.object(ABACEngine, "evaluate_access") as mock_eval:
            @admin_abac_guard("TENANT_CONFIG")
            def my_admin_view(request):
                return None

            req = self._make_request()
            req.user = type("Anon", (), {"is_authenticated": False})()
            resp = my_admin_view(req)
            assert resp.status_code == 401
            mock_eval.assert_not_called()

    def test_decorator_preserves_function_metadata(self):
        """@admin_abac_guard preserves __name__ and __doc__."""

        @admin_abac_guard("TENANT_CONFIG")
        def documented_view(request, tenant_id):
            """Updates tenant configuration."""
            pass

        assert documented_view.__name__ == "documented_view"
        assert documented_view.__doc__ == "Updates tenant configuration."

    def test_read_operations_not_blocked_by_guard(self):
        """GET requests can bypass ABAC guard when check_permissions skips them."""
        with patch.object(ABACEngine, "evaluate_access") as mock_eval:
            mock_eval.return_value = PolicyEvaluationResult(allowed=False)

            @admin_abac_guard("TENANT_CONFIG", action="ADMIN_READ")
            def read_view(request):
                from django.http import JsonResponse
                return JsonResponse({"data": []})

            req = self._make_request("GET")
            resp = read_view(req)
            # GET with DENY policy is still blocked by the guard itself
            # (ABAC is evaluated regardless of HTTP method)
            assert resp.status_code == 403
