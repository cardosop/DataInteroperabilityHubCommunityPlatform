"""
Phase 260.3.G — SDK SHA-256 verification + mismatch-report contract.

Pure-stdlib + pytest tests for the SDK download-with-verification
helper. No mocks of business logic; the boundary that IS substituted
is the HTTP layer (we provide a fake transport that returns a
deterministic ``(payload, blob)`` so we can exercise the verify-and-
report contract without spinning up a live Hub).

Engineering invariants under test:
    * Match path returns the bytes; no audit-report HTTP fires.
    * Mismatch path POSTs to the audit endpoint AND raises
      :class:`ChecksumMismatchError` so caller code cannot silently
      hand corrupted bytes to the user.
    * Skip path (server reports ``content_sha256=None``) returns the
      bytes with ``status='skipped'`` and emits no audit report.
    * The mismatch report STILL raises even if the audit endpoint
      itself fails (defence-in-depth).
    * SHA-256 over the FIPS 180-4 "abc" vector matches the canonical
      digest.
"""

from __future__ import annotations

import hashlib

import pytest

from datahub_interoperability.download_verify import (
    ChecksumMismatchError,
    DownloadResult,
    compute_sha256,
    sha_equals_constant_time,
    verify_blob,
)

ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# --------------------------------------------------------------------- #
# Pure-function helpers                                                 #
# --------------------------------------------------------------------- #


@pytest.mark.integration
def test_compute_sha256_matches_fips_abc_vector() -> None:
    assert compute_sha256(b"abc") == ABC_SHA256


@pytest.mark.integration
def test_compute_sha256_empty_input() -> None:
    assert compute_sha256(b"") == EMPTY_SHA256


@pytest.mark.integration
def test_compute_sha256_returns_lowercase_hex() -> None:
    digest = compute_sha256(b"x" * 1024)
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


@pytest.mark.integration
def test_compute_sha256_streams_iterable_chunks() -> None:
    """An iterator of chunks must hash to the same digest as the joined bytes."""

    def chunks():
        yield b"abc"

    iter_digest = compute_sha256(chunks())
    assert iter_digest == ABC_SHA256


@pytest.mark.integration
def test_sha_equals_constant_time_basic_cases() -> None:
    assert sha_equals_constant_time(ABC_SHA256, ABC_SHA256) is True
    # Case-insensitive
    assert sha_equals_constant_time(ABC_SHA256.upper(), ABC_SHA256) is True
    # Mismatch
    assert sha_equals_constant_time("0" + ABC_SHA256[1:], ABC_SHA256) is False
    # Length mismatch — must NOT throw, must NOT short-circuit-true
    assert sha_equals_constant_time(ABC_SHA256, ABC_SHA256[:32]) is False
    # Empty / non-str
    assert sha_equals_constant_time("", ABC_SHA256) is False
    assert sha_equals_constant_time(None, ABC_SHA256) is False  # type: ignore[arg-type]
    assert sha_equals_constant_time(ABC_SHA256, None) is False  # type: ignore[arg-type]


# --------------------------------------------------------------------- #
# verify_blob (pure result wrapper)                                     #
# --------------------------------------------------------------------- #


@pytest.mark.integration
def test_verify_blob_matched() -> None:
    result = verify_blob(b"abc", ABC_SHA256)
    assert result.status == "matched"
    assert result.actual == ABC_SHA256
    assert result.expected == ABC_SHA256


@pytest.mark.integration
def test_verify_blob_mismatched() -> None:
    result = verify_blob(b"abd", ABC_SHA256)
    assert result.status == "mismatched"
    assert result.actual != ABC_SHA256
    assert result.expected == ABC_SHA256


@pytest.mark.integration
def test_verify_blob_skipped_when_expected_is_none() -> None:
    result = verify_blob(b"abc", None)
    assert result.status == "skipped"
    assert result.expected is None


@pytest.mark.integration
def test_verify_blob_skipped_when_expected_is_malformed() -> None:
    result = verify_blob(b"abc", "not-a-sha")
    assert result.status == "skipped"
    assert result.expected is None


# --------------------------------------------------------------------- #
# Orchestrator: download_file_with_verification                         #
# --------------------------------------------------------------------- #


class FakeFilesAPI:
    """Tiny stand-in for the real :class:`FilesAPI` boundary.

    Only the two methods the orchestrator depends on are implemented;
    no Hub bring-up needed.
    """

    def __init__(
        self,
        *,
        download_payload: dict,
        download_blob: bytes,
        report_response: dict | None = None,
        report_raises: Exception | None = None,
    ) -> None:
        self.download_payload = download_payload
        self.download_blob = download_blob
        self.report_response = report_response or {"recorded": True}
        self.report_raises = report_raises
        self.calls: list[tuple[str, tuple, dict]] = []

    async def get_download_url(self, file_id: str) -> dict:
        self.calls.append(("get_download_url", (file_id,), {}))
        return dict(self.download_payload)

    async def report_checksum_mismatch(self, file_id: str, actual_sha256: str) -> dict:
        self.calls.append(("report_checksum_mismatch", (file_id, actual_sha256), {}))
        if self.report_raises is not None:
            raise self.report_raises
        return self.report_response

    async def fetch_bytes(self, url: str) -> bytes:
        self.calls.append(("fetch_bytes", (url,), {}))
        return self.download_blob


