"""
Phase 228 F4 (228.F4.22) — inbound endpoint tests.

Pins ``POST /api/v1/lineage/openlineage/events/`` (REQ-LIN-F4-002):

* Capability-flag gate — 404 when ``lineage.openlineage_export``
  is OFF (228.F4.8).
* Bearer-token authentication against ``OpenLineageIngestApiKey``.
* HMAC signature verification (``X-Meshant-Signature``).
* JSON-Schema validation against the OpenLineage 2.0.0 subset —
  malformed payload returns 400.
* Revoked / expired keys are rejected.
* Successful POST returns 202 + processes the event.

Plus the admin key-management endpoints (REQ-LIN-F4-003):

* ``GET /api/v1/lineage/openlineage/keys/`` lists keys for the
  caller's tenant.
* ``POST .../keys/`` creates a new key — returns the plaintext ONCE.
* ``DELETE .../keys/<id>/`` revokes a key.
* All key endpoints are admin-only (TENANT_ADMIN).

No internal mocks; only the network boundary (the underlying
adapter's HTTP call would be a separate adapter test).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import timedelta

import pytest
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient


HMAC_KEY = "test-hmac-signing-key-32-bytes-long-XYZ"
INBOUND_URL = "/api/v1/lineage/openlineage/events/"
KEYS_URL = "/api/v1/lineage/openlineage/keys/"


def _create_tenant():
    """Tenant with an ACTIVE BASE-category subscription so the billing
    middleware doesn't reject POST / DELETE at the gate.

    Pre-fix the inbound tests failed with ``subscription_inactive``
    because the middleware queries
    ``Subscription.objects.filter(tenant=t, category='BASE')`` and
    a fresh test tenant has none. The billing/tests/plan_fixtures
    helper is the canonical reuse-safe plan factory the rest of the
    suite leans on."""
    from django.utils import timezone
    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.billing.tests.plan_fixtures import (
        create_unique_tenant, get_pro_plan,
    )

    plan = get_pro_plan()
    tenant = create_unique_tenant(
        name_prefix="OL Co", slug_prefix="ol-co", plan=plan,
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        category="BASE",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    return tenant


def _create_admin(tenant):
    from django.contrib.auth import get_user_model
    from hub.apps.users.models import Role, UserRole
    User = get_user_model()
    u = User.objects.create(email=f"admin-{uuid.uuid4().hex[:6]}@x", tenant=tenant)
    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=u, tenant=tenant, role=role)
    return u


def _create_active_key(tenant):
    from hub.apps.integrations.openlineage.models import (
        OpenLineageIngestApiKey,
        generate_ingest_key_plaintext,
        hash_ingest_key,
    )
    plaintext = generate_ingest_key_plaintext()
    row = OpenLineageIngestApiKey.objects.create(
        tenant=tenant,
        label="test-key",
        key_prefix=plaintext.removeprefix("msh_ol_")[:8],
        key_hash=hash_ingest_key(plaintext),
    )
    return plaintext, row


def _build_valid_event(*, source_id=None, target_id=None) -> dict:
    return {
        "eventType": "COMPLETE",
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "https://meshant.com/",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "etl", "name": "orders_etl"},
        "inputs": [{"namespace": "meshant.contracts", "name": source_id or str(uuid.uuid4())}],
        "outputs": [{"namespace": "meshant.contracts", "name": target_id or str(uuid.uuid4())}],
    }


def _hmac_sign(body: bytes, key: str = HMAC_KEY) -> str:
    return "sha256=" + hmac.new(
        key.encode("utf-8"), body, hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Inbound — capability flag gate (F4.8)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestCapabilityGate(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_returns_404_when_capability_off(self):
        # Test env defaults flags to True. Override OFF and verify 404.
        with override_settings(
            CAPABILITY_FLAGS={"lineage.openlineage_export": False},
            OPENLINEAGE_HMAC_SIGNING_KEY=HMAC_KEY,
        ):
            client = APIClient()
            event = _build_valid_event()
            body = json.dumps(event).encode("utf-8")
            resp = client.post(
                INBOUND_URL,
                data=body,
                content_type="application/json",
                HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
                HTTP_X_MESHANT_OPENLINEAGE_KEY="msh_ol_anything",
            )
        assert resp.status_code == 404, (
            f"capability-flag-OFF must return 404, not 401/403/500; "
            f"got {resp.status_code} body={resp.content!r}"
        )


# ---------------------------------------------------------------------------
# Inbound — auth + HMAC
# ---------------------------------------------------------------------------


@override_settings(OPENLINEAGE_HMAC_SIGNING_KEY=HMAC_KEY)
@pytest.mark.django_db(transaction=True)
class TestInboundAuthAndHmac(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_missing_bearer_returns_401(self):
        client = APIClient()
        event = _build_valid_event()
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
        )
        assert resp.status_code == 401

    def test_invalid_bearer_returns_401(self):
        client = APIClient()
        event = _build_valid_event()
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY="msh_ol_does-not-exist",
        )
        assert resp.status_code == 401

    def test_revoked_key_returns_401(self):
        from django.utils import timezone
        tenant = _create_tenant()
        plaintext, row = _create_active_key(tenant)
        row.revoked_at = timezone.now()
        row.save()

        client = APIClient()
        event = _build_valid_event()
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 401

    def test_expired_key_returns_401(self):
        from django.utils import timezone
        tenant = _create_tenant()
        plaintext, row = _create_active_key(tenant)
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()

        client = APIClient()
        event = _build_valid_event()
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 401

    def test_invalid_hmac_returns_401(self):
        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)

        client = APIClient()
        event = _build_valid_event()
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE="sha256=wrong-signature",
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 401

    def test_valid_request_returns_202(self):
        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)

        client = APIClient()
        event = _build_valid_event()
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 202, (
            f"valid request expected 202; got {resp.status_code} "
            f"body={resp.content!r}"
        )

    def test_malformed_event_returns_400(self):
        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)

        client = APIClient()
        bad_event = {"eventType": "BOGUS"}  # missing required keys
        body = json.dumps(bad_event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Key admin endpoints (F4.7.2)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestKeyAdminEndpoints(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_list_keys_admin_only(self):
        tenant = _create_tenant()
        admin = _create_admin(tenant)
        _, _ = _create_active_key(tenant)

        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.get(KEYS_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert len(data["keys"]) >= 1
        # No plaintext / no hash leaked.
        for k in data["keys"]:
            assert "key_hash" not in k
            assert "plaintext" not in k

    def test_list_keys_unauthenticated_403(self):
        client = APIClient()
        resp = client.get(KEYS_URL)
        assert resp.status_code in (401, 403)

    def test_create_key_returns_plaintext_once(self):
        tenant = _create_tenant()
        admin = _create_admin(tenant)

        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.post(
            KEYS_URL, data={"label": "marquez-prod"}, format="json",
        )
        assert resp.status_code == 201, resp.content
        data = resp.json()
        # Plaintext returned ONCE on creation.
        assert "plaintext" in data
        assert data["plaintext"].startswith("msh_ol_")
        assert "id" in data
        # Subsequent list does NOT return the plaintext.
        list_resp = client.get(KEYS_URL).json()
        for k in list_resp["keys"]:
            assert "plaintext" not in k

    def test_revoke_key_returns_204(self):
        from hub.apps.integrations.openlineage.models import (
            OpenLineageIngestApiKey,
        )

        tenant = _create_tenant()
        admin = _create_admin(tenant)
        _, row = _create_active_key(tenant)

        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.delete(f"{KEYS_URL}{row.id}/")
        assert resp.status_code == 204
        row.refresh_from_db()
        assert row.revoked_at is not None
