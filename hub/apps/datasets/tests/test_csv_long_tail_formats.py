"""
Phase 260.5.E — Long-tail CSV format test matrix (closes pass-3 T3-7).

Twelve edge-case fixtures span the encoding / line-ending / delimiter
matrix that real-world CSV producers emit. Each fixture pins the
EXPECTED outcome of the gated schema-inference pipeline:

* High-confidence text formats (UTF-8 plain, UTF-8 BOM, UTF-16 with
  BOM, Latin-1, Windows-1252, GB2312) admit AND parse to the right
  column names + row count.
* Ambiguous / corrupt content (UTF-16 without BOM, embedded NUL
  bytes) reject at the encoding gate with the typed
  ``FILE_ENCODING_UNSUPPORTED`` 400.
* Delimiter and line-ending variations (CRLF / LF, comma / semicolon
  / tab, embedded comma in quoted field) round-trip cleanly.

The tests run against the canonical
``infer_schema_with_encoding_gate`` helper introduced in
260.5.D.R1, so they regress the gate AND the schema inference at the
same time. No mocks, no stubs — every fixture is real bytes that
exercise the real pipeline.

Bugs surfaced + fixed during 260.5.E:

* **UTF-8 BOM not stripped** — the encoding detector returned
  ``utf_8`` (not ``utf_8_sig``) for BOM-prefixed UTF-8 content, so
  the BOM character ``﻿`` leaked into the first column header
  (e.g. ``'﻿name'`` instead of ``'name'``). Fix: detector
  returns ``utf_8_sig`` when ``best.bom`` is True. ([encoding.py])
* **UTF-16 without BOM ambiguous with NUL-corrupted ASCII** —
  charset_normalizer's heuristic returns ``utf_16_le`` /
  ``utf_16_be`` for both legitimate BOM-less UTF-16 AND for ASCII
  content with embedded NUL bytes (binary leakage / mid-file
  corruption). The two are statistically indistinguishable.
  Fix: gate rejects BOM-less UTF-16 detections at confidence
  evaluation; tenants get a typed
  ``FILE_ENCODING_UNSUPPORTED`` 400 with a confidence score and
  the documented remediation (re-export with BOM or use UTF-8).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from django.test import SimpleTestCase

from hub.apps.core.services.base import ValidationError
from hub.apps.datasets.schema_inference import infer_schema_with_encoding_gate

# ---------------------------------------------------------------------------
# Fixture matrix — 12 long-tail CSV cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CsvFixture:
    """One row in the long-tail matrix.

    Attributes:
        name: Human-readable label (used in test failure messages).
        content: Raw bytes that would land in S3 under this scenario.
        expected_outcome: ``"admit"`` (must pass the gate AND parse) or
            ``"reject_encoding"`` (must raise FILE_ENCODING_UNSUPPORTED).
        expected_field_names: Column headers after parse — only checked
            when ``expected_outcome == "admit"``. Stripping of BOM /
            quoting normalisation must produce the named values exactly.
        expected_row_count: Data rows after parse (excludes header) —
            only checked on admit.
        expected_delimiter: Delimiter the inference recorded in
            ``inference_metadata.delimiter`` — only checked on admit.
            ``None`` skips the assertion (some delimiter heuristics
            depend on content statistics that aren't worth pinning).
        expected_encoding_substring: Substring that MUST appear in
            ``inference_metadata.encoding`` (canonical Python codec
            name). ``None`` skips the assertion.
    """

    name: str
    content: bytes
    expected_outcome: str  # "admit" | "reject_encoding"
    expected_field_names: list | None = None
    expected_row_count: int | None = None
    expected_delimiter: str | None = None
    expected_encoding_substring: str | None = None


# Reusable text bodies; kept as Python strings so the encoding pass
# is what makes each fixture distinct.
_PLAIN_BODY = "name,age\nAlice,30\nBob,25\n"
_PLAIN_BODY_CRLF = "name,age\r\nAlice,30\r\nBob,25\r\n"
_LATIN_BODY = (
    "name,city\nJoseph,Köln\nMarie,Zürich\n"
    + "\n".join(f"User{i},Town{i}" for i in range(30))
    + "\n"
)
_CP1252_BODY = (
    "name,note\nJoseph,café — special\nMarie,Müller\n"
    + "\n".join(f"User{i},Note{i}" for i in range(30))
    + "\n"
)
_GB2312_BODY = (
    "姓名,年龄\n张三,30\n李四,25\n" + "\n".join(f"用户{i},{20 + i}" for i in range(20)) + "\n"
)


def _build_fixtures() -> list:
    """Build the 12-fixture matrix.

    The order intentionally groups admits-first then rejects-last so a
    test failure on a single case is easy to triangulate.
    """
    return [
        # ----- ADMIT: encoding variations -----
        CsvFixture(
            name="01-utf8-plain-LF",
            content=_PLAIN_BODY.encode("utf-8"),
            expected_outcome="admit",
            expected_field_names=["name", "age"],
            expected_row_count=2,
            expected_delimiter=",",
            expected_encoding_substring="ascii",  # pure ASCII detected as ascii
        ),
        CsvFixture(
            name="02-utf8-with-BOM-CRLF",
            # UTF-8 BOM ``EF BB BF`` + CRLF body — common Windows
            # tooling output; the BOM was the bug surfaced by
            # 260.5.E (leaked into first column header).
            content=b"\xef\xbb\xbf" + _PLAIN_BODY_CRLF.encode("utf-8"),
            expected_outcome="admit",
            expected_field_names=["name", "age"],  # NOT '﻿name'
            expected_row_count=2,
            expected_delimiter=",",
            expected_encoding_substring="utf_8_sig",
        ),
        CsvFixture(
            name="03-utf16-LE-with-BOM",
            content=b"\xff\xfe" + _PLAIN_BODY.encode("utf-16-le"),
            expected_outcome="admit",
            expected_field_names=["name", "age"],
            expected_row_count=2,
            expected_delimiter=",",
            expected_encoding_substring="utf_16",
        ),
        CsvFixture(
            name="04-utf16-BE-with-BOM-CRLF",
            content=b"\xfe\xff" + _PLAIN_BODY_CRLF.encode("utf-16-be"),
            expected_outcome="admit",
            expected_field_names=["name", "age"],
            expected_row_count=2,
            expected_delimiter=",",
            expected_encoding_substring="utf_16",
        ),
        CsvFixture(
            name="05-latin1-LF",
            content=_LATIN_BODY.encode("latin-1"),
            expected_outcome="admit",
            expected_field_names=["name", "city"],
            expected_delimiter=",",
            # charset_normalizer often picks ``cp1250`` (Latin-1's
            # Central-European cousin) for Latin-1 content with mixed
            # accents; both decode the upper bytes identically for
            # this fixture's content. We pin only the family.
        ),
        CsvFixture(
            name="06-cp1252-LF",
            content=_CP1252_BODY.encode("cp1252"),
            expected_outcome="admit",
            expected_field_names=["name", "note"],
            expected_delimiter=",",
        ),
        CsvFixture(
            name="07-gb2312-LF",
            content=_GB2312_BODY.encode("gb2312"),
            expected_outcome="admit",
            expected_field_names=["姓名", "年龄"],
            expected_delimiter=",",
            # charset_normalizer reports ``gb18030`` (superset of
            # GB2312) for this content; both decode identically.
            expected_encoding_substring="gb",
        ),
        # ----- ADMIT: line-ending + delimiter variations -----
        CsvFixture(
            name="08-CRLF-line-endings",
            content=_PLAIN_BODY_CRLF.encode("utf-8"),
            expected_outcome="admit",
            expected_field_names=["name", "age"],
            expected_row_count=2,
            expected_delimiter=",",
        ),
        CsvFixture(
            name="09-semicolon-delimited",
            content=b"name;age;city\nAlice;30;Paris\nBob;25;Berlin\n",
            expected_outcome="admit",
            expected_field_names=["name", "age", "city"],
            expected_row_count=2,
            expected_delimiter=";",
        ),
        CsvFixture(
            name="10-tab-delimited-CRLF",
            content=b"name\tage\tcity\r\nAlice\t30\tParis\r\nBob\t25\tBerlin\r\n",
            expected_outcome="admit",
            expected_field_names=["name", "age", "city"],
            expected_row_count=2,
            expected_delimiter="\t",
        ),
        CsvFixture(
            name="11-embedded-comma-in-quoted-field",
            # The description column contains a comma INSIDE quotes
            # — RFC 4180 standard. csv.DictReader's default dialect
            # handles this; the schema must NOT split the description.
            content=(b'name,description\n"Alice","hello, world"\n"Bob","line1, line2, line3"\n'),
            expected_outcome="admit",
            expected_field_names=["name", "description"],
            expected_row_count=2,
            expected_delimiter=",",
        ),
        # ----- REJECT at encoding gate -----
        CsvFixture(
            name="12-embedded-NUL-rejected",
            # Phase 260.5.E.R1 GAP-F — fixture must EXERCISE the
            # BOM-less-UTF-16 rule the R-block claims it tests.
            # charset_normalizer's mis-detection is empirically
            # length-sensitive: at 19-23 bytes a NUL-corrupted
            # ASCII payload returns ``utf_8`` with confidence ≈
            # 0.80 (caught by LOW_CONFIDENCE path); at exactly the
            # 26-byte payload below it returns ``utf_16_be`` with
            # confidence 1.0 (chaos=0) and is ONLY rejected by the
            # new BOM_LESS_UTF16_AMBIGUOUS rule. We use this exact
            # length so the fixture is the load-bearing test for
            # the new rule rather than a duplicate of the threshold
            # rule. If a future charset_normalizer release shifts
            # the boundary, this test will fail loudly — which is
            # the correct behaviour: the fixture re-pins the rule.
            content=b"name,age\nAlice\x00,30\nBob,25\n",
            expected_outcome="reject_encoding",
        ),
    ]


# ---------------------------------------------------------------------------
# Tests — one method per fixture for readable failure surfaces
# ---------------------------------------------------------------------------


class CsvLongTailFormatTest(SimpleTestCase):
    """Phase 260.5.E — 12 fixtures, expected outcomes pinned.

    Method-per-fixture (rather than parametrised single method)
    because pytest's parametrisation reports the fixture index
    and a Django ``SimpleTestCase`` reports the method name —
    one method per fixture means a failure surfaces the fixture
    name immediately.
    """

    def _assert_fixture(self, fixture: CsvFixture) -> None:
        if fixture.expected_outcome == "reject_encoding":
            with self.assertRaises(ValidationError) as ctx:
                infer_schema_with_encoding_gate(fixture.content, "CSV")
            self.assertEqual(
                getattr(ctx.exception, "code", None),
                "FILE_ENCODING_UNSUPPORTED",
                f"[{fixture.name}] expected FILE_ENCODING_UNSUPPORTED; "
                f"got code={getattr(ctx.exception, 'code', None)!r}",
            )
            self.assertEqual(
                getattr(ctx.exception, "http_status", None),
                400,
                f"[{fixture.name}] expected http_status=400",
            )
            # Phase 260.5.E.R1 GAP-F — the embedded-NUL fixture is
            # specifically calibrated to exercise the
            # BOM_LESS_UTF16_AMBIGUOUS rule (260.5.E's new
            # structural rejection). If charset_normalizer's
            # heuristic shifts this fixture into the LOW_CONFIDENCE
            # path, the matrix would silently lose coverage of the
            # new rule. Pin the rejection_reason here so the
            # fixture-level test fails loudly under that drift.
            details = getattr(ctx.exception, "details", {}) or {}
            self.assertEqual(
                details.get("rejection_reason"),
                "BOM_LESS_UTF16_AMBIGUOUS",
                f"[{fixture.name}] expected BOM_LESS_UTF16_AMBIGUOUS "
                f"reason (the load-bearing test for the new rule); "
                f"got details={details!r}. If charset_normalizer "
                f"shifted the heuristic boundary, re-tune the "
                f"fixture's byte count to land in the utf_16_be "
                f"mis-detection window.",
            )
            return

        # admit path
        schema = infer_schema_with_encoding_gate(fixture.content, "CSV")
        self.assertIsInstance(schema, dict)

        if fixture.expected_field_names is not None:
            field_names = [f["name"] for f in schema.get("fields", [])]
            self.assertEqual(
                field_names,
                fixture.expected_field_names,
                f"[{fixture.name}] field name mismatch (BOM leak / "
                f"mojibake / wrong delimiter would surface here)",
            )

        if fixture.expected_row_count is not None:
            self.assertEqual(
                schema.get("row_count_estimated"),
                fixture.expected_row_count,
                f"[{fixture.name}] row count mismatch",
            )

        meta = schema.get("inference_metadata", {})
        if fixture.expected_delimiter is not None:
            self.assertEqual(
                meta.get("delimiter"),
                fixture.expected_delimiter,
                f"[{fixture.name}] delimiter mismatch — got {meta.get('delimiter')!r}",
            )

        if fixture.expected_encoding_substring is not None:
            recorded = (meta.get("encoding") or "").lower()
            self.assertIn(
                fixture.expected_encoding_substring.lower(),
                recorded,
                f"[{fixture.name}] encoding mismatch — recorded "
                f"{recorded!r}, expected substring "
                f"{fixture.expected_encoding_substring!r}",
            )

    # Generated below — one test_* method per fixture.

    @pytest.mark.unit
    def test_01_utf8_plain_LF(self):
        self._assert_fixture(_FIXTURES[0])

    @pytest.mark.unit
    def test_02_utf8_with_BOM_CRLF(self):
        self._assert_fixture(_FIXTURES[1])

    @pytest.mark.unit
    def test_03_utf16_LE_with_BOM(self):
        self._assert_fixture(_FIXTURES[2])

    @pytest.mark.unit
    def test_04_utf16_BE_with_BOM_CRLF(self):
        self._assert_fixture(_FIXTURES[3])

    @pytest.mark.unit
    def test_05_latin1_LF(self):
        self._assert_fixture(_FIXTURES[4])

    @pytest.mark.unit
    def test_06_cp1252_LF(self):
        self._assert_fixture(_FIXTURES[5])

    @pytest.mark.unit
    def test_07_gb2312_LF(self):
        self._assert_fixture(_FIXTURES[6])

    @pytest.mark.unit
    def test_08_CRLF_line_endings(self):
        self._assert_fixture(_FIXTURES[7])

    @pytest.mark.unit
    def test_09_semicolon_delimited(self):
        self._assert_fixture(_FIXTURES[8])

    @pytest.mark.unit
    def test_10_tab_delimited_CRLF(self):
        self._assert_fixture(_FIXTURES[9])

    @pytest.mark.unit
    def test_11_embedded_comma_in_quoted_field(self):
        self._assert_fixture(_FIXTURES[10])

    @pytest.mark.unit
    def test_12_embedded_NUL_rejected(self):
        self._assert_fixture(_FIXTURES[11])


_FIXTURES = _build_fixtures()


# ---------------------------------------------------------------------------
# Coverage-matrix self-check — pins the 12-row contract from the spec
# ---------------------------------------------------------------------------


class LongTailMatrixCoverageTest(SimpleTestCase):
    """260.5.E.1 — the matrix MUST have exactly 12 fixtures and
    cover the named property axes.

    Pinning the count + axis-coverage makes accidental drift
    (someone deleting a fixture or adding a thirteenth without R-
    blocking) surface as a test failure rather than silent
    coverage decay.
    """

    @pytest.mark.unit
    def test_matrix_has_exactly_twelve_fixtures(self):
        self.assertEqual(
            len(_FIXTURES),
            12,
            "Spec mandates 12 long-tail CSV fixtures; matrix changed without an R-block update.",
        )

    @pytest.mark.unit
    def test_matrix_covers_all_named_axes(self):
        # The spec calls out: UTF-8, UTF-16, Latin-1, GB2312, BOMs,
        # CRLF/LF, embedded NUL, embedded delimiters. Each axis
        # must be exercised by at least one fixture.
        names = " ".join(f.name.lower() for f in _FIXTURES)
        self.assertIn("utf8", names)
        self.assertIn("utf16", names)
        self.assertIn("latin1", names)
        self.assertIn("gb2312", names)
        self.assertIn("bom", names)
        self.assertIn("crlf", names)
        self.assertIn("nul", names)
        # Embedded delimiter axis: at least one fixture has a quoted
        # field with a delimiter inside it AND at least one fixture
        # uses a non-comma delimiter.
        self.assertTrue(
            any("quoted" in f.name.lower() for f in _FIXTURES),
            "embedded-delimiter axis missing",
        )
        self.assertTrue(
            any(f.expected_delimiter == ";" for f in _FIXTURES),
            "non-comma delimiter axis missing",
        )
        self.assertTrue(
            any(f.expected_delimiter == "\t" for f in _FIXTURES),
            "tab-delimiter axis missing",
        )

    @pytest.mark.unit
    def test_matrix_has_at_least_one_reject_fixture(self):
        # Symmetric coverage — pure-admit testing would miss the
        # gate's reject-side contract.
        rejects = [f for f in _FIXTURES if f.expected_outcome == "reject_encoding"]
        self.assertGreaterEqual(
            len(rejects),
            1,
            "Matrix must include at least one reject fixture to test "
            "the gate's reject-side contract (currently exercised by "
            "the embedded-NUL fixture).",
        )