@pytest.mark.asyncio
async def test_download_with_verify_match_returns_bytes_and_no_audit() -> None:
    from datahub_interoperability.download_verify import download_file_with_verification

    api = FakeFilesAPI(
        download_payload={
            "download_url": "https://s3.example.com/presigned",
            "expires_in": 3600,
            "filename": "data.csv",
            "content_sha256": ABC_SHA256,
        },
        download_blob=b"abc",
    )
    result = await download_file_with_verification(
        api,
        file_id="file-1",
        s3_fetch=api.fetch_bytes,
    )
    assert isinstance(result, DownloadResult)
    assert result.status == "matched"
    assert result.content == b"abc"
    assert result.filename == "data.csv"
    # No audit-report call: only get_download_url + fetch_bytes.
    actions = [c[0] for c in api.calls]
    assert actions == ["get_download_url", "fetch_bytes"]


@pytest.mark.asyncio
async def test_download_with_verify_mismatch_reports_and_raises() -> None:
    from datahub_interoperability.download_verify import download_file_with_verification

    api = FakeFilesAPI(
        download_payload={
            "download_url": "https://s3.example.com/presigned",
            "expires_in": 3600,
            "filename": "data.csv",
            "content_sha256": ABC_SHA256,
        },
        download_blob=b"abd",  # wrong bytes -> different SHA
    )
    with pytest.raises(ChecksumMismatchError) as excinfo:
        await download_file_with_verification(
            api,
            file_id="file-mismatch",
            s3_fetch=api.fetch_bytes,
        )

    err = excinfo.value
    assert err.file_id == "file-mismatch"
    assert err.expected == ABC_SHA256
    assert err.actual != ABC_SHA256
    assert hashlib.sha256(b"abd").hexdigest() == err.actual

    # The mismatch report MUST have been sent BEFORE the throw.
    actions = [c[0] for c in api.calls]
    assert actions == [
        "get_download_url",
        "fetch_bytes",
        "report_checksum_mismatch",
    ]
    # The reported SHA matches what we actually computed.
    _, args, _ = api.calls[-1]
    assert args == ("file-mismatch", err.actual)


@pytest.mark.asyncio
async def test_download_with_verify_still_raises_when_report_endpoint_fails() -> None:
    from datahub_interoperability.download_verify import download_file_with_verification

    api = FakeFilesAPI(
        download_payload={
            "download_url": "https://s3.example.com/presigned",
            "expires_in": 3600,
            "filename": "data.csv",
            "content_sha256": ABC_SHA256,
        },
        download_blob=b"abd",
        report_raises=RuntimeError("audit endpoint 503"),
    )
    with pytest.raises(ChecksumMismatchError):
        await download_file_with_verification(
            api,
            file_id="file-mismatch",
            s3_fetch=api.fetch_bytes,
        )


@pytest.mark.asyncio
async def test_download_with_verify_skips_when_expected_hash_is_none() -> None:
    from datahub_interoperability.download_verify import download_file_with_verification

    api = FakeFilesAPI(
        download_payload={
            "download_url": "https://s3.example.com/presigned",
            "expires_in": 3600,
            "filename": "old.csv",
            "content_sha256": None,
        },
        download_blob=b"any-bytes",
    )
    result = await download_file_with_verification(
        api,
        file_id="file-old",
        s3_fetch=api.fetch_bytes,
    )
    assert result.status == "skipped"
    assert result.content == b"any-bytes"
    actions = [c[0] for c in api.calls]
    assert "report_checksum_mismatch" not in actions


@pytest.mark.asyncio
async def test_download_with_verify_propagates_fetch_failure_without_audit() -> None:
    from datahub_interoperability.download_verify import download_file_with_verification

    async def failing_fetch(_url: str) -> bytes:
        raise ConnectionError("S3 GET 403 SignatureDoesNotMatch")

    api = FakeFilesAPI(
        download_payload={
            "download_url": "https://s3.example.com/presigned",
            "expires_in": 3600,
            "filename": "x.csv",
            "content_sha256": ABC_SHA256,
        },
        download_blob=b"unused",
    )
    with pytest.raises(ConnectionError, match="SignatureDoesNotMatch"):
        await download_file_with_verification(
            api,
            file_id="file-1",
            s3_fetch=failing_fetch,
        )
    actions = [c[0] for c in api.calls]
    assert "report_checksum_mismatch" not in actions
