"""
Integration tests for BUSINESS_LOGIC_INTEGRATION.md documentation.

Validates that the consolidated document (focused on the Business Rules
Framework and chain-based validation) is complete and accurate.
"""

import os

from django.test import TestCase


class BusinessLogicIntegrationDocumentationTest(TestCase):
    """Test suite for BUSINESS_LOGIC_INTEGRATION.md — consolidated doc."""

    def setUp(self):
        self.doc_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "docs",
            "BUSINESS_LOGIC_INTEGRATION.md",
        )

    def _read_doc_content(self):
        with open(self.doc_path, encoding="utf-8") as f:
            return f.read()

    # ── File existence ──────────────────────────────────────────────────

    def test_documentation_file_exists(self):
        self.assertTrue(
            os.path.exists(self.doc_path),
            f"Documentation file not found: {self.doc_path}",
        )

    # ── Business Rules Framework ────────────────────────────────────────

    def test_business_rules_framework_section_exists(self):
        content = self._read_doc_content()
        self.assertIn("## Business Rules Framework", content)

    def test_framework_components_documented(self):
        content = self._read_doc_content()
        self.assertIn("### Framework Components", content)
        self.assertIn("base.py", content)
        self.assertIn("chain_registry.py", content)
        self.assertIn("registry.py", content)

    def test_existing_chains_table_documented(self):
        content = self._read_doc_content()
        self.assertIn("### Existing Chains", content)
        # Verify the known chains are listed
        self.assertIn("contract.publish", content)
        self.assertIn("asset.activate", content)
        self.assertIn("marketplace.listing.publish", content)
        self.assertIn("governance.approval.advance", content)
        self.assertIn("semantic.query.execute", content)

    def test_integration_points_documented(self):
        content = self._read_doc_content()
        self.assertIn("### Integration Points", content)
        self.assertIn("Contract service", content)
        self.assertIn("Asset service", content)
        self.assertIn("Marketplace service", content)
        self.assertIn("Governance service", content)

    def test_decision_tree_documented(self):
        content = self._read_doc_content()
        self.assertIn("### Decision Tree for New Validations", content)
        self.assertIn("execute_chain()", content)

    def test_audit_section_documented(self):
        content = self._read_doc_content()
        self.assertIn("### Audit", content)
        self.assertIn("business_rules", content)

    def test_anti_patterns_documented(self):
        content = self._read_doc_content()
        self.assertIn("### Anti-Patterns to Avoid", content)
        self.assertIn("Bypassing chains", content)
        self.assertIn("Missing tenant scoping", content)

    # ── Virtualization ──────────────────────────────────────────────────

    def test_virtualization_service_documented(self):
        content = self._read_doc_content()
        self.assertIn("#### VirtualizationService", content)
        self.assertIn("VirtualizationService", content)
        self.assertIn("federated query", content)

    def test_virtualization_business_rules_documented(self):
        content = self._read_doc_content()
        self.assertIn("#### Virtualization Business Rules", content)
        self.assertIn("VirtualDatasetValidation", content)
        self.assertIn("FederatedQueryValidation", content)
