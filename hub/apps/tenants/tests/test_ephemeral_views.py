"""
Unit + integration tests for the Phase 226 OQ4 ephemeral-tenant endpoint.

Three concentric rings:

  1. Pure helpers — slug builder + email builder + env/token gates.
     No DB, no network. Verify shape + edge cases.
  2. View — APIClient round-trip with token gating, env gating, and a
     happy-path provisioning that materialises tenant + admin + role.
  3. Cleanup contract — assert the produced slug starts with the canonical
     prefix the staging-prefix-purge cron sweeps, so a leak is auto-collected.

No mocks/stubs — uses the real User and Tenant models.
"""

from __future__ import annotations

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.ephemeral_views import (
    EPHEMERAL_TENANT_PREFIX,
    _build_admin_email,
    _build_unique_slug,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ----------------------------------------------------- 1. Pure helpers


class BuildUniqueSlugTest(TestCase):
    def test_starts_with_canonical_prefix(self):
        # Cleanup contract: staging-prefix-purge sweeps anything starting
        # with `e2e-`; the more specific `e2e-ephemeral-` keeps these
        # distinguishable from other test fixtures.
        slug = _build_unique_slug("My Tenant")
        self.assertTrue(slug.startswith(EPHEMERAL_TENANT_PREFIX))
        self.assertTrue(slug.startswith("e2e-"))

    def test_two_calls_produce_distinct_slugs(self):
        a = _build_unique_slug("same name")
        b = _build_unique_slug("same name")
        self.assertNotEqual(a, b, "slug uniqueness comes from the random suffix")

    def test_handles_empty_suggested_name(self):
        slug = _build_unique_slug("")
        self.assertTrue(slug.startswith(EPHEMERAL_TENANT_PREFIX))

    def test_sanitises_unsafe_characters(self):
        slug = _build_unique_slug("Tenant!! With $$Symbols")
        # Must remain a valid DRF slug (lowercase + digits + hyphens).
        for ch in slug:
            self.assertTrue(ch.isalnum() or ch == "-", f"unsafe char {ch!r} in slug {slug!r}")

    def test_truncates_long_names(self):
        slug = _build_unique_slug("x" * 500)
        # ≤ Tenant.slug max_length (255) by construction.
        self.assertLessEqual(len(slug), 255)


class BuildAdminEmailTest(TestCase):
    def test_includes_slug(self):
        email = _build_admin_email("e2e-ephemeral-foo-abcd1234")
        self.assertIn("e2e-ephemeral-foo-abcd1234", email)

    def test_uses_test_only_domain(self):
        # The .test TLD is reserved (RFC 2606) — emails to it never leave
        # the network. Important for an endpoint that returns plaintext
        # passwords; we don't want them resolving to a real mailbox.
        email = _build_admin_email("e2e-ephemeral-x")
        self.assertTrue(email.endswith("@e2e.meshant.test"))


# Pure-helper tests for `is_e2e_environment` / `verify_e2e_token` live
# alongside the helper module they cover, at
# `hub/apps/api/tests/test_e2e_gating.py`. The view-level integration
# tests below exercise the gates through the real HTTP contract.


# ----------------------------------------------------- 2. View round-trip


@override_settings(ENVIRONMENT="test", DEBUG=False, E2E_TEST_SECRET="test-secret-aaa")
class EphemeralTenantViewTest(TestCase):
    """End-to-end against the real DB, real User/Tenant/Role models."""

    URL = "/api/v1/tenants/ephemeral/"

    def setUp(self):
        self.client = APIClient()

    def _post(self, body=None, *, token="test-secret-aaa"):
        headers = {}
        if token is not None:
            headers["HTTP_X_E2E_TOKEN"] = token
        return self.client.post(
            self.URL,
            data=body or {},
            format="json",
            **headers,
        )

    def test_happy_path_provisions_tenant_admin_and_role(self):
        res = self._post({"name": "spec-1", "label": "isolation-matrix"})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)

        _body = res.json()
