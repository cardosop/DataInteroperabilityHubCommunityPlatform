"""
Phase 260.3.G — SDK SHA-256 verification + corrupted-download audit.

Pure-stdlib helpers + an asyncio-compatible orchestrator that wraps
:class:`FilesAPI` to download a file, verify its SHA-256 against the
platform-stored hash, and on mismatch report the audit row to the
platform AND raise :class:`ChecksumMismatchError` so caller code
cannot silently hand corrupted bytes back to an integration.

Boundaries
----------
The HTTP boundary is the only side-effect surface:

* :meth:`FilesAPI.get_download_url` returns
  ``{download_url, expires_in, filename, content_sha256}``.
* The S3 GET is performed by ``s3_fetch(url) -> bytes``. Production
  callers pass :func:`fetch_bytes_via_httpx`; tests pass a fake.
* :meth:`FilesAPI.report_checksum_mismatch` POSTs the actual hash to
  the audit endpoint; failures DO NOT mask the
  :class:`ChecksumMismatchError`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Iterator, Optional, Protocol, Union

__all__ = [
    "ChecksumMismatchError",
    "DownloadResult",
    "VerifyResult",
    "compute_sha256",
    "download_file_with_verification",
    "fetch_bytes_via_httpx",
    "sha_equals_constant_time",
    "verify_blob",
]


_SHA256_HEX_LEN = 64


# --------------------------------------------------------------------- #
# Pure helpers                                                          #
# --------------------------------------------------------------------- #


def compute_sha256(data: Union[bytes, Iterable[bytes], Iterator[bytes]]) -> str:
    """Return the lowercase hex SHA-256 digest of ``data``.

    Accepts either a single ``bytes`` blob OR an iterable of byte
    chunks. The chunked path lets callers stream large downloads
    without materialising the full payload in memory.
    """
    hasher = hashlib.sha256()
    if isinstance(data, (bytes, bytearray, memoryview)):
        hasher.update(bytes(data))
    else:
        for chunk in data:
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                raise TypeError(
                    f"compute_sha256 chunks must be bytes-like; got {type(chunk).__name__}"
                )
            hasher.update(bytes(chunk))
    return hasher.hexdigest()


def sha_equals_constant_time(a: object, b: object) -> bool:
    """Constant-time hex SHA-256 equality.

    Returns ``False`` on any non-string input, length mismatch, or
    per-character difference; never raises. The constant-time loop
    only kicks in on the per-character compare; preflight type and
    length checks short-circuit because their failure modes are
    programming bugs (not side-channel targets).
    """
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    if not a or not b:
        return False
    if len(a) != len(b):
        return False
    al = a.lower()
    bl = b.lower()
    diff = 0
    for ca, cb in zip(al, bl):
        diff |= ord(ca) ^ ord(cb)
    return diff == 0


@dataclass(frozen=True)
class VerifyResult:
    """Structured outcome from :func:`verify_blob`."""

    status: str  # "matched" | "mismatched" | "skipped"
    expected: Optional[str]
    actual: Optional[str]
    reason: Optional[str] = None  # populated when status == "skipped"


def verify_blob(content: bytes, expected: Optional[str]) -> VerifyResult:
    """Verify a single blob's SHA-256 against the expected hex digest.

    Returns ``VerifyResult.status``:
      * ``matched``    — hashes agree.
      * ``mismatched`` — hashes disagree; ``actual`` carries the
        computed hex.
      * ``skipped``    — caller passed ``None`` or a malformed
        ``expected``; ``reason`` indicates which.
    """
    if expected is None:
        return VerifyResult(status="skipped", expected=None, actual=None, reason="no-expected-hash")
    if not isinstance(expected, str) or len(expected) != _SHA256_HEX_LEN or not all(
        c in "0123456789abcdefABCDEF" for c in expected
    ):
        return VerifyResult(
            status="skipped", expected=None, actual=None, reason="malformed-expected-hash"
        )
    actual = compute_sha256(content)
    if sha_equals_constant_time(actual, expected):
        return VerifyResult(status="matched", expected=expected.lower(), actual=actual)
    return VerifyResult(status="mismatched", expected=expected.lower(), actual=actual)


# --------------------------------------------------------------------- #
# Orchestrator                                                          #
# --------------------------------------------------------------------- #


class ChecksumMismatchError(RuntimeError):
    """Raised by :func:`download_file_with_verification` on SHA mismatch.

    Carries the file id and both hashes so caller code (CLI, an
    integration, an air-gap copier) can render a precise diagnostic
    or trigger a retry.
    """

    def __init__(self, *, file_id: str, expected: str, actual: str) -> None:
        super().__init__(
            f"Downloaded file SHA-256 does not match the platform-stored hash "
            f"for file {file_id} (expected {expected[:16]}…, got {actual[:16]}…). "
            f"Refusing to deliver corrupted bytes."
        )
        self.file_id = file_id
        self.expected = expected.lower()
        self.actual = actual.lower()


@dataclass(frozen=True)
class DownloadResult:
    """Structured outcome from :func:`download_file_with_verification`."""

    status: str  # "matched" | "skipped"
    content: bytes
    filename: str
    expected: Optional[str]
    actual: Optional[str]


class _FilesAPILike(Protocol):
    """Subset of :class:`FilesAPI` we depend on (kept narrow for testability)."""

    async def get_download_url(self, file_id: str) -> dict[str, Any]: ...

    async def report_checksum_mismatch(
        self, file_id: str, actual_sha256: str
    ) -> dict[str, Any]: ...


S3FetchFn = Callable[[str], Awaitable[bytes]]


async def fetch_bytes_via_httpx(url: str) -> bytes:
    """Default S3 fetch used when the caller doesn't inject one.

    Imported lazily so the SDK's pure-stdlib import path is not
    burdened with httpx for users who never download files.
    """
    import httpx

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def download_file_with_verification(
    files_api: _FilesAPILike,
    *,
    file_id: str,
    s3_fetch: S3FetchFn = fetch_bytes_via_httpx,
) -> DownloadResult:
    """Download ``file_id`` and verify the SHA-256 against the platform hash.

    On ``status='matched'`` (or ``status='skipped'`` for older files
    without a stored hash) returns a :class:`DownloadResult` carrying
    the bytes. On mismatch, posts the actual hash to the platform's
    audit endpoint AND raises :class:`ChecksumMismatchError`. The
    mismatch path keeps the audit-report best-effort (a 5xx on the
    audit endpoint must NOT mask the corruption error).
    """
    payload = await files_api.get_download_url(file_id)
    download_url = payload["download_url"]
    filename = payload.get("filename", "")
    expected = payload.get("content_sha256")

    content = await s3_fetch(download_url)

    result = verify_blob(content, expected)
    if result.status == "matched":
        return DownloadResult(
            status="matched",
            content=content,
            filename=filename,
            expected=result.expected,
            actual=result.actual,
        )
    if result.status == "skipped":
        return DownloadResult(
            status="skipped",
            content=content,
            filename=filename,
            expected=None,
            actual=None,
        )

    # Mismatch — best-effort audit + refuse-to-return.
    actual = result.actual or compute_sha256(content)
    try:
        await files_api.report_checksum_mismatch(file_id, actual)
    except Exception:
        # Audit-endpoint failures must NOT mask the corruption error;
        # the raise below is the load-bearing safety contract.
        pass
    raise ChecksumMismatchError(
        file_id=file_id,
        expected=str(expected),
        actual=actual,
    )
