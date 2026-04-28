"""
E2E test-only webhook sink (Phase 226 G11).

A scratch HTTP endpoint that accepts inbound webhook POSTs and records
them so an E2E test can later assert "the platform actually delivered
this event to the registered URL". Resolves Open Question §8: rather
than depending on a third-party (httpbin / webhook.site / requestbin),
the sink lives inside the same backend, owned by the same SLO, and
costs zero outbound network.

Architecture
------------

Per-test sink ids
  Each spec generates a fresh UUID4 sink id. Webhooks register with
  ``target_url = {API_BASE}/api/v1/test/webhook-sink/<sink_id>/``.
  Inbound POSTs to that path are recorded in the cache backend
  (Redis-backed in production) under key
  ``webhook-sink:<sink_id>:deliveries``.

Read path (gated)
  ``GET /api/v1/test/webhook-sink/<sink_id>/?token=<E2E_TEST_SECRET>``
  returns the recorded list. Gating mirrors the rest of the
  ``/api/v1/test/`` family — when ``E2E_TEST_SECRET`` is unset the
  endpoint 404s, so production is closed by default.

Receive path (open)
  POSTs are accepted without authentication because the platform
  invokes the sink the same way any external receiver would (no
  bearer token, no E2E header). The sink id itself is the secret
  — it's a fresh UUID4 known only to the test. Random brute-force
  by an attacker is computationally infeasible.

Forced-failure subflow
  Adding ``?fail=500`` (or 503) to the sink URL makes the sink
  return that status. This lets E2E specs exercise the retry +
  DLQ path of the WebhookDeliveryService without any real flaky
  network.

Storage limits
  - Max 100 recorded deliveries per sink (older ones evicted).
  - 1-hour TTL on the cache entry.
  - 10 KiB cap on stored body per delivery (truncated with marker).
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny

from hub.apps.api.e2e_gating import is_e2e_environment, verify_e2e_token
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Cache parameters. Tuned for E2E specs that may run for a few minutes
# end-to-end with parallel workers. 1-hour TTL is generous; the sink id
# is random per test so collisions are not a concern.
SINK_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
SINK_MAX_DELIVERIES = 100
SINK_BODY_TRUNCATE_BYTES = 10 * 1024  # 10 KiB

# Allowed forced-failure status codes — restricted set so a misconfigured
# spec can't make the sink return arbitrary 4xx and confuse the diagnostic.
ALLOWED_FAIL_STATUSES = frozenset({500, 502, 503, 504})


def _cache_key(sink_id: str) -> str:
    return f"webhook-sink:{sink_id}:deliveries"


def _validate_sink_id(sink_id: str) -> None:
    """Reject non-UUID sink ids (defence against path traversal / cache key DoS)."""
    if not sink_id or len(sink_id) > 64:
        raise NotFound("sink not found")
    # Restrict to hex + hyphen — UUID4 shape.
    for ch in sink_id:
        if not (ch.isalnum() or ch == "-"):
            raise NotFound("sink not found")


def _verify_read_token(request: Any) -> bool:
    """Webhook-sink-specific token gate: header OR ``?token=`` query parameter.

    Delegates to the shared ``verify_e2e_token`` for the header path, then
    falls back to ``?token=`` so a curl-style debugging session can read the
    sink without crafting a header (the GET path is operator-friendly by
    design). The query-param branch uses ``hmac.compare_digest`` itself to
    keep the timing-safe comparison everywhere.
    """
    import hmac

    # Header path — same posture as every other test-only endpoint.
    if verify_e2e_token(request):
        return True
    # Webhook-sink-only fallback: ?token= query parameter.
    secret = getattr(settings, "E2E_TEST_SECRET", "") or ""
    if not secret:
        return False
    provided = request.query_params.get("token") if hasattr(request, "query_params") else None
    if not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), secret.encode("utf-8"))


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST", "GET", "DELETE"])
@authentication_classes([])  # The sink mimics an external webhook receiver:
                              # do NOT try to authenticate the inbound token,
                              # since real outbound webhook deliveries don't
                              # carry a hub Bearer credential. The read path
                              # is gated by ``?token=`` against E2E_TEST_SECRET.
@permission_classes([AllowAny])
def webhook_sink(request, sink_id: str):
    """E2E webhook sink — record / read / clear inbound deliveries.

    POST: accept any inbound payload, store it, return 200 (or the forced-
          failure status when ``?fail=500|502|503|504`` is set).
    GET:  return the recorded list. Token-gated.
    DELETE: clear the recorded list. Token-gated.

    Path: ``/api/v1/test/webhook-sink/<sink_id>/``
    """
    # Production lockout — endpoint 404s when the env or secret is unconfigured.
    if not is_e2e_environment():
        raise NotFound("sink not found")

    _validate_sink_id(sink_id)
    cache_key = _cache_key(sink_id)

    if request.method == "POST":
        # Optional forced-failure mode for retry / DLQ E2E.
        fail_raw = request.query_params.get("fail")
        if fail_raw:
            try:
                fail_status = int(fail_raw)
            except (TypeError, ValueError):
                fail_status = 0
            if fail_status in ALLOWED_FAIL_STATUSES:
                # Still record the attempt so the test can verify the
                # platform attempted delivery before giving up.
                _record(cache_key, request, status_returned=fail_status)
                return Response(
                    {"error": "forced failure for E2E retry/DLQ test"},
                    status=fail_status,
                )

        _record(cache_key, request, status_returned=200)
        return Response({"received": True})

    if request.method == "GET":
        if not _verify_read_token(request):
            raise NotFound("sink not found")
        deliveries = cache.get(cache_key) or []
        return Response({"sink_id": sink_id, "count": len(deliveries), "deliveries": deliveries})

    # DELETE
    if not _verify_read_token(request):
        raise NotFound("sink not found")
    cache.delete(cache_key)
    return Response({"sink_id": sink_id, "cleared": True})


def _record(cache_key: str, request: Any, *, status_returned: int) -> None:
    """Append the inbound delivery to the cache list.

    Body capped at SINK_BODY_TRUNCATE_BYTES; bigger payloads marked
    ``truncated: true``. The headers are filtered to drop the bearer
    token and any other Authorization-shaped value (defence in depth —
    real outbound webhooks never carry user bearer tokens, but a
    misconfiguration must not leak credentials into the sink log).
    """
    from django.utils import timezone

    raw_body: bytes
    try:
        raw_body = request.body if hasattr(request, "body") else b""
    except Exception:
        raw_body = b""
    truncated = len(raw_body) > SINK_BODY_TRUNCATE_BYTES
    body_bytes = raw_body[:SINK_BODY_TRUNCATE_BYTES]
    try:
        body_text = body_bytes.decode("utf-8", errors="replace")
    except Exception:
        body_text = ""
    body_parsed: Any = None
    if body_text:
        try:
            import json

            body_parsed = json.loads(body_text)
        except Exception:
            body_parsed = None

    headers: dict[str, str] = {}
    if hasattr(request, "headers"):
        for key, value in request.headers.items():
            kl = key.lower()
            if kl in ("authorization", "cookie", "x-e2e-token", "set-cookie"):
                continue
            headers[key] = value

    delivery = {
        "received_at": timezone.now().isoformat(),
        "method": getattr(request, "method", ""),
        "headers": headers,
        "body_text": body_text if body_parsed is None else None,
        "body_parsed": body_parsed,
        "truncated": truncated,
        "status_returned": status_returned,
    }

    deliveries = cache.get(cache_key) or []
    deliveries.append(delivery)
    if len(deliveries) > SINK_MAX_DELIVERIES:
        deliveries = deliveries[-SINK_MAX_DELIVERIES:]
    try:
        cache.set(cache_key, deliveries, SINK_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("webhook_sink_cache_set_failed key=%s err=%s", cache_key, exc)
