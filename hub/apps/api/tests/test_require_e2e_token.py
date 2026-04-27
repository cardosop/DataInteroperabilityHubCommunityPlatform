"""
Tests for ``require_e2e_token`` decorator — the shared-secret gate on the
four ``/api/v1/test/ensure-e2e-*`` endpoints.

The decorator's invariants:
  (a) empty/unset E2E_TEST_SECRET → 404 unconditionally (failsafe)
  (b) missing X-E2E-Token header → 404
  (c) wrong X-E2E-Token value → 404 (via hmac.compare_digest, constant-time)
  (d) correct X-E2E-Token + permitted env → not 404
  (e) correct X-E2E-Token + ENVIRONMENT=production → still 404
      (view-body env guard is defense-in-depth; the token alone is not
      enough to expose E2E endpoints on production)

This test targets ``ensure_e2e_users`` which is ``AllowAny`` — it exercises
the decorator without requiring an authenticated client fixture. The other
three E2E views get the same decorator applied; a separate post-condition
assertion in ``views.py`` verifies the decorator is present on all four.

No mocks — the decorator is tested via the real Django URLconf and test
client. Only the runtime configuration (settings) is overridden per test.
"""
from __future__ import annotations

import pytest
from django.test import TestCase, override_settings


pytestmark = pytest.mark.django_db

ENSURE_E2E_USERS_URL = "/api/v1/test/ensure-e2e-users/"
TEST_SECRET = "test-secret-not-used-in-production-deadbeef1234"


class RequireE2ETokenDecoratorGateTest(TestCase):
    """End-to-end HTTP tests of the token gate on the public AllowAny view."""

    @override_settings(E2E_TEST_SECRET="", ENVIRONMENT="staging")
    def test_empty_secret_returns_404_even_with_header(self):
        # Failsafe: if the secret isn't provisioned, no token value can unlock.
        response = self.client.post(
            ENSURE_E2E_USERS_URL,
            content_type="application/json",
            HTTP_X_E2E_TOKEN="anything",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(E2E_TEST_SECRET=TEST_SECRET, ENVIRONMENT="staging")
    def test_missing_header_returns_404(self):
        response = self.client.post(
            ENSURE_E2E_USERS_URL, content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(E2E_TEST_SECRET=TEST_SECRET, ENVIRONMENT="staging")
    def test_wrong_header_returns_404(self):
        response = self.client.post(
            ENSURE_E2E_USERS_URL,
            content_type="application/json",
            HTTP_X_E2E_TOKEN="wrong-value",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(E2E_TEST_SECRET=TEST_SECRET, ENVIRONMENT="production")
    def test_correct_token_on_production_still_returns_404(self):
        # Defense-in-depth: view-body env guard must still fire even when
        # the token matches, so a production leak of the secret doesn't
        # unlock the endpoints.
        response = self.client.post(
            ENSURE_E2E_USERS_URL,
            content_type="application/json",
            HTTP_X_E2E_TOKEN=TEST_SECRET,
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(E2E_TEST_SECRET=TEST_SECRET, ENVIRONMENT="staging")
    def test_correct_token_on_staging_passes_the_gate(self):
        # A correct token + permitted env yields NOT 404. The body may return
        # 200 (full fixture flow) or 4xx (validation) depending on state —
        # the point is the token-gate is not the failure reason.
        response = self.client.post(
            ENSURE_E2E_USERS_URL,
            content_type="application/json",
            data="{}",
            HTTP_X_E2E_TOKEN=TEST_SECRET,
        )
        self.assertNotEqual(
            response.status_code,
            404,
            "Correct token + staging should pass the decorator gate",
        )


class AllFiveE2EViewsCarryTheDecoratorTest(TestCase):
    """
    Post-condition check: every test-only e2e view has the decorator applied.

    DRF's ``@api_view`` rewrites the symbol into a ``WrappedAPIView.as_view()``
    class-based view, which obscures the inner ``_require_e2e_token = True``
    marker at runtime. Rather than wrestle with DRF internals, we parse the
    source file via ``ast`` and verify each view definition literally carries
    the ``@require_e2e_token`` decorator in its decorator list. This is the
    true post-condition and is resilient to DRF changes.

    Updated 2026-04-27 (cycle 7): ``reset_e2e_auth_rate_limits`` added so the
    staging E2E runner can clear the per-tenant auth limiter pre-flight
    instead of accumulating 429s across the 287-test MVP suite. The new view
    is ``AllowAny`` (the limiter blocks the very logins needed to authenticate),
    so the only security boundary is the X-E2E-Token shared-secret gate —
    making this post-condition test load-bearing.
    """

    def test_all_e2e_views_have_the_decorator(self):
        import ast
        import inspect

        from hub.apps.api import views as views_module

        expected_decorated = {
            "ensure_e2e_invitation_token",
            "ensure_e2e_subscription",
            "ensure_e2e_tenant_switch_setup",
            "ensure_e2e_users",
            "reset_e2e_auth_rate_limits",
        }

        tree = ast.parse(inspect.getsource(views_module))
        seen: dict[str, list[str]] = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name in expected_decorated
            ):
                decorator_names: list[str] = []
                for d in node.decorator_list:
                    if isinstance(d, ast.Name):
                        decorator_names.append(d.id)
                    elif isinstance(d, ast.Call) and isinstance(
                        d.func, ast.Name
                    ):
                        decorator_names.append(d.func.id)
                seen[node.name] = decorator_names

        not_found = expected_decorated - set(seen.keys())
        self.assertFalse(
            not_found,
            f"Expected E2E view functions not found in source: {not_found}",
        )

        missing_decorator = [
            name
            for name, decs in seen.items()
            if "require_e2e_token" not in decs
        ]
        self.assertFalse(
            missing_decorator,
            f"E2E views missing @require_e2e_token in source: {missing_decorator}",
        )
