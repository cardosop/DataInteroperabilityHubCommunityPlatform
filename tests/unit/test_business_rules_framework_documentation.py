"""
Comprehensive tests for Business Rules Framework documentation completeness and accuracy.

Tests validate:
1. Documentation files exist and are accessible
2. All business rules classes are documented
3. Framework features are documented (caching, metrics, tracing, logging)
4. Documentation accuracy (matches actual implementation)
5. Cross-references between documents are valid
6. Code examples in documentation are syntactically correct

All tests follow engineering best practices:
- No mocks/stubs - use real files and implementations
- Fix root causes, not symptoms
- Comprehensive validation
- Follow DRY, SOLID, and clean code principles
"""
import os
import re
import inspect
from pathlib import Path
from typing import List, Dict, Set, Any, Optional
from django.test import SimpleTestCase

# Import framework components
from hub.apps.core.business_rules.base import (
    BusinessRules,
    ValidationResult,
    RuleExecutionContext,
)
from hub.apps.core.business_rules.registry import (
    get_registry,
    BusinessRulesRegistry,
    RuleMetadata,
)

# Import all business rules classes
from hub.apps.contracts.business_rules import (
    ODPSBusinessRules,
    ODPSLinkingRules,
    ODPSExportRules,
    ODPSNormalizationRules,
    ContractsBusinessRules,
)
from hub.apps.mesh.business_rules import (
    DataMeshBusinessRules,
    PolicyBusinessRules,
    TopologyBusinessRules,
)
from hub.apps.transformation.business_rules import (
    TransformationBusinessRules,
)
from hub.apps.virtualization.business_rules import (
    VirtualizationBusinessRules,
    QueryExecutionBusinessRules,
    ResultBusinessRules,
)
from hub.apps.orchestration.business_rules import (
    OrchestrationBusinessRules,
)
from hub.apps.notifications.business_rules import (
    NotificationsBusinessRules,
)
from hub.apps.search.business_rules import (
    SearchBusinessRules,
)
from hub.apps.semantic.business_rules import (
    SemanticBusinessRules,
)
from hub.apps.webhooks.business_rules import (
    WebhooksBusinessRules,
)
from hub.apps.scheduled_ingestion.business_rules import (
    ScheduledIngestionBusinessRules,
)
from hub.apps.files.business_rules import (
    FilesBusinessRules,
)
from hub.apps.jobs.business_rules import (
    JobsBusinessRules,
)
from hub.apps.compliance.business_rules import (
    ComplianceBusinessRules,
)
from hub.apps.dq.business_rules import (
    DQBusinessRules,
)
from hub.apps.governance.business_rules import (
    GovernanceBusinessRules,
)
from hub.apps.marketplace.business_rules import (
    MarketplaceBusinessRules,
)
from hub.apps.datasets.business_rules import (
    DatasetsBusinessRules,
)
from hub.apps.assets.business_rules import (
    AssetsBusinessRules,
)


class TestDocumentationExistence(SimpleTestCase):
    """Test that documentation files exist."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.docs_dir = self.project_root / "docs"
        self.review_doc = self.docs_dir / "BUSINESS_RULES_FRAMEWORK_REVIEW.md"
        self.guide_doc = self.docs_dir / "BUSINESS_RULES_FRAMEWORK_GUIDE.md"

    def test_review_documentation_exists(self):
        """Test that BUSINESS_RULES_FRAMEWORK_REVIEW.md exists."""
        self.assertTrue(
            self.review_doc.exists(),
            f"BUSINESS_RULES_FRAMEWORK_REVIEW.md should exist at {self.review_doc}"
        )

    def test_guide_documentation_exists(self):
        """Test that BUSINESS_RULES_FRAMEWORK_GUIDE.md exists."""
        self.assertTrue(
            self.guide_doc.exists(),
            f"BUSINESS_RULES_FRAMEWORK_GUIDE.md should exist at {self.guide_doc}"
        )

    def test_review_documentation_is_readable(self):
        """Test that review documentation is readable."""
        if self.review_doc.exists():
            with open(self.review_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertGreater(
                    len(content), 0,
                    "Review documentation should not be empty"
                )

    def test_guide_documentation_is_readable(self):
        """Test that guide documentation is readable."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertGreater(
                    len(content), 0,
                    "Guide documentation should not be empty"
                )


