"""
Phase 260.5.F — Schema-inference resource limits + sample mode.

Pure-unit tests for ``hub.apps.datasets.inference_limits``. No DB,
no S3 — just the planner / truncation primitives. The integration
tests exercising the wired pipeline live in
:mod:`test_dataset_inference_limits_integration`.

The contract under test:

* **FULL_READ tier** — files ≤ FULL_READ threshold → full read
  plan, no sampled metadata.
* **SAMPLE tier** — TEXT-format files between FULL_READ and MAX
  thresholds → sample plan with ``bytes_to_read`` capped at the
  configured sample size, ``is_sampled=True``.
* **REJECT tier** — files > MAX → typed
  ``FILE_TOO_LARGE_FOR_INFERENCE`` 413 with full triage payload.
* **Binary formats** (Parquet / XLSX / XLS) — never SAMPLE-mode
  (the prefix of a binary container isn't parseable); FULL_READ
  up to MAX, then REJECT.
* **Truncation** — text content trims to last newline; binary
  passes through unchanged.
"""
from __future__ import annotations
import pytest

from django.test import SimpleTestCase, override_settings

from hub.apps.core.services.base import ValidationError
from hub.apps.datasets.inference_limits import (
    INFERENCE_FULL_READ_BYTES_DEFAULT,
    INFERENCE_MAX_BYTES_DEFAULT,
    INFERENCE_SAMPLE_BYTES_DEFAULT,
    InferenceMode,
    InferencePlan,
    plan_inference_for_file,
    truncate_to_clean_boundary,
)


class InferenceLimitConstantsTest(SimpleTestCase):
    """Pin the default thresholds so silent re-tuning of any of
    them surfaces as a test failure rather than a quiet behaviour
    shift across deployments."""

    @pytest.mark.unit
    def test_full_read_default_is_50_mb(self):
        self.assertEqual(INFERENCE_FULL_READ_BYTES_DEFAULT, 50 * 1024 * 1024)

    @pytest.mark.unit
    def test_sample_default_is_50_mb(self):
        self.assertEqual(INFERENCE_SAMPLE_BYTES_DEFAULT, 50 * 1024 * 1024)

    @pytest.mark.unit
    def test_max_default_is_1_gb(self):
        # The spec mandates the 1 GB sanity cap.
        self.assertEqual(INFERENCE_MAX_BYTES_DEFAULT, 1 * 1024 * 1024 * 1024)


