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


@pytest.mark.parametrize(("prefix", "_label"), _BINARY_DISGUISE_PREFIXES)
def test_each_binary_prefix_rejected_for_text_csv(prefix: bytes, _label: str):
    head = prefix + b"\x00" * 16
    with pytest.raises(ValidationError) as ei:
        validate_magic_bytes_for_content_type(content_type="text/csv", head=head)
    assert ei.value.code == "FILE_FORMAT_MISMATCH"
    assert ei.value.details.get("detected_signature") == _label


# ---------------------------------------------------------------------------
# magic_byte_check_post_upload — the storage-I/O gate wired into
# FileViewSet.complete_upload (260.DoD.7)
# ---------------------------------------------------------------------------


class _FakeStorageClient:
    def __init__(self, head: bytes | None = None, error: Exception | None = None):
        self._head = head
        self._error = error
        self.calls: list[tuple[str, int | None]] = []

    def get_file_content(self, key: str, max_bytes: int | None = None) -> bytes:
        self.calls.append((key, max_bytes))
        if self._error is not None:
            raise self._error
        return self._head or b""


class _FakeFile:
    def __init__(self, content_type: str | None, storage_path: str = "tenant/key.csv"):
        self.id = "11111111-2222-4333-8444-555555555555"
        self.content_type = content_type
        self.storage_path = storage_path


def test_post_upload_gate_rejects_pe_as_csv():
    from hub.apps.files.magic_bytes import magic_byte_check_post_upload

    file_obj = _FakeFile(content_type="text/csv")
    storage = _FakeStorageClient(head=b"MZ\x90\x00" + b"\x00" * 64)
    with pytest.raises(ValidationError) as ei:
        magic_byte_check_post_upload(file_obj=file_obj, storage_client=storage)
    assert ei.value.code == "FILE_FORMAT_MISMATCH"
    # Head sniff reads at most the spec'd 8 KiB.
    assert storage.calls[0][1] == 8192


def test_post_upload_gate_fails_closed_on_storage_read_error():
    """W10.3 (round-3 re-audit): a storage read failure must BLOCK the
    completion, never skip the disguise check (the pre-fix fail-open
    return-None let an unverified object complete)."""
    from hub.apps.files.magic_bytes import magic_byte_check_post_upload

    file_obj = _FakeFile(content_type="text/csv")
    storage = _FakeStorageClient(error=RuntimeError("storage head read failed"))
    with pytest.raises(ValidationError) as ei:
        magic_byte_check_post_upload(file_obj=file_obj, storage_client=storage)
    assert ei.value.code == "FILE_CONTENT_VALIDATION_UNAVAILABLE"


def test_post_upload_gate_accepts_matching_content():
    from hub.apps.files.magic_bytes import magic_byte_check_post_upload

    file_obj = _FakeFile(content_type="text/csv")
    storage = _FakeStorageClient(head=b"col1,col2\n1,2\n")
    magic_byte_check_post_upload(file_obj=file_obj, storage_client=storage)


def test_post_upload_gate_noop_when_flag_off(settings):
    from hub.apps.files.magic_bytes import magic_byte_check_post_upload

    settings.MAGIC_BYTE_VALIDATION_ENABLED = False
    file_obj = _FakeFile(content_type="text/csv")
    storage = _FakeStorageClient(head=b"MZ\x90\x00" + b"\x00" * 64)
    magic_byte_check_post_upload(file_obj=file_obj, storage_client=storage)
    assert storage.calls == []


def test_post_upload_gate_noop_without_declared_content_type(settings):
    from hub.apps.files.magic_bytes import magic_byte_check_post_upload

    settings.MAGIC_BYTE_VALIDATION_ENABLED = True
    file_obj = _FakeFile(content_type=None)
    storage = _FakeStorageClient(head=b"MZ\x90\x00")
    magic_byte_check_post_upload(file_obj=file_obj, storage_client=storage)
    assert storage.calls == []


def test_post_upload_gate_fails_closed_on_storage_error(settings):
    """W10.3 (round-3 re-audit) — the pre-fix fail-open pin asserted the
    SKIP behaviour (a storage read error returned None and the disguise
    check silently never ran); the re-audit flipped the contract: a
    read error must BLOCK completion (the SHA-256 check covers
    bit-integrity only, never content-type disguise)."""
    from hub.apps.files.magic_bytes import magic_byte_check_post_upload

    settings.MAGIC_BYTE_VALIDATION_ENABLED = True
    file_obj = _FakeFile(content_type="text/csv")
    storage = _FakeStorageClient(error=RuntimeError("S3 down"))
    with pytest.raises(ValidationError) as ei:
        magic_byte_check_post_upload(file_obj=file_obj, storage_client=storage)
    assert ei.value.code == "FILE_CONTENT_VALIDATION_UNAVAILABLE"


class TestDefaultEnabled:
    """W1.18 — the magic-byte gate ships DEFAULT-ON (no env opt-in needed)."""

    def test_default_is_enabled_when_env_unset(self, settings):
        # Reads the settings.py default — NOT an override. The env var is
        # deliberately left unset so any regression of the default back to
        # False flips this pin RED.
        assert settings.MAGIC_BYTE_VALIDATION_ENABLED is True

    def test_gate_fires_under_default(self, settings):
        from hub.apps.files.magic_bytes import magic_byte_check_post_upload

        file_obj = _FakeFile(content_type="text/csv")
        storage = _FakeStorageClient(head=b"MZ\x90\x00" + b"\x00" * 64)
        with pytest.raises(ValidationError) as ei:
            magic_byte_check_post_upload(file_obj=file_obj, storage_client=storage)
        assert ei.value.code == "FILE_FORMAT_MISMATCH"
