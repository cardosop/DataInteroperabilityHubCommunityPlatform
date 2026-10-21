"""
W5.3 (oss-release-remediation R2-F3) — notification SSE stream pins.

The stream endpoint must accept the browser's native SSE Accept header:
both the browser's EventSource and a fetch-based SSE reader send
``Accept: text/event-stream``. DRF 3.16 negotiates content BEFORE the
handler, and the default renderer set (JSON/Browsable) rejects that
Accept header with 406 NotAcceptable — so every direct SSE request
406'd (production reverse proxies do not rewrite Accept; only the dev
proxy's Accept-override masked the bug in E2E). The fix: an
``EventStreamRenderer`` whose media type is ``text/event-stream``.
"""

import uuid

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, Tenant

User = get_user_model()


def _first_stream_chunk(response):
    """Consume the first streamed chunk (async — the W5.3 contract)."""

    async def take_first():
        async for chunk in response.streaming_content:
            return chunk
        return None

    return async_to_sync(take_first)()


@pytest.fixture
def api_client():
    return APIClient()


def _make_user():
    # A minimal user for the IsAuthenticated gate — the stream routes
    # events by user_id, so any real user works.
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"T {uid}",
        slug=f"t-{uid}",
        kyc_status=KYCStatus.VERIFIED,
    )
    return User.objects.create_user(
        email=f"sse-pin-{uid}@example.com",
        password="TestPass123",
        tenant=tenant,
    )


@pytest.mark.django_db
def test_stream_accepts_sse_accept_header(api_client):
    """GET with Accept: text/event-stream must open the stream (200),
    not 406 (pre-fix DRF content negotiation rejected the header)."""
    user = _make_user()
    api_client.force_authenticate(user=user)

    response = api_client.get(
        "/api/v1/notifications/stream/",
        HTTP_ACCEPT="text/event-stream",
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    # W5.3 — the response MUST be async-streaming: Django 6's ASGI
    # handler materializes sync iterators wholesale (sync_to_async(list))
    # and an infinite SSE stream delivered zero bytes forever.
    assert response.is_async is True
    # The backend's first frame (stream_views.py) is the ready event.
    first_chunk = _first_stream_chunk(response)
    assert b"event: ready" in first_chunk


@pytest.mark.django_db
def test_stream_accepts_browser_default_accept(api_client):
    """A browser with the standard wildcard Accept list must also open
    the stream (regression: the dev proxy normalizes to application/json,
    but real clients may send */*)."""
    user = _make_user()
    api_client.force_authenticate(user=user)

    response = api_client.get(
        "/api/v1/notifications/stream/",
        HTTP_ACCEPT="*/*",
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")


@pytest.mark.django_db
def test_stream_requires_authentication(api_client):
    """The stream stays behind IsAuthenticated (regression)."""
    response = api_client.get(
        "/api/v1/notifications/stream/",
        HTTP_ACCEPT="text/event-stream",
    )
    assert response.status_code in (401, 403)
