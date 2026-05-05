"""
Phase 250.1.A — fail-closed-at-intake API behaviour for ``POST /assets/data-first/``.

Pins the new contract:

* 250.1.A.9 — when the compliance-service circuit breaker is OPEN
  AND the tenant has ``allow_intake_on_compliance_degraded=False``,
  the endpoint refuses with 503 + ``Retry-After`` header BEFORE
  starting the workflow. Tenants that opted in proceed (the
  workflow then marks the gate WARN per the flag).
* 250.1.A.10 — per-user 60/min and per-tenant 600/min rate limits.
  We can't easily exhaust the bucket in a unit test, but we can
  prove the throttle classes are wired into the endpoint.
* 250.1.A.11 — request body over 100 MB returns 413 BEFORE auth
  parsing.
* 250.1.A.3 — workflow ``FailClosedRejection`` maps to 422 +
  ``ASSET_FAIL_CLOSED_REJECTED`` with gate context in details.

External boundaries (compliance / DQ HTTP, S3) are mocked at their
boundaries so the test focuses on the API contract, not the
microservice behaviour.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.assets.throttles import (
    AssetDataFirstTenantThrottle,
    AssetDataFirstUserThrottle,
)
from hub.apps.core.resilience.circuit_breaker import CircuitBreakerState
from hub.apps.core.resilience.service_breakers import (
    get_shared_circuit_breaker,
    reset_shared_circuit_breakers_for_service,
)
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_authenticated_client(allow_degraded: bool = False):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
        allow_intake_on_compliance_degraded=allow_degraded,
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
    return client, tenant, user, file_obj


class DataFirstBodyCapTest(TestCase):
    """Phase 250.1.A.11 — 100 MB body cap returns 413.

    Also pins the defence-in-depth contract that chunked uploads
    (no Content-Length) are rejected with 411 Length Required so a
    malicious client cannot bypass the cap by streaming the body.
    """

    def test_oversized_body_returns_413(self):
        client, _tenant, _user, file_obj = _seed_authenticated_client()
        oversize = 100 * 1024 * 1024 + 1
        response = client.post(
            "/api/v1/assets/data-first/",
            {"file_id": str(file_obj.id), "key": "a", "name": "A"},
            format="json",
            CONTENT_LENGTH=str(oversize),
        )
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert response.data["code"] == "PAYLOAD_TOO_LARGE"
        assert response.data["details"]["max_bytes"] == 100 * 1024 * 1024

    def test_chunked_upload_returns_411_length_required(self):
        """A request without Content-Length (e.g., chunked) MUST be 411.

        Without this guard, a malicious client could stream a 1 GB body
        with no Content-Length and we'd have to call ``len(request.body)``
        to know the size — buffering the whole payload first, the very
        DoS the cap was meant to prevent.
        """
        client, _tenant, _user, file_obj = _seed_authenticated_client()
        response = client.post(
            "/api/v1/assets/data-first/",
            {"file_id": str(file_obj.id), "key": "k", "name": "N"},
            format="json",
            HTTP_TRANSFER_ENCODING="chunked",
            CONTENT_LENGTH="",  # explicitly clear it
        )
        assert response.status_code == status.HTTP_411_LENGTH_REQUIRED
        assert response.data["code"] == "LENGTH_REQUIRED"

    def test_invalid_content_length_returns_400(self):
        client, _tenant, _user, file_obj = _seed_authenticated_client()
        response = client.post(
            "/api/v1/assets/data-first/",
            {"file_id": str(file_obj.id), "key": "k", "name": "N"},
            format="json",
            CONTENT_LENGTH="not-a-number",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "BAD_REQUEST"

    def test_under_cap_does_not_return_413(self):
        """A normal request size doesn't trip the body cap.

        The compliance circuit-breaker is also forced CLOSED so the
        endpoint doesn't 503 out before reaching the workflow path.
        """
        from hub.apps.testing.idempotency_helpers import post_data_first

        reset_shared_circuit_breakers_for_service("compliance-service")
        client, tenant, _user, file_obj = _seed_authenticated_client()
        # The downstream workflow will fail (no real services) but
        # the response code MUST NOT be 413 — that's the assertion.
        response = post_data_first(
            client,
            "/api/v1/assets/data-first/",
            {"file_id": str(file_obj.id), "key": "ok-key", "name": "OK"},
            tenant=tenant,
        )
        assert response.status_code != status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class DataFirstThrottleWiringTest(TestCase):
    """Phase 250.1.A.10 — verify both throttle classes are wired."""

    def test_data_first_action_has_both_throttles(self):
        from hub.apps.assets.views import AssetViewSet

        view = AssetViewSet()
        view.action = "data_first"
        throttles = view.get_throttles()
        assert any(isinstance(t, AssetDataFirstUserThrottle) for t in throttles)
        assert any(isinstance(t, AssetDataFirstTenantThrottle) for t in throttles)


class DataFirstDegradedModeTest(TestCase):
    """Phase 250.1.A.9 — compliance breaker OPEN gates intake."""

    def setUp(self):
        # Reset before AND after each test so we don't leak state.
        reset_shared_circuit_breakers_for_service("compliance-service")

    def tearDown(self):
        reset_shared_circuit_breakers_for_service("compliance-service")

    def test_circuit_open_no_tenant_optin_returns_503_with_retry_after(self):
        from hub.apps.testing.idempotency_helpers import post_data_first

        client, tenant, _user, file_obj = _seed_authenticated_client(
            allow_degraded=False
        )
        breaker = get_shared_circuit_breaker("compliance-service")
        breaker._set_state(CircuitBreakerState.OPEN)

        response = post_data_first(
            client,
            "/api/v1/assets/data-first/",
            {
                "file_id": str(file_obj.id),
                "key": "k",
                "name": "N",
            },
            tenant=tenant,
        )
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["code"] == "COMPLIANCE_SERVICE_UNAVAILABLE"
        # Retry-After header MUST be present per HTTP semantics so a
        # well-behaved client backs off rather than retrying tightly.
        assert response["Retry-After"], "Retry-After header missing"

    def test_circuit_open_with_tenant_optin_does_not_short_circuit_to_503(self):
        """When the tenant opted in, the endpoint hands off to the workflow.

        The workflow itself may still fail (no real services in the
        unit test) but the 503 short-circuit MUST NOT trip.
        """
        from hub.apps.testing.idempotency_helpers import post_data_first

        client, tenant, _user, file_obj = _seed_authenticated_client(
            allow_degraded=True
        )
        breaker = get_shared_circuit_breaker("compliance-service")
        breaker._set_state(CircuitBreakerState.OPEN)

        response = post_data_first(
            client,
            "/api/v1/assets/data-first/",
            {
                "file_id": str(file_obj.id),
                "key": "k2",
                "name": "N2",
            },
            tenant=tenant,
        )
        # Must NOT be the upstream 503 short-circuit. Any other
        # response (workflow failure, success, 422 fail-closed) is
        # acceptable here — the assertion is about the code path,
        # not the workflow outcome.
        assert response.status_code != status.HTTP_503_SERVICE_UNAVAILABLE or (
            response.data.get("code") != "COMPLIANCE_SERVICE_UNAVAILABLE"
        )


class DataFirstFailClosedGateTest(TestCase):
    """Phase 250.1.A.3 — gate FAIL maps to 422 + audit + no Asset row.

    These end-to-end tests exercise the workflow with mocked compliance
    + DQ microservice clients so we can force the desired gate
    outcome and assert on the wire response.
    """

    def setUp(self):
        reset_shared_circuit_breakers_for_service("compliance-service")
        reset_shared_circuit_breakers_for_service("dq-service")

    def tearDown(self):
        reset_shared_circuit_breakers_for_service("compliance-service")
        reset_shared_circuit_breakers_for_service("dq-service")

    def _patch_storage(self):
        return patch(
            "hub.apps.files.storage.S3StorageClient.get_file_content",
            return_value=b"a,b\n1,2\n",
        )

    def test_compliance_fail_returns_422_and_no_asset_persisted(self):
        client, tenant, _user, file_obj = _seed_authenticated_client()
        with self._patch_storage(), patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
            return_value={
                "overall_status": "FAIL",
                "risk_level": "HIGH",
                "allowed_to_store": False,
                "metadata": {},
            },
        ), patch(
            "hub.apps.dq.service_client.DQServiceClient.run_dq",
            return_value={
                "overall_status": "PASS",
                "quality_score": 100,
                "metadata": {},
            },
        ):
            from hub.apps.testing.idempotency_helpers import post_data_first
            response = post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "fail-key",
                    "name": "Fail Asset",
                },
                tenant=tenant,
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            f"got {response.status_code}: {response.data}"
        )
        assert response.data["code"] == "ASSET_FAIL_CLOSED_REJECTED"

        # Critical fail-closed contract: no Asset row created.
        assert Asset.objects.filter(tenant=tenant, key="fail-key").count() == 0

    def test_dq_fail_returns_422_and_no_asset_persisted(self):
        from hub.apps.testing.idempotency_helpers import post_data_first

        client, tenant, _user, file_obj = _seed_authenticated_client()
        with self._patch_storage(), patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
            return_value={
                "overall_status": "PASS",
                "allowed_to_store": True,
                "metadata": {},
            },
        ), patch(
            "hub.apps.dq.service_client.DQServiceClient.run_dq",
            return_value={
                "overall_status": "FAIL",
                "quality_score": 12.0,
                "metadata": {},
            },
        ):
            response = post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "dq-fail-key",
                    "name": "DQ Fail Asset",
                },
                tenant=tenant,
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.data["code"] == "ASSET_FAIL_CLOSED_REJECTED"
        assert Asset.objects.filter(tenant=tenant, key="dq-fail-key").count() == 0
