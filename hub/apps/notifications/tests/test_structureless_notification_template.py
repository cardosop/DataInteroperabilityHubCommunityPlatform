"""
Phase 227 L10.9 — notification template renders cleanly.

The template lives at
``notifications/emails/asset_contract_structureless_pending.html`` and is
used at the T-14, T-0, T+7, T+30, T+44 milestones of the structureless-
contract rollout. These tests pin the canonical context shape and the
key copy elements so a stray edit does not silently break the in-app
and email notifications driving the rollout.
"""
from django.test import TestCase, override_settings

from hub.apps.notifications.templates import render_email_template


CANONICAL_CONTEXT = {
    "tenant_name": "Acme Data Co",
    "app_name": "Meshant",
    "deadline_iso": "2026-04-30T00:00:00Z",
    "contracts": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "orders",
            "spec_type": "ODCS",
            "schema_editor_url": (
                "https://stagingmeshant-internal.example.com/contracts/"
                "550e8400-e29b-41d4-a716-446655440000/edit?tab=schema"
            ),
        },
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "name": "customer-events",
            "spec_type": "ODPS",
            "schema_editor_url": (
                "https://stagingmeshant-internal.example.com/contracts/"
                "660e8400-e29b-41d4-a716-446655440001/edit?tab=schema"
            ),
        },
    ],
}

TEMPLATE_NAME = "notifications/emails/asset_contract_structureless_pending.html"


class StructurelessPendingTemplateRenderTest(TestCase):
    """The template must render without raising on the canonical context."""

    def test_renders_html_and_text(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertGreater(len(result["html"]), 0)
        self.assertGreater(len(result["text"]), 0)

    def test_renders_tenant_name(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("Acme Data Co", result["html"])

    def test_renders_app_name(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("Meshant", result["html"])

    def test_renders_deadline_iso(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("2026-04-30T00:00:00Z", result["html"])

    def test_renders_contract_names(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("orders", result["html"])
        self.assertIn("customer-events", result["html"])

    def test_renders_contract_ids(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("550e8400-e29b-41d4-a716-446655440000", result["html"])
        self.assertIn("660e8400-e29b-41d4-a716-446655440001", result["html"])

    def test_renders_spec_types(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("ODCS", result["html"])
        self.assertIn("ODPS", result["html"])

    def test_renders_schema_editor_links(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        for contract in CANONICAL_CONTEXT["contracts"]:
            self.assertIn(contract["schema_editor_url"], result["html"])

    def test_renders_remediation_call_to_action(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("Schema editor", result["html"])
        self.assertIn("Action required", result["html"])

    def test_phase_227_mentions_structureless_programme(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        self.assertIn("Phase 227", result["html"])
        self.assertIn("structureless", result["html"].lower())

    def test_renders_with_no_contracts_falls_back_to_message(self):
        ctx = dict(CANONICAL_CONTEXT, contracts=[])
        result = render_email_template(TEMPLATE_NAME, ctx)
        self.assertIn("No specific contracts attached", result["html"])

    def test_contract_without_schema_editor_url_uses_fallback(self):
        ctx = dict(
            CANONICAL_CONTEXT,
            contracts=[
                {
                    "id": "770e8400-e29b-41d4-a716-446655440002",
                    "name": "noschema",
                    "spec_type": "ODCS",
                    "schema_editor_url": None,
                },
            ],
        )
        result = render_email_template(TEMPLATE_NAME, ctx)
        self.assertIn("Use the Schema editor in Meshant", result["html"])

    def test_contract_without_name_falls_back_to_id(self):
        ctx = dict(
            CANONICAL_CONTEXT,
            contracts=[
                {
                    "id": "880e8400-e29b-41d4-a716-446655440003",
                    "name": "",
                    "spec_type": "ODCS",
                    "schema_editor_url": None,
                },
            ],
        )
        result = render_email_template(TEMPLATE_NAME, ctx)
        self.assertIn("880e8400-e29b-41d4-a716-446655440003", result["html"])

    @override_settings(APP_NAME="Meshant")
    def test_app_name_default_injection_when_omitted(self):
        ctx = dict(CANONICAL_CONTEXT)
        ctx.pop("app_name", None)
        result = render_email_template(TEMPLATE_NAME, ctx)
        # render_email_template injects app_name from settings.APP_NAME.
        self.assertIn("Meshant", result["html"])

    def test_text_version_strips_html_tags(self):
        result = render_email_template(TEMPLATE_NAME, CANONICAL_CONTEXT)
        # html2text (or fallback) should produce plain text with no <table> tags.
        self.assertNotIn("<table", result["text"])
        # Key copy still appears in plain text.  Use whitespace-tolerant
        # matching: html2text wraps long paragraphs at ~80 columns, so
        # "Phase 227" can land split across a newline as "Phase\n227".
        # A regex with ``\s+`` between the words tolerates the line-wrap
        # while still asserting the text mentions the phase by name.
        self.assertIn("Acme Data Co", result["text"])
        self.assertRegex(result["text"], r"Phase\s+227")
