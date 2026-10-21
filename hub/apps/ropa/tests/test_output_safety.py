"""W8.3 — RoPA artefact output safety (CSV formula injection + HTML escaping).

The RoPA CSV and the RoPA PDF HTML are built from tenant-controlled
strings (asset names, purpose keys, subject categories, gap messages).
Pre-fix, both rendered them verbatim: a CSV cell beginning with ``=``,
``+``, ``-`` or ``@`` executes as a formula when the download is opened
in Excel/LibreOffice (CWE-1236), and the PDF's HTML template
interpolated values without encoding, letting a hostile asset name
inject markup/CSS into the generated document.

These pins run against the REAL renderers (no mocks) — pure functions,
no database.
"""

from __future__ import annotations

import csv
import io

from django.test import SimpleTestCase

from hub.apps.ropa.models import RopaOutputFormat
from hub.apps.ropa.services.renderers import _ropa_html, render_by_format

# Formula payloads drawn from the CWE-1236 canonical examples.
HOSTILE_ACTIVITY = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "key": "@SUM(1,1)",
    "name": '=HYPERLINK("http://evil.example","click")',
    "status": "ACTIVE",
    "processing_purposes": [{"id": "1", "key": "+cmd|' /C calc'!A0", "name": "Purpose"}],
    "categories_of_subjects": ["-2+3+cmd|' /C calc'!A0"],
    "recipient_categories": ["processors"],
    "retention_policies": [{"id": "r1", "key": "keep-5y", "name": "Keep 5y"}],
}


def _csv_rows(raw: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(raw.decode("utf-8"))))


class RopaCsvFormulaSafetyTests(SimpleTestCase):
    """``render_csv_bytes`` neutralises formula-triggering cells."""

    def _payload(self, activity: dict) -> dict:
        return {
            "meta": {"regulation": "GDPR", "asset_count": 1, "cache_version": 0},
            "activities": [activity],
            "gaps": [],
        }

    def test_csv_neutralises_formula_cells(self):
        raw, mime, _fname = render_by_format(RopaOutputFormat.CSV, self._payload(HOSTILE_ACTIVITY))
        self.assertEqual(mime, "text/csv")
        rows = _csv_rows(raw)

        # Every data cell must be spreadsheet-safe: no cell may start
        # with a formula trigger.
        triggers = ("=", "+", "-", "@", "\t", "\r")
        for row in rows[1:]:
            for cell in row:
                self.assertFalse(
                    cell.startswith(triggers),
                    f"un-neutralised formula cell: {cell!r}",
                )
        # The hostile values are present, guarded.
        self.assertIn("'@SUM(1,1)", [c for r in rows for c in r])
        self.assertIn('\'=HYPERLINK("http://evil.example","click")', [c for r in rows for c in r])

    def test_csv_benign_values_roundtrip_unchanged(self):
        activity = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "key": "customer-db",
            "name": "Customer Database",
            "status": "ACTIVE",
            "processing_purposes": [{"id": "1", "key": "marketing", "name": "Marketing"}],
            "categories_of_subjects": ["customers", "prospects"],
            "recipient_categories": ["processors", "affiliates"],
            "retention_policies": [{"id": "r1", "key": "keep-5y", "name": "Keep 5y"}],
        }
        raw, _, _ = render_by_format(RopaOutputFormat.CSV, self._payload(activity))
        rows = _csv_rows(raw)
        self.assertEqual(rows[0][0], "asset_id")
        data = rows[1]
        self.assertEqual(data[1], "customer-db")
        self.assertEqual(data[2], "Customer Database")
        self.assertEqual(data[4], "marketing")
        self.assertEqual(data[5], "customers,prospects")
        self.assertEqual(data[6], "processors,affiliates")

    def test_csv_retention_count_stays_numeric(self):
        raw, _, _ = render_by_format(RopaOutputFormat.CSV, self._payload(HOSTILE_ACTIVITY))
        rows = _csv_rows(raw)
        self.assertEqual(rows[1][7], "1")  # len(retention_policies), unguarded

    def test_csv_empty_activity_list(self):
        raw, _, _ = render_by_format(
            RopaOutputFormat.CSV, {"meta": {}, "activities": [], "gaps": []}
        )
        rows = _csv_rows(raw)
        self.assertEqual(len(rows), 1)  # header only


