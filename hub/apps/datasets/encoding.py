"""
Phase 260.5.D — Text-encoding detection with confidence gating.

Closes Gap pass-3 B3-16 (silent mojibake from low-confidence decode).

Why this module exists
----------------------
Schema inference and sample-extraction pipelines decode CSV / JSON
file bytes to text BEFORE handing the content to pandas. The legacy
detector at ``schema_inference.detect_encoding`` was a try-each-
encoding loop that returned the FIRST charset whose ``.decode()``
did not raise. That has two failure modes:

1. **Silent mojibake** — Latin-1 decodes ANY byte stream without
   raising (every byte is a valid Latin-1 code point), so a UTF-16
   file mistakenly tried as Latin-1 third in the order would
   "succeed" and pandas would happily parse 2-byte glyphs as
   pairs of garbage characters.
2. **No confidence signal** — operators investigating a malformed
   file in production had no way to ask "how confident is the
   platform that this is UTF-8?" because confidence was never
   computed.

The fix is a real statistical detector (``charset_normalizer``)
plus a hard gate: anything below ``MIN_ENCODING_CONFIDENCE`` is
rejected at the dataset-creation boundary with the stable
``FILE_ENCODING_UNSUPPORTED`` error code, before pandas ever sees
the bytes. Operators see a 400 with a confidence score in
``details`` and can ask the tenant to re-encode (UTF-8) or supply
a binary format.

License posture
---------------
``charset_normalizer`` is **MIT-licensed** (see
``charset_normalizer.__init__.METADATA`` or
``pip show charset-normalizer``) and is already a transitive
dependency of ``requests``. The 260.5.D spec proposed
``chardet`` (LGPL) as the default and ``charset-normalizer`` (MIT)
as the license-clean alternative; we take the alternative because
(a) avoids the LGPL flag for the platform's MIT/Apache mix,
(b) avoids adding a new top-level Python dep when one is already
on the dep tree, (c) ``charset_normalizer`` is the actively-
maintained successor that ``requests`` switched to in 2022.

API
---
* :func:`detect_encoding` — pure detector, returns
  :class:`EncodingDetection` with ``encoding``, ``confidence``,
  ``is_confident``, ``bom`` fields. NEVER raises on detection
  failure — the caller decides what to do with low confidence.
* :func:`validate_text_encoding` — raises
  :class:`hub.apps.core.services.base.ValidationError` with
  ``code='FILE_ENCODING_UNSUPPORTED'`` and ``http_status=400``
  when the gate rejects.
* :data:`MIN_ENCODING_CONFIDENCE` — the threshold (0.9) the
  spec mandates.
"""

from __future__ import annotations

from dataclasses import dataclass

from charset_normalizer import from_bytes

from hub.apps.core.services.base import ValidationError

# Phase 260.5.D.2 — spec-mandated threshold. Confidence is computed
# as ``1.0 - chaos`` from charset_normalizer; chaos is a 0..1
# statistical noise score where 0 is a perfect fit. The 0.9
# threshold corresponds to chaos ≤ 0.1 — empirically the cut-off
# below which charset_normalizer's matches start to include
# implausible candidates (e.g. UTF-16 from short ASCII payloads
# with even byte counts).
MIN_ENCODING_CONFIDENCE: float = 0.9

# Phase 260.5.D — formats this module gates. Binary formats
# (Parquet, Avro, ORC) are not text and have their own header
# inspection; gating them here would produce false positives.
TEXT_FORMATS: frozenset[str] = frozenset({"CSV", "JSON"})