class PlanInferenceForFileTest(SimpleTestCase):
    """Tier-by-tier planner behaviour."""

    @pytest.mark.unit
    def test_small_csv_returns_full_read_plan(self):
        plan = plan_inference_for_file(file_size=1024, file_format="CSV")
        self.assertEqual(plan.mode, InferenceMode.FULL_READ)
        self.assertEqual(plan.bytes_to_read, 1024)
        self.assertEqual(plan.total_bytes, 1024)
        self.assertFalse(plan.is_sampled)

    @pytest.mark.unit
    def test_csv_at_full_read_boundary_is_full_read(self):
        # File exactly at the FULL_READ threshold MUST take the
        # full-read path. Off-by-one in the comparison would push
        # at-boundary files into SAMPLE mode unnecessarily.
        size = INFERENCE_FULL_READ_BYTES_DEFAULT
        plan = plan_inference_for_file(file_size=size, file_format="CSV")
        self.assertEqual(plan.mode, InferenceMode.FULL_READ)

    @pytest.mark.unit
    def test_csv_above_full_read_threshold_returns_sample_plan(self):
        size = INFERENCE_FULL_READ_BYTES_DEFAULT + 1
        plan = plan_inference_for_file(file_size=size, file_format="CSV")
        self.assertEqual(plan.mode, InferenceMode.SAMPLE)
        self.assertEqual(plan.bytes_to_read, INFERENCE_SAMPLE_BYTES_DEFAULT)
        self.assertEqual(plan.total_bytes, size)
        self.assertTrue(plan.is_sampled)

    @pytest.mark.unit
    def test_json_above_threshold_returns_sample_plan(self):
        # JSON is the OTHER text format the planner samples. Asym-
        # metric coverage between CSV and JSON would let JSON load
        # multi-GB payloads silently.
        size = 200 * 1024 * 1024
        plan = plan_inference_for_file(file_size=size, file_format="JSON")
        self.assertEqual(plan.mode, InferenceMode.SAMPLE)
        self.assertTrue(plan.is_sampled)

    @pytest.mark.unit
    def test_parquet_above_threshold_does_not_sample(self):
        # Parquet's footer-at-end layout makes a byte-prefix sample
        # unreadable; the planner returns FULL_READ until the MAX
        # cap kicks in.
        size = 100 * 1024 * 1024
        plan = plan_inference_for_file(file_size=size, file_format="PARQUET")
        self.assertEqual(plan.mode, InferenceMode.FULL_READ)
        self.assertEqual(plan.bytes_to_read, size)
        self.assertFalse(plan.is_sampled)

    @pytest.mark.unit
    def test_xlsx_above_threshold_does_not_sample(self):
        size = 80 * 1024 * 1024
        plan = plan_inference_for_file(file_size=size, file_format="XLSX")
        self.assertEqual(plan.mode, InferenceMode.FULL_READ)
        self.assertFalse(plan.is_sampled)

    @pytest.mark.unit
    def test_oversize_csv_raises_typed_413(self):
        size = INFERENCE_MAX_BYTES_DEFAULT + 1
        with self.assertRaises(ValidationError) as ctx:
            plan_inference_for_file(file_size=size, file_format="CSV")
        # Spec contract — error code + HTTP 413.
        self.assertEqual(
            getattr(ctx.exception, "code", None), "FILE_TOO_LARGE_FOR_INFERENCE"
        )
        self.assertEqual(getattr(ctx.exception, "http_status", None), 413)

    @pytest.mark.unit
    def test_oversize_parquet_raises_typed_413(self):
        # Symmetric coverage — binary formats hit the same cap.
        size = INFERENCE_MAX_BYTES_DEFAULT + 1
        with self.assertRaises(ValidationError) as ctx:
            plan_inference_for_file(file_size=size, file_format="PARQUET")
        self.assertEqual(
            getattr(ctx.exception, "code", None), "FILE_TOO_LARGE_FOR_INFERENCE"
        )

    @pytest.mark.unit
    def test_oversize_details_carry_full_triage_payload(self):
        size = INFERENCE_MAX_BYTES_DEFAULT * 5
        with self.assertRaises(ValidationError) as ctx:
            plan_inference_for_file(file_size=size, file_format="CSV")
        details = getattr(ctx.exception, "details", {}) or {}
        # Operators reading the 4xx body need: actual size, the
        # cap that fired, both supporting thresholds, the format
        # (so cross-format triage works), and a remediation hint.
        for field in (
            "file_size", "max_bytes", "full_read_bytes",
            "sample_bytes", "file_format", "remediation",
        ):
            self.assertIn(
                field, details,
                f"FILE_TOO_LARGE_FOR_INFERENCE details missing {field!r}; "
                f"got {details!r}",
            )
        self.assertEqual(details["file_size"], size)
        self.assertEqual(details["file_format"], "CSV")

    @pytest.mark.unit
    def test_negative_size_raises_value_error(self):
        # File.size is unsigned by contract; defensive type check
        # surfaces upstream corruption (rare, but cheap to assert).
        with self.assertRaises(ValueError):
            plan_inference_for_file(file_size=-1, file_format="CSV")

    @pytest.mark.unit
    def test_zero_size_is_full_read(self):
        # Empty file is a degenerate-but-legal case (the encoding
        # gate's vacuously-safe case). Plan must NOT raise; the
        # downstream parser handles "no rows" with its own error.
        plan = plan_inference_for_file(file_size=0, file_format="CSV")
        self.assertEqual(plan.mode, InferenceMode.FULL_READ)
        self.assertEqual(plan.bytes_to_read, 0)
        self.assertFalse(plan.is_sampled)


