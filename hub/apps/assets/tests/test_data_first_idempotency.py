"""
Phase 250.1.D — idempotency-key tests for ``POST /assets/data-first/``.

Pins the contract from D250.8:

* The ``Idempotency-Key`` header MUST be present on every
  ``POST /assets/data-first/`` request and MUST follow the format
  ``<tenant_uuid>:<sha256(body)>`` (lowercase hex SHA-256 of the
  canonical request body).
* A duplicate request (same key + same body) within a 24-hour TTL
  returns the **cached response** without re-running the workflow.
  Cached responses preserve the original status code, headers
  (notably ``Retry-After``), and body.
* A duplicate **key with a different body** returns
  ``409 Conflict`` + ``IDEMPOTENCY_KEY_MISMATCH`` so a client never
  silently bypasses the deduplication contract.
* If the key tenant prefix doesn't match the authenticated tenant,
  the request is rejected as ``IDEMPOTENCY_KEY_TENANT_MISMATCH``.
* When Redis is unavailable the endpoint **degrades gracefully** —
  the request executes normally without idempotency caching; an
  ops-visible warning is logged but the user is not blocked.

External boundaries (S3, compliance, DQ HTTP clients) are mocked at
their boundaries; idempotency caching uses the real
``django.core.cache`` backend.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.core.resilience.service_breakers import (
    reset_shared_circuit_breakers_for_service,
)
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_authenticated_client(allow_degraded: bool = False, fail_closed: bool = False):
    """Seed a tenant + user + active file; return APIClient + tenant + file.

    ``fail_closed`` defaults to **False** here so the workflow's gate
    doesn't reject in tests that don't explicitly exercise the
    fail-closed path. The tests in this file are about idempotency
    semantics, not the gate.
    """
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
        allow_intake_on_compliance_degraded=allow_degraded,
        compliance_fail_closed_enabled=fail_closed,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)
    file_obj = File.objects.create(
        tenant=tenant,
        name="data.csv",
        content_type="text/csv",
        size=42,
        status=FileStatus.ACTIVE,
        storage_path=f"{tenant.id}/{uuid.uuid4()}/data.csv",
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, tenant, file_obj


def _compose_key(tenant_uuid, body_bytes: bytes) -> str:
    """Compose a valid ``Idempotency-Key`` per D250.8.

    Mirror of the SDK's :func:`compose_idempotency_key` so tests stay
    independent of the SDK module — if the SDK drifts from the
    server contract, both paths catch it.
    """
    sha = hashlib.sha256(body_bytes).hexdigest()
    return f"{tenant_uuid}:{sha}"


def _canonical_bytes(body: dict) -> bytes:
    """Canonical JSON bytes the server hashes — must match SDK output."""
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _post_canonical(client, body: dict, idem_key: str):
    """POST canonical bytes (matching the key's SHA) directly to data-first.

    Bypasses APIClient's ``format="json"`` (which uses default JSON
    encoding) so the bytes the server hashes match the bytes our
    helper hashed. Without this, every test would 409 with
    ``IDEMPOTENCY_KEY_MISMATCH`` because of whitespace differences.
    """
    return client.post(
        "/api/v1/assets/data-first/",
        _canonical_bytes(body),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=idem_key,
    )


def _patch_storage(content: bytes = b"a,b\n1,2\n"):
    return patch(
        "hub.apps.files.storage.S3StorageClient.get_file_content",
        return_value=content,
    )


def _patch_compliance_pass():
    return patch(
        "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
        return_value={
            "overall_status": "PASS",
            "allowed_to_store": True,
            "metadata": {},
        },
    )


def _patch_dq_pass():
    return patch(
        "hub.apps.dq.service_client.DQServiceClient.run_dq",
        return_value={
            "overall_status": "PASS",
            "quality_score": 95.0,
            "metadata": {},
        },
    )


class IdempotencyKeyRequiredTest(TestCase):
    """Phase 250.1.D.1 — ``Idempotency-Key`` header is required."""

    def setUp(self):
        reset_shared_circuit_breakers_for_service("compliance-service")
        cache.clear()

    def test_missing_header_returns_400_idempotency_key_required(self):
        client, _tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "asset-no-idem",
            "name": "Asset no idem",
        }
        # Deliberately omit HTTP_IDEMPOTENCY_KEY. The request body
        # encoding doesn't matter because the missing-key check
        # short-circuits before the body is hashed.
        response = client.post(
            "/api/v1/assets/data-first/",
            _canonical_bytes(body),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    def test_malformed_header_returns_400(self):
        client, _tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "asset-bad-fmt",
            "name": "Asset bad fmt",
        }
        canonical = _canonical_bytes(body)
        for bad_key in [
            "ab",  # too short — middleware rejects
            "!!invalid",  # invalid chars — middleware rejects
            f"{uuid.uuid4()}:tooshort",  # view-level parse_key rejects
        ]:
            response = client.post(
                "/api/v1/assets/data-first/",
                canonical,
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=bad_key,
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST, (
                f"key {bad_key!r} should be 400 but got {response.status_code}"
            )
            try:
                body = response.json()
            except ValueError:
                body = response.content.decode("utf-8", errors="replace")
            if isinstance(body, dict):
                # Two possible response shapes:
                #   {"error": {"code": "INVALID_IDEMPOTENCY_KEY", ...}}  (middleware)
                #   {"error": "message", "code": "IDEMPOTENCY_KEY_MALFORMED"}  (view)
                err = body.get("error", {})
                code = err.get("code", "") if isinstance(err, dict) else body.get("code", "")
            else:
                code = str(body)
            assert code in (
                "IDEMPOTENCY_KEY_MALFORMED",
                "INVALID_IDEMPOTENCY_KEY",
            ), f"unexpected code for {bad_key!r}: {body}"

    def test_tenant_mismatch_in_key_returns_400(self):
        """Key prefix MUST match the request's authenticated tenant."""
        client, _tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "asset-tenant-mismatch",
            "name": "Tenant mismatch",
        }
        # Use a UUID that doesn't belong to the authenticated tenant.
        wrong_tenant = uuid.uuid4()
        canonical = _canonical_bytes(body)
        bad_key = f"{wrong_tenant}:{hashlib.sha256(canonical).hexdigest()}"
        response = client.post(
            "/api/v1/assets/data-first/",
            canonical,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=bad_key,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "IDEMPOTENCY_KEY_TENANT_MISMATCH"


class IdempotencyKeyReplayTest(TestCase):
    """Phase 250.1.D.2 — same key + same body returns cached response."""

    def setUp(self):
        reset_shared_circuit_breakers_for_service("compliance-service")
        cache.clear()

    def _execute(self, client, body, idem_key):
        with _patch_storage(), _patch_compliance_pass(), _patch_dq_pass():
            return _post_canonical(client, body, idem_key)

    def test_same_key_same_body_returns_cached_response_without_re_running_workflow(self):
        client, tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "asset-replay",
            "name": "Asset Replay",
        }
        idem_key = _compose_key(tenant.id, _canonical_bytes(body))

        first = self._execute(client, body, idem_key)
        assert first.status_code == status.HTTP_201_CREATED, first.data
        first_asset_id = first.data["asset_id"]

        # Replay: workflow MUST NOT execute again. We verify by
        # asserting the response body is byte-for-byte identical AND
        # that no NEW Asset row was created.
        before_count = Asset.objects.filter(tenant=tenant).count()
        # Patch the workflow to RAISE if called — this proves the
        # idempotency cache short-circuits before reaching it.
        with patch(
            "hub.apps.orchestration.workflows.asset_creation.AssetCreationWorkflow.execute"
        ) as mock_execute:
            mock_execute.side_effect = AssertionError(
                "workflow MUST NOT be re-executed on idempotent replay"
            )
            second = _post_canonical(client, body, idem_key)

        assert second.status_code == first.status_code
        assert second.json() == first.json()
        assert second.json()["asset_id"] == first_asset_id
        # No new asset created on replay.
        after_count = Asset.objects.filter(tenant=tenant).count()
        assert after_count == before_count

    def test_replay_carries_idempotent_replay_header(self):
        """Replay responses MUST be marked with ``Idempotency-Replayed: true``.

        Lets clients distinguish a fresh execution from a deduped
        replay (helpful for ops dashboards + client retry logic).
        """
        client, tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "asset-replay-header",
            "name": "Asset Replay Header",
        }
        idem_key = _compose_key(tenant.id, _canonical_bytes(body))

        first = self._execute(client, body, idem_key)
        assert first.status_code == status.HTTP_201_CREATED
        assert first.get("Idempotency-Replayed") in (None, "false"), (
            "first response is NOT a replay"
        )

        second = _post_canonical(client, body, idem_key)
        assert second.get("Idempotency-Replayed") == "true"