@dataclass(frozen=True)
class EncodingDetection:
    """Result of a single encoding-detection pass.

    ``encoding`` is the canonical Python codec name (``utf_8``,
    ``utf_16_le``, ``cp1252``, ...) — already decode-ready via
    ``bytes.decode(detection.encoding)``.

    ``confidence`` is in [0.0, 1.0] where 1.0 is perfect. Empty
    input is treated as a special case: confidence=1.0 with
    encoding ``ascii`` (vacuously decode-safe). Random bytes that
    charset_normalizer cannot match return confidence=0.0 with
    encoding=None.

    ``bom`` is True if the source bytes opened with a Byte-Order
    Mark (UTF-8 BOM ``EF BB BF``, UTF-16 ``FF FE`` / ``FE FF``,
    UTF-32 BOMs). Useful for downstream serialisation that wants
    to round-trip the BOM rather than silently strip it.
    """

    encoding: str | None
    confidence: float
    is_confident: bool
    bom: bool

    @property
    def chaos(self) -> float:
        """Inverse of confidence — 0.0 is perfect, 1.0 is gibberish."""
        return 1.0 - self.confidence


def detect_encoding(content: bytes) -> EncodingDetection:
    """Detect the most likely encoding of ``content``.

    Pure (no I/O, no exceptions on detection failure). Returns
    a :class:`EncodingDetection` the caller can branch on.

    Edge cases:
    * **Empty bytes** → ``EncodingDetection(encoding='ascii',
      confidence=1.0, is_confident=True, bom=False)``. An empty
      file decodes vacuously to an empty string in any encoding;
      we pick ``ascii`` as the canonical answer because every
      Python codec is a superset of ASCII.
    * **Single-byte ASCII** → high confidence (the empty case
      generalises — pure ASCII content has zero structural
      ambiguity for charset_normalizer's heuristics).
    * **Random bytes** that the detector cannot match →
      ``EncodingDetection(encoding=None, confidence=0.0,
      is_confident=False, bom=False)``. The caller (typically
      :func:`validate_text_encoding`) is responsible for
      rejecting.
    """
    if not content:
        return EncodingDetection(
            encoding="ascii",
            confidence=1.0,
            is_confident=True,
            bom=False,
        )

    matches = from_bytes(content)
    best = matches.best()
    if best is None:
        return EncodingDetection(
            encoding=None,
            confidence=0.0,
            is_confident=False,
            bom=False,
        )

    confidence = max(0.0, min(1.0, 1.0 - best.chaos))
    encoding = best.encoding
    bom = bool(best.bom)

    # Phase 260.5.E — UTF-16 without BOM is genuinely ambiguous.
    # The byte pattern of a BOM-less UTF-16 file is statistically
    # IDENTICAL to ASCII content corrupted with embedded NUL bytes
    # (e.g. binary data leaked into a CSV upload, or a mid-file
    # truncation that left ``\x00`` markers). charset_normalizer
    # returns ``utf_16_le`` / ``utf_16_be`` (with ``bom=False``)
    # for both cases — we cannot distinguish them. The safe default
    # is to refuse: legitimate UTF-16 producers (Excel, Notepad,
    # most exporters) include a BOM, so BOM-less UTF-16 is unusual
    # enough that operator inspection is the right outcome. Rejecting
    # at the gate (via ``is_confident=False``) surfaces the typed
    # ``FILE_ENCODING_UNSUPPORTED`` 400 with a confidence score the
    # operator can investigate; if it's a real BOM-less UTF-16
    # corpus, the tenant adds a BOM and retries.
    if encoding in ("utf_16_le", "utf_16_be") and not bom:
        return EncodingDetection(
            encoding=encoding,
            confidence=confidence,
            is_confident=False,
            bom=False,
        )

    # Phase 260.5.E — UTF-8 with BOM: charset_normalizer reports
    # the encoding as ``utf_8`` (BOM intact in the bytes). Decoding
    # via the ``utf_8`` codec leaves the BOM character ``﻿``
    # at the start of the decoded string, which then leaks into
    # the first CSV column header (e.g. ``'﻿name'`` instead
    # of ``'name'``). Switching the canonical codec name to
    # ``utf_8_sig`` makes ``bytes.decode(encoding)`` strip the BOM
    # automatically — same content, no header pollution. The
    # ``bom=True`` flag is preserved on the result so downstream
    # serialisation can still round-trip the BOM if needed.
    if encoding == "utf_8" and bom:
        encoding = "utf_8_sig"

    return EncodingDetection(
        encoding=encoding,
        confidence=confidence,
        is_confident=confidence >= MIN_ENCODING_CONFIDENCE,
        bom=bom,
    )


