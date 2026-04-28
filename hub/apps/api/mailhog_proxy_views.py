"""
E2E test-only MailHog inbox proxy (Phase 226 OQ-MailHog).

Forwards two GET endpoints from the test runner to the in-cluster MailHog
HTTP API:

  - ``GET /api/v1/test/mailhog/messages/``        → list inbox
  - ``GET /api/v1/test/mailhog/messages/<id>/``   → single message

The shared E2E gating posture from ``hub/apps/api/e2e_gating.py`` applies:

  * Production lockout via ``is_e2e_environment()`` (env not in
    {test, staging} and not DEBUG → 404).
  * Token gate via ``verify_e2e_token()`` (``X-E2E-Token`` must equal
    ``settings.E2E_TEST_SECRET`` byte-for-byte; absent secret → 404).
  * Both gates close the SAME way (404), so a probe cannot enumerate
    the endpoint's existence.

Defence-in-depth properties:

  - **Hardcoded internal URL**: the upstream MailHog URL comes from
    ``settings.MAILHOG_INTERNAL_URL`` (set in helm/values.staging.yaml),
    NEVER from request input. Closes SSRF + DNS-rebinding.
  - **No redirects**: ``allow_redirects=False`` stops upstream-controlled
    rebind and 30x ping-loops.
  - **Path validation**: ``message_id`` is restricted to alphanumeric +
    hyphen, ≤ 64 chars. Rejects path traversal at the URL routing layer
    (``<str:message_id>``) AND in the validator below.
  - **Token never forwarded**: ``X-E2E-Token``, ``Authorization``,
    ``Cookie`` headers are stripped before contacting MailHog so a
    compromised MailHog never sees Meshant credentials.
  - **Generic upstream errors**: connection refused / DNS / timeout
    surface as 503 with a fixed message; never echo the underlying
    exception class to the caller.
  - **Bounded body**: upstream response body capped at 1 MiB. MailHog
    payloads include full email bodies which can be sizeable but are
    never legitimately larger than that.
  - **Forced JSON content-type**: response Content-Type is forced to
    ``application/json`` regardless of upstream — defends against a
    misrouted upstream serving HTML.

The proxy is **read-only** by contract: only GET is wired. The chart's
NetworkPolicy guarantees that this Django view is the only path through
which an external caller can read MailHog. DELETE on the inbox is
performed by the daily ``mailhog-prune`` CronJob from inside the cluster,
never via this proxy.
"""

from __future__ import annotations

import logging
from typing import Any, Tuple

import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from hub.apps.api.e2e_gating import is_e2e_environment, verify_e2e_token

logger = logging.getLogger(__name__)

# Upstream call timeout. MailHog's in-memory store responds in
# single-digit ms in nominal conditions; 5 seconds is a generous ceiling
# that still keeps a hung pod from holding a Django worker hostage.
UPSTREAM_TIMEOUT_SECONDS = 5

# Maximum bytes we copy from the upstream response back to the caller.
# Sized for "plenty of room for a typical password-reset email payload"
# without enabling the proxy as a DoS amplifier.
MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1 MiB

# Maximum length of the message_id path parameter. MailHog IDs are
# usually <hash>@<domain> shapes; 64 chars is room enough.
MAX_MESSAGE_ID_LEN = 64

# Headers we MUST NOT forward upstream. Defence-in-depth: even if a
# future caller adds these by mistake, MailHog never sees Meshant secrets.
FORBIDDEN_FORWARD_HEADERS = frozenset(
    {"x-e2e-token", "authorization", "cookie", "x-csrftoken", "csrf-token"}
)


def _gate_or_404(request: Any) -> None:
    """Run the env + token gates. Raises ``NotFound`` on any miss."""
    if not is_e2e_environment():
        raise NotFound("mailhog proxy is not enabled in this environment")
    if not verify_e2e_token(request):
        # Same 404 on bad-secret as on missing-env so a probe cannot tell
        # which gate it failed.
        raise NotFound("mailhog proxy is not enabled in this environment")


def _resolve_upstream_base() -> str:
    """Return the configured MailHog base URL, or empty if unset.

    Pure helper so the test harness can pin the empty / set branches
    without monkey-patching ``settings``.
    """
    return (getattr(settings, "MAILHOG_INTERNAL_URL", "") or "").rstrip("/")


def _validate_message_id(message_id: str) -> bool:
    """Pure: True if ``message_id`` is safe to interpolate into a URL.

    Restricts to a conservative shape (letters/digits/hyphen/underscore/dot
    plus ``@`` because MailHog IDs occasionally embed a domain) and a
    bounded length. ``.`` is in the allow-list because legitimate MailHog
    IDs use it (e.g. ``<hash>@example.com``), so we cannot reject all
    dots. Path-traversal sequences (``..``) and any leading/trailing dot
    are rejected explicitly to close the residual gap left by allowing
    individual dots.

    The URL pattern's ``<str:message_id>`` captures up to the next ``/``
    already (slashes are structurally impossible here), but we
    double-validate in case the pattern is ever loosened.
    """
    if not message_id or len(message_id) > MAX_MESSAGE_ID_LEN:
        return False
    # Reject any path-traversal sequence: `..` collapsed by an HTTP
    # server's path normalisation (e.g. `messages/abc/../admin`) would
    # let an attacker reach upstream paths outside `/api/v1/messages/`.
    if ".." in message_id:
        return False
    # Leading/trailing dots aren't legitimate either — they're a typical
    # source of normalisation surprises and aren't part of any real
    # MailHog ID format.
    if message_id.startswith(".") or message_id.endswith("."):
        return False
    for ch in message_id:
        if not (ch.isalnum() or ch in "-_.@"):
            return False
    return True


