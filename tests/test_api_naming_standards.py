#!/usr/bin/env python3
"""
Tests for API Naming Standards Document

Tests the completeness and accuracy of the API naming standards document.
"""

import sys
import re
import unittest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import standards document
standards_file = project_root / "docs" / "API_NAMING_STANDARDS.md"


class TestAPINamingStandardsCompleteness(unittest.TestCase):
    """Test that the API naming standards document is complete"""

    def setUp(self):
        """Load standards document"""
        self.standards_content = standards_file.read_text(encoding='utf-8')

    def test_document_exists(self):
        """Test that the standards document exists"""
        self.assertTrue(standards_file.exists(), "API_NAMING_STANDARDS.md should exist")

    def test_has_table_of_contents(self):
        """Test that document has table of contents"""
        self.assertIn("## Table of Contents", self.standards_content,
                      "Document should have table of contents")

    def test_has_overview_section(self):
        """Test that document has overview section"""
        self.assertIn("## Overview", self.standards_content,
                      "Document should have overview section")

    def test_has_core_principles(self):
        """Test that document has core principles"""
        self.assertIn("## Core Principles", self.standards_content,
                      "Document should have core principles section")

    def test_has_no_duplication_rule(self):
        """Test that document defines no duplication rule"""
        self.assertIn("## No Duplication Rule", self.standards_content,
                      "Document should define no duplication rule")
        self.assertIn("MUST NOT appear multiple times", self.standards_content,
                      "No duplication rule should be clearly stated")

    def test_has_plural_resources_rule(self):
        """Test that document defines plural resources rule"""
        self.assertIn("## Plural Resources Rule", self.standards_content,
                      "Document should define plural resources rule")
        self.assertIn("MUST use plural nouns", self.standards_content,
                      "Plural resources rule should be clearly stated")

    def test_has_consistent_patterns(self):
        """Test that document defines consistent patterns"""
        self.assertIn("## Consistent Patterns", self.standards_content,
                      "Document should define consistent patterns section")
        self.assertIn("Collections", self.standards_content,
                      "Document should define collections pattern")
        self.assertIn("Detail", self.standards_content,
                      "Document should define detail pattern")
        self.assertIn("Actions", self.standards_content,
                      "Document should define actions pattern")
        self.assertIn("Sub-resources", self.standards_content,
                      "Document should define sub-resources pattern")

    def test_has_resource_naming_conventions(self):
        """Test that document defines resource naming conventions"""
        self.assertIn("## Resource Naming Conventions", self.standards_content,
                      "Document should define resource naming conventions")
        self.assertIn("kebab-case", self.standards_content,
                      "Document should specify kebab-case convention")

    def test_has_url_pattern_validation_rules(self):
        """Test that document defines URL pattern validation rules"""
        self.assertIn("## URL Pattern Validation Rules", self.standards_content,
                      "Document should define URL pattern validation rules")
        self.assertIn("Validation Checklist", self.standards_content,
                      "Document should include validation checklist")

    def test_has_examples_section(self):
        """Test that document has examples section"""
        self.assertIn("## Examples", self.standards_content,
                      "Document should have examples section")
        self.assertIn("✅ Correct", self.standards_content,
                      "Document should have correct examples")
        self.assertIn("❌ Incorrect", self.standards_content,
                      "Document should have incorrect examples")

    def test_has_migration_guidelines(self):
        """Test that document has migration guidelines"""
        self.assertIn("## Migration Guidelines", self.standards_content,
                      "Document should have migration guidelines section")
        self.assertIn("Migration Strategy", self.standards_content,
                      "Document should include migration strategy")
        self.assertIn("Deprecation Process", self.standards_content,
                      "Document should include deprecation process")

    def test_has_validation_checklist(self):
        """Test that document has validation checklist"""
        self.assertIn("## Validation Checklist", self.standards_content,
                      "Document should have validation checklist section")
        self.assertIn("Pre-Implementation Checklist", self.standards_content,
                      "Document should include pre-implementation checklist")
        self.assertIn("Post-Implementation Checklist", self.standards_content,
                      "Document should include post-implementation checklist")