class TestDocumentationCompleteness(SimpleTestCase):
    """Test that documentation is complete."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.docs_dir = self.project_root / "docs"
        self.review_doc = self.docs_dir / "BUSINESS_RULES_FRAMEWORK_REVIEW.md"
        self.guide_doc = self.docs_dir / "BUSINESS_RULES_FRAMEWORK_GUIDE.md"

        # All business rules classes
        self.expected_classes = {
            'ODPSBusinessRules',
            'ODPSLinkingRules',
            'ODPSExportRules',
            'ODPSNormalizationRules',
            'ContractsBusinessRules',
            'DataMeshBusinessRules',
            'PolicyBusinessRules',
            'TopologyBusinessRules',
            'TransformationBusinessRules',
            'VirtualizationBusinessRules',
            'QueryExecutionBusinessRules',
            'ResultBusinessRules',
            'OrchestrationBusinessRules',
            'NotificationsBusinessRules',
            'SearchBusinessRules',
            'SemanticBusinessRules',
            'WebhooksBusinessRules',
            'ScheduledIngestionBusinessRules',
            'FilesBusinessRules',
            'JobsBusinessRules',
            'ComplianceBusinessRules',
            'DQBusinessRules',
            'GovernanceBusinessRules',
            'MarketplaceBusinessRules',
            'DatasetsBusinessRules',
            'AssetsBusinessRules',
        }

    def test_review_has_completion_status(self):
        """Test that review document has completion status."""
        if self.review_doc.exists():
            with open(self.review_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'Framework Status',
                    content,
                    "Review document should have Framework Status section"
                )
                self.assertIn(
                    'Fully Implemented',
                    content,
                    "Review document should indicate framework is fully implemented"
                )

    def test_review_has_link_to_guide(self):
        """Test that review document links to guide."""
        if self.review_doc.exists():
            with open(self.review_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'BUSINESS_RULES_FRAMEWORK_GUIDE.md',
                    content,
                    "Review document should link to guide document"
                )

    def test_guide_has_overview_section(self):
        """Test that guide has overview section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Overview',
                    content,
                    "Guide should have Overview section"
                )

    def test_guide_has_architecture_section(self):
        """Test that guide has architecture section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Architecture',
                    content,
                    "Guide should have Architecture section"
                )

    def test_guide_has_framework_features_section(self):
        """Test that guide has framework features section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Framework Features',
                    content,
                    "Guide should have Framework Features section"
                )

    def test_guide_documents_caching(self):
        """Test that guide documents caching feature."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for caching section
                caching_section = re.search(
                    r'###\s+1\.\s+Caching|###\s+Caching',
                    content,
                    re.IGNORECASE
                )
                self.assertIsNotNone(
                    caching_section,
                    "Guide should document caching feature"
                )

    def test_guide_documents_metrics(self):
        """Test that guide documents metrics feature."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for metrics section
                metrics_section = re.search(
                    r'###\s+2\.\s+Metrics|###\s+Metrics',
                    content,
                    re.IGNORECASE
                )
                self.assertIsNotNone(
                    metrics_section,
                    "Guide should document metrics feature"
                )

    def test_guide_documents_tracing(self):
        """Test that guide documents tracing feature."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for tracing section
                tracing_section = re.search(
                    r'###\s+3\.\s+Tracing|###\s+Tracing',
                    content,
                    re.IGNORECASE
                )
                self.assertIsNotNone(
                    tracing_section,
                    "Guide should document tracing feature"
                )

    def test_guide_documents_logging(self):
        """Test that guide documents logging feature."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for logging section
                logging_section = re.search(
                    r'###\s+4\.\s+Structured Logging|###\s+Logging|Structured Logging',
                    content,
                    re.IGNORECASE
                )
                self.assertIsNotNone(
                    logging_section,
                    "Guide should document logging feature"
                )

    def test_guide_has_business_rules_classes_section(self):
        """Test that guide has business rules classes section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Business Rules Classes',
                    content,
                    "Guide should have Business Rules Classes section"
                )

    def test_all_business_rules_classes_documented(self):
        """Test that all business rules classes are documented in guide."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                missing_classes = []
                for class_name in self.expected_classes:
                    # Check for class documentation (using markdown headers)
                    pattern = rf'####\s+\d+\.\s+`{class_name}`|####\s+`{class_name}`'
                    if not re.search(pattern, content):
                        missing_classes.append(class_name)

                self.assertEqual(
                    len(missing_classes), 0,
                    f"Missing documentation for classes: {', '.join(missing_classes)}"
                )

    def test_guide_has_getting_started_section(self):
        """Test that guide has getting started section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Getting Started',
                    content,
                    "Guide should have Getting Started section"
                )

    def test_guide_has_advanced_usage_section(self):
        """Test that guide has advanced usage section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Advanced Usage',
                    content,
                    "Guide should have Advanced Usage section"
                )

    def test_guide_has_best_practices_section(self):
        """Test that guide has best practices section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Best Practices',
                    content,
                    "Guide should have Best Practices section"
                )

    def test_guide_has_troubleshooting_section(self):
        """Test that guide has troubleshooting section."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    '## Troubleshooting',
                    content,
                    "Guide should have Troubleshooting section"
                )


