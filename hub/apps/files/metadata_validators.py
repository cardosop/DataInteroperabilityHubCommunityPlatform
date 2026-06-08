"""
Phase 260.5.G — ``File.metadata_json`` size cap (closes pass-3 B3-1).

Single canonical validator that enforces the 64 KB cap on
``File.metadata_json`` regardless of the write path:

* **Serializer level** — DRF write paths (current and future) call
  :func:`validate_metadata_json_size` from a field-level validator
  so over-cap user input rejects with HTTP 400 and the typed code
  ``FILE_METADATA_TOO_LARGE`` BEFORE the service layer ever runs.
* **Model level** — ``File.save()`` defensively re-validates so
  ANY caller (services, signals, management commands, raw ORM
  writes) is subject to the same cap. Without the model-level
  check, a future feature that stuffs schema / lineage into
  ``metadata_json`` could silently bloat the column past the spec
  size and bypass the API gate.

The 64 KB number is the spec-mandated value (HIGH severity, B3-1).
It's a STRING-LENGTH proxy for "this metadata is too big to live
in a row column" — Postgres JSONB has no hard limit but rows
above ~8 KB pay TOAST overhead, and at multi-MB sizes a single
``SELECT *`` for an admin tool can exhaust memory in worker
contexts. The cap protects the platform against pathological
internal writes AND against user-supplied metadata from a future
write API.

Byte calculation
----------------
We measure ``len(json.dumps(metadata, ensure_ascii=False,
sort_keys=True).encode('utf-8'))``. ``ensure_ascii=False`` is the
deliberate choice — it gives the same byte count the user
SUBMITTED on the wire (rather than the conservative ASCII-escaped
form which over-counts non-ASCII content). ``sort_keys=True``
makes the size deterministic regardless of dict insertion order.

Empty / null
------------
``None`` and ``{}`` count as 0 bytes (vacuously safe). Boundary
between admit and reject is "size > MAX" not "size >= MAX" —
exactly 64 KB is admitted as the documented hard cap.
"""
from __future__ import annotations
import json
from typing import Any, Mapping, Optional

from hub.apps.core.services.base import ValidationError


# Spec-mandated cap. Operators can override by replacing the
# constant in a derived module if needed; production should not
# tune this without a corresponding R-block update because clients
# rely on the 64 KB ceiling for the size of metadata they can
# round-trip through the platform.
MAX_METADATA_JSON_BYTES: int = 64 * 1024  # 64 KB


def metadata_json_size_bytes(metadata: Optional[Mapping[str, Any]]) -> int:
    """Return the canonical JSON-serialized byte count of *metadata*.

    Mirrors the byte budget the user would consume on the wire if
    they submitted this metadata as the body of a JSON HTTP
    request. ``None`` and ``{}`` return 0; everything else is
    serialized with ``ensure_ascii=False`` (matches user-submitted
    UTF-8) and ``sort_keys=True`` (deterministic across calls).

    Raises ``TypeError`` propagated from ``json.dumps`` if the
    metadata contains non-JSON-serializable values (datetime,
    UUID, etc.) — the caller is expected to coerce these
    BEFORE storing in ``metadata_json`` (the JSONField does the
    same; mismatch surfaces as a clear traceback rather than
    silently 0-counted).
    """
    if metadata is None or metadata == {}:
        return 0
    payload = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return len(payload.encode("utf-8"))


def validate_metadata_json_size(
    metadata: Optional[Mapping[str, Any]],
    *,
    field_name: str = "metadata_json",
) -> None:
    """Phase 260.5.G — raise ``FILE_METADATA_TOO_LARGE`` when
    *metadata* exceeds :data:`MAX_METADATA_JSON_BYTES`.

    Pure (no I/O, no DB). Re-runnable from any layer — serializer
    field-level validator, model ``save()`` override, service-
    layer pre-write check. The boundary check is *strict greater
    than* (``>``), so exactly 64 KB is admitted; one byte more
    rejects.

    Args:
        metadata: The candidate JSON-serializable payload. ``None``
            and ``{}`` pass trivially.
        field_name: Surface field name for the error envelope so
            future callers (e.g. a separate ``user_metadata`` slot)
            can reuse the same validator with the right error
            attribution.

    Raises:
        ValidationError: with ``code='FILE_METADATA_TOO_LARGE'``,
        ``http_status=400``, and ``details`` carrying the actual
        size + cap so operators / SDK consumers have the full
        triage payload in the 4xx body.
    """
    size_bytes = metadata_json_size_bytes(metadata)
    if size_bytes <= MAX_METADATA_JSON_BYTES:
        return

    raise ValidationError(
        (
            f"File.{field_name} of {size_bytes:,} bytes exceeds the "
            f"{MAX_METADATA_JSON_BYTES:,}-byte cap. Reduce the "
            f"metadata payload (drop verbose fields, move large "
            f"values to a separate Dataset / object) and retry."
        ),
        code="FILE_METADATA_TOO_LARGE",
        details={
            "field_name": field_name,
            "size_bytes": size_bytes,
            "max_bytes": MAX_METADATA_JSON_BYTES,
            "remediation": "reduce_metadata_or_split",
        },
        http_status=400,
    )


__all__ = [
    "MAX_METADATA_JSON_BYTES",
    "metadata_json_size_bytes",
    "validate_metadata_json_size",
]