class RopaHtmlEscapingTests(SimpleTestCase):
    """``_ropa_html`` HTML-escapes every payload-derived value."""

    def _hostile_payload(self) -> dict:
        return {
            "meta": {
                "regulation": 'GDPR"><img src=x onerror=alert(1)>',
                "asset_count": 1,
                "cache_version": 0,
                "controller_name": "Acme</h1><script>alert(1)</script>",
                "dpo_contact": 'dpo" onmouseover="evil',
                "generated_at": "2026-05-13T12:00:00Z",
                "tenant_name": "Tenant <b>X</b>",
            },
            "activities": [
                {
                    "id": "a-uuid-1",
                    "key": "key</td><td>injected",
                    "name": "<script>alert(1)</script>",
                    "status": "ACTIVE",
                    "processing_purposes": [
                        {"id": "1", "key": "p1", "name": "<img src=x onerror=alert(1)>"}
                    ],
                    "categories_of_subjects": ["<b>subjects</b>"],
                    "recipient_categories": ["a&b <i>inc</i>"],
                    "third_country_transfers": ["<u>US</u>"],
                    "transfer_safeguards": "SCC & More",
                    "retention_period": "5y & counting",
                    "retention_policies": [],
                    "security_measures": ["encrypt</td><td>x"],
                }
            ],
            "gaps": [
                {
                    "code": "MISSING_<b>PURPOSE</b>",
                    "asset_key": "orphan</li><li>injected",
                    "message": 'No purpose "defined" & <script>alert(2)</script>',
                }
            ],
        }

    def test_activity_cells_are_escaped(self):
        html = _ropa_html(self._hostile_payload())
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("key</td><td>injected", html)
        self.assertIn("key&lt;/td&gt;&lt;td&gt;injected", html)

    def test_purposes_subjects_recipients_escaped(self):
        html = _ropa_html(self._hostile_payload())
        self.assertNotIn("<img src=x onerror=alert(1)>", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertNotIn("<b>subjects</b>", html)
        self.assertIn("&lt;b&gt;subjects&lt;/b&gt;", html)
        self.assertIn("a&amp;b &lt;i&gt;inc&lt;/i&gt;", html)

    def test_third_country_retention_measures_escaped(self):
        html = _ropa_html(self._hostile_payload())
        self.assertNotIn("<u>US</u>", html)
        self.assertIn("&lt;u&gt;US&lt;/u&gt;", html)
        self.assertIn("5y &amp; counting", html)
        self.assertNotIn("encrypt</td><td>x", html)
        self.assertIn("encrypt&lt;/td&gt;&lt;td&gt;x", html)

    def test_metadata_is_escaped(self):
        html = _ropa_html(self._hostile_payload())
        self.assertNotIn('GDPR"><img src=x onerror=alert(1)>', html)
        self.assertNotIn("Acme</h1><script>alert(1)</script>", html)
        self.assertNotIn('dpo" onmouseover="evil', html)
        self.assertNotIn("<b>X</b>", html)
        self.assertIn("&lt;b&gt;X&lt;/b&gt;", html)
        # quotes escaped too (attribute-safe even if re-used in attributes)
        self.assertIn("dpo&quot; onmouseover=&quot;evil", html)

    def test_gap_fields_are_escaped(self):
        html = _ropa_html(self._hostile_payload())
        self.assertNotIn("MISSING_<b>PURPOSE</b>", html)
        self.assertIn("MISSING_&lt;b&gt;PURPOSE&lt;/b&gt;", html)
        self.assertNotIn("orphan</li><li>injected", html)
        self.assertNotIn("<script>alert(2)</script>", html)
        self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;", html)

    def test_static_template_markup_survives(self):
        """Only payload-derived values are escaped — the template itself
        (headings, table, footer) must remain intact."""
        html = _ropa_html(self._hostile_payload())
        for marker in (
            "<h1>Record of Processing Activities</h1>",
            "<table>",
            "<thead>",
            "<th>Key</th>",
            "GDPR Art. 30",
            'class="footer-note"',
        ):
            self.assertIn(marker, html)

    def test_benign_html_renders_normally(self):
        payload = {
            "meta": {"regulation": "GDPR", "asset_count": 0, "cache_version": 0},
            "activities": [],
            "gaps": [],
        }
        html = _ropa_html(payload)
        self.assertIn("Controller", html)
        self.assertIn("N/A", html)
