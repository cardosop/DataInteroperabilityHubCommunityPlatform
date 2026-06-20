"""
Unit tests for the shared E2E-gating module.

The module backs three production safeguards:

  * Production lockout for `webhook_sink_views.webhook_sink`.
  * Production lockout for `tenants.ephemeral_views.ephemeral_tenant`.
  * Constant-time token comparison shared by both.

These tests live in `hub/apps/api/tests/` rather than alongside any one
caller because the gating module is the *single source of truth* for
both endpoints. Drift between callers would be the failure mode this
consolidation is intended to prevent.

No mocks/stubs — the helpers are dependency-light by design and exercised
with `override_settings` + tiny ad-hoc request shapes.
"""

from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from hub.apps.api.e2e_gating import (
    PERMITTED_E2E_ENVIRONMENTS,
    is_e2e_environment,
    verify_e2e_token,
)

# No `pytest.mark.django_db` — these tests do not touch the database. They
# exercise the gating helpers directly with `override_settings` + ad-hoc
# request shapes. `SimpleTestCase` enforces that contract: any DB access
# (which would indicate test drift) raises immediately rather than silently
# slipping past CI on a misconfigured runner.


class PermittedEnvironmentsConstantTest(SimpleTestCase):
    """The set of permitted environments is part of the public contract."""

    def test_permitted_set_is_test_and_staging(self):
        # Production is intentionally excluded. Adding it would re-introduce
        # the failure mode this module was created to close.
        assert frozenset({"test", "staging"}) == PERMITTED_E2E_ENVIRONMENTS


class IsE2eEnvironmentTest(SimpleTestCase):
    @override_settings(DEBUG=False, ENVIRONMENT="production")
    def test_production_locked_out(self):
        assert is_e2e_environment() is False

    @override_settings(DEBUG=False, ENVIRONMENT="staging")
    def test_staging_allowed(self):
        assert is_e2e_environment() is True

    @override_settings(DEBUG=False, ENVIRONMENT="test")
    def test_test_allowed(self):
        assert is_e2e_environment() is True

    @override_settings(DEBUG=False, ENVIRONMENT="development")
    def test_development_without_debug_locked_out(self):
        # `development` is NOT permitted when DEBUG is False — the only
        # local-dev escape hatch is DEBUG=True. This pins the consolidation
        # decision: ephemeral_views previously allowed "development",
        # webhook_sink did not; the shared module aligns on the stricter
        # posture.
        assert is_e2e_environment() is False

    @override_settings(DEBUG=True, ENVIRONMENT="production")
    def test_debug_overrides_environment(self):
        # Local dev with DEBUG=True is permitted regardless of ENVIRONMENT
        # so a `python manage.py runserver` shell can hit the endpoint.
        assert is_e2e_environment() is True

    @override_settings(DEBUG=False, ENVIRONMENT="")
    def test_empty_environment_locked_out(self):
        # An empty ENVIRONMENT value (e.g. an unset env var falling back
        # to '') must not pass the gate. Guards the defensive default in
        # `getattr(settings, 'ENVIRONMENT', '') or ''`.
        assert is_e2e_environment() is False


class VerifyE2eTokenTest(SimpleTestCase):
    @override_settings(E2E_TEST_SECRET="")
    def test_unset_secret_returns_false(self):
        class FakeRequest:
            headers = {"X-E2E-Token": "anything"}

        assert verify_e2e_token(FakeRequest()) is False

    @override_settings(E2E_TEST_SECRET="correct-horse")
    def test_matching_token_passes(self):
        class FakeRequest:
            headers = {"X-E2E-Token": "correct-horse"}

        assert verify_e2e_token(FakeRequest()) is True

    @override_settings(E2E_TEST_SECRET="correct-horse")
    def test_mismatched_token_rejected(self):
        class FakeRequest:
            headers = {"X-E2E-Token": "wrong-horse"}

        assert verify_e2e_token(FakeRequest()) is False

    @override_settings(E2E_TEST_SECRET="correct-horse")
    def test_lowercase_header_accepted(self):
        # Some Playwright fixtures send the lowercase form; both must work.
        class FakeRequest:
            headers = {"x-e2e-token": "correct-horse"}

        assert verify_e2e_token(FakeRequest()) is True

    @override_settings(E2E_TEST_SECRET="correct-horse")
    def test_missing_header_rejected(self):
        class FakeRequest:
            headers = {}

        assert verify_e2e_token(FakeRequest()) is False

    @override_settings(E2E_TEST_SECRET="correct-horse")
    def test_request_without_headers_attr_rejected(self):
        # The helper must tolerate non-Django request objects passed
        # in by ad-hoc test code without crashing.
        class BareRequest:
            pass

        assert verify_e2e_token(BareRequest()) is False

    @override_settings(E2E_TEST_SECRET="correct-horse")
    def test_empty_string_token_rejected(self):
        class FakeRequest:
            headers = {"X-E2E-Token": ""}

        assert verify_e2e_token(FakeRequest()) is False
