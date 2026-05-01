"""
Phase 228.F3.17 — endpoint tests for the lineage subscription CRUD
surface at ``/api/v1/lineage/subscriptions/``.

Coverage:

* Create — happy path; cap exceeded (400 SUBSCRIPTION_CAP_EXCEEDED);
  duplicate (409 SUBSCRIPTION_ALREADY_EXISTS); cross-tenant source
  (403); both source fields set (400 INVALID_SUBSCRIPTION_SOURCE).
* List — only the requesting user's own subscriptions are visible;
  another user's UUID returns 404; cursor pagination crosses page
  boundaries.
* Patch — threshold + channel updates persist; FK fields are
  immutable.
* Delete — hard-delete; row gone from list afterwards.

No mocks of internal code.  Real DB rows for tenants, users,
contracts, subscriptions.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tenant(slug_prefix: str = "f3") -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant) -> "User":  # type: ignore[name-defined]
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{suffix}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _make_contract(tenant: Tenant, name: str = "c"):
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uuid.uuid4().hex[:6]}",
        name=name,
        status=AssetStatus.DRAFT,
    )
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json={"info": {"name": name}, "models": []},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.ACTIVE,
    )


def _client(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


URL = "/api/v1/lineage/subscriptions/"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class LineageSubscriptionCreateTests(TestCase):

    def test_create_subscription_to_own_contract(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        c = _make_contract(tenant)

        response = _client(user).post(
            URL,
            data={
                "source_contract": str(c.id),
                "severity_threshold": "HIGH",
                "in_app": True,
                "email": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["source_contract"], str(c.id))
        self.assertEqual(body["severity_threshold"], "HIGH")
        self.assertEqual(body["user"], str(user.id))

    def test_xor_invariant_violation_returns_400(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        c = _make_contract(tenant)
        a = Asset.objects.create(
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="aXor",
            status=AssetStatus.DRAFT,
        )
        response = _client(user).post(
            URL,
            data={
                "source_contract": str(c.id),
                "source_asset": str(a.id),
                "severity_threshold": "HIGH",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        # Either format the validator surfaces; both are spec-compliant
        # 400 with a typed code.
        body = response.json()
        text_payload = str(body).upper()
        self.assertIn("INVALID_SUBSCRIPTION_SOURCE", text_payload)

    def test_neither_source_set_returns_400(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        response = _client(user).post(
            URL,
            data={"severity_threshold": "HIGH"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_cross_tenant_source_returns_403(self):
        tenant_a = _make_tenant("xt-a")
        tenant_b = _make_tenant("xt-b")
        user_a = _make_user(tenant_a)
        c_b = _make_contract(tenant_b, name="b")  # foreign tenant's contract
        response = _client(user_a).post(
            URL,
            data={"source_contract": str(c_b.id), "severity_threshold": "HIGH"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)

    def test_duplicate_subscription_returns_409(self):
        tenant = _make_tenant()
        user = _make_user(tenant)
        c = _make_contract(tenant)
        body = {"source_contract": str(c.id), "severity_threshold": "HIGH"}
        first = _client(user).post(URL, data=body, format="json")
        self.assertEqual(first.status_code, 201)
        second = _client(user).post(URL, data=body, format="json")
        self.assertEqual(second.status_code, 409, second.content)
        self.assertEqual(
            second.json().get("code"), "SUBSCRIPTION_ALREADY_EXISTS",
        )

    def test_per_user_cap_enforced_at_101st(self):
        from hub.apps.contracts.lineage_subscription_views import (
            PER_USER_SUBSCRIPTION_CAP,
        )
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant()
        user = _make_user(tenant)
        # Bulk-seed N existing subscriptions cheaply (skip the API
        # round-trip — we just need to count).
        contracts = [
            _make_contract(tenant, name=f"cap-{i}")
            for i in range(PER_USER_SUBSCRIPTION_CAP)
        ]
        LineageSubscription.objects.bulk_create([
            LineageSubscription(
                user=user, source_contract=c, severity_threshold="HIGH",
            )
            for c in contracts
        ])

        # The 101st create attempt must be rejected.
        c_extra = _make_contract(tenant, name="cap-extra")
        response = _client(user).post(
            URL,
            data={"source_contract": str(c_extra.id), "severity_threshold": "HIGH"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        body = response.json()
        self.assertEqual(body.get("code"), "SUBSCRIPTION_CAP_EXCEEDED")
        self.assertEqual(body.get("cap"), PER_USER_SUBSCRIPTION_CAP)


# ---------------------------------------------------------------------------
# List + retrieve
# ---------------------------------------------------------------------------


class LineageSubscriptionListTests(TestCase):

    def test_list_only_returns_own_subscriptions(self):
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant()
        user_a = _make_user(tenant)
        user_b = _make_user(tenant)
        c1 = _make_contract(tenant, name="c1")
        c2 = _make_contract(tenant, name="c2")
        LineageSubscription.objects.create(user=user_a, source_contract=c1)
        LineageSubscription.objects.create(user=user_b, source_contract=c2)

        response = _client(user_a).get(URL)
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_contract"], str(c1.id))

    def test_pagination_accepts_limit_query_param(self):
        """REQ-LIN-F3-003 spec uses ``?limit=N`` (not ``?page_size=N``).
        Phase 228.F3.MetaDoD audit fix wires the alias."""
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant("limit")
        user = _make_user(tenant)
        contracts = [
            _make_contract(tenant, name=f"lim-{i}") for i in range(10)
        ]
        LineageSubscription.objects.bulk_create([
            LineageSubscription(
                user=user, source_contract=c, severity_threshold="HIGH",
            )
            for c in contracts
        ])
        response = _client(user).get(f"{URL}?limit=3")
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(len(body["results"]), 3)
        self.assertIsNotNone(body["next_cursor"])

    def test_cursor_pagination_75_subscriptions(self):
        """REQ-LIN-F3-003 spec scenario "Cursor pagination":
            GIVEN 75 subscriptions
            WHEN GET ?page_size=50
            THEN 50 results + next_cursor
            WHEN GET with next_cursor
            THEN remaining 25 results
        Phase 228.F3.MetaDoD audit fix.
        """
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant("pag")
        user = _make_user(tenant)
        # Create 75 contracts so we have 75 distinct sources.
        contracts = [
            _make_contract(tenant, name=f"pag-{i}") for i in range(75)
        ]
        LineageSubscription.objects.bulk_create([
            LineageSubscription(
                user=user, source_contract=c, severity_threshold="HIGH",
            )
            for c in contracts
        ])

        first = _client(user).get(f"{URL}?page_size=50")
        self.assertEqual(first.status_code, 200, first.content)
        first_body = first.json()
        self.assertEqual(len(first_body["results"]), 50)
        self.assertIsNotNone(first_body["next_cursor"])

        # The next_cursor returned by StandardCursorPagination is a
        # full URL — the test client accepts it via .get().
        second = _client(user).get(first_body["next_cursor"])
        self.assertEqual(second.status_code, 200, second.content)
        second_body = second.json()
        self.assertEqual(len(second_body["results"]), 25)

    def test_retrieve_other_users_subscription_404(self):
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant()
        user_a = _make_user(tenant)
        user_b = _make_user(tenant)
        c = _make_contract(tenant)
        sub = LineageSubscription.objects.create(
            user=user_b, source_contract=c,
        )
        response = _client(user_a).get(f"{URL}{sub.id}/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Patch + Delete
# ---------------------------------------------------------------------------


class LineageSubscriptionMutationTests(TestCase):

    def test_patch_severity_threshold(self):
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant()
        user = _make_user(tenant)
        c = _make_contract(tenant)
        sub = LineageSubscription.objects.create(
            user=user, source_contract=c, severity_threshold="HIGH",
        )
        response = _client(user).patch(
            f"{URL}{sub.id}/",
            data={"severity_threshold": "CRITICAL", "email": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        sub.refresh_from_db()
        self.assertEqual(sub.severity_threshold, "CRITICAL")
        self.assertTrue(sub.email)

    def test_patch_cannot_change_source(self):
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant()
        user = _make_user(tenant)
        c1 = _make_contract(tenant, name="c1")
        c2 = _make_contract(tenant, name="c2")
        sub = LineageSubscription.objects.create(user=user, source_contract=c1)

        response = _client(user).patch(
            f"{URL}{sub.id}/",
            data={"source_contract": str(c2.id)},
            format="json",
        )
        # PATCH serializer only exposes severity + channel fields, so
        # the source_contract field is silently ignored.  The row
        # should retain the original FK.
        self.assertIn(response.status_code, (200, 400))
        sub.refresh_from_db()
        self.assertEqual(str(sub.source_contract_id), str(c1.id))

    def test_delete_unsubscribes(self):
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant()
        user = _make_user(tenant)
        c = _make_contract(tenant)
        sub = LineageSubscription.objects.create(user=user, source_contract=c)
        response = _client(user).delete(f"{URL}{sub.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            LineageSubscription.objects.filter(id=sub.id).exists(),
        )