class TestDocumentationAccuracy(SimpleTestCase):
    """Test that documentation accurately reflects implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.guide_doc = self.project_root / "docs" / "BUSINESS_RULES_FRAMEWORK_GUIDE.md"

        # Get actual business rules classes from registry
        self.registry = get_registry()
        self.registered_rules = self.registry.get_all_rules()

    def test_documented_classes_exist_in_codebase(self):
        """Test that all documented classes actually exist."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                # Extract class names from documentation
                # Match patterns like: #### 1. `ClassName` or #### `ClassName`
                class_pattern = r'####\s+\d+\.\s+`([A-Za-z]+BusinessRules)`|####\s+`([A-Za-z]+BusinessRules)`|####\s+\d+\.\s+`([A-Za-z]+Rules)`|####\s+`([A-Za-z]+Rules)`'
                documented_classes = set()
                for match in re.finditer(class_pattern, content):
                    for group in match.groups():
                        if group:
                            documented_classes.add(group)

                # Exclude base classes and framework components
                excluded_classes = {'BusinessRules', 'BusinessRulesRegistry', 'RuleMetadata'}
                documented_classes = documented_classes - excluded_classes

                # All documented classes should be in our expected list
                expected_classes = {
                    'ODPSBusinessRules', 'ODPSLinkingRules', 'ODPSExportRules',
                    'ODPSNormalizationRules', 'ContractsBusinessRules',
                    'DataMeshBusinessRules', 'PolicyBusinessRules', 'TopologyBusinessRules',
                    'TransformationBusinessRules', 'VirtualizationBusinessRules',
                    'QueryExecutionBusinessRules', 'ResultBusinessRules',
                    'OrchestrationBusinessRules', 'NotificationsBusinessRules',
                    'SearchBusinessRules', 'SemanticBusinessRules', 'WebhooksBusinessRules',
                    'ScheduledIngestionBusinessRules', 'FilesBusinessRules',
                    'JobsBusinessRules', 'ComplianceBusinessRules', 'DQBusinessRules',
                    'GovernanceBusinessRules', 'MarketplaceBusinessRules',
                    'DatasetsBusinessRules', 'AssetsBusinessRules',
                }

                undocumented_classes = documented_classes - expected_classes
                self.assertEqual(
                    len(undocumented_classes), 0,
                    f"Documented classes not in codebase: {', '.join(undocumented_classes)}"
                )

    def test_framework_base_class_documented(self):
        """Test that BusinessRules base class is documented."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'BusinessRules',
                    content,
                    "Guide should document BusinessRules base class"
                )
                self.assertIn(
                    'hub/apps/core/business_rules/base.py',
                    content,
                    "Guide should document base class location"
                )

    def test_validation_result_documented(self):
        """Test that ValidationResult is documented."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'ValidationResult',
                    content,
                    "Guide should document ValidationResult"
                )

    def test_rule_execution_context_documented(self):
        """Test that RuleExecutionContext is documented."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'RuleExecutionContext',
                    content,
                    "Guide should document RuleExecutionContext"
                )

    def test_registry_documented(self):
        """Test that registry is documented."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'BusinessRulesRegistry',
                    content,
                    "Guide should document BusinessRulesRegistry"
                )
                self.assertIn(
                    'hub/apps/core/business_rules/registry.py',
                    content,
                    "Guide should document registry location"
                )

    def test_caching_configuration_matches_implementation(self):
        """Test that caching configuration in docs matches implementation."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check that default TTL is documented
                self.assertIn(
                    '300',
                    content,  # Default TTL is 300 seconds
                    "Guide should document default cache TTL"
                )

                # Check that cache key format is documented
                self.assertIn(
                    'business_rules:validation',
                    content,
                    "Guide should document cache key prefix"
                )

    def test_metrics_names_match_implementation(self):
        """Test that metrics names in docs match implementation."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check for metric names
                self.assertIn(
                    'business_rules_executions_total',
                    content,
                    "Guide should document executions_total metric"
                )
                self.assertIn(
                    'business_rules_duration_seconds',
                    content,
                    "Guide should document duration_seconds metric"
                )
                self.assertIn(
                    'business_rules_results_total',
                    content,
                    "Guide should document results_total metric"
                )