def validate_text_encoding(
    content: bytes,
    file_format: str,
) -> EncodingDetection:
    """Phase 260.5.D — gate at the dataset-creation boundary.

    Returns the :class:`EncodingDetection` for downstream callers
    to use the resolved ``encoding`` (avoiding a redundant second
    detection pass in :mod:`schema_inference`).

    Raises :class:`ValidationError` with ``code=
    'FILE_ENCODING_UNSUPPORTED'`` and ``http_status=400`` when:

    * The detector returned ``encoding=None`` (no plausible match
      at all — usually true random bytes, e.g. an encrypted or
      already-compressed payload mis-routed to text inference).
    * The detector returned a match but
      ``confidence < MIN_ENCODING_CONFIDENCE`` — surfacing the
      score so the operator can investigate.
    * Phase 260.5.E: the detector returned BOM-less UTF-16 — a
      structurally ambiguous case (statistically indistinguishable
      from NUL-corrupted ASCII).

    Each rejection path tags ``details.rejection_reason`` with a
    machine-readable token so SDK / FE consumers can distinguish
    them without parsing the human-readable message:

    * ``LOW_CONFIDENCE`` — confidence below the floor (charset_-
      normalizer wasn't sure or returned no match at all).
    * ``BOM_LESS_UTF16_AMBIGUOUS`` — BOM-less UTF-16 detection,
      rejected as a structural rule (260.5.E.GAP-B).

    Binary formats (``PARQUET``, ``AVRO``, ``ORC``) are passed
    through unchecked; they have their own magic-byte header
    inspection elsewhere. ``file_format`` is matched against
    :data:`TEXT_FORMATS` (case-insensitive).
    """
    fmt = (file_format or "").upper()
    if fmt not in TEXT_FORMATS:
        # Binary or unknown — caller should have format-specific
        # validation. Return a neutral "skipped" detection so the
        # caller can still record an audit-trail field.
        return EncodingDetection(
            encoding=None,
            confidence=1.0,
            is_confident=True,
            bom=False,
        )

    detection = detect_encoding(content)
    if detection.is_confident and detection.encoding is not None:
        return detection

    # Phase 260.5.E.R1 GAP-E — distinguish the two reject paths so
    # the operator-facing message is COHERENT. Without the split,
    # a BOM-less UTF-16 rejection would surface as "confidence=1.00,
    # threshold=0.90" — the human reads "above threshold but
    # rejected" and is confused. Tagging the path lets us emit a
    # message that matches the actual reason for refusal.
    if detection.encoding in ("utf_16_le", "utf_16_be") and not detection.bom:
        rejection_reason = "BOM_LESS_UTF16_AMBIGUOUS"
        message = (
            f"BOM-less {detection.encoding.upper()} {fmt} content is "
            f"structurally ambiguous (the byte pattern is statistically "
            f"indistinguishable from NUL-corrupted ASCII / binary "
            f"leakage). Re-export with a UTF-16 BOM (FF FE for LE, "
            f"FE FF for BE) or convert to UTF-8."
        )
    else:
        rejection_reason = "LOW_CONFIDENCE"
        message = (
            f"Charset for {fmt} content could not be confidently detected "
            f"(confidence={detection.confidence:.2f}, threshold="
            f"{MIN_ENCODING_CONFIDENCE:.2f}). Re-encode the file as UTF-8 "
            f"or supply a binary format such as Parquet."
        )

    raise ValidationError(
        message,
        code="FILE_ENCODING_UNSUPPORTED",
        details={
            "file_format": fmt,
            "detected_encoding": detection.encoding,
            "confidence": detection.confidence,
            "min_confidence": MIN_ENCODING_CONFIDENCE,
            "bom": detection.bom,
            "rejection_reason": rejection_reason,
        },
        http_status=400,
    )


__all__ = [
    "MIN_ENCODING_CONFIDENCE",
    "TEXT_FORMATS",
    "EncodingDetection",
    "detect_encoding",
    "validate_text_encoding",
]