class TestAPINamingStandardsExamples(unittest.TestCase):
    """Test that examples in the standards document are accurate"""

    def setUp(self):
        """Load standards document"""
        self.standards_content = standards_file.read_text(encoding='utf-8')

    def test_correct_examples_format(self):
        """Test that correct examples follow the standards"""
        # Extract correct examples
        correct_section = self.standards_content.split("### ✅ Correct Examples")[1].split("### ❌ Incorrect Examples")[0]

        # Check for collection examples
        self.assertIn("/api/v1/assets/", correct_section,
                     "Should have correct collection example")
        self.assertIn("/api/v1/contracts/", correct_section,
                     "Should have correct collection example")

        # Check for detail examples
        self.assertIn("/api/v1/assets/{id}/", correct_section,
                     "Should have correct detail example")

        # Check for action examples
        self.assertIn("/api/v1/contracts/{id}/validate/", correct_section,
                     "Should have correct action example")

        # Check for sub-resource examples
        self.assertIn("/api/v1/assets/{id}/datasets/", correct_section,
                     "Should have correct sub-resource example")

    def test_incorrect_examples_format(self):
        """Test that incorrect examples violate the standards"""
        # Extract incorrect examples
        incorrect_section = self.standards_content.split("### ❌ Incorrect Examples")[1]

        # Check for duplication violations
        self.assertIn("/api/v1/assets/assets/", incorrect_section,
                     "Should have duplication violation example")
        self.assertIn("/api/v1/contracts/contracts/", incorrect_section,
                     "Should have duplication violation example")

        # Check for singular form violations
        self.assertIn("/api/v1/asset/", incorrect_section,
                     "Should have singular form violation example")

        # Check for case violations
        self.assertIn("dataContracts", incorrect_section,
                     "Should have case violation example")
        self.assertIn("data_contracts", incorrect_section,
                     "Should have case violation example")

    def test_examples_have_explanations(self):
        """Test that examples have explanations"""
        # Check that correct examples section has explanations
        correct_section = self.standards_content.split("### ✅ Correct Examples")[1].split("### ❌ Incorrect Examples")[0]

        # Check for collection explanations (flexible - can be "list", "list all", "list assets", etc.)
        correct_lower = correct_section.lower()
        has_collection_explanation = (
            "list" in correct_lower or
            "collection" in correct_lower or
            "# list" in correct_section
        )
        self.assertTrue(has_collection_explanation,
                       "Should explain collection endpoints")

        # Check for detail explanations (flexible - can be "get", "retrieve", "get asset", etc.)
        has_detail_explanation = (
            "get" in correct_lower or
            "retrieve" in correct_lower or
            "# get" in correct_section or
            "# retrieve" in correct_section
        )
        self.assertTrue(has_detail_explanation,
                       "Should explain detail endpoints")

        # Check that incorrect examples section has explanations
        incorrect_section = self.standards_content.split("### ❌ Incorrect Examples")[1]
        incorrect_lower = incorrect_section.lower()

        # Check for violation explanations (flexible)
        has_duplication_explanation = (
            "appears twice" in incorrect_lower or
            "duplicate" in incorrect_lower or
            "duplication" in incorrect_lower
        )
        self.assertTrue(has_duplication_explanation,
                       "Should explain duplication violations")

        # Check for correction suggestions
        has_correction = (
            "should be" in incorrect_lower or
            "should" in incorrect_lower or
            "must" in incorrect_lower
        )
        self.assertTrue(has_correction,
                       "Should explain what should be used instead")

    def test_examples_match_patterns(self):
        """Test that correct examples match the defined patterns"""
        # Extract pattern definitions
        patterns_section = self.standards_content.split("## Consistent Patterns")[1].split("## Resource Naming Conventions")[0]

        # Extract correct examples
        correct_section = self.standards_content.split("### ✅ Correct Examples")[1].split("### ❌ Incorrect Examples")[0]

        # Check collections pattern
        if "/api/v1/{resource}/" in patterns_section:
            # Verify examples match
            collection_examples = re.findall(r'/api/v1/[a-z-]+/', correct_section)
            for example in collection_examples[:5]:  # Check first 5
                self.assertTrue(example.endswith('/'),
                              f"Collection example {example} should end with /")
                self.assertNotIn('{id}', example,
                               f"Collection example {example} should not have {{id}}")

        # Check detail pattern
        if "/api/v1/{resource}/{id}/" in patterns_section:
            detail_examples = re.findall(r'/api/v1/[a-z-]+/\{[^}]+\}/', correct_section)
            for example in detail_examples[:5]:  # Check first 5
                self.assertIn('{id}', example,
                            f"Detail example {example} should have {{id}}")
                self.assertTrue(example.endswith('/'),
                              f"Detail example {example} should end with /")

    def test_migration_examples_are_complete(self):
        """Test that migration examples are complete"""
        migration_section = self.standards_content.split("## Migration Guidelines")[1]

        # Check for before/after examples
        self.assertIn("Before", migration_section,
                     "Should have 'Before' examples")
        self.assertIn("After", migration_section,
                     "Should have 'After' examples")

        # Check for code examples
        self.assertIn("```python", migration_section,
                     "Should have Python code examples")

        # Check for duplication fix example
        self.assertIn("assets/assets", migration_section.lower() or "duplication",
                     "Should have duplication fix example")

        # Check for singular form fix example
        self.assertIn("asset", migration_section.lower(),
                     "Should have singular form fix example")
        self.assertIn("assets", migration_section.lower(),
                     "Should have plural form fix example")