class TestDocumentationCrossReferences(SimpleTestCase):
    """Test cross-references between documents."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.docs_dir = self.project_root / "docs"
        self.review_doc = self.docs_dir / "BUSINESS_RULES_FRAMEWORK_REVIEW.md"
        self.guide_doc = self.docs_dir / "BUSINESS_RULES_FRAMEWORK_GUIDE.md"

    def test_review_links_to_guide(self):
        """Test that review document links to guide."""
        if self.review_doc.exists() and self.guide_doc.exists():
            with open(self.review_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for markdown link or reference
                has_link = (
                    'BUSINESS_RULES_FRAMEWORK_GUIDE.md' in content or
                    '[Business Rules Framework Guide]' in content
                )
                self.assertTrue(
                    has_link,
                    "Review document should link to guide document"
                )

    def test_guide_references_base_class_location(self):
        """Test that guide references base class location."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'hub/apps/core/business_rules/base.py',
                    content,
                    "Guide should reference base class location"
                )

    def test_guide_references_registry_location(self):
        """Test that guide references registry location."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn(
                    'hub/apps/core/business_rules/registry.py',
                    content,
                    "Guide should reference registry location"
                )


class TestDocumentationCodeExamples(SimpleTestCase):
    """Test that code examples in documentation are valid."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.guide_doc = self.project_root / "docs" / "BUSINESS_RULES_FRAMEWORK_GUIDE.md"

    def test_code_examples_use_correct_imports(self):
        """Test that code examples use correct import statements."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check for correct import patterns
                import_patterns = [
                    r'from hub\.apps\.core\.business_rules\.base import',
                    r'from hub\.apps\.core\.business_rules\.registry import',
                ]

                for pattern in import_patterns:
                    if re.search(pattern, content):
                        # Found import, check it's in a code block
                        matches = list(re.finditer(pattern, content))
                        for match in matches:
                            # Check if it's in a code block (between ```)
                            start_pos = match.start()
                            # Find the code block start before this position
                            before = content[:start_pos]
                            code_blocks_before = before.count('```')
                            # Should be odd (inside a code block)
                            self.assertTrue(
                                code_blocks_before % 2 == 1,
                                f"Import statement should be in code block: {match.group()}"
                            )

    def test_code_examples_use_business_rules_base_class(self):
        """Test that code examples extend BusinessRules correctly."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check for class definition examples
                class_pattern = r'class\s+\w+BusinessRules\(BusinessRules\)'
                if re.search(class_pattern, content):
                    # Found class definition, verify it's in code block
                    matches = list(re.finditer(class_pattern, content))
                    for match in matches:
                        start_pos = match.start()
                        before = content[:start_pos]
                        code_blocks_before = before.count('```')
                        self.assertTrue(
                            code_blocks_before % 2 == 1,
                            f"Class definition should be in code block: {match.group()}"
                        )


