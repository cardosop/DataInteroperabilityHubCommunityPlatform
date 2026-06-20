"""
Phase 260.5.F — Schema-inference resource limits with sample-mode fallback.

Closes pass-3 B3-4 (memory exhaustion / OOM kill on multi-GB CSV
schema inference). The original spec proposal was to *refuse*
inference for files above ``DATASET_INFERENCE_MAX_BYTES``; the
review correctly pushed back that a refusal is overly restrictive
when sample-based inference works for the same use case. This
module implements the engineering-grade tiered policy:

* **FULL_READ tier** — files ≤ ``DATASET_INFERENCE_FULL_READ_BYTES``
  (default 50 MB): existing behaviour. Full payload read, full
  inference, no sampled metadata. Most real-world tenants land here.

* **SAMPLE tier** — files between ``DATASET_INFERENCE_FULL_READ_BYTES``
  and ``DATASET_INFERENCE_MAX_BYTES`` (default 50 MB – 1 GB),
  TEXT formats only: ranged read of the first
  ``DATASET_INFERENCE_SAMPLE_BYTES`` (default 50 MB), truncated to
  the last clean format boundary (last newline) so the parser
  doesn't choke on a half-row at the cut. Inference runs on the
  sample; ``inference_metadata.sampled=True`` plus
  ``sample_bytes`` / ``total_bytes`` flag the result. Type
  inference is statistical anyway — 50 MB of a typical CSV is
  ~2.5 M rows, far more than the 10 K-row sample the inference
  helper takes internally.

* **REJECT tier** — files > ``DATASET_INFERENCE_MAX_BYTES``: refuse
  with ``FILE_TOO_LARGE_FOR_INFERENCE`` 400. This is a SANITY
  cap, not an inference cap — files this large usually indicate
  bad upstream tooling (someone uploaded a backup dump as a CSV)
  or a tenant who needs the streaming-pyarrow alternative
  (260.5.F.3, deferred).

Binary formats (PARQUET / XLSX / XLS) cannot be sampled by byte
truncation — Parquet's footer-at-end layout makes a truncated
prefix unreadable, and XLSX is a ZIP archive (truncation breaks
the central directory). Binary formats run FULL_READ up to
``DATASET_INFERENCE_MAX_BYTES`` and REJECT above. Per-format
streaming alternatives (pyarrow footer-only Parquet metadata) are
the right long-term fix and are tracked under 260.5.F.3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from django.conf import settings

from hub.apps.core.services.base import ValidationError

# ---------------------------------------------------------------------------
# Defaults — can be overridden in settings for tenant-specific tuning.
# ---------------------------------------------------------------------------

# Files at-or-below this size run the existing FULL_READ path.
INFERENCE_FULL_READ_BYTES_DEFAULT: int = 50 * 1024 * 1024  # 50 MB

# When a TEXT-format file exceeds the FULL_READ threshold, the
# storage fetch reads only this many bytes. 50 MB of typical CSV
# is ~2.5 M rows — more than 250× the 10 K-row sample the
# downstream inference helper actually uses.
INFERENCE_SAMPLE_BYTES_DEFAULT: int = 50 * 1024 * 1024  # 50 MB

# Files larger than this are refused outright with
# ``FILE_TOO_LARGE_FOR_INFERENCE``. The cap is a sanity / DoS
# limit, not an inference quality gate; sampling handles the
# inference quality concern up to this size.
INFERENCE_MAX_BYTES_DEFAULT: int = 1 * 1024 * 1024 * 1024  # 1 GB

# Formats whose schema can be inferred from a byte-prefix sample.
# Binary container formats (Parquet footer, XLSX central directory)
# cannot — they are FULL_READ only.
_TEXT_SAMPLEABLE_FORMATS: frozenset = frozenset({"CSV", "JSON"})


class InferenceMode(str, Enum):
    """Read mode the dispatch layer should use for this file."""

    FULL_READ = "FULL_READ"
    SAMPLE = "SAMPLE"


@dataclass(frozen=True)
class InferencePlan:
    """Decision record produced by :func:`plan_inference_for_file`.

    Carried into the storage-fetch layer (controls ``max_bytes``)
    and into the schema-inference dispatch (controls metadata
    enrichment). Frozen so accidental mutation in the call chain
    is a build break.
    """

    mode: InferenceMode
    bytes_to_read: int
    total_bytes: int
    is_sampled: bool
    file_format: str

    @property
    def metadata_for_schema(self) -> dict:
        """Subset of fields that should land in
        ``inference_metadata`` so consumers (FE, SDK, contract
        drift) know the schema came from a sample."""
        return {
            "sampled": self.is_sampled,
            "sample_bytes": self.bytes_to_read if self.is_sampled else None,
            "total_bytes": self.total_bytes,
            "row_count_estimated_from_sample": self.is_sampled,
        }


def _full_read_bytes() -> int:
    return int(
        getattr(
            settings,
            "DATASET_INFERENCE_FULL_READ_BYTES",
            INFERENCE_FULL_READ_BYTES_DEFAULT,
        )
    )


def _sample_bytes() -> int:
    return int(
        getattr(
            settings,
            "DATASET_INFERENCE_SAMPLE_BYTES",
            INFERENCE_SAMPLE_BYTES_DEFAULT,
        )
    )


def _max_bytes() -> int:
    return int(
        getattr(
            settings,
            "DATASET_INFERENCE_MAX_BYTES",
            INFERENCE_MAX_BYTES_DEFAULT,
        )
    )


def plan_inference_for_file(
    *,
    file_size: int,
    file_format: str,
) -> InferencePlan:
    """Decide read mode for *file_size* of *file_format*.

    Returns an :class:`InferencePlan` for FULL_READ or SAMPLE.
    Raises :class:`ValidationError` with
    ``code='FILE_TOO_LARGE_FOR_INFERENCE'`` and ``http_status=413``
    when the file exceeds the SANITY cap (``DATASET_INFERENCE_MAX_BYTES``).

    Choice of HTTP 413 (Payload Too Large) over 400: 413 is the
    semantically correct status for "request entity too large"
    and lets generic intermediaries (CDN / WAF) treat the error
    consistently with size-based throttling. The 4xx code IS
    typed (``FILE_TOO_LARGE_FOR_INFERENCE``) so SDK consumers
    can branch precisely.
    """
    if file_size < 0:
        # Defensive — File.size is unsigned by contract, but
        # typed checks at the boundary are cheap.
        raise ValueError(f"file_size must be ≥ 0; got {file_size!r}")

    fmt = (file_format or "").upper()
    full_read_threshold = _full_read_bytes()
    max_threshold = _max_bytes()

    if file_size > max_threshold:
        raise ValidationError(
            (
                f"File of {file_size:,} bytes exceeds the schema-inference "
                f"size cap ({max_threshold:,} bytes). For text formats this "
                f"would normally be sampled, but the upper sanity limit "
                f"protects against pathological uploads (mis-routed backup "
                f"dumps, mis-typed file ids). Split the file into smaller "
                f"chunks, or wait for the streaming-pyarrow alternative "
                f"(spec item 260.5.F.3)."
            ),
            code="FILE_TOO_LARGE_FOR_INFERENCE",
            details={
                "file_size": file_size,
                "max_bytes": max_threshold,
                "full_read_bytes": full_read_threshold,
                "sample_bytes": _sample_bytes(),
                "file_format": fmt,
                "remediation": "split_or_wait_for_streaming_alt",
            },
            http_status=413,
        )

    # Binary formats: cannot be sampled. FULL_READ up to MAX.
    if fmt not in _TEXT_SAMPLEABLE_FORMATS:
        return InferencePlan(
            mode=InferenceMode.FULL_READ,
            bytes_to_read=file_size,
            total_bytes=file_size,
            is_sampled=False,
            file_format=fmt,
        )

    # Text format below FULL_READ threshold: full read.
    if file_size <= full_read_threshold:
        return InferencePlan(
            mode=InferenceMode.FULL_READ,
            bytes_to_read=file_size,
            total_bytes=file_size,
            is_sampled=False,
            file_format=fmt,
        )

    # Text format above FULL_READ. Phase 260.5.F.R1 GAP-C — if the
    # configured SAMPLE byte budget is large enough to cover the
    # whole file, the read would transfer every byte AND the
    # downstream parser would see every row. That is FUNCTIONALLY
    # equivalent to a FULL_READ, so the schema MUST be tagged
    # ``sampled=False`` to avoid misleading FE / contract-drift
    # consumers (a "sampled" flag on a schema produced from the
    # full file would falsely advertise partial-coverage). This
    # matters when an operator overrides ``DATASET_INFERENCE_*``
    # such that ``SAMPLE_BYTES > FULL_READ_BYTES`` — a legitimate
    # configuration (e.g. "sample more than the full-read default
    # for slightly-large files") that without this clause produces
    # contradictory metadata.
    sample_threshold = _sample_bytes()
    if sample_threshold >= file_size:
        return InferencePlan(
            mode=InferenceMode.FULL_READ,
            bytes_to_read=file_size,
            total_bytes=file_size,
            is_sampled=False,
            file_format=fmt,
        )

    # Genuine SAMPLE mode — sample budget strictly less than file.
    return InferencePlan(
        mode=InferenceMode.SAMPLE,
        bytes_to_read=sample_threshold,
        total_bytes=file_size,
        is_sampled=True,
        file_format=fmt,
    )


def truncate_to_clean_boundary(content: bytes, file_format: str) -> bytes:
    """Truncate *content* to the last clean parser boundary.

    For TEXT formats: cut at the last ``\\n`` byte so the parser
    sees only complete rows. Without this, sampling the first 50 MB
    of a 60 MB CSV would leave the LAST row partially constructed
    — csv.DictReader's behaviour on a half-row is dialect-dependent
    (some versions silently drop, some raise). Truncating at the
    last newline guarantees deterministic parsing.

    For BINARY formats (PARQUET / XLSX / XLS): the function is a
    no-op — there is no "clean boundary" inside a binary container
    that doesn't match the format's specific structure (Parquet
    footer offset, XLSX ZIP entry alignment). Binary formats are
    FULL_READ only by ``plan_inference_for_file``, so this function
    isn't called on them in practice; the no-op is defensive in
    case a future caller routes binary content through here.
    """
    fmt = (file_format or "").upper()
    if fmt not in _TEXT_SAMPLEABLE_FORMATS:
        return content
    if not content:
        return content
    last_nl = content.rfind(b"\n")
    if last_nl == -1:
        # No newline at all — no complete row. Return as-is and
        # let the parser handle the edge case (typically results
        # in a single-row "header only" schema, which is the
        # honest outcome for a CSV with no data rows).
        return content
    truncated = content[: last_nl + 1]
    # Edge case (Phase 260.5.F.R2): if the only newline is the one
    # AFTER the CSV header, truncating leaves header-only bytes —
    # ``schema_inference`` then raises ``CSV file is empty or has
    # no headers`` because it needs at least one data row to infer
    # column types. When SAMPLE_BYTES is small enough that even
    # the first data row gets clipped, returning the un-truncated
    # bytes is strictly better: csv.DictReader treats a partial
    # last line as a single complete row in Python 3 (no separator
    # required at EOF), so the parser still produces one usable
    # data row instead of zero.
    if truncated.count(b"\n") <= 1 and last_nl + 1 < len(content):
        return content
    return truncated


__all__ = [
    "INFERENCE_FULL_READ_BYTES_DEFAULT",
    "INFERENCE_MAX_BYTES_DEFAULT",
    "INFERENCE_SAMPLE_BYTES_DEFAULT",
    "InferenceMode",
    "InferencePlan",
    "plan_inference_for_file",
    "truncate_to_clean_boundary",
]
