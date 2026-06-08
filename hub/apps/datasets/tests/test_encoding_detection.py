"""
Phase 260.5.D — Encoding-detection unit tests.

These tests run on the pure module (``hub.apps.datasets.encoding``)
with no DB or storage dependency. The integration-layer tests
exercising the gate inside ``DatasetService.create_dataset_from_file``
live in :mod:`test_dataset_encoding_gate`.

The contract under test is:

* The detector returns a structured :class:`EncodingDetection` with
  encoding, confidence, ``is_confident`` flag, and BOM presence.
* Empty input is the vacuously-safe case (confidence=1.0, ASCII).
* Pure ASCII / well-formed UTF-8 / UTF-16 + BOM all clear the
  0.9 threshold and admit.
* Random bytes are rejected by the validator with the stable
  ``FILE_ENCODING_UNSUPPORTED`` code and HTTP 400.
* Binary formats (Parquet) bypass the validator unchecked.
* The ``confidence`` field is a real number in [0.0, 1.0] (not
  None, not an opaque enum) so operators can reason about edge
  cases.
"""
from __future__ import annotations
import pytest

import os

from django.test import SimpleTestCase

from hub.apps.core.services.base import ValidationError
from hub.apps.datasets.encoding import (
    MIN_ENCODING_CONFIDENCE,
    TEXT_FORMATS,
    EncodingDetection,
    detect_encoding,
    validate_text_encoding,
)


class DetectEncodingPureUnitTest(SimpleTestCase):
    """Pure detector — no DB, no I/O."""

    @pytest.mark.unit
    def test_threshold_constant_is_zero_point_nine(self):
        # Phase 260.5.D.2 spec-mandated threshold. Pinning it as a
        # test makes the contract explicit; a future refactor that
        # silently lowers the threshold (e.g. to admit Latin-1
        # marketing exports that confuse the detector) would have
        # to update this test too.
        self.assertEqual(
            MIN_ENCODING_CONFIDENCE,
            0.9,
            "Spec mandates 0.9 confidence floor; do not weaken without R-block.",
        )

    @pytest.mark.unit
    def test_text_formats_includes_csv_and_json(self):
        # Binary formats MUST NOT be in this set — gating Parquet
        # would produce false 400s on legitimate uploads.
        self.assertIn("CSV", TEXT_FORMATS)
        self.assertIn("JSON", TEXT_FORMATS)
        self.assertNotIn("PARQUET", TEXT_FORMATS)
        self.assertNotIn("AVRO", TEXT_FORMATS)
        self.assertNotIn("ORC", TEXT_FORMATS)

    @pytest.mark.unit
    def test_empty_bytes_admit_as_ascii(self):
        # Vacuously safe — an empty file decodes to "" in any
        # codec. ASCII is the canonical answer because every Python
        # codec is a superset of ASCII.
        result = detect_encoding(b"")
        self.assertEqual(result.encoding, "ascii")
        self.assertEqual(result.confidence, 1.0)
        self.assertTrue(result.is_confident)
        self.assertFalse(result.bom)

    @pytest.mark.unit
    def test_pure_ascii_admit_with_full_confidence(self):
        result = detect_encoding(b"name,age\nAlice,30\nBob,25\n")
        self.assertEqual(result.encoding, "ascii")
        self.assertEqual(result.confidence, 1.0)
        self.assertTrue(result.is_confident)

    @pytest.mark.unit
    def test_utf8_with_non_ascii_admit(self):
        content = "café,müller,hôtel\n€,£,¥\n".encode("utf-8")
        result = detect_encoding(content)
        # ``utf_8`` is the canonical Python codec name (not the
        # IANA ``utf-8`` form).
        self.assertEqual(result.encoding, "utf_8")
        self.assertGreaterEqual(
            result.confidence,
            MIN_ENCODING_CONFIDENCE,
            f"Expected confident UTF-8; got {result!r}",
        )
        self.assertTrue(result.is_confident)
        self.assertFalse(result.bom)

    @pytest.mark.unit
    def test_utf8_with_bom_marks_bom_field(self):
        # UTF-8 BOM ``EF BB BF`` is legal in some Windows tooling
        # output. The detector should admit AND record the BOM so
        # downstream serialisation can round-trip it.
        #
        # Phase 260.5.E pinned a stricter contract: when BOM is
        # present, the detector returns ``utf_8_sig`` (NOT
        # ``utf_8``) so that downstream ``bytes.decode(encoding)``
        # automatically strips the BOM. This shifts BOM-handling
        # responsibility from "every caller must remember to use
        # utf-8-sig" to "the detector returns the right codec
        # name". The ``bom=True`` flag is preserved separately so
        # serialisers can still round-trip the BOM if needed.
        content = b"\xef\xbb\xbf" + "hello,world".encode("utf-8")
        result = detect_encoding(content)
        self.assertEqual(
            result.encoding,
            "utf_8_sig",
            "Phase 260.5.E: detector MUST return utf_8_sig for "
            "BOM-prefixed UTF-8 so downstream decode strips the BOM.",
        )
        self.assertTrue(result.bom, "UTF-8 BOM must propagate to result.bom")
        self.assertTrue(result.is_confident)
        # Load-bearing behaviour: decoding via the returned codec
        # MUST strip the BOM from the resulting string. Without
        # this round-trip the column-header bug surfaces in
        # downstream CSV inference.
        decoded = content.decode(result.encoding)
        self.assertFalse(
            decoded.startswith("﻿"),
            f"BOM character leaked through; got {decoded!r}",
        )
        self.assertTrue(decoded.startswith("hello"))

    @pytest.mark.unit
    def test_utf16_with_bom_admit(self):
        # UTF-16 with BOM is unambiguous — confidence MUST clear
        # the threshold. Without enough text the detector can pick
        # ``utf_16``, ``utf_16_le`` or ``utf_16_be`` — assert the
        # FAMILY rather than the exact variant.
        content = "héllo wörld; this row has enough text to be unambiguous".encode(
            "utf-16"
        )
        result = detect_encoding(content)
        self.assertIsNotNone(result.encoding)
        self.assertTrue(result.encoding.startswith("utf_16"))
        self.assertTrue(result.bom)
        self.assertTrue(result.is_confident)

    @pytest.mark.unit
    def test_random_bytes_reject_with_zero_confidence(self):
        # True random bytes — usually no plausible match. If
        # charset_normalizer surprisingly returns a match for some
        # platform-specific reason, the chaos score will be high
        # and the threshold will reject anyway.
        content = os.urandom(2000)
        result = detect_encoding(content)
        self.assertFalse(
            result.is_confident,
            f"Random bytes claimed {result!r}; threshold is broken",
        )

    @pytest.mark.unit
    def test_chaos_property_is_inverse_of_confidence(self):
        result = EncodingDetection(
            encoding="utf_8", confidence=0.85, is_confident=False, bom=False
        )
        self.assertAlmostEqual(result.chaos, 0.15, places=6)