class IdempotencyKeyMismatchTest(TestCase):
    """Phase 250.1.D.3 — same key, different body → 409 ``IDEMPOTENCY_KEY_MISMATCH``."""

    def setUp(self):
        reset_shared_circuit_breakers_for_service("compliance-service")
        cache.clear()

    def test_same_key_different_body_returns_409(self):
        client, tenant, file_obj = _seed_authenticated_client()
        body_a = {
            "file_id": str(file_obj.id),
            "key": "key-mismatch-a",
            "name": "Asset A",
        }
        idem_key = _compose_key(tenant.id, _canonical_bytes(body_a))

        # Send body_b with the same key — body hash differs from key suffix.
        body_b = dict(body_a)
        body_b["name"] = "Asset B (different)"
        response = _post_canonical(client, body_b, idem_key)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "IDEMPOTENCY_KEY_MISMATCH"


class IdempotencyKeyRedisDownTest(TestCase):
    """Phase 250.1.D.6 — endpoint must degrade gracefully when Redis is down."""

    def setUp(self):
        reset_shared_circuit_breakers_for_service("compliance-service")
        cache.clear()

    def test_redis_get_failure_does_not_block_request(self):
        """When the idempotency middleware cannot reach Redis, the request
        passes through unaffected (fail-open) and the workflow runs
        normally.

        The middleware uses ``get_redis_client()`` from
        ``idempotency_utils`` (not Django's cache). Patching that
        function to return ``None`` causes the middleware to skip
        idempotency processing entirely — the request reaches the
        view and produces 201.
        """
        client, tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "asset-redis-down",
            "name": "Asset Redis Down",
        }
        idem_key = _compose_key(tenant.id, _canonical_bytes(body))

        with (
            _patch_storage(),
            _patch_compliance_pass(),
            _patch_dq_pass(),
            patch(
                "hub.apps.api.middleware.idempotency_utils.get_redis_client",
                return_value=None,
            ),
        ):
            response = _post_canonical(client, body, idem_key)

        # The request MUST succeed (degrade gracefully).
        assert response.status_code == status.HTTP_201_CREATED
        # The response is NOT a replay (middleware was bypassed).
        assert response.get("Idempotency-Replayed") in (None, "false")


