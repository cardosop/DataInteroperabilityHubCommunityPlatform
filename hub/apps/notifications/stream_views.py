"""
Phase 228.F3.16 — Server-Sent Events stream for real-time
notifications.

Endpoint: ``GET /api/v1/notifications/stream/``

The endpoint upgrades the HTTP connection to SSE
(``Content-Type: text/event-stream``) and streams events from the
Redis pub/sub channel the existing ``publish_event`` helper writes
to (Phase 223.1.10 — ``notification.created``).

Behaviour:

* On connect, the server subscribes to the user's pub/sub channel
  with a 30-second poll loop (so a stalled client gets a periodic
  comment-ping that keeps proxies from idling out the connection).
* Every ``notification.created`` event matching ``user_id`` is
  forwarded as an ``event: notification.created`` message.
* On disconnect (client closes, server timeout, or worker shutdown),
  the loop exits cleanly and the connection is released.

Fallback path: when Redis is unavailable, the endpoint returns
HTTP 200 with a single ``event: ready`` message and exits, so the
client's ``EventSource`` will reconnect — the frontend hook
(:func:`useNotificationStream`) detects the early-close and falls
back to the existing polling cadence (30s).

Auth: ``IsAuthenticated``.  No tenant-scope filter here — the
client receives events for the current ``request.user`` only;
backend events are routed by ``user_id``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING

import redis
from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, renderers
from rest_framework.views import APIView

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class EventStreamRenderer(renderers.BaseRenderer):
    """
    W5.3 (R2-F3) — content-negotiation renderer for the SSE endpoint.

    DRF 3.16 negotiates the Accept header BEFORE the handler runs; the
    default renderer set (JSON/Browsable) rejects ``Accept:
    text/event-stream`` — the header both the browser's native
    EventSource and fetch-based SSE readers send — with 406
    NotAcceptable. Production reverse proxies do not rewrite Accept
    (only the dev proxy does), so every direct SSE request 406'd.

    The renderer is NEVER invoked: the view returns a plain
    ``StreamingHttpResponse`` directly; this class exists solely so
    content negotiation accepts the media type.
    """

    media_type = "text/event-stream"
    format = "stream"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):  # noqa: ARG002 — DRF render signature
        # The stream itself never reaches DRF rendering (the view returns
        # a plain StreamingHttpResponse). DRF DOES route error envelopes
        # here (401/429/5xx produced by the exception handler), and the
        # client's error normalization reads them as JSON — render the
        # envelope as JSON so an SSE-Accept error response stays
        # machine-readable instead of crashing the renderer.
        return json.dumps(data).encode("utf-8")


# Periodic comment-ping interval — keeps proxies (nginx, ALB) from
# idling out the connection.  SSE comment lines start with ":" and
# the browser ignores them.
_PING_INTERVAL_SECONDS = 30
# Hard ceiling per connection so a hung worker can't accumulate
# zombie SSE generators.  Clients reconnect via EventSource's
# built-in retry.
_MAX_CONNECTION_SECONDS = 60 * 30


class NotificationStreamView(APIView):
    """SSE endpoint."""

    permission_classes = [permissions.IsAuthenticated]
    # W5.3 (R2-F3) — accept the SSE media type (see EventStreamRenderer)
    # AND application/json (reverse proxies/dev tooling may normalize the
    # Accept header; error envelopes render as JSON through JSONRenderer,
    # which the client's error normalization reads).
    renderer_classes = [EventStreamRenderer, renderers.JSONRenderer]  # noqa: RUF012 — DRF class attr idiom

    @extend_schema(
        summary="SSE notification stream",
        description=(
            "Streams notification events as server-sent events "
            "(``text/event-stream``). Non-SSE Accepts receive a JSON "
            "error envelope."
        ),
        responses={
            # NOTE: only the media-typed 200 key — mixing it with a plain
            # 200 in the same operation makes drf-spectacular merge the two
            # entries and crash on the missing 'content' key.
            (200, "text/event-stream"): OpenApiResponse(
                description="Server-sent event stream of notification events",
                response=OpenApiTypes.STR,
            ),
            401: OpenApiResponse(description="Unauthorized"),
        },
        tags=["Notifications"],
    )
    def get(self, request, *_args, **_kwargs):
        user_id = str(request.user.id)
        response = StreamingHttpResponse(
            _event_stream(user_id),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # Disable nginx buffering.
        return response


async def _event_stream(user_id: str) -> AsyncIterator[bytes]:
    """Yield SSE-framed messages until the connection ends.

    W5.3 (R2-F3) — an ASYNC generator is mandatory: Django 6's ASGI
    handler materializes SYNC streaming iterators wholesale
    (``sync_to_async(list)(stream)``) before sending the first byte —
    an infinite SSE stream therefore delivered zero bytes forever.
    Async iterators stream incrementally.
    """
    # Initial "ready" event — the client uses this to confirm the
    # stream is open before flipping its mode away from polling.
    yield b"event: ready\ndata: {}\n\n"

    pubsub = _try_get_pubsub(user_id)
    if pubsub is None:
        # Redis not available — fall back: client will reconnect via
        # EventSource retry, and the polling path keeps the inbox
        # fresh in the meantime.
        return

    deadline = time.time() + _MAX_CONNECTION_SECONDS
    last_ping = time.time()
    try:
        while time.time() < deadline:
            # Non-blocking poll: get_message returns None when no
            # event is available, so we control the loop cadence. The
            # blocking read runs off the event loop.
            message = await asyncio.to_thread(pubsub.get_message, 1.0)
            now = time.time()
            if message and message.get("type") == "message":
                payload = _decode_payload(message.get("data"))
                if payload and _is_for_user(payload, user_id):
                    yield _format_event(
                        event_type=payload.get("event_type", "notification.created"),
                        data=payload,
                    )
                    last_ping = now
                    continue
            # Periodic ping — comment line, not a real event.
            if now - last_ping >= _PING_INTERVAL_SECONDS:
                yield b": ping\n\n"
                last_ping = now
    except Exception as exc:
        logger.warning("notification_stream_error user_id=%s err=%s", user_id, exc)
    finally:
        with contextlib.suppress(Exception):
            pubsub.close()


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------


def _try_get_pubsub(user_id: str):
    """Subscribe to the user's notification channel.  Returns the
    pubsub object on success, ``None`` when Redis is unavailable."""
    try:
        from hub.apps.contracts.signals import _get_redis_client

        client = _get_redis_client()
        if client is None:
            return None
        pubsub = client.pubsub()
        # The publisher writes to a tenant- + user-scoped channel
        # (see hub.apps.core.events.publisher).  We subscribe to the
        # user-scoped pattern.
        pubsub.subscribe(f"notification:user:{user_id}")
        return pubsub
    except (ImportError, redis.RedisError) as exc:
        logger.debug("notification_stream_pubsub_unavailable err=%s", exc)
        return None


def _decode_payload(raw) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _is_for_user(payload: dict, user_id: str) -> bool:
    return str(payload.get("user_id")) == str(user_id)


def _format_event(*, event_type: str, data: dict) -> bytes:
    body = json.dumps(data, separators=(",", ":"))
    return f"event: {event_type}\ndata: {body}\n\n".encode()
