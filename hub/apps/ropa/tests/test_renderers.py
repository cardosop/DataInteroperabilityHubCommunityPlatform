"""RoPA artefact renderers — real JSON / CSV / DOCX serialization (no mocks)."""

from __future__ import annotations

import json

import pytest
from django.test import TestCase

from hub.apps.ropa.models import RopaOutputFormat
from hub.apps.ropa.services.renderers import render_by_format

pytestmark = pytest.mark.django_db(transaction=True)


class RopaRendererTests(TestCase):
    """``render_by_format`` returns bytes, MIME type, and download filename."""

    def _minimal_payload(self) -> dict:
        return {
            "meta": {"regulation": "GDPR", "asset_count": 1, "cache_version": 0},
            "activities": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "key": "a1",
                    "name": "One",
                    "domain": None,
                    "status": "ACTIVE",
                    "processing_purposes": [{"id": "1", "key": "p1", "name": "Purpose"}],
                    "categories_of_subjects": ["customers"],
                    "recipient_categories": ["processors"],
                    "retention_policies": [],
                }
            ],
            "gaps": [],
        }

    def test_json_roundtrip_readable(self):
        payload = self._minimal_payload()
        raw, mime, fname = render_by_format(RopaOutputFormat.JSON, payload)
        self.assertEqual(mime, "application/json")
        self.assertEqual(fname, "ropa.json")
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["meta"]["regulation"], "GDPR")

    def test_csv_has_header_and_row(self):
        payload = self._minimal_payload()
        raw, mime, fname = render_by_format(RopaOutputFormat.CSV, payload)
        self.assertEqual(mime, "text/csv")
        self.assertEqual(fname, "ropa.csv")
        lines = raw.decode("utf-8").strip().splitlines()
        self.assertGreaterEqual(len(lines), 2)
        self.assertIn("asset_key", lines[0])
        self.assertIn("a1", lines[1])

    def test_docx_non_empty(self):
        payload = self._minimal_payload()
        # ``python-docx`` is an optional renderer dependency (not in
        # the base test container; production images install it).
        # Skip when missing — same shape as the WeasyPrint guard
        # below.
        try:
            raw, mime, fname = render_by_format(RopaOutputFormat.DOCX, payload)
        except ModuleNotFoundError as exc:
            if "docx" in str(exc):
                self.skipTest("python-docx not available in this runtime")
            raise
        self.assertTrue(raw.startswith(b"PK"))  # ZIP / OOXML envelope
        self.assertIn("wordprocessingml", mime)
        self.assertEqual(fname, "ropa.docx")

    def test_pdf_when_weasyprint_available(self):
        payload = self._minimal_payload()
        try:
            raw, mime, fname = render_by_format(RopaOutputFormat.PDF, payload)
        except RuntimeError as exc:
            if "WeasyPrint" in str(exc):
                self.skipTest("WeasyPrint / native libs not available in this runtime")
            raise
        self.assertEqual(mime, "application/pdf")
        self.assertEqual(fname, "ropa.pdf")
        self.assertTrue(raw.startswith(b"%PDF"))

    # ── Phase 277.B.089 — Art. 30 field coverage ────────────────

    def _full_payload(self) -> dict:
        return {
            "meta": {
                "regulation": "GDPR",
                "asset_count": 2,
                "cache_version": 0,
                "controller_name": "Acme Corp",
                "dpo_contact": "dpo@acme.example.com",
                "generated_at": "2026-05-13T12:00:00Z",
                "tenant_name": "Acme Corp",
            },
            "activities": [
                {
                    "id": "a-uuid-1",
                    "key": "customer-db",
                    "name": "Customer Database",
                    "domain": "Marketing",
                    "status": "ACTIVE",
                    "processing_purposes": [
                        {"id": "p1", "key": "marketing", "name": "Marketing"},
                    ],
                    "categories_of_subjects": ["customers", "prospects"],
                    "recipient_categories": ["processors", "affiliates"],
                    "third_country_transfers": ["US"],
                    "transfer_safeguards": "Standard Contractual Clauses",
                    "retention_period": "5 years after last interaction",
                    "retention_policies": [
                        {"name": "Marketing Retention", "key": "mkt-ret-5y"},
                    ],
                    "security_measures": [
                        "Encryption at rest (AES-256)",
                        "Access logging",
                        "Role-based access control",
                    ],
                },
            ],
            "gaps": [
                {
                    "code": "MISSING_PURPOSE",
                    "asset_key": "orphan-db",
                    "message": "No processing purpose defined",
                },
            ],
        }

    def test_html_includes_all_art30_sections(self):
        """HTML template includes all 9 GDPR Art. 30 section headings."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html(self._full_payload())
        sections = [
            "Controller and Data Protection Officer",
            "Purposes of Processing",
            "Categories of Data Subjects",
            "Categories of Recipients",
            "Transfers to Third Countries",
            "Retention Periods",
            "Technical and Organisational Security Measures",
            "Gaps and Completeness",
            "Processing Activities",
        ]
        for sec in sections:
            self.assertIn(sec, html, f"Missing section: {sec}")

    def test_html_includes_controller_and_dpo(self):
        """HTML includes controller name and DPO contact from metadata."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html(self._full_payload())
        self.assertIn("Acme Corp", html)
        self.assertIn("dpo@acme.example.com", html)

    def test_html_includes_third_country_transfers(self):
        """HTML includes third-country transfer info per Art. 30(1)(e)."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html(self._full_payload())
        self.assertIn("US", html)
        self.assertIn("Standard Contractual Clauses", html)

    def test_html_includes_retention_period(self):
        """HTML includes retention period per Art. 30(1)(f)."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html(self._full_payload())
        self.assertIn("5 years after last interaction", html)

    def test_html_includes_security_measures(self):
        """HTML includes security measures per Art. 30(1)(g)."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html(self._full_payload())
        self.assertIn("Encryption at rest", html)
        self.assertIn("Access logging", html)

    def test_html_includes_gaps(self):
        """HTML includes gaps/completeness section."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html(self._full_payload())
        self.assertIn("MISSING_PURPOSE", html)
        self.assertIn("orphan-db", html)

    def test_html_includes_article_reference(self):
        """HTML footer includes GDPR Art. 30 reference."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html(self._full_payload())
        self.assertIn("Article 30", html)

    def test_html_empty_activity_renders_no_rows(self):
        """Empty activities list produces a table with no data rows."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html({"meta": {}, "activities": [], "gaps": []})
        self.assertNotIn("<td>", html)

    def test_html_defaults_missing_metadata(self):
        """Missing metadata fields use safe defaults (Controller, N/A)."""
        from hub.apps.ropa.services.renderers import _ropa_html

        html = _ropa_html({"meta": {}, "activities": [], "gaps": []})
        self.assertIn("Controller", html)
        self.assertIn("N/A", html)
