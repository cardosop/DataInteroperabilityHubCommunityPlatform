"""
Phase 260.2.B — magic-byte validation (pure logic; no I/O).

Table-driven tests double as mutation-test surrogates: each binary disguise prefix
must reject ``text/csv`` independently.
"""

from __future__ import annotations

import pytest

from hub.apps.core.services.base import ValidationError
from hub.apps.files.magic_bytes import (
    _BINARY_DISGUISE_PREFIXES,
    validate_magic_bytes_for_content_type,
)

pytestmark = pytest.mark.unit


def test_csv_pe_mz_rejected():
    with pytest.raises(ValidationError) as ei:
        validate_magic_bytes_for_content_type(
            content_type="text/csv",
            head=b"MZ\x90\x00" + b"\x00" * 8,
        )
    assert ei.value.code == "FILE_FORMAT_MISMATCH"
    assert ei.value.details.get("detected_signature") == "pe_mz"


def test_csv_plain_ascii_accepted():
    validate_magic_bytes_for_content_type(
        content_type="text/csv",
        head=b"col1,col2\n1,2\n",
    )


def test_json_accepts_object_and_array():
    validate_magic_bytes_for_content_type(
        content_type="application/json",
        head=b'  {"ok": true}',
    )
    validate_magic_bytes_for_content_type(
        content_type="application/json",
        head=b"\n\t[]",
    )


def test_json_rejects_pe():
    with pytest.raises(ValidationError) as ei:
        validate_magic_bytes_for_content_type(
            content_type="application/json",
            head=b"MZ\x00",
        )
    assert ei.value.code == "FILE_FORMAT_MISMATCH"


def test_json_rejects_non_object_start():
    with pytest.raises(ValidationError) as ei:
        validate_magic_bytes_for_content_type(
            content_type="application/json",
            head=b'"just a string"',
        )
    assert ei.value.details.get("detected_signature") == "json_invalid_start"


def test_pdf_requires_percent_pdf():
    validate_magic_bytes_for_content_type(
        content_type="application/pdf",
        head=b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n",
    )
    with pytest.raises(ValidationError):
        validate_magic_bytes_for_content_type(
            content_type="application/pdf",
            head=b"NOTPDF",
        )


def test_unknown_mime_skips_validation():
    validate_magic_bytes_for_content_type(
        content_type="application/octet-stream",
        head=b"MZ\x00whatever",
    )


def test_empty_content_type_rejected():
    with pytest.raises(ValidationError) as ei:
        validate_magic_bytes_for_content_type(content_type="", head=b"abc")
    assert ei.value.code == "FILE_FORMAT_MISMATCH"


@pytest.mark.parametrize("prefix,_label", _BINARY_DISGUISE_PREFIXES)
def test_each_binary_prefix_rejected_for_text_csv(prefix: bytes, _label: str):
    head = prefix + b"\x00" * 16
    with pytest.raises(ValidationError) as ei:
        validate_magic_bytes_for_content_type(content_type="text/csv", head=head)
    assert ei.value.code == "FILE_FORMAT_MISMATCH"
    assert ei.value.details.get("detected_signature") == _label