class IdempotencyServiceUnitTest(TestCase):
    """Pure-Python contract tests for the IdempotencyService helpers."""

    def setUp(self):
        cache.clear()

    def test_validate_key_format_accepts_canonical_form(self):
        from hub.apps.core.idempotency import IdempotencyService

        tenant_uuid = uuid.uuid4()
        body_sha = hashlib.sha256(b"hello").hexdigest()
        key = f"{tenant_uuid}:{body_sha}"
        parsed_uuid, parsed_sha = IdempotencyService.parse_key(key)
        assert str(parsed_uuid) == str(tenant_uuid)
        assert parsed_sha == body_sha

    def test_parse_key_rejects_malformed_inputs(self):
        from hub.apps.core.idempotency import (
            IdempotencyError,
            IdempotencyService,
        )

        bad_inputs = [
            "",
            "no-colon-here",
            "::",
            "not-a-uuid:" + ("a" * 64),
            f"{uuid.uuid4()}:tooshort",
            f"{uuid.uuid4()}:" + ("g" * 64),  # 'g' is not hex
            f"{uuid.uuid4()}:" + ("a" * 63),  # one short
        ]
        for bad in bad_inputs:
            # Empty / falsy keys raise IdempotencyKeyMissing;
            # malformed keys raise IdempotencyKeyMalformed.
            # Both inherit from IdempotencyError.
            with pytest.raises(IdempotencyError):
                IdempotencyService.parse_key(bad)

    def test_compose_key_round_trip(self):
        from hub.apps.core.idempotency import IdempotencyService

        tenant_uuid = uuid.uuid4()
        body = b'{"a":1}'
        key = IdempotencyService.compose_key(tenant_uuid, body)
        # Server can validate the body matches the key prefix.
        IdempotencyService.assert_body_matches_key(key, body, tenant_uuid)

    def test_assert_body_matches_key_raises_on_mismatch(self):
        from hub.apps.core.idempotency import (
            IdempotencyKeyBodyMismatch,
            IdempotencyService,
        )

        tenant_uuid = uuid.uuid4()
        key = IdempotencyService.compose_key(tenant_uuid, b'{"a":1}')
        with pytest.raises(IdempotencyKeyBodyMismatch):
            IdempotencyService.assert_body_matches_key(key, b'{"a":2}', tenant_uuid)

    def test_assert_body_matches_key_raises_on_tenant_mismatch(self):
        from hub.apps.core.idempotency import (
            IdempotencyKeyTenantMismatch,
            IdempotencyService,
        )

        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        key = IdempotencyService.compose_key(tenant_a, b'{"a":1}')
        with pytest.raises(IdempotencyKeyTenantMismatch):
            IdempotencyService.assert_body_matches_key(key, b'{"a":1}', tenant_b)

    # --------------------------------------------------------------
    # Phase 250.1.D review-pass — new contract pins
    # --------------------------------------------------------------

    def test_parse_key_rejects_uppercase_uuid_prefix(self):
        """Phase 250.1.D review-pass — non-canonical UUID case must reject.

        ``uuid.UUID()`` accepts any case, but the cache uses the raw
        header bytes — so ``ABCDEF...:hash`` and ``abcdef...:hash``
        would yield TWO separate cache entries for the same logical
        request, defeating idempotency. parse_key MUST enforce the
        canonical lowercase form.
        """
        from hub.apps.core.idempotency import (
            IdempotencyKeyMalformed,
            IdempotencyService,
        )

        body_sha = hashlib.sha256(b"hello").hexdigest()
        # Uppercase UUID — should reject
        upper = "ABCDEF00-1111-2222-3333-444455556666"
        with pytest.raises(IdempotencyKeyMalformed):
            IdempotencyService.parse_key(f"{upper}:{body_sha}")
        # Mixed case — should reject
        mixed = "AbCdEf00-1111-2222-3333-444455556666"
        with pytest.raises(IdempotencyKeyMalformed):
            IdempotencyService.parse_key(f"{mixed}:{body_sha}")
        # Lowercase canonical — should pass
        lower = "abcdef00-1111-2222-3333-444455556666"
        parsed_uuid, _ = IdempotencyService.parse_key(f"{lower}:{body_sha}")
        assert str(parsed_uuid) == lower

    def test_acquire_lock_returns_true_on_first_call_false_on_second(self):
        """Phase 250.1.D review-pass — lock is mutually exclusive.

        Two consecutive calls with the same key — the first acquires
        (returns True), the second fails to acquire (returns False).
        After release, the lock is free again.
        """
        from hub.apps.core.idempotency import IdempotencyService

        key = "lock-test-key-1"
        scope = "test.scope"

        # First call wins the lock
        assert IdempotencyService.acquire_lock(key, scope=scope, ttl_seconds=60) is True
        # Second call sees the lock held — returns False
        assert IdempotencyService.acquire_lock(key, scope=scope, ttl_seconds=60) is False

        # Release frees the slot
        IdempotencyService.release_lock(key, scope=scope)
        # Third call (post-release) wins again
        assert IdempotencyService.acquire_lock(key, scope=scope, ttl_seconds=60) is True

        # Cleanup
        IdempotencyService.release_lock(key, scope=scope)

    def test_scope_isolates_cache_entries(self):
        """Phase 250.1.D review-pass — same key under different scopes
        MUST produce different cache entries (no cross-endpoint replay)."""
        from hub.apps.core.idempotency import (
            CachedResponse,
            IdempotencyService,
        )

        key = "scope-isolation-test"
        resp_a = CachedResponse(status_code=201, data={"who": "A"}, headers={})
        resp_b = CachedResponse(status_code=201, data={"who": "B"}, headers={})

        IdempotencyService.store_response(key, resp_a, scope="endpoint.a", ttl_seconds=60)
        IdempotencyService.store_response(key, resp_b, scope="endpoint.b", ttl_seconds=60)

        got_a = IdempotencyService.get_cached_response(key, scope="endpoint.a")
        got_b = IdempotencyService.get_cached_response(key, scope="endpoint.b")
        assert got_a is not None and got_a.data == {"who": "A"}
        assert got_b is not None and got_b.data == {"who": "B"}
        # No-scope lookup is yet ANOTHER bucket — also isolated.
        got_unscoped = IdempotencyService.get_cached_response(key)
        assert got_unscoped is None

    def test_acquire_lock_degrades_gracefully_on_cache_failure(self):
        """Phase 250.1.D review-pass — cache.add() failure → return True.

        Letting requests through during a Redis outage is the documented
        degraded-mode contract. The alternative (uniform 409) would be
        worse for tenants than the small window of true concurrent
        duplication that requires both Redis-down AND a parallel retry.
        """
        from hub.apps.core.idempotency import IdempotencyService

        with patch(
            "hub.apps.core.idempotency.cache.add",
            side_effect=ConnectionError("redis down"),
        ):
            assert IdempotencyService.acquire_lock("k", scope="s", ttl_seconds=60) is True


