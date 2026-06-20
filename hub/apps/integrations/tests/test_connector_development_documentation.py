#!/usr/bin/env python3
"""
Tests for Connector Development Documentation Validation

Tests verify:
1. Documentation files exist and are complete
2. Code examples are syntactically correct
3. Diagnostic commands are executable
4. References are correct and up-to-date
5. All sections are properly formatted

All tests use real implementations (no mocks/stubs).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

from django.test import TestCase

# Add project root to path for imports
# Test file is at: hub/apps/integrations/tests/test_connector_development_documentation.py
# Project root is 4 levels up
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def find_file_path(relative_path: str) -> Path | None:
    """
    Helper function to find a file path across multiple possible locations.

    Args:
        relative_path: Relative path from project root (e.g., "docs/RUNBOOKS.md")

    Returns:
        Path object if found, None otherwise
    """
    possible_paths = [
        PROJECT_ROOT / relative_path,
        Path("/app") / relative_path,
        Path("/home/ph/Desktop/DataInteroperabilityHub") / relative_path,
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


class TestConnectorDevelopmentDocumentationExists(TestCase):
    """Test that connector development documentation files exist"""

    def test_development_guide_exists(self):
        """Test that DEVELOPMENT.md exists"""
        dev_guide_path = find_file_path("docs/connectors/DEVELOPMENT.md")

        self.assertIsNotNone(dev_guide_path, "DEVELOPMENT.md should exist")
        self.assertTrue(
            dev_guide_path.is_file(), f"DEVELOPMENT.md should be a file: {dev_guide_path}"
        )

    def test_development_guide_not_empty(self):
        """Test that DEVELOPMENT.md is not empty"""
        dev_guide_path = find_file_path("docs/connectors/DEVELOPMENT.md")

        if dev_guide_path and dev_guide_path.exists():
            content = dev_guide_path.read_text()
            self.assertGreater(
                len(content),
                1000,
                "DEVELOPMENT.md should have substantial content (at least 1000 characters)",
            )
        else:
            self.skipTest("DEVELOPMENT.md not found")

    def test_runbooks_updated(self):
        """Test that RUNBOOKS.md includes connector pattern violations section"""
        runbooks_path = find_file_path("docs/RUNBOOKS.md")

        self.assertIsNotNone(runbooks_path, "RUNBOOKS.md should exist")
        content = runbooks_path.read_text()
        self.assertIn(
            "Marketplace Connector Pattern Violations",
            content,
            "RUNBOOKS.md should include 'Marketplace Connector Pattern Violations' section",
        )


class TestConnectorDevelopmentDocumentationStructure(TestCase):
    """Test that connector development documentation has proper structure"""

    def setUp(self):
        """Set up test fixtures"""
        self.dev_guide_path = find_file_path("docs/connectors/DEVELOPMENT.md")

        if not self.dev_guide_path or not self.dev_guide_path.exists():
            raise unittest.SkipTest("DEVELOPMENT.md not found")

        self.content = self.dev_guide_path.read_text()

    def test_has_table_of_contents(self):
        """Test that documentation has table of contents"""
        self.assertIn("Table of Contents", self.content)

    def test_has_overview_section(self):
        """Test that documentation has overview section"""
        self.assertIn("## Overview", self.content)

    def test_has_metadata_first_architecture_section(self):
        """Test that documentation has metadata-first architecture section"""
        self.assertIn("## Metadata-First Architecture", self.content)

    def test_has_implementation_checklist_section(self):
        """Test that documentation has implementation checklist section"""
        self.assertIn("## Connector Implementation Checklist", self.content)

    def test_has_testing_requirements_section(self):
        """Test that documentation has testing requirements section"""
        self.assertIn("## Testing Requirements", self.content)

    def test_has_reference_implementations_section(self):
        """Test that documentation has reference implementations section"""
        self.assertIn("## Reference Implementations", self.content)

    def test_has_common_mistakes_section(self):
        """Test that documentation has common mistakes section"""
        self.assertIn("## Common Mistakes to Avoid", self.content)

    def test_has_best_practices_section(self):
        """Test that documentation has best practices section"""
        self.assertIn("## Best Practices", self.content)


class TestCodeExamplesSyntax(TestCase):
    """Test that code examples in documentation are syntactically correct"""

    def setUp(self):
        """Set up test fixtures"""
        self.dev_guide_path = find_file_path("docs/connectors/DEVELOPMENT.md")

        if not self.dev_guide_path or not self.dev_guide_path.exists():
            raise unittest.SkipTest("DEVELOPMENT.md not found")

        self.content = self.dev_guide_path.read_text()

    def extract_python_code_blocks(self) -> list[dict[str, str]]:
        """Extract Python code blocks from markdown"""
        code_blocks = []
        pattern = r"```python\n(.*?)```"

        for match in re.finditer(pattern, self.content, re.DOTALL):
            code = match.group(1).strip()
            # Skip if it's a comment-only block or too short
            if len(code) > 10 and not code.startswith("#"):
                # Skip blocks that are clearly placeholder examples:
                # - Function signatures with ... (e.g., "def sync_pull(self, ...):")
                # - Blocks that are just showing structure without implementation
                # - Blocks ending with ellipsis
                is_placeholder = (
                    re.search(
                        r"def\s+\w+\([^)]*\.\.\.[^)]*\):", code
                    )  # Function with ... in signature
                    or code.count("...") > 2  # Multiple ... placeholders
                    or (
                        code.endswith("...") and len(code.split("\n")) < 5
                    )  # Short block ending with ...
                )

                if not is_placeholder:
                    code_blocks.append(
                        {"code": code, "line_start": self.content[: match.start()].count("\n") + 1}
                    )

        return code_blocks

    def test_python_code_blocks_syntax(self):
        """Test that all Python code blocks are syntactically correct"""
        code_blocks = self.extract_python_code_blocks()

        self.assertGreater(len(code_blocks), 0, "Documentation should contain Python code examples")

        syntax_errors = []
        for i, block in enumerate(code_blocks):
            try:
                ast.parse(block["code"])
            except SyntaxError as e:
                # Some blocks might be incomplete examples - check if it's a real error
                # Skip blocks that are clearly example snippets (have placeholder comments or incomplete)
                code_lower = block["code"].lower()
                is_example_snippet = any(
                    skip_pattern in code_lower
                    for skip_pattern in [
                        "# ...",
                        "# your implementation",
                        "# placeholder",
                        "pass  #",
                        "def sync_pull(self, ...)",
                        "def map_to_hub_asset(self, listing, ...)",
                        "def download_resource(self, ...",
                    ]
                )

                # Also check if it's a function signature with ... placeholder
                has_placeholder_signature = bool(
                    re.search(r"def\s+\w+\([^)]*\.\.\.[^)]*\):", block["code"])
                )

                # Check if it has ... in function calls or return statements (common in documentation examples)
                has_placeholder_in_calls = bool(
                    re.search(
                        r"(return\s+\w+\([^)]*\.\.\.[^)]*\)|\.\.\s*\)|,\s*\.\.\s*[,)])",
                        block["code"],
                    )
                )

                if (
                    not is_example_snippet
                    and not has_placeholder_signature
                    and not has_placeholder_in_calls
                ):
                    syntax_errors.append(
                        {
                            "block": i + 1,
                            "line": block["line_start"],
                            "error": str(e),
                            "code_preview": block["code"][:150],
                        }
                    )

        if syntax_errors:
            error_messages = "\n".join(
                [
                    f"Block {err['block']} (line {err['line']}): {err['error']}\n  Preview: {err['code_preview']}..."
                    for err in syntax_errors[:5]  # Show first 5 errors
                ]
            )
            self.fail(
                f"Found {len(syntax_errors)} syntax errors in Python code blocks:\n{error_messages}"
            )


class TestDiagnosticCommandsExecutable(TestCase):
    """Test that diagnostic commands in RUNBOOKS.md are executable"""

    def setUp(self):
        """Set up test fixtures"""
        self.runbooks_path = find_file_path("docs/RUNBOOKS.md")

        if not self.runbooks_path or not self.runbooks_path.exists():
            raise unittest.SkipTest("RUNBOOKS.md not found")

        assert self.runbooks_path is not None  # Type narrowing for type checker
        self.content = self.runbooks_path.read_text()

    def extract_python_code_blocks(self) -> list[dict[str, str]]:
        """Extract Python code blocks from markdown"""
        code_blocks = []
        pattern = r"```python\n(.*?)```"

        for match in re.finditer(pattern, self.content, re.DOTALL):
            code = match.group(1).strip()
            # Only extract diagnostic commands (they import models/services)
            if any(
                keyword in code
                for keyword in [
                    "from hub.apps.integrations",
                    "from hub.apps.assets",
                    "MarketplaceSyncJob",
                    "Asset.objects",
                    "connector.sync_pull",
                    "connector.map_to_hub_asset",
                ]
            ):
                code_blocks.append(
                    {"code": code, "line_start": self.content[: match.start()].count("\n") + 1}
                )

        return code_blocks

    def test_diagnostic_commands_syntax(self):
        """Test that diagnostic commands are syntactically correct"""
        code_blocks = self.extract_python_code_blocks()

        self.assertGreater(
            len(code_blocks), 0, "RUNBOOKS.md should contain diagnostic Python commands"
        )

        syntax_errors = []
        for i, block in enumerate(code_blocks):
            try:
                ast.parse(block["code"])
            except SyntaxError as e:
                syntax_errors.append({"block": i + 1, "line": block["line_start"], "error": str(e)})

        if syntax_errors:
            error_messages = "\n".join(
                [
                    f"Block {err['block']} (line {err['line']}): {err['error']}"
                    for err in syntax_errors
                ]
            )
            self.fail(
                f"Found {len(syntax_errors)} syntax errors in diagnostic commands:\n{error_messages}"
            )

    def test_diagnostic_commands_imports_valid(self):
        """Test that diagnostic commands use valid imports"""
        code_blocks = self.extract_python_code_blocks()

        valid_imports = [
            "from hub.apps.integrations.models import",
            "from hub.apps.integrations.factory import",
            "from hub.apps.integrations.base import",
            "from hub.apps.integrations.config.marketplace_instances import",
            "from hub.apps.assets.models import",
            "from django.utils import timezone",
            "from datetime import timedelta",
        ]

        invalid_imports = []
        for i, block in enumerate(code_blocks):
            # Check if imports are valid
            for line in block["code"].split("\n"):
                if line.strip().startswith("from ") or line.strip().startswith("import "):
                    # Check if it's a valid import pattern
                    is_valid = any(valid_pattern in line for valid_pattern in valid_imports)
                    if not is_valid and "hub.apps" in line:
                        invalid_imports.append(
                            {
                                "block": i + 1,
                                "line": line.strip(),
                                "block_line": block["line_start"],
                            }
                        )

        if invalid_imports:
            error_details = "\n".join(
                f"  Block {imp['block']} (line {imp['block_line']}): {imp['line']}"
                for imp in invalid_imports[:10]
            )
            self.fail(
                f"Found {len(invalid_imports)} invalid or unexpected imports in "
                f"diagnostic commands in RUNBOOKS.md.  Either fix the import in "
                f"the documentation or add the new import path to the "
                f"``valid_imports`` list in this test:\n{error_details}"
            )


class TestReferencesCorrect(TestCase):
    """Test that references in documentation are correct"""

    def setUp(self):
        """Set up test fixtures"""
        self.dev_guide_path = find_file_path("docs/connectors/DEVELOPMENT.md")

        if not self.dev_guide_path or not self.dev_guide_path.exists():
            raise unittest.SkipTest("DEVELOPMENT.md not found")

        self.content = self.dev_guide_path.read_text()

    def test_reference_implementations_exist(self):
        """Test that referenced connector files exist"""
        # Check CKAN connector reference
        ckan_path = find_file_path("hub/apps/integrations/connectors/ckan_connector.py")
        self.assertIsNotNone(ckan_path, "CKAN connector should exist (referenced in documentation)")

        # Check DadosGovBr connector reference
        dados_path = find_file_path("hub/apps/integrations/connectors/dados_gov_br_connector.py")
        self.assertIsNotNone(
            dados_path, "DadosGovBr connector should exist (referenced in documentation)"
        )

        # Check Snowflake connector reference
        snowflake_path = find_file_path("hub/apps/integrations/connectors/snowflake_connector.py")
        self.assertIsNotNone(
            snowflake_path, "Snowflake connector should exist (referenced in documentation)"
        )

    def test_pattern_verification_tests_exist(self):
        """Test that referenced pattern verification tests exist"""
        pattern_tests_path = find_file_path("hub/apps/integrations/tests/test_connector_pattern.py")
        self.assertIsNotNone(
            pattern_tests_path,
            "Pattern verification tests should exist (referenced in documentation)",
        )

    def test_base_connector_class_exists(self):
        """Test that base connector class exists"""
        base_path = find_file_path("hub/apps/integrations/base.py")
        self.assertIsNotNone(
            base_path, "Base connector class should exist (referenced in documentation)"
        )

    def test_workflow_file_exists(self):
        """Test that workflow file referenced in documentation exists."""
        self.assertIn(
            "marketplace_sync.py", self.content,
            "DEVELOPMENT.md should reference marketplace_sync.py workflow file"
        )
        workflow_path = find_file_path("hub/apps/orchestration/workflows/marketplace_sync.py")
        self.assertIsNotNone(
            workflow_path, "Workflow file should exist (referenced in documentation)"
        )


class TestDocumentationCompleteness(TestCase):
    """Test that documentation is complete with all required sections"""

    def setUp(self):
        """Set up test fixtures"""
        self.dev_guide_path = find_file_path("docs/connectors/DEVELOPMENT.md")

        if not self.dev_guide_path or not self.dev_guide_path.exists():
            raise unittest.SkipTest("DEVELOPMENT.md not found")

        self.content = self.dev_guide_path.read_text()

    def test_has_sync_pull_examples(self):
        """Test that documentation has sync_pull() examples"""
        # Check for correct example
        self.assertIn("def sync_pull(self, ...):", self.content)
        self.assertIn("mappings.append(mapping)", self.content)
        self.assertIn("SyncResult", self.content)

        # Check for incorrect example (should be marked as wrong)
        self.assertIn("❌", self.content)  # Should have wrong examples marked

    def test_has_map_to_hub_asset_examples(self):
        """Test that documentation has map_to_hub_asset() examples"""
        self.assertIn("def map_to_hub_asset(self,", self.content)
        self.assertIn("MarketplaceAssetMapping", self.content)
        self.assertIn("external", self.content.lower())

    def test_has_download_resource_examples(self):
        """Test that documentation has download_resource() examples"""
        self.assertIn("def download_resource(self,", self.content)
        self.assertIn("destination_path", self.content)

    def test_has_checklist_items(self):
        """Test that documentation has all required checklist items."""
        # Distinct conceptual items (case-insensitive matching handles
        # variations in capitalisation).
        checklist_markers = [
            "sync_pull()",
            "map_to_hub_asset()",
            "download_resource()",
            "push operations",
            "error handling",
        ]

        content_lower = self.content.lower()
        missing_markers = [
            m for m in checklist_markers
            if m not in self.content and m.lower() not in content_lower
        ]

        self.assertEqual(
            len(missing_markers), 0,
            f"Missing checklist items in documentation: {missing_markers}"
        )

    def test_has_test_examples(self):
        """Test that documentation has test examples"""
        self.assertIn("def test_", self.content)
        self.assertIn("pytest", self.content.lower())


class TestRunbooksDiagnosticCommands(TestCase):
    """Test that RUNBOOKS.md diagnostic commands are complete"""

    def setUp(self):
        """Set up test fixtures"""
        self.runbooks_path = find_file_path("docs/RUNBOOKS.md")

        if not self.runbooks_path or not self.runbooks_path.exists():
            raise unittest.SkipTest("RUNBOOKS.md not found")

        assert self.runbooks_path is not None  # Type narrowing for type checker
        self.content = self.runbooks_path.read_text()

    def test_has_pattern_violations_section(self):
        """Test that RUNBOOKS.md has pattern violations section"""
        self.assertIn("## Marketplace Connector Pattern Violations", self.content)

    def test_has_symptoms_section(self):
        """Test that RUNBOOKS.md has symptoms section"""
        self.assertIn("### Symptoms", self.content)

    def test_has_diagnosis_section(self):
        """Test that RUNBOOKS.md has diagnosis section"""
        self.assertIn("### Diagnosis", self.content)

    def test_has_diagnostic_commands(self):
        """Test that RUNBOOKS.md has diagnostic commands"""
        # Check for Python code blocks with diagnostic commands
        python_blocks = re.findall(r"```python\n(.*?)```", self.content, re.DOTALL)

        diagnostic_keywords = [
            "MarketplaceSyncJob",
            "Asset.objects",
            "sync_pull",
            "map_to_hub_asset",
            "download_resource",
        ]

        has_diagnostics = any(
            any(keyword in block for keyword in diagnostic_keywords) for block in python_blocks
        )

        self.assertTrue(has_diagnostics, "RUNBOOKS.md should contain diagnostic Python commands")

    def test_has_common_issues_section(self):
        """Test that RUNBOOKS.md has common issues section"""
        self.assertIn("### Common Issues", self.content)

    def test_has_resolution_steps(self):
        """Test that RUNBOOKS.md has resolution steps"""
        self.assertIn("### Resolution Steps", self.content)
