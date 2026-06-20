"""
Phase 250.1.D.5 — SDK idempotency-key composer tests.

Pin the byte-for-byte agreement between the SDK key composer and
the server-side ``IdempotencyService.compose_key``. If either side
drifts, every replay would silently 409 the user — these tests
catch the drift at SDK build-time.

These tests are pure-stdlib and do NOT import Django. The
"server agrees" check is implemented by hashing the same canonical
bytes the server would hash; the actual server module is exercised
in ``hub/apps/assets/tests/test_data_first_idempotency.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid

import pytest

from datahub_interoperability.idempotency import (
    IDEMPOTENCY_HEADER,
    canonical_body_bytes,
    compose_idempotency_key,
)

_KEY_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{64}$")


def test_header_constant_is_canonical_form():
    assert IDEMPOTENCY_HEADER == "Idempotency-Key"


def test_canonical_body_bytes_is_stable_across_dict_orderings():
    """Two dicts with the same data but different key insertion order
    MUST produce identical canonical bytes (otherwise the SHA differs)."""
    a = {"name": "x", "key": "k", "file_id": "f"}
    b = {"file_id": "f", "key": "k", "name": "x"}
    assert canonical_body_bytes(a) == canonical_body_bytes(b)


def test_canonical_body_bytes_uses_compact_separators():
    """The output MUST NOT contain the JSON default ``", "`` /
    ``": "`` separators — those bytes leak into the SHA and would
    desync from the server."""
    out = canonical_body_bytes({"a": 1, "b": 2})
    assert b": " not in out
    assert b", " not in out


def test_canonical_body_bytes_passes_through_bytes():
    raw = b'{"already-encoded":true}'
    assert canonical_body_bytes(raw) is raw or canonical_body_bytes(raw) == raw


def test_canonical_body_bytes_encodes_str_as_utf8():
    s = '{"unicode": "é"}'
    assert canonical_body_bytes(s) == s.encode("utf-8")


def test_canonical_body_bytes_rejects_unsupported_types():
    with pytest.raises(TypeError):
        canonical_body_bytes(12345)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        canonical_body_bytes(None)  # type: ignore[arg-type]


def test_compose_idempotency_key_format():
    tenant = uuid.uuid4()
    key = compose_idempotency_key(tenant, {"a": 1})
    assert _KEY_RE.match(key), f"key {key!r} does not match canonical format"


def test_compose_idempotency_key_normalises_uuid_to_lowercase():
    tenant = "ABCDEF00-1111-2222-3333-444455556666"
    key = compose_idempotency_key(tenant, {"a": 1})
    prefix = key.split(":", 1)[0]
    # uuid.UUID() canonical form is lowercase, hyphenated.
    assert prefix == prefix.lower()
    assert prefix == "abcdef00-1111-2222-3333-444455556666"


def test_compose_idempotency_key_rejects_non_uuid_tenant():
    with pytest.raises(ValueError):
        compose_idempotency_key("not-a-uuid", {"a": 1})


def test_compose_idempotency_key_is_deterministic():
    tenant = uuid.uuid4()
    body = {"file_id": "abc", "key": "xyz", "name": "test"}
    k1 = compose_idempotency_key(tenant, body)
    k2 = compose_idempotency_key(tenant, body)
    assert k1 == k2


def test_compose_idempotency_key_matches_manual_computation():
    """The SDK output MUST equal the manual ``<uuid>:<sha256(canonical)>``
    a server-side test would compute. This is the core "no drift"
    assertion."""
    tenant = uuid.UUID("01234567-89ab-cdef-0123-456789abcdef")
    body = {"file_id": "f", "key": "k", "name": "n"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_sha = hashlib.sha256(canonical).hexdigest()
    key = compose_idempotency_key(tenant, body)
    assert key == f"{tenant}:{expected_sha}"


def test_compose_idempotency_key_differs_when_body_differs():
    tenant = uuid.uuid4()
    k1 = compose_idempotency_key(tenant, {"a": 1})
    k2 = compose_idempotency_key(tenant, {"a": 2})
    assert k1 != k2
    # The tenant prefix is the same; only the SHA suffix should differ.
    assert k1.split(":")[0] == k2.split(":")[0]
    assert k1.split(":")[1] != k2.split(":")[1]


def test_compose_idempotency_key_differs_when_tenant_differs():
    body = {"a": 1}
    k1 = compose_idempotency_key(uuid.uuid4(), body)
    k2 = compose_idempotency_key(uuid.uuid4(), body)
    assert k1 != k2
    # Tenant prefixes differ; SHA suffixes are identical.
    assert k1.split(":")[0] != k2.split(":")[0]
    assert k1.split(":")[1] == k2.split(":")[1]