class PlanMetadataTest(SimpleTestCase):
    """The plan's ``metadata_for_schema`` is what flows onto the
    Dataset row's ``inference_metadata`` field. Pin its shape so
    downstream consumers (FE, contract drift) can rely on it."""

    @pytest.mark.unit
    def test_full_read_metadata_omits_sample_bytes(self):
        plan = plan_inference_for_file(file_size=1024, file_format="CSV")
        meta = plan.metadata_for_schema
        self.assertFalse(meta["sampled"])
        self.assertIsNone(meta["sample_bytes"])
        self.assertEqual(meta["total_bytes"], 1024)
        self.assertFalse(meta["row_count_estimated_from_sample"])

    @pytest.mark.unit
    def test_sample_metadata_carries_sample_and_total_bytes(self):
        size = 200 * 1024 * 1024
        plan = plan_inference_for_file(file_size=size, file_format="CSV")
        meta = plan.metadata_for_schema
        self.assertTrue(meta["sampled"])
        self.assertEqual(meta["sample_bytes"], INFERENCE_SAMPLE_BYTES_DEFAULT)
        self.assertEqual(meta["total_bytes"], size)
        self.assertTrue(meta["row_count_estimated_from_sample"])


class TruncateToCleanBoundaryTest(SimpleTestCase):
    """The truncation primitive applied to SAMPLE-mode reads."""

    @pytest.mark.unit
    def test_csv_truncates_to_last_newline(self):
        # A 50 MB ranged read of a 60 MB CSV will land mid-row;
        # the truncation must cut at the last complete row so
        # csv.DictReader doesn't see a half-row at the end.
        content = b"id,name\n1,Alice\n2,Bob\n3,Charl"
        truncated = truncate_to_clean_boundary(content, "CSV")
        self.assertEqual(truncated, b"id,name\n1,Alice\n2,Bob\n")
        self.assertTrue(truncated.endswith(b"\n"))

    @pytest.mark.unit
    def test_csv_with_no_partial_row_is_unchanged(self):
        # Already ends at a newline boundary — return identity.
        content = b"id,name\n1,Alice\n2,Bob\n"
        self.assertEqual(truncate_to_clean_boundary(content, "CSV"), content)

    @pytest.mark.unit
    def test_json_truncates_to_last_newline(self):
        # NDJSON is line-delimited; same truncation rule applies.
        content = b'{"a": 1}\n{"b": 2}\n{"c":'
        truncated = truncate_to_clean_boundary(content, "JSON")
        self.assertEqual(truncated, b'{"a": 1}\n{"b": 2}\n')

    @pytest.mark.unit
    def test_csv_with_no_newline_at_all_is_unchanged(self):
        # Single-row content (header only? data only?) — no clean
        # boundary to cut. Return as-is and let the parser handle.
        content = b"id,name,age"
        self.assertEqual(truncate_to_clean_boundary(content, "CSV"), content)

    @pytest.mark.unit
    def test_parquet_is_a_no_op(self):
        # Binary container — there is no "clean boundary" inside
        # that the byte-prefix truncation can find. Pass through.
        content = b"PAR1\x00\xff\xfd\x00\x00\xab" * 10
        self.assertEqual(truncate_to_clean_boundary(content, "PARQUET"), content)

    @pytest.mark.unit
    def test_xlsx_is_a_no_op(self):
        content = b"PK\x03\x04" + b"\x00" * 100
        self.assertEqual(truncate_to_clean_boundary(content, "XLSX"), content)

    @pytest.mark.unit
    def test_empty_content_is_a_no_op(self):
        self.assertEqual(truncate_to_clean_boundary(b"", "CSV"), b"")