def _generic_503(reason: str) -> Response:
    """Build a fixed-shape 503 with no internal detail. ``reason`` is
    logged at WARNING level; the client only sees the generic body."""
    logger.warning("mailhog proxy upstream unavailable: %s", reason)
    return Response(
        {"detail": "mailhog upstream unavailable"},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
        content_type="application/json",
    )


def _proxy_get(upstream_url: str) -> Tuple[Any, int]:
    """Run the upstream GET with safety rails, return (body_dict, status).

    Pure-ish: takes the resolved URL, returns the parsed body + status
    or raises a typed exception via ``requests``. Caller handles
    exceptions and the 503 mapping.

    Caps the response body before parsing — a hostile upstream cannot
    push more than MAX_RESPONSE_BYTES into Django's process memory.
    """
    response = requests.get(
        upstream_url,
        timeout=UPSTREAM_TIMEOUT_SECONDS,
        allow_redirects=False,
        # Don't forward ANY of the request's headers to MailHog. Even if
        # the caller passed Authorization/Cookie by mistake, they don't
        # leak. The blank dict here is the explicit "no headers" signal.
        headers={"Accept": "application/json"},
    )
    if response.status_code >= 500:
        raise requests.HTTPError(f"upstream {response.status_code}")
    if response.status_code != 200:
        # Forward 404 from MailHog as our own 404 — the caller is asking
        # for a message id that doesn't exist.
        raise NotFound("mailhog message not found")

    # Read at most MAX_RESPONSE_BYTES + 1 to detect over-cap shapes.
    body_bytes = response.content[: MAX_RESPONSE_BYTES + 1]
    if len(body_bytes) > MAX_RESPONSE_BYTES:
        # Truncate. We can't usefully forward a half-decoded JSON, so
        # surface a structured error and let the caller retry.
        raise requests.HTTPError("upstream body exceeds proxy cap")

    try:
        return response.json(), response.status_code
    except ValueError as exc:
        raise requests.HTTPError(f"upstream non-JSON: {exc}")


@extend_schema(exclude=True, tags=["API"])
@api_view(["GET"])
# Skip DRF authentication entirely. The proxy's ONLY auth is the
# `verify_e2e_token` gate inside `_gate_or_404`; running DRF's default
# authentication backends (JWT etc.) on this endpoint would cause an
# inbound `Authorization: Bearer <jwt>` header to short-circuit with a
# 401 BEFORE our gates fire, which would (a) leak the endpoint's existence
# (different status from production lockout) and (b) break the test's
# defence-in-depth check that callers can mistakenly carry credentials
# without breaking the proxy. Mirrors `webhook_sink_views.py`.
@authentication_classes([])
@permission_classes([AllowAny])
def mailhog_messages_list(request):
    """Forward to ``GET <MAILHOG_INTERNAL_URL>/api/v1/messages``.

    Returns the MailHog v1 list payload as-is. Test runners parse it
    with the existing client at
    ``frontend/e2e/fixtures/auth-journey-steps.ts``.
    """
    _gate_or_404(request)
    base = _resolve_upstream_base()
    if not base:
        return _generic_503("MAILHOG_INTERNAL_URL is empty")
    url = f"{base}/api/v1/messages"
    try:
        body, _status = _proxy_get(url)
    except requests.Timeout:
        return _generic_503("upstream timeout")
    except requests.ConnectionError:
        return _generic_503("upstream connection refused / DNS")
    except requests.HTTPError as exc:
        return _generic_503(f"upstream http error: {exc}")
    return Response(body, status=status.HTTP_200_OK, content_type="application/json")


@extend_schema(exclude=True, tags=["API"])
@api_view(["GET"])
# Skip DRF authentication entirely. The proxy's ONLY auth is the
# `verify_e2e_token` gate inside `_gate_or_404`; running DRF's default
# authentication backends (JWT etc.) on this endpoint would cause an
# inbound `Authorization: Bearer <jwt>` header to short-circuit with a
# 401 BEFORE our gates fire, which would (a) leak the endpoint's existence
# (different status from production lockout) and (b) break the test's
# defence-in-depth check that callers can mistakenly carry credentials
# without breaking the proxy. Mirrors `webhook_sink_views.py`.
@authentication_classes([])
@permission_classes([AllowAny])
def mailhog_message_detail(request, message_id: str):
    """Forward to ``GET <MAILHOG_INTERNAL_URL>/api/v1/messages/<message_id>``.

    Path-parameter ``message_id`` is double-validated (URL pattern + shape
    check) before interpolation — never trust the captured value.
    """
    _gate_or_404(request)
    if not _validate_message_id(message_id):
        # Same 404 shape as the env / token gates so a probe cannot map
        # the validator's surface.
        raise NotFound("mailhog message not found")
    base = _resolve_upstream_base()
    if not base:
        return _generic_503("MAILHOG_INTERNAL_URL is empty")
    url = f"{base}/api/v1/messages/{message_id}"
    try:
        body, _status = _proxy_get(url)
    except requests.Timeout:
        return _generic_503("upstream timeout")
    except requests.ConnectionError:
        return _generic_503("upstream connection refused / DNS")
    except requests.HTTPError as exc:
        return _generic_503(f"upstream http error: {exc}")
    return Response(body, status=status.HTTP_200_OK, content_type="application/json")
