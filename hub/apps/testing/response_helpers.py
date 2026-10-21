"""
Cross-compatible response-body accessor for tests.

The data-first endpoints can return either:

* a DRF ``Response`` (the view's normal path) — ``.data`` is the
  parsed payload.
* a Django ``JsonResponse`` (e.g. from
  :class:`hub.apps.api.middleware.idempotency.IdempotencyMiddleware`,
  which intercepts requests BEFORE DRF and rejects missing /
  malformed Idempotency-Keys with a JsonResponse — see
  ``hub/apps/api/middleware/idempotency.py:117``) — ``.data`` does
  not exist on ``HttpResponse`` subclasses.

Tests must accept both because middleware short-circuits are
architecturally valid responses, not bugs.
"""

from __future__ import annotations

import json


def response_body(response):
    """Return the parsed body of a DRF Response or Django HttpResponse.

    * DRF Response → ``response.data`` (already parsed).
    * Django HttpResponse / JsonResponse → ``json.loads(response.content)``.
    * Empty content → ``{}``.

    Useful when the view path may be intercepted by middleware that
    returns ``JsonResponse``; a simple ``response.data`` access then
    raises ``AttributeError``.

    Envelope harmonisation: the platform has two error shapes in
    flight at the moment —

    * DRF (``hub.apps.core.responses.api_error_response``) emits the
      flat shape ``{"detail": "...", "code": "...", "details": {...}}``.
    * Older middleware (``hub.apps.api.middleware.idempotency``) emits
      a nested envelope ``{"error": {"code": "...", "message": "...",
      "http_status": ...}}``.

    Tests assert ``body["code"]``; without harmonisation they get
    ``KeyError: 'code'`` against the nested envelope.  Flatten the
    nested envelope so callers see ``code`` (and ``message`` /
    ``http_status``) at the top level regardless of which path
    produced the response.  The original ``error`` dict stays
    available for tests that still want it.
    """
    data = getattr(response, "data", None)
    if data is None:
        content = getattr(response, "content", b"") or b""
        if not content:
            data = {}
        else:
            try:
                data = json.loads(content.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                data = {}

    if isinstance(data, dict):
        nested = data.get("error")
        if isinstance(nested, dict) and "code" in nested and "code" not in data:
            merged = {**data, **{k: v for k, v in nested.items() if k not in data}}
            return merged
    return data