class IdempotencyConcurrencyLockTest(TestCase):
    """Phase 250.1.D review-pass — concurrent-request lock at the view layer.

    Without the lock, two parallel POSTs with the same Idempotency-Key
    would both see cache MISS → both run the workflow → side-effects
    duplicated. The view now acquires an atomic in-flight lock via
    ``cache.add()``; the loser of the race gets HTTP 409
    ``IDEMPOTENCY_REQUEST_IN_PROGRESS`` so the client can poll the
    cache instead of duplicating the side-effects.
    """

    def setUp(self):
        reset_shared_circuit_breakers_for_service("compliance-service")
        cache.clear()

    def test_second_request_with_in_flight_key_returns_409(self):
        """While a first request holds the lock, a second request 409s."""
        from hub.apps.core.idempotency import IdempotencyService

        client, tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "concurrent-lock-test",
            "name": "Concurrent Lock Test",
        }
        idem_key = _compose_key(tenant.id, _canonical_bytes(body))

        # Manually pre-acquire the lock to simulate a parallel
        # in-flight request (the actual view uses cache.add() so two
        # real concurrent POSTs would race the same way; pre-acquiring
        # here is the deterministic equivalent for unit testing).
        scope = "assets.data-first.v1"
        assert IdempotencyService.acquire_lock(idem_key, scope=scope, ttl_seconds=60)

        try:
            response = _post_canonical(client, body, idem_key)
        finally:
            IdempotencyService.release_lock(idem_key, scope=scope)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "IDEMPOTENCY_REQUEST_IN_PROGRESS"
        # Retry-After header MUST be present so well-behaved clients
        # back off and let the in-flight winner finish.
        assert response["Retry-After"]

    def test_lock_released_on_workflow_success(self):
        """After a successful workflow, the lock MUST be released.

        Otherwise the next replay-able retry would 409 with
        REQUEST_IN_PROGRESS for the entire 6-min lock TTL, even
        though the response is already cached and would be served
        instantly via cache hit.
        """
        from hub.apps.core.idempotency import IdempotencyService

        client, tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "lock-release-test",
            "name": "Lock Release Test",
        }
        idem_key = _compose_key(tenant.id, _canonical_bytes(body))
        scope = "assets.data-first.v1"

        with _patch_storage(), _patch_compliance_pass(), _patch_dq_pass():
            response = _post_canonical(client, body, idem_key)
        assert response.status_code == status.HTTP_201_CREATED, response.data

        # Lock MUST be free — re-acquiring should succeed immediately.
        assert (
            IdempotencyService.acquire_lock(
                idem_key,
                scope=scope,
                ttl_seconds=60,
            )
            is True
        )
        IdempotencyService.release_lock(idem_key, scope=scope)

    def test_lock_released_on_unhandled_exception(self):
        """Unhandled exceptions in the workflow MUST still release the lock.

        Without the wide ``except Exception`` at the bottom of the
        view's data_first method, a 5xx leak would keep the lock
        held until TTL (~6 min), 409-ing every retry.
        """
        from hub.apps.core.idempotency import IdempotencyService

        client, tenant, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "lock-exception-release-test",
            "name": "Lock Exception Release",
        }
        idem_key = _compose_key(tenant.id, _canonical_bytes(body))
        scope = "assets.data-first.v1"

        # Force the workflow to raise an unhandled exception by
        # patching execute() to raise something the view doesn't catch.
        with (
            _patch_storage(),
            patch(
                "hub.apps.orchestration.workflows.asset_creation.AssetCreationWorkflow.execute",
                side_effect=RuntimeError("boom — unhandled"),
            ),
        ):
            try:
                _post_canonical(client, body, idem_key)
            except Exception:
                # The view's wide except re-raises; our smoke test
                # accepts that — what we're verifying is that the
                # finally / except path released the lock.
                pass

        # Lock MUST be free even though the workflow blew up.
        assert (
            IdempotencyService.acquire_lock(
                idem_key,
                scope=scope,
                ttl_seconds=60,
            )
            is True
        )
        IdempotencyService.release_lock(idem_key, scope=scope)
