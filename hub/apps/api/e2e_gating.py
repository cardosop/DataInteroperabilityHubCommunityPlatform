"""
Shared environment + token gates for test-only API endpoints.

Single source of truth for *both* sides of the "this endpoint must never
serve production traffic" contract. Two endpoints currently consume it:

  - ``hub/apps/api/webhook_sink_views.py``        (Phase 226 G11)
  - ``hub/apps/tenants/ephemeral_views.py``       (Phase 226 OQ4)

Why one module: the `ensure_e2e_*` family, the webhook sink, and the
ephemeral-tenant endpoint share an identical threat model — leaking any
of them in production is a high-severity incident. Two implementations
in two files means two audit points and two reviewers asking "are these
really the same?" One implementation = one audit point.

Posture
-------

  - **Production lockout (env gate).** ``settings.ENVIRONMENT`` is read
    once. ``DEBUG=True`` is the local-dev escape hatch (so a developer
    running ``manage.py runserver`` can hit the endpoint). Otherwise
    only ``test`` and ``staging`` are permitted. ``settings.py`` already
    normalises ``ENVIRONMENT`` via ``.strip().lower()`` so we don't
    re-normalise here — that would imply two callers might pass
    differently-cased values, which would itself be a misconfiguration.
  - **Token gate.** The ``X-E2E-Token`` (or ``x-e2e-token``) request
    header must equal ``settings.E2E_TEST_SECRET`` byte-for-byte.
    Comparison is via ``hmac.compare_digest`` to avoid a timing oracle.
    An empty / unset secret causes ``verify_e2e_token`` to return False
    so the endpoint 404s — production stays closed by default even if
    the URL accidentally gets mounted there.

Both gates close the same way (return False → caller raises 404). The
view does NOT distinguish between "missing env" and "wrong token" — a
probe cannot tell which gate it failed, so the endpoint's existence
is not enumerable.
"""

from __future__ import annotations

import hmac
from typing import Any

from django.conf import settings

# Environments where test-only endpoints are permitted to mount.
# Kept in a constant so both `is_e2e_environment` and any future system
# check can read it without drift.
PERMITTED_E2E_ENVIRONMENTS = frozenset({"test", "staging"})


def is_e2e_environment() -> bool:
    """Return True iff the running environment is permitted for test-only endpoints.

    Posture mirrors ``hub/apps/api/checks.py:check_e2e_secret_when_endpoints_mounted``:
    DEBUG=True opens the local-dev path; otherwise ENVIRONMENT must be in
    the permitted set. Production is closed.
    """
    if getattr(settings, "DEBUG", False):
        return True
    env = getattr(settings, "ENVIRONMENT", "") or ""
    return env in PERMITTED_E2E_ENVIRONMENTS


def _extract_token_header(request: Any) -> str:
    """Return the ``X-E2E-Token`` header value, or empty string.

    Django/DRF surfaces request headers in case-insensitive form via
    ``request.headers``; we still probe both cases because some
    middleware (notably during Playwright fixture wiring) constructs
    fake-request objects with bare-dict headers that are NOT
    case-insensitive.
    """
    if not hasattr(request, "headers"):
        return ""
    headers = request.headers
    return headers.get("X-E2E-Token", "") or headers.get("x-e2e-token", "") or ""


def verify_e2e_token(request: Any) -> bool:
    """Constant-time match of ``X-E2E-Token`` against ``settings.E2E_TEST_SECRET``.

    Returns False when:
      - ``E2E_TEST_SECRET`` is unset / empty (closed by default — production
        without the secret stays a 404 even if the endpoint is mounted).
      - The header is missing.
      - The header value differs from the secret in any byte.

    Uses ``hmac.compare_digest`` for the comparison so a remote attacker
    cannot use timing differences to recover the secret one byte at a time.
    """
    secret = getattr(settings, "E2E_TEST_SECRET", "") or ""
    if not secret:
        return False
    provided = _extract_token_header(request)
    if not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), secret.encode("utf-8"))
