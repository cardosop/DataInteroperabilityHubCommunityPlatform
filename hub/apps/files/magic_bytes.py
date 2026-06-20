"""
Phase 260.2.B — declarative content-type ↔ magic-byte validation (server-side).

Pure validation helpers (no I/O). Used by ``magic_byte_check_post_upload`` after
``S3StorageClient.download_range`` returns the object head.
"""

from __future__ import annotations

from hub.apps.core.services.base import ValidationError

# Maximum bytes read from object storage for sniffing (spec: first 8 KiB).
MAGIC_BYTE_HEAD_BYTES: int = 8192

# MIME parameter strip only; callers should pass RFC content-type when possible.
_TEXT_LIKE_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text/csv",
        "text/plain",
        "text/tab-separated-values",
        "application/csv",
        "text/html",
        "application/x-ndjson",
    }
)

# (prefix, detector_id) — detector_id is stable for audits and tests.
_BINARY_DISGUISE_PREFIXES: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "pe_mz"),
    (b"\x7fELF", "elf"),
    (b"%PDF", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\x89PNG", "png_short"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif87a"),
    (b"GIF89a", "gif89a"),
    (b"RIFF", "riff"),  # WEBP often RIFF....WEBP; blocks obvious binary payloads
    (b"PK\x03\x04", "zip"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole_cfbf"),  # .xls / legacy OLE
)


def normalize_content_type(content_type: str) -> str:
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def _head_starts_with_any_prefix(head: bytes) -> tuple[bytes, str] | None:
    for prefix, label in _BINARY_DISGUISE_PREFIXES:
        if len(head) >= len(prefix) and head[: len(prefix)] == prefix:
            return prefix, label
    return None


def _reject_text_like_binary(head: bytes, *, declared_mime: str) -> None:
    hit = _head_starts_with_any_prefix(head)
    if hit is None:
        return
    _prefix, label = hit
    raise ValidationError(
        f"Declared MIME {declared_mime!r} is incompatible with detected "
        f"binary signature ({label}).",
        code="FILE_FORMAT_MISMATCH",
        details={
            "declared_content_type": declared_mime,
            "detected_signature": label,
        },
    )


def _strip_utf8_bom_and_leading_ws(data: bytes) -> bytes:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    # Only strip ASCII whitespace commonly allowed before JSON
    while data[:1] in (b" ", b"\t", b"\n", b"\r"):
        data = data[1:]
    return data


def _validate_json_head(head: bytes, *, declared_mime: str) -> None:
    _reject_text_like_binary(head, declared_mime=declared_mime)
    stripped = _strip_utf8_bom_and_leading_ws(head)
    if not stripped:
        return
    if stripped[:1] not in (b"{", b"["):
        raise ValidationError(
            "Declared application/json but first non-whitespace byte is not '{' or '['.",
            code="FILE_FORMAT_MISMATCH",
            details={
                "declared_content_type": declared_mime,
                "detected_signature": "json_invalid_start",
            },
        )


def _validate_required_prefix(
    head: bytes,
    *,
    declared_mime: str,
    required: bytes,
    label: str,
) -> None:
    if len(head) < len(required) or head[: len(required)] != required:
        raise ValidationError(
            f"Declared {declared_mime!r} but content does not start with expected magic ({label}).",
            code="FILE_FORMAT_MISMATCH",
            details={
                "declared_content_type": declared_mime,
                "detected_signature": f"expected_{label}",
            },
        )


# Normalized MIME → (prefix bytes, audit label)
_REQUIRED_PREFIX_BY_MIME: dict[str, tuple[bytes, str]] = {
    "application/pdf": (b"%PDF", "pdf_magic"),
    "image/png": (b"\x89PNG\r\n\x1a\n", "png_magic"),
    "image/jpeg": (b"\xff\xd8\xff", "jpeg_magic"),
    "image/gif": (b"GIF8", "gif_magic"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        b"PK\x03\x04",
        "ooxml_zip_magic",
    ),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        b"PK\x03\x04",
        "ooxml_zip_magic",
    ),
    "application/vnd.ms-excel": (
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
        "xls_ole_magic",
    ),
    "application/parquet": (b"PAR1", "parquet_magic"),
    "application/x-parquet": (b"PAR1", "parquet_magic"),
}


def validate_magic_bytes_for_content_type(*, content_type: str, head: bytes) -> None:
    """
    Raise ``ValidationError`` with code ``FILE_FORMAT_MISMATCH`` when the head
    of the object disagrees with the declared MIME type.
    """
    declared = normalize_content_type(content_type)
    if not declared:
        raise ValidationError(
            "Missing content type for magic-byte validation.",
            code="FILE_FORMAT_MISMATCH",
            details={"declared_content_type": ""},
        )

    if declared in _REQUIRED_PREFIX_BY_MIME:
        prefix, label = _REQUIRED_PREFIX_BY_MIME[declared]
        _validate_required_prefix(head, declared_mime=declared, required=prefix, label=label)
        return

    if declared == "application/json" or declared.endswith("+json"):
        _validate_json_head(head, declared_mime=declared)
        return

    if declared in _TEXT_LIKE_CONTENT_TYPES:
        _reject_text_like_binary(head, declared_mime=declared)
        return

    # Types without a strict map: no server-side magic enforcement.
