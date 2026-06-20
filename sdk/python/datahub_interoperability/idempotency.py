"""
Phase 250.1.D.5 — client-side idempotency-key composer.

The DataHub SDK MUST compose the same ``Idempotency-Key`` value the
server expects per D250.8: ``<tenant_uuid>:<sha256(canonical_body)>``.
The canonical body is JSON serialised with ``sort_keys=True`` and
the most compact ``separators`` so two equivalent payloads with
different whitespace produce the **same** key.

Keep this module pure-stdlib so it imports cleanly in any
asyncio context — no httpx, no Django, no third-party deps. The
SDK's :class:`AssetsAPI` calls into here when sending
``POST /assets/data-first/`` so users get correct deduplication for
free without having to compute the hash themselves.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Union

__all__ = [
    "compose_idempotency_key",
    "canonical_body_bytes",
    "IDEMPOTENCY_HEADER",
]


#: Wire header name. Pinned in this constant so server + client +
#: tests reference the same string — a typo in either site
#: silently breaks deduplication.
IDEMPOTENCY_HEADER: str = "Idempotency-Key"


_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_body_bytes(
    body: Union[bytes, bytearray, str, dict, list],
) -> bytes:
    """Return the canonical bytes used to compute the SHA-256 over a body.

    Mirror of
    :func:`hub.apps.core.idempotency.IdempotencyService.canonical_body_bytes`
    so the client and server agree byte-for-byte on the hash input.
    Whitespace, key order and number formatting MUST match: we
    serialise dict / list inputs with ``sort_keys=True`` and the
    most compact separators ``(",", ":")``. Raw ``bytes`` /
    ``bytearray`` inputs pass through unchanged so callers that
    already hold the wire body skip the round-trip.
    """
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, (dict, list)):
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    raise TypeError(f"unsupported body type for canonical_body_bytes: {type(body)!r}")


def compose_idempotency_key(
    tenant_uuid: Union[str, uuid.UUID],
    body: Union[bytes, bytearray, str, dict, list],
) -> str:
    """Compose ``<tenant_uuid>:<sha256(body)>`` per D250.8.

    Args:
        tenant_uuid: Caller's tenant identifier. Accepts a UUID
            instance or its string representation. The output is
            normalised to the canonical lowercase form so equivalent
            inputs yield byte-identical keys.
        body: The request body. ``dict`` / ``list`` are JSON-serialised
            with ``sort_keys=True``; ``str`` is UTF-8 encoded;
            ``bytes`` passes through.

    Returns:
        A ``Idempotency-Key`` header value. Exactly one colon
        separates the tenant prefix from the SHA-256 hex suffix;
        both fields are lowercase.

    Raises:
        ValueError: ``tenant_uuid`` is not a valid UUID.
        TypeError: ``body`` is not one of the supported types.

    Example::

        from datahub_interoperability.idempotency import (
            compose_idempotency_key, IDEMPOTENCY_HEADER,
        )
        body = {"file_id": "...", "key": "my-asset", "name": "..."}
        key = compose_idempotency_key(my_tenant_uuid, body)
        await client.post("assets/data-first/", data=body, headers={IDEMPOTENCY_HEADER: key})
    """
    body_bytes = canonical_body_bytes(body)
    sha = hashlib.sha256(body_bytes).hexdigest()
    # Normalise via uuid.UUID round-trip — rejects non-UUID strings
    # AND lowercases the canonical form.
    normalised_tenant = str(uuid.UUID(str(tenant_uuid)))
    key = f"{normalised_tenant}:{sha}"
    # Defensive sanity-check — if the SHA library ever returned a
    # non-hex digest the server would reject the key with 400; we
    # surface that as a TypeError on the client side instead.
    if not _SHA256_HEX_RE.match(sha):
        raise TypeError(f"hashlib.sha256 produced a non-hex digest: {sha!r}")
    return key
