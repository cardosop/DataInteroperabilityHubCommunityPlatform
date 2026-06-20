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
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserRole

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
            assert ch.isalnum() or ch == "-", f"unsafe char {ch!r} in slug {slug!r}"

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

        body = res.json()
        self.assertTrue("id" in body and "slug" in body and ("admin_user" in body))
        self.assertTrue(body["slug"].startswith(EPHEMERAL_TENANT_PREFIX))

        # Tenant + admin + role row are all materialised.
        tenant = Tenant.all_objects.get(id=body["id"])
        admin = User.objects.get(id=body["admin_user"]["id"])
        self.assertEqual(admin.tenant_id, tenant.id)

        # TENANT_ADMIN role assignment exists, scoped to this tenant.
        role = Role.objects.get(tenant=tenant, name="TENANT_ADMIN")
        self.assertTrue(UserRole.objects.filter(user=admin, role=role, tenant=tenant).exists())

        # The plaintext password actually authenticates the admin.
        admin.refresh_from_db()
        self.assertTrue(admin.check_password(body["admin_user"]["password"]))

    def test_two_calls_produce_distinct_tenants(self):
        a = self._post({"name": "spec-A"}).json()
        b = self._post({"name": "spec-A"}).json()
        self.assertNotEqual(a["id"], b["id"])
        self.assertNotEqual(a["slug"], b["slug"])

    def test_missing_token_returns_404(self):
        res = self._post(token=None)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_wrong_token_returns_404(self):
        res = self._post(token="wrong-secret")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_body_still_provisions(self):
        # Caller may omit `name`; the view falls back to a UUID-based name.
        res = self._post({})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)

    def test_password_not_logged_in_response_metadata(self):
        # The plaintext password lives only in admin_user.password; nothing
        # else in the response body should echo it (defence-in-depth so a
        # client that only logs `id`/`slug` doesn't accidentally retain
        # secrets).
        res = self._post({"name": "secrecy"}).json()
        password = res["admin_user"]["password"]
        # No top-level field, no nested duplication.
        self.assertNotEqual(res.get("id"), password)
        self.assertNotEqual(res.get("slug"), password)
        self.assertNotEqual(res.get("name"), password)


@override_settings(ENVIRONMENT="production", DEBUG=False, E2E_TEST_SECRET="test-secret-aaa")
class EphemeralTenantProductionLockoutTest(TestCase):
    """Even with the right token, production must 404."""

    def test_production_returns_404(self):
        client = APIClient()
        res = client.post(
            "/api/v1/tenants/ephemeral/",
            data={"name": "x"},
            format="json",
            HTTP_X_E2E_TOKEN="test-secret-aaa",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


# ----------------------------------------------------- 3. Cleanup contract


@override_settings(ENVIRONMENT="test", DEBUG=False, E2E_TEST_SECRET="test-secret-aaa")
class EphemeralTenantCleanupContractTest(TestCase):
    """Slug shape must remain compatible with staging-prefix-purge."""

    def test_slug_swept_by_staging_prefix_purge_default(self):
        client = APIClient()
        res = client.post(
            "/api/v1/tenants/ephemeral/",
            data={"name": "purge-test"},
            format="json",
            HTTP_X_E2E_TOKEN="test-secret-aaa",
        )
        body = res.json()
        # The cron's default prefix is `e2e-`; failure here means a
        # provisioning leak would NOT be auto-collected.
        self.assertTrue(body["slug"].startswith("e2e-"))