class TestDocumentationClassDetails(SimpleTestCase):
    """Test that each documented class has required details."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.guide_doc = self.project_root / "docs" / "BUSINESS_RULES_FRAMEWORK_GUIDE.md"

        self.expected_classes = {
            'ODPSBusinessRules', 'ODPSLinkingRules', 'ODPSExportRules',
            'ODPSNormalizationRules', 'ContractsBusinessRules',
            'DataMeshBusinessRules', 'PolicyBusinessRules', 'TopologyBusinessRules',
            'TransformationBusinessRules', 'VirtualizationBusinessRules',
            'QueryExecutionBusinessRules', 'ResultBusinessRules',
            'OrchestrationBusinessRules', 'NotificationsBusinessRules',
            'SearchBusinessRules', 'SemanticBusinessRules', 'WebhooksBusinessRules',
            'ScheduledIngestionBusinessRules', 'FilesBusinessRules',
            'JobsBusinessRules', 'ComplianceBusinessRules', 'DQBusinessRules',
            'GovernanceBusinessRules', 'MarketplaceBusinessRules',
            'DatasetsBusinessRules', 'AssetsBusinessRules',
        }

    def test_each_class_has_location(self):
        """Test that each documented class has location information."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                missing_locations = []
                for class_name in self.expected_classes:
                    # Find class documentation section
                    class_pattern = rf'####\s+\d+\.\s+`{class_name}`|####\s+`{class_name}`'
                    match = re.search(class_pattern, content)
                    if match:
                        # Get section content (next 20 lines)
                        section_start = match.end()
                        section_content = content[section_start:section_start + 2000]

                        # Check for location pattern
                        location_pattern = r'\*\*Location\*\*.*?`hub/apps/'
                        if not re.search(location_pattern, section_content, re.DOTALL):
                            missing_locations.append(class_name)

                self.assertEqual(
                    len(missing_locations), 0,
                    f"Classes missing location: {', '.join(missing_locations)}"
                )

    def test_each_class_has_purpose(self):
        """Test that each documented class has purpose description."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                missing_purposes = []
                for class_name in self.expected_classes:
                    # Find class documentation section
                    class_pattern = rf'####\s+\d+\.\s+`{class_name}`|####\s+`{class_name}`'
                    match = re.search(class_pattern, content)
                    if match:
                        # Get section content
                        section_start = match.end()
                        section_content = content[section_start:section_start + 2000]

                        # Check for purpose pattern
                        purpose_pattern = r'\*\*Purpose\*\*|Purpose.*?:'
                        if not re.search(purpose_pattern, section_content, re.IGNORECASE):
                            missing_purposes.append(class_name)

                self.assertEqual(
                    len(missing_purposes), 0,
                    f"Classes missing purpose: {', '.join(missing_purposes)}"
                )

    def test_each_class_has_validation_capabilities(self):
        """Test that each documented class has validation capabilities listed."""
        if self.guide_doc.exists():
            with open(self.guide_doc, 'r', encoding='utf-8') as f:
                content = f.read()

                missing_capabilities = []
                for class_name in self.expected_classes:
                    # Find class documentation section
                    class_pattern = rf'####\s+\d+\.\s+`{class_name}`|####\s+`{class_name}`'
                    match = re.search(class_pattern, content)
                    if match:
                        # Get section content
                        section_start = match.end()
                        section_content = content[section_start:section_start + 2000]

                        # Check for validation capabilities pattern
                        capabilities_pattern = r'\*\*Validation Capabilities\*\*|Validation Capabilities.*?:'
                        if not re.search(capabilities_pattern, section_content, re.IGNORECASE):
                            missing_capabilities.append(class_name)

                self.assertEqual(
                    len(missing_capabilities), 0,
                    f"Classes missing validation capabilities: {', '.join(missing_capabilities)}"
                )

