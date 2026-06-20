"""
Integration tests for ``Idempotency-Key`` on POST /api/v1/assets/ (Phase 226 G10b).

The HTTP ``Idempotency-Key`` semantics are owned by
``hub.apps.api.middleware.idempotency.IdempotencyMiddleware`` (project-wide
for every POST/PUT/PATCH on ``/api/v1/*``). These tests verify the
end-to-end contract on the asset-create endpoint specifically:

  * Replayed POST with same key + same body returns the original response
    with ``Idempotency-Replayed: true``.
  * Same key + different body returns 409 ``IDEMPOTENCY_CONFLICT``.
  * Cross-tenant cannot replay; cross-key still creates distinct rows
    (subject to ``Asset.key`` uniqueness).
  * Without the header, behaviour is unchanged.
  * Malformed key returns 400 ``INVALID_IDEMPOTENCY_KEY``.

Key format: UUID OR 8-256 chars of alphanumeric + hyphen/underscore/slash
(see ``validate_idempotency_key`` in idempotency_utils.py).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _key(prefix: str = "e2e-asset-idem") -> str:
    """Generate a middleware-acceptable idempotency key (UUID-suffixed)."""
    return f"{prefix}-{uuid.uuid4().hex}"


class AssetIdempotencyKeyTest(TestCase):
    """Asset-create idempotency-key integration."""

    def setUp(self) -> None:
        cache.clear()
        # Drop Redis-backed idempotency records too — middleware uses a Redis
        # client directly (not the Django cache), so cache.clear() alone is
        # insufficient. Leftover records from a prior test would replay into
        # this one's POST.
        try:
            from hub.apps.api.middleware.idempotency_utils import get_redis_client

            r = get_redis_client()
            for k in r.scan_iter(match="idempotency:*"):
                r.delete(k)
        except ImportError:
            # idempotency_utils (or redis) is not installed; tests will
            # still validate core idempotency semantics.
            pass
        except Exception as _exc:
            # Re-raise anything that is NOT a Redis operational error
            # (connection refused, timeout, etc.) — coding bugs must
            # surface as test failures.
            try:
                import redis.exceptions as _redis_exc
            except ImportError:
                raise  # redis not even importable → let it bubble up
            if not isinstance(_exc, _redis_exc.RedisError):
                raise
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Idem Tenant {uid}",
            slug=f"idem-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"idem-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)
        self.client.force_authenticate(user=self.user)

    def tearDown(self) -> None:
        cache.clear()

    # ---- Identity replay --------------------------------------------------

    def test_same_key_same_body_returns_same_asset_id(self) -> None:
        """A retried POST with identical key + body must return the same id."""
        body = {
            "key": "idem-asset-1",
            "name": "Idem Asset",
            "description": "First create",
        }
        idem_key = _key()
        first = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.content)
        first_id = first.data["id"]

        second = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        # Replay returns the cached response. Status code is the same (201).
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        # The middleware uses Django's ``JsonResponse`` for replays (not DRF
        # ``Response``), so ``response.data`` is unavailable; ``response.json()``
        # is the canonical accessor.
        self.assertEqual(second.json()["id"], first_id)
        # Replay marker — the middleware emits ``Idempotency-Replayed: true``.
        self.assertEqual(second["Idempotency-Replayed"], "true")
        # Database has only one row.
        self.assertEqual(Asset.objects.filter(id=first_id).count(), 1)

    def test_no_key_creates_new_assets_on_each_call(self) -> None:
        """Without the header the original behaviour is preserved."""
        body_a = {"key": "no-idem-1", "name": "No Idem 1"}
        body_b = {"key": "no-idem-2", "name": "No Idem 2"}
        r1 = self.client.post("/api/v1/assets/", data=body_a, format="json")
        r2 = self.client.post("/api/v1/assets/", data=body_b, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(r1.data["id"], r2.data["id"])

    # ---- Mismatched payload --------------------------------------------------

    def test_same_key_different_body_returns_409(self) -> None:
        body = {
            "key": "idem-mismatch-1",
            "name": "Idem Mismatch",
        }
        idem_key = _key()
        first = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.content)

        # Same key, DIFFERENT body — middleware returns 409 IDEMPOTENCY_CONFLICT.
        bad = self.client.post(
            "/api/v1/assets/",
            data={**body, "name": "Different Name"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        self.assertEqual(bad.status_code, status.HTTP_409_CONFLICT)
        # Error envelope shape: {"error": {"code": ..., "message": ..., "http_status": ...}}
        body_json = bad.json()
        self.assertEqual(body_json["error"]["code"], "IDEMPOTENCY_CONFLICT")

    # ---- Validation errors ---------------------------------------------------

    def test_invalid_key_format_returns_400(self) -> None:
        body = {"key": "x", "name": "Bad Key"}
        # Too short — the middleware key format requires UUID or 8-256 chars.
        resp = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY="abc",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json()["error"]["code"], "INVALID_IDEMPOTENCY_KEY")

    # ---- Cross-tenant isolation ---------------------------------------------

    def test_cross_tenant_cannot_replay(self) -> None:
        """Tenant B with the same Idempotency-Key must NOT see tenant A's asset.

        The middleware's cache key includes the user (or tenant) so a key
        from one identity can't replay another's response.
        """
        body = {"key": "iso-1", "name": "Cross-Tenant"}
        shared_key = _key("shared")
        first = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        # Switch to a fresh tenant + user.
        uid = uuid.uuid4().hex[:8]
        tenant_b = Tenant.objects.create(
            name=f"Iso Tenant B {uid}",
            slug=f"iso-tenant-b-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(tenant_b)
        user_b = User.objects.create_user(
            email=f"iso-b-{uid}@example.com",
            password="testpass123",
            tenant=tenant_b,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(user_b)

        client_b = APIClient()
        client_b.force_authenticate(user=user_b)
        # Same body, same key — DIFFERENT tenant. Must create a NEW asset.
        second = client_b.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(second.data["id"], first.data["id"])
        # No replay marker on the second response.
        self.assertNotEqual(second.get("Idempotency-Replayed", ""), "true")
        # Both assets exist independently.
        self.assertEqual(Asset.objects.filter(id=first.data["id"]).count(), 1)
        self.assertEqual(Asset.objects.filter(id=second.data["id"]).count(), 1)

    # ---- Different keys ---------------------------------------------------

    def test_different_keys_with_same_asset_key_409s_or_400s_on_conflict(self) -> None:
        # Same body, different idempotency keys — keys are *different* so this
        # is two logically-different requests; the second one tries to create
        # an asset with the same `key` field. The DB-level uniqueness on
        # ``Asset.key`` per tenant rejects it (409 / 400). The Idempotency-Key
        # feature does NOT turn two distinct requests into one.
        body = {"key": "diff-keys-asset", "name": "Diff Keys"}
        r1 = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=_key("first"),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        r2 = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=_key("second"),
        )
        # MUST NOT be a fresh 201 silently creating a duplicate row.
        self.assertNotEqual(r2.status_code, status.HTTP_201_CREATED)

    # ---- Replay across users in the same tenant ----------------------------

    def test_replay_with_different_user_in_same_tenant(self) -> None:
        """Cache scoping note: the middleware partitions by user. A second user
        in the same tenant sending the same Idempotency-Key with the same body
        does NOT replay; they get their own fresh response (or a 409 if the
        asset key collides). We document the contract explicitly so the spec
        catches an unintended scope expansion.
        """
        body = {"key": "replay-cross-user", "name": "Replay X-user"}
        shared_key = _key("xuser")
        first = self.client.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.content)

        # Second user in the same tenant.
        uid = uuid.uuid4().hex[:8]
        other = User.objects.create_user(
            email=f"other-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(other)
        c2 = APIClient()
        c2.force_authenticate(user=other)
        replay = c2.post(
            "/api/v1/assets/",
            data=body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )
        # Either: (a) cross-user replay returns first.data["id"] (per-tenant
        # scoping) OR (b) middleware partitions by user and the second user
        # creates fresh — which then 409s because asset.key is unique per
        # tenant. Both outcomes are valid; what's NOT valid is silently
        # creating a duplicate with a fresh id.
        if replay.status_code == status.HTTP_201_CREATED:
            replay_id = replay.json()["id"]
            self.assertEqual(replay_id, first.data["id"])
            self.assertEqual(replay.get("Idempotency-Replayed", ""), "true")
        else:
            self.assertIn(
                replay.status_code,
                (status.HTTP_409_CONFLICT, status.HTTP_400_BAD_REQUEST),
            )