class ValidateTextEncodingTest(SimpleTestCase):
    """Service-boundary gate — raises on confidence floor breach."""

    @pytest.mark.unit
    def test_valid_utf8_csv_returns_detection(self):
        content = b"name,age\nAlice,30\n"
        result = validate_text_encoding(content, "CSV")
        self.assertTrue(result.is_confident)
        self.assertIsNotNone(result.encoding)

    @pytest.mark.unit
    def test_valid_utf8_json_returns_detection(self):
        content = b'{"name": "Alice", "age": 30}'
        result = validate_text_encoding(content, "JSON")
        self.assertTrue(result.is_confident)

    @pytest.mark.unit
    def test_parquet_format_passes_through_unchecked(self):
        # Binary format — gate does NOT inspect the content. Even
        # a payload that would fail CSV gating must pass when
        # format=PARQUET. False positives on Parquet are the
        # primary risk this carve-out closes.
        content = os.urandom(2000)
        result = validate_text_encoding(content, "PARQUET")
        # Returned detection signals "skipped" via is_confident=True
        # and encoding=None (no detection ran).
        self.assertTrue(result.is_confident)
        self.assertIsNone(result.encoding)

    @pytest.mark.unit
    def test_unknown_format_passes_through(self):
        # Caller bears responsibility for unknown formats — the
        # gate is intentionally permissive for formats it cannot
        # reason about.
        content = b"\x00\x01\x02\x03"
        result = validate_text_encoding(content, "AVRO")
        self.assertTrue(result.is_confident)

    @pytest.mark.unit
    def test_lowercase_format_string_normalised(self):
        # File-format strings are uppercased internally so callers
        # that pass ``"csv"`` get the same treatment as ``"CSV"``.
        result = validate_text_encoding(b"a,b\n1,2\n", "csv")
        self.assertTrue(result.is_confident)

    @pytest.mark.unit
    def test_random_bytes_csv_raises_with_stable_code(self):
        content = os.urandom(2000)
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(content, "CSV")
        # Stable contract — SDK / FE consumers branch on this code.
        self.assertEqual(getattr(ctx.exception, "code", None), "FILE_ENCODING_UNSUPPORTED")
        self.assertEqual(getattr(ctx.exception, "http_status", None), 400)
        details = getattr(ctx.exception, "details", {}) or {}
        # The 400 body MUST surface the score so the operator can
        # decide whether to ask the tenant to re-encode or to widen
        # the platform's tolerance for this particular tenant.
        self.assertIn("confidence", details)
        self.assertIn("min_confidence", details)
        self.assertEqual(details["min_confidence"], MIN_ENCODING_CONFIDENCE)
        self.assertEqual(details["file_format"], "CSV")
        self.assertLess(details["confidence"], MIN_ENCODING_CONFIDENCE)

    @pytest.mark.unit
    def test_random_bytes_json_raises(self):
        # JSON path uses the same gate. Asymmetric coverage between
        # CSV and JSON would let the JSON path silently mojibake.
        content = os.urandom(2000)
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(content, "JSON")
        self.assertEqual(
            getattr(ctx.exception, "code", None), "FILE_ENCODING_UNSUPPORTED"
        )

    @pytest.mark.unit
    def test_empty_csv_admits(self):
        # An empty file is a different validation concern (row-
        # count gate, etc.) — the encoding gate must NOT reject it.
        result = validate_text_encoding(b"", "CSV")
        self.assertTrue(result.is_confident)


