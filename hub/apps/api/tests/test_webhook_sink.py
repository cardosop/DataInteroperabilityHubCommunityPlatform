"""
Tests for the E2E webhook sink (Phase 226 G11).

The sink is a small but security-sensitive endpoint:
  - Production must stay 404.
  - Read endpoint must be token-gated.
  - Inbound payloads must be recorded faithfully and capped.
  - Forced-failure subflow must return the requested status.

These tests pin every branch. ``override_settings`` is applied per-method
because pytest-style classes (no ``SimpleTestCase`` parent) reject the
class-level decorator since Django 4+.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():  # type: ignore[no-untyped-def]  # test: edge-case type exercise
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def sink_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def client() -> APIClient:
    return APIClient()


_E2E_SETTINGS = dict(ENVIRONMENT="test", E2E_TEST_SECRET="e2e-secret")


class TestWebhookSinkRecord:
    @override_settings(**_E2E_SETTINGS)
    def test_post_records_payload_and_returns_200(self, client: APIClient, sink_id: str) -> None:
        body = {"event_type": "asset.created", "data": {"asset_id": "abc"}}
        resp = client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        # Read back via GET with token.
        read = client.get(
            f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret",
        )
        assert read.status_code == 200
        data = read.json()
        assert data["sink_id"] == sink_id
        assert data["count"] == 1
        delivery = data["deliveries"][0]
        assert delivery["method"] == "POST"
        assert delivery["body_parsed"] == body
        assert delivery["status_returned"] == 200

    @override_settings(**_E2E_SETTINGS)
    def test_two_posts_record_two_deliveries(self, client: APIClient, sink_id: str) -> None:
        for i in range(2):
            client.post(
                f"/api/v1/test/webhook-sink/{sink_id}/",
                data=json.dumps({"i": i}),
                content_type="application/json",
            )
        read = client.get(f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret")
        assert read.json()["count"] == 2

    @override_settings(**_E2E_SETTINGS)
    def test_authorization_header_is_stripped_from_recorded_headers(
        self, client: APIClient, sink_id: str
    ) -> None:
        # If a misbehaving caller leaks an Authorization header to the sink,
        # the sink MUST NOT echo it back to the test reader.
        client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/",
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer secret-token",
            HTTP_X_E2E_TOKEN="another-secret",
        )
        read = client.get(f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret")
        delivery = read.json()["deliveries"][0]
        # Compare case-insensitively because Django normalises some.
        keys = [k.lower() for k in delivery["headers"]]
        assert "authorization" not in keys
        assert "x-e2e-token" not in keys


class TestWebhookSinkForcedFailure:
    @override_settings(**_E2E_SETTINGS)
    def test_fail_500_returns_500_and_still_records(self, client: APIClient, sink_id: str) -> None:
        body = {"event_type": "asset.retire"}
        resp = client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/?fail=500",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 500
        read = client.get(f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret").json()
        assert read["count"] == 1
        assert read["deliveries"][0]["status_returned"] == 500

    @override_settings(**_E2E_SETTINGS)
    def test_fail_502_returns_502(self, client: APIClient, sink_id: str) -> None:
        resp = client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/?fail=502",
            data="{}",
            content_type="application/json",
        )
        assert resp.status_code == 502

    @override_settings(**_E2E_SETTINGS)
    def test_fail_with_disallowed_status_falls_back_to_200(
        self, client: APIClient, sink_id: str
    ) -> None:
        resp = client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/?fail=418",
            data="{}",
            content_type="application/json",
        )
        # 418 is not in the allow-list — sink ignores and records normally.
        assert resp.status_code == 200


class TestWebhookSinkRead:
    @override_settings(**_E2E_SETTINGS)
    def test_get_without_token_returns_404(self, client: APIClient, sink_id: str) -> None:
        resp = client.get(f"/api/v1/test/webhook-sink/{sink_id}/")
        assert resp.status_code == 404

    @override_settings(**_E2E_SETTINGS)
    def test_get_with_wrong_token_returns_404(self, client: APIClient, sink_id: str) -> None:
        resp = client.get(f"/api/v1/test/webhook-sink/{sink_id}/?token=wrong")
        assert resp.status_code == 404

    @override_settings(**_E2E_SETTINGS)
    def test_get_with_correct_token_returns_200(self, client: APIClient, sink_id: str) -> None:
        resp = client.get(f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @override_settings(**_E2E_SETTINGS)
    def test_get_with_header_token_returns_200(self, client: APIClient, sink_id: str) -> None:
        """Verify the X-E2E-Token header auth path works (not just ?token= query param)."""
        resp = client.get(
            f"/api/v1/test/webhook-sink/{sink_id}/",
            HTTP_X_E2E_TOKEN="e2e-secret",
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @override_settings(**_E2E_SETTINGS)
    def test_delete_clears_deliveries(self, client: APIClient, sink_id: str) -> None:
        client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/",
            data="{}",
            content_type="application/json",
        )
        client.delete(f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret")
        read = client.get(f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret")
        assert read.json()["count"] == 0


class TestWebhookSinkProductionLockout:
    """Sink must 404 in production AND when E2E_TEST_SECRET is unset."""

    @override_settings(ENVIRONMENT="production", DEBUG=False, E2E_TEST_SECRET="")
    def test_production_post_returns_404(self, client: APIClient, sink_id: str) -> None:
        resp = client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/",
            data="{}",
            content_type="application/json",
        )
        assert resp.status_code == 404

    @override_settings(ENVIRONMENT="production", DEBUG=False, E2E_TEST_SECRET="")
    def test_production_get_returns_404(self, client: APIClient, sink_id: str) -> None:
        resp = client.get(f"/api/v1/test/webhook-sink/{sink_id}/")
        assert resp.status_code == 404

    @override_settings(ENVIRONMENT="staging", E2E_TEST_SECRET="")
    def test_staging_without_secret_post_records_but_get_404s(
        self, client: APIClient, sink_id: str
    ) -> None:
        # Staging is permitted by environment; the read path still requires
        # E2E_TEST_SECRET. With it unset, GET MUST 404 even though POST
        # works (no leak of recorded payloads).
        client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/",
            data="{}",
            content_type="application/json",
        )
        resp = client.get(f"/api/v1/test/webhook-sink/{sink_id}/")
        assert resp.status_code == 404


class TestWebhookSinkValidation:
    @override_settings(**_E2E_SETTINGS)
    def test_invalid_sink_id_404s(self, client: APIClient) -> None:
        # Path traversal attempt
        resp = client.post(
            "/api/v1/test/webhook-sink/..%2Fadmin/",
            data="{}",
            content_type="application/json",
        )
        # Either Django URL routing rejects the path (404) or the validator
        # does. Both are acceptable outcomes — what matters is no 200.
        assert resp.status_code in (404, 400)

    @override_settings(**_E2E_SETTINGS)
    def test_oversized_body_truncated_with_marker(self, client: APIClient, sink_id: str) -> None:
        big_body = {"data": "x" * 20_000}
        client.post(
            f"/api/v1/test/webhook-sink/{sink_id}/",
            data=json.dumps(big_body),
            content_type="application/json",
        )
        read = client.get(f"/api/v1/test/webhook-sink/{sink_id}/?token=e2e-secret").json()
        assert read["deliveries"][0]["truncated"] is True
