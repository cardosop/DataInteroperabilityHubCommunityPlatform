"""
Phase 250.1.D — test helpers for endpoints that enforce the
``Idempotency-Key`` header.

Existing legacy tests posted to ``/api/v1/assets/data-first/`` without
the header (because it didn't exist before 250.1.D). Adding the
header by hand to every test method would be mechanical churn. This
module provides a small wrapper that auto-composes the key from the
authenticated tenant + request body, so legacy tests can switch a
single call site instead of every assertion.

Usage
-----

::

    from hub.apps.testing.idempotency_helpers import post_data_first

    response = post_data_first(
        self.client,
        "/api/v1/assets/data-first/",
        {"file_id": ..., "key": "...", "name": "..."},
        tenant=self.tenant,
    )

The helper also exposes ``compose_test_idempotency_key`` for tests
that need to construct the key explicitly (e.g., to test mismatch
behaviour).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def _canonical_body_bytes(body: dict[str, Any] | list | bytes | str) -> bytes:
    """Mirror of :func:`hub.apps.core.idempotency.IdempotencyService.canonical_body_bytes`.

    Kept inline (no import from production code) so a refactor in
    the production module doesn't silently break legacy tests via a
    chain of indirection — this helper is the test-side contract
    pin.
    """
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, (dict, list)):
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    raise TypeError(f"unsupported body type: {type(body)!r}")


def compose_test_idempotency_key(
    tenant_uuid: str | uuid.UUID,
    body: dict[str, Any] | list | bytes | str,
) -> str:
    """Compose a valid ``Idempotency-Key`` for ``body`` under ``tenant_uuid``."""
    canonical = _canonical_body_bytes(body)
    sha = hashlib.sha256(canonical).hexdigest()
    normalised = str(uuid.UUID(str(tenant_uuid)))
    return f"{normalised}:{sha}"


def post_data_first(
    client,
    url: str,
    body: dict[str, Any] | None,
    *,
    tenant=None,
    tenant_uuid: str | uuid.UUID | None = None,
    extra_headers: dict[str, str] | None = None,
    **post_kwargs: Any,
):
    """POST ``body`` to ``url`` with a valid auto-composed Idempotency-Key.

    Args:
        client: The DRF/Django ``APIClient`` instance.
        url: Endpoint URL (typically ``/api/v1/assets/data-first/``).
        body: Request body (dict). May be ``None`` for tests that
            send a literally empty body — the helper composes the
            key over an empty JSON object in that case so the
            request is still well-formed.
        tenant: Tenant model instance (its ``id`` is used for the
            key prefix). Mutually exclusive with ``tenant_uuid``.
        tenant_uuid: Explicit tenant UUID override. Useful when the
            test deliberately wants a mismatched tenant prefix.
        extra_headers: Additional ``HTTP_*`` headers to forward to
            APIClient.post (override the auto-injected key by
            passing ``HTTP_IDEMPOTENCY_KEY``).
        **post_kwargs: Other kwargs forwarded to APIClient.post
            (e.g. ``CONTENT_LENGTH=...``).

    Returns:
        The APIClient response.

    The helper serialises the body to **canonical** JSON bytes
    (``sort_keys=True``, compact separators) and sends them via
    ``content_type="application/json"`` so the wire bytes match
    what the server hashes. Using ``format="json"`` instead would
    let APIClient pick its own JSON encoding (default whitespace,
    insertion order) and the server SHA would diverge from the
    SDK SHA — every request would 409 with
    ``IDEMPOTENCY_KEY_MISMATCH``.
    """
    if tenant_uuid is not None:
        effective_tenant_uuid: str | uuid.UUID = tenant_uuid
    elif tenant is not None:
        effective_tenant_uuid = tenant.id
    else:
        raise ValueError("post_data_first requires `tenant` or `tenant_uuid`")

    canonical_body = body if body is not None else {}
    canonical_bytes = _canonical_body_bytes(canonical_body)
    auto_key = compose_test_idempotency_key(effective_tenant_uuid, canonical_bytes)

    headers: dict[str, str] = {"HTTP_IDEMPOTENCY_KEY": auto_key}
    if extra_headers:
        headers.update(extra_headers)

    # Strip the user-friendly ``format="json"`` if present — we're
    # sending pre-serialised bytes, so APIClient must NOT touch the
    # body. ``content_type`` tells DRF the wire format.
    post_kwargs.pop("format", None)
    post_kwargs.setdefault("content_type", "application/json")
    return client.post(url, canonical_bytes, **headers, **post_kwargs)