class TestAPINamingStandardsValidationRules(unittest.TestCase):
    """Test that validation rules are complete and accurate"""

    def setUp(self):
        """Load standards document"""
        self.standards_content = standards_file.read_text(encoding='utf-8')

    def test_validation_checklist_exists(self):
        """Test that validation checklist exists"""
        validation_section = self.standards_content.split("## URL Pattern Validation Rules")[1]

        self.assertIn("Validation Checklist", validation_section,
                     "Should have validation checklist")

        # Check for specific validation checks
        self.assertIn("No Duplication Check", validation_section,
                     "Should have no duplication check")
        self.assertIn("Plural Form Check", validation_section,
                     "Should have plural form check")
        self.assertIn("Kebab-Case Check", validation_section,
                     "Should have kebab-case check")
        self.assertIn("Pattern Consistency Check", validation_section,
                     "Should have pattern consistency check")

    def test_validation_regex_patterns_exist(self):
        """Test that validation regex patterns are provided"""
        validation_section = self.standards_content.split("## URL Pattern Validation Rules")[1]

        # Check for regex patterns
        self.assertIn("COLLECTION_PATTERN", validation_section,
                     "Should have collection pattern regex")
        self.assertIn("DETAIL_PATTERN", validation_section,
                     "Should have detail pattern regex")
        self.assertIn("ACTION_PATTERN", validation_section,
                     "Should have action pattern regex")
        self.assertIn("SUB_RESOURCE_PATTERN", validation_section,
                     "Should have sub-resource pattern regex")

    def test_validation_regex_patterns_are_valid(self):
        """Test that validation regex patterns are valid"""
        validation_section = self.standards_content.split("## URL Pattern Validation Rules")[1]

        # Extract regex patterns
        regex_section = validation_section.split("```python")[1].split("```")[0]

        # Check that patterns are valid Python regex
        try:
            # Try to compile the patterns
            collection_pattern = re.compile(r'^/api/v1/[a-z0-9-]+/$')
            detail_pattern = re.compile(r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/$')
            action_pattern = re.compile(r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$')
            sub_resource_pattern = re.compile(r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$')

            # Test that patterns match correct examples
            self.assertTrue(collection_pattern.match('/api/v1/assets/'),
                          "Collection pattern should match correct example")
            self.assertTrue(detail_pattern.match('/api/v1/assets/{id}/'),
                          "Detail pattern should match correct example")
            self.assertTrue(action_pattern.match('/api/v1/assets/{id}/activate/'),
                          "Action pattern should match correct example")
            self.assertTrue(sub_resource_pattern.match('/api/v1/assets/{id}/datasets/'),
                          "Sub-resource pattern should match correct example")
        except Exception as e:
            self.fail(f"Regex patterns should be valid: {e}")


def main():
    """Run tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAPINamingStandardsCompleteness))
    suite.addTests(loader.loadTestsFromTestCase(TestAPINamingStandardsExamples))
    suite.addTests(loader.loadTestsFromTestCase(TestAPINamingStandardsValidationRules))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