class ValidationErrorShapeTest(SimpleTestCase):
    """The 400 envelope must carry enough info for triage without
    re-fetching the file."""

    @pytest.mark.unit
    def test_details_payload_carries_encoding_and_score(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(os.urandom(1500), "CSV")
        details = getattr(ctx.exception, "details", {}) or {}
        # Every field operators need:
        #   - file_format: which gate fired
        #   - detected_encoding: best guess (None if no match)
        #   - confidence: actual score
        #   - min_confidence: threshold (so the body is self-
        #     describing — operators don't need to look up the
        #     constant)
        #   - bom: whether the file opens with a BOM (sometimes a
        #     useful triage signal — Windows tooling tends to emit
        #     BOMs)
        for field in ("file_format", "detected_encoding", "confidence", "min_confidence", "bom"):
            self.assertIn(
                field, details,
                f"FILE_ENCODING_UNSUPPORTED details missing field {field!r}; "
                f"got {details!r}",
            )

    @pytest.mark.unit
    def test_message_includes_threshold_for_self_describing_4xx(self):
        # The human-readable message is what shows up in the FE
        # toast. It MUST include both the actual confidence and
        # the threshold so the user can act without reading the
        # ``details`` payload. Pinned for the LOW_CONFIDENCE path
        # only — the BOM_LESS_UTF16_AMBIGUOUS path uses a different
        # message (see ``BomlessUtf16RejectionTest``).
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(os.urandom(1500), "CSV")
        message = getattr(ctx.exception, "message", str(ctx.exception))
        self.assertIn("confidence", message.lower())
        self.assertIn("0.9", message, "Threshold must appear in message")


class BomlessUtf16RejectionTest(SimpleTestCase):
    """Phase 260.5.E.R1 GAP-B + GAP-E — pin the BOM-less UTF-16
    rejection rule and the coherent error contract.

    Two reject paths share ``FILE_ENCODING_UNSUPPORTED`` 400 but
    surface DIFFERENT messages + ``rejection_reason`` tags:

    * ``LOW_CONFIDENCE`` — charset_normalizer scored below the
      0.9 floor (e.g. random bytes).
    * ``BOM_LESS_UTF16_AMBIGUOUS`` — detector returned
      ``utf_16_le`` / ``utf_16_be`` with no BOM. We refuse
      because the byte pattern is statistically indistinguishable
      from NUL-corrupted ASCII; legit UTF-16 producers always
      include a BOM.
    """

    @pytest.mark.unit
    def test_pure_utf16_le_no_bom_rejected_with_typed_reason(self):
        # Genuine UTF-16-LE content with no BOM. charset_normalizer
        # detects ``utf_16_le`` with confidence 1.0 — without the
        # 260.5.E rule, this would PASS the gate and silently
        # decode (potentially OK, but indistinguishable from
        # corruption — see ``test_short_nul_corrupted_ascii_*``).
        body = (
            "name,age\nAlice,30\nBob,25\n"
            "Charlie,40\nDave,28\nEve,55\n"
        )
        content = body.encode("utf-16-le")
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(content, "CSV")
        details = getattr(ctx.exception, "details", {}) or {}
        self.assertEqual(
            details.get("rejection_reason"),
            "BOM_LESS_UTF16_AMBIGUOUS",
            f"BOM-less UTF-16 must tag rejection_reason; got {details!r}",
        )
        self.assertIn(
            "utf_16",
            (details.get("detected_encoding") or ""),
            "Detected encoding must be preserved in details for triage",
        )
        self.assertFalse(details.get("bom"))

    @pytest.mark.unit
    def test_short_nul_corrupted_ascii_rejected_via_utf16_path(self):
        # 26-byte ASCII content with one embedded NUL byte. At
        # this exact length charset_normalizer mis-detects as
        # ``utf_16_be`` with confidence 1.0 (the NUL/non-NUL
        # byte pattern matches UTF-16-BE statistics); shorter or
        # longer payloads land in the LOW_CONFIDENCE path. The
        # BOM_LESS_UTF16 rule is the load-bearing reject for this
        # narrow band; without it, the gate would admit confidence
        # =1.0 and the user would see "CSV file is empty or has
        # no headers" downstream from the gibberish decode.
        content = b"name,age\nAlice\x00,30\nBob,25\n"
        assert len(content) == 26, "fixture re-tuned: drift detected"
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(content, "CSV")
        details = getattr(ctx.exception, "details", {}) or {}
        # The reason tag is what guarantees this test exercises
        # the new rule rather than the threshold path.
        self.assertEqual(
            details.get("rejection_reason"),
            "BOM_LESS_UTF16_AMBIGUOUS",
            f"Short NUL-corrupted ASCII should hit the BOM_LESS_UTF16 "
            f"path; got {details!r}",
        )

    @pytest.mark.unit
    def test_low_confidence_path_tags_LOW_CONFIDENCE(self):
        # Random bytes — no plausible match. Pinning the tag here
        # ensures the two reject paths stay distinguishable.
        content = os.urandom(2000)
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(content, "CSV")
        details = getattr(ctx.exception, "details", {}) or {}
        self.assertEqual(
            details.get("rejection_reason"),
            "LOW_CONFIDENCE",
            f"Random bytes must tag LOW_CONFIDENCE; got {details!r}",
        )

    @pytest.mark.unit
    def test_bomless_utf16_message_does_not_lie_about_confidence(self):
        # GAP-E regression: the original message said "could not
        # be confidently detected (confidence=1.00, threshold=
        # 0.90)" for BOM-less UTF-16 — confidence above threshold
        # but reject. The new message MUST NOT make that claim;
        # it should explain the structural reason.
        body = "name,age\n" + "\n".join(f"row{i},{i}" for i in range(20))
        content = body.encode("utf-16-le")
        with self.assertRaises(ValidationError) as ctx:
            validate_text_encoding(content, "CSV")
        message = getattr(ctx.exception, "message", str(ctx.exception))
        self.assertIn(
            "BOM",
            message,
            f"BOM-less UTF-16 message must mention BOM; got {message!r}",
        )
        self.assertNotIn(
            "could not be confidently detected",
            message,
            "BOM-less UTF-16 must NOT use the LOW_CONFIDENCE message; "
            "the detector WAS confident — we refuse on a structural "
            "rule, not a confidence floor.",
        )

    @pytest.mark.unit
    def test_bomless_utf16_with_bom_admits_unchanged(self):
        # Sanity / regression: legitimate UTF-16 WITH BOM must
        # continue to admit. ``utf-16-le`` ENCODE + leading BOM
        # bytes ``\xff\xfe`` is the well-formed shape.
        body = "name,age\nAlice,30\nBob,25\n"
        content = b"\xff\xfe" + body.encode("utf-16-le")
        result = validate_text_encoding(content, "CSV")
        self.assertTrue(result.is_confident)
        self.assertTrue(result.bom)
        # charset_normalizer canonicalises to ``utf_16`` (no LE/BE
        # suffix) when BOM is present; Python's ``utf_16`` codec
        # auto-detects byte order from the BOM.
        self.assertEqual(result.encoding, "utf_16")


class GatedInferenceDispatchTest(SimpleTestCase):
    """Phase 260.5.D.R1 — canonical gated dispatch helper.

    The audit-pass discovery was that the gate had been wired
    into ``services.py`` only — ``refresh.py``,
    ``worker_services.py``, and ``ingestion.py`` had their own
    format-dispatch blocks that bypassed the gate. The fix is
    encapsulation: ``infer_schema_with_encoding_gate`` is the
    SINGLE entry point all callers MUST use. These tests pin the
    contract so a future drift cannot recur silently.
    """

    @pytest.mark.unit
    def test_helper_is_a_module_export(self):
        # Pinned as a regression: removing the helper from the
        # module surface would cause every caller to ImportError
        # at runtime — a loud failure, but the test catches it
        # at static-analysis time.
        from hub.apps.datasets import schema_inference

        self.assertTrue(
            hasattr(schema_inference, "infer_schema_with_encoding_gate"),
            "Canonical gated helper must be a public module attribute",
        )

    @pytest.mark.unit
    def test_csv_with_valid_utf8_dispatches_to_csv_inference(self):
        from hub.apps.datasets.schema_inference import (
            infer_schema_with_encoding_gate,
        )

        body = b"id,name\n1,alice\n2,bob\n"
        schema = infer_schema_with_encoding_gate(body, "CSV")
        # ``infer_schema_from_csv`` returns a dict shape; we don't
        # over-couple to its keys here — just assert it produced
        # SOMETHING usable, not the empty dict the worker fallback
        # would have produced under the old (gate-bypassing)
        # dispatch.
        self.assertIsInstance(schema, dict)
        self.assertNotEqual(schema, {})

    @pytest.mark.unit
    def test_csv_with_random_bytes_raises_typed_error_through_helper(self):
        from hub.apps.datasets.schema_inference import (
            infer_schema_with_encoding_gate,
        )

        with self.assertRaises(ValidationError) as ctx:
            infer_schema_with_encoding_gate(os.urandom(2000), "CSV")
        # Same code as the bare gate — callers don't need to know
        # the helper exists to handle the typed error.
        self.assertEqual(
            getattr(ctx.exception, "code", None), "FILE_ENCODING_UNSUPPORTED"
        )
        self.assertEqual(getattr(ctx.exception, "http_status", None), 400)

    @pytest.mark.unit
    def test_unsupported_format_raises_typed_error(self):
        # ``AVRO`` / ``ORC`` / unknown formats — the helper must
        # raise a TYPED ValidationError (code=UNSUPPORTED_FILE_FORMAT)
        # so callers can distinguish "format not supported" from
        # "encoding not detected" and from "inference failed".
        from hub.apps.datasets.schema_inference import (
            infer_schema_with_encoding_gate,
        )

        with self.assertRaises(ValidationError) as ctx:
            infer_schema_with_encoding_gate(b"irrelevant", "AVRO")
        self.assertEqual(
            getattr(ctx.exception, "code", None), "UNSUPPORTED_FILE_FORMAT"
        )

    @pytest.mark.unit
    def test_parquet_skips_encoding_gate(self):
        # Binary format — the gate must NOT inspect the content.
        # We pass random bytes; the parquet parser will raise its
        # own error (NOT FILE_ENCODING_UNSUPPORTED). Catching the
        # broad Exception is the right test posture: we care that
        # the gate didn't fire, not what happens downstream.
        from hub.apps.datasets.schema_inference import (
            infer_schema_with_encoding_gate,
        )

        try:
            infer_schema_with_encoding_gate(os.urandom(100), "PARQUET")
        except ValidationError as e:
            self.assertNotEqual(
                getattr(e, "code", None),
                "FILE_ENCODING_UNSUPPORTED",
                "Parquet must NOT trigger the text-encoding gate",
            )
        except Exception:
            # Parquet parser raised — that's fine; it's not the
            # encoding gate's concern.
            pass