class SettingsOverrideTest(SimpleTestCase):
    """Operator-tunable settings — verify they actually flow
    through the planner. Without this, a settings override would
    silently no-op."""

    @override_settings(DATASET_INFERENCE_MAX_BYTES=10 * 1024)
    @pytest.mark.unit
    def test_max_bytes_override_is_honoured(self):
        # Override tightens the cap to 10 KB; any file above
        # should reject.
        with self.assertRaises(ValidationError) as ctx:
            plan_inference_for_file(file_size=20 * 1024, file_format="CSV")
        self.assertEqual(
            getattr(ctx.exception, "code", None), "FILE_TOO_LARGE_FOR_INFERENCE"
        )

    @override_settings(
        DATASET_INFERENCE_FULL_READ_BYTES=1024,
        # Phase 260.5.F.R1 GAP-C — if ``SAMPLE_BYTES`` covers the
        # whole file, the planner downgrades to FULL_READ (no point
        # tagging "sampled=True" on a read that touched every byte).
        # That downgrade fires here at the default 50 MB sample
        # budget for a 2 KB file. Tighten ``SAMPLE_BYTES`` below
        # ``file_size`` so genuine SAMPLE mode is the legitimate
        # outcome the test is asserting.
        DATASET_INFERENCE_SAMPLE_BYTES=1536,
    )
    @pytest.mark.unit
    def test_full_read_threshold_override_is_honoured(self):
        # Override drops the FULL_READ threshold to 1 KB; any
        # text file above that size should sample.
        plan = plan_inference_for_file(file_size=2048, file_format="CSV")
        self.assertEqual(plan.mode, InferenceMode.SAMPLE)

    @override_settings(DATASET_INFERENCE_SAMPLE_BYTES=8192)
    @pytest.mark.unit
    def test_sample_bytes_override_is_honoured(self):
        # Override caps the SAMPLE read at 8 KB. We need a file
        # LARGER than the sample budget so SAMPLE mode actually
        # fires (otherwise GAP-C would downgrade to FULL_READ).
        size = INFERENCE_FULL_READ_BYTES_DEFAULT + 16384
        plan = plan_inference_for_file(file_size=size, file_format="CSV")
        self.assertEqual(plan.mode, InferenceMode.SAMPLE)
        self.assertEqual(plan.bytes_to_read, 8192)


class SampleCoversWholeFileDowngradeTest(SimpleTestCase):
    """Phase 260.5.F.R1 GAP-C — when ``SAMPLE_BYTES`` covers the
    whole file, the planner MUST downgrade to FULL_READ.

    Without this rule, files between ``FULL_READ_BYTES`` and
    ``SAMPLE_BYTES`` (a legitimate operator-tuning configuration —
    e.g. "sample more than the full-read default for slightly-
    large files") would be tagged ``sampled=True`` even though
    every byte was read. FE / contract-drift consumers would see
    a misleading partial-coverage flag on a schema produced from
    the full payload.
    """

    @override_settings(
        DATASET_INFERENCE_FULL_READ_BYTES=10 * 1024 * 1024,
        DATASET_INFERENCE_SAMPLE_BYTES=50 * 1024 * 1024,
    )
    @pytest.mark.unit
    def test_sample_budget_larger_than_file_is_full_read(self):
        # File 20 MB; FULL_READ threshold 10 MB; SAMPLE budget
        # 50 MB. The 20 MB file is above FULL_READ but the SAMPLE
        # budget covers it entirely → effectively FULL_READ.
        plan = plan_inference_for_file(
            file_size=20 * 1024 * 1024, file_format="CSV"
        )
        self.assertEqual(
            plan.mode, InferenceMode.FULL_READ,
            "SAMPLE budget covers whole file → must downgrade to FULL_READ",
        )
        self.assertFalse(
            plan.is_sampled,
            "Schema metadata MUST NOT advertise sampled=True for a "
            "read that transferred every byte",
        )
        # bytes_to_read equals total — no partial read.
        self.assertEqual(plan.bytes_to_read, plan.total_bytes)

    @override_settings(
        DATASET_INFERENCE_FULL_READ_BYTES=10 * 1024 * 1024,
        DATASET_INFERENCE_SAMPLE_BYTES=50 * 1024 * 1024,
    )
    @pytest.mark.unit
    def test_genuine_partial_read_still_samples(self):
        # File 100 MB; SAMPLE budget 50 MB. 50 MB < 100 MB →
        # genuine partial read → SAMPLE mode.
        plan = plan_inference_for_file(
            file_size=100 * 1024 * 1024, file_format="CSV"
        )
        self.assertEqual(plan.mode, InferenceMode.SAMPLE)
        self.assertTrue(plan.is_sampled)
        self.assertLess(plan.bytes_to_read, plan.total_bytes)

    @override_settings(
        DATASET_INFERENCE_FULL_READ_BYTES=10 * 1024 * 1024,
        DATASET_INFERENCE_SAMPLE_BYTES=20 * 1024 * 1024,
    )
    @pytest.mark.unit
    def test_at_sample_threshold_boundary_is_full_read(self):
        # File size exactly equal to SAMPLE budget → still
        # downgrades (the read covers the whole file).
        plan = plan_inference_for_file(
            file_size=20 * 1024 * 1024, file_format="CSV"
        )
        self.assertEqual(plan.mode, InferenceMode.FULL_READ)
        self.assertFalse(plan.is_sampled)
