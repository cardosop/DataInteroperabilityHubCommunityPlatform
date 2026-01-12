"""
Integration tests for BUSINESS_LOGIC_INTEGRATION.md documentation.

These tests validate that the documentation is complete, accurate, and up-to-date
with the current implementation.
"""
import os
from django.test import TestCase


class BusinessLogicIntegrationDocumentationTest(TestCase):
    """Test suite for BUSINESS_LOGIC_INTEGRATION.md documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.doc_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'docs',
            'BUSINESS_LOGIC_INTEGRATION.md'
        )

    def _read_doc_content(self):
        """Read the documentation file content."""
        with open(self.doc_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_documentation_file_exists(self):
        """Test that the documentation file exists."""
        self.assertTrue(
            os.path.exists(self.doc_path),
            f"Documentation file not found: {self.doc_path}"
        )

    def test_documentation_has_version(self):
        """Test that documentation has version information."""
        content = self._read_doc_content()
        self.assertIn("**Version**:", content)
        self.assertIn("**Last Updated**:", content)

    def test_service_layer_coordination_section_exists(self):
        """Test that service layer coordination section exists."""
        content = self._read_doc_content()
        self.assertIn("## Service Layer Coordination", content)
        self.assertIn("### Service Layer Pattern", content)
        self.assertIn("All business logic is coordinated through service layer classes that extend `BaseService`", content)

    def test_transformation_service_documented(self):
        """Test that TransformationService is documented with implementation status."""
        content = self._read_doc_content()
        self.assertIn("#### TransformationService ✅ (Implemented - Phase 9.5.1)", content)
        self.assertIn("**Location**: `hub/apps/transformation/services.py`", content)
        self.assertIn("**Status**: ✅ Implemented", content)
        self.assertIn("**Phase**: 9.5.1", content)
        self.assertIn("**Responsibilities**:", content)
        self.assertIn("**Integration**:", content)
        self.assertIn("**Key Methods**:", content)
        self.assertIn("`create_pipeline()`", content)
        self.assertIn("`execute_pipeline()`", content)
        self.assertIn("`validate_pipeline_compatibility()`", content)

    def test_datamesh_service_documented(self):
        """Test that DataMeshService is documented with implementation status."""
        content = self._read_doc_content()
        self.assertIn("#### DataMeshService ✅ (Implemented - Phase 9.5.2)", content)
        self.assertIn("**Location**: `hub/apps/mesh/services.py`", content)
        self.assertIn("**Status**: ✅ Implemented", content)
        self.assertIn("**Phase**: 9.5.2", content)
        self.assertIn("**Responsibilities**:", content)
        self.assertIn("**Integration**:", content)
        self.assertIn("**Key Methods**:", content)
        self.assertIn("`create_domain()`", content)
        self.assertIn("`update_domain()`", content)
        self.assertIn("`transfer_ownership()`", content)

    def test_virtualization_service_documented(self):
        """Test that VirtualizationService is documented with implementation status."""
        content = self._read_doc_content()
        self.assertIn("#### VirtualizationService ✅ (Implemented - Phase 9.5.3)", content)
        self.assertIn("**Location**: `hub/apps/virtualization/services.py`", content)
        self.assertIn("**Status**: ✅ Implemented", content)
        self.assertIn("**Phase**: 9.5.3", content)
        self.assertIn("**Responsibilities**:", content)
        self.assertIn("**Integration**:", content)
        self.assertIn("**Key Methods**:", content)
        self.assertIn("`create_virtual_dataset()`", content)
        self.assertIn("`execute_query()`", content)
        self.assertIn("`validate_schema_alignment()`", content)

    def test_business_rules_framework_section_exists(self):
        """Test that business rules framework section exists."""
        content = self._read_doc_content()
        self.assertIn("## Business Rules Framework ✅ (Implemented - Phase 9.7.2)", content)
        self.assertIn("**Status**: ✅ Implemented (Phase 9.7.2)", content)
        self.assertIn("**Location**: `hub/apps/core/business_rules/`", content)

    def test_business_rules_framework_components_documented(self):
        """Test that business rules framework components are documented."""
        content = self._read_doc_content()
        self.assertIn("### Framework Architecture", content)
        self.assertIn("**Base Classes** (`hub/apps/core/business_rules/base.py`)", content)
        self.assertIn("**Common Utilities** (`hub/apps/core/business_rules/utils.py`)", content)
        self.assertIn("**Registry** (`hub/apps/core/business_rules/registry.py`)", content)
        self.assertIn("#### Base Class", content)
        self.assertIn("#### ValidationResult Pattern", content)
        self.assertIn("#### Rule Execution Context", content)
        self.assertIn("#### Framework Registry", content)

    def test_transformation_business_rules_documented(self):
        """Test that Transformation business rules are documented."""
        content = self._read_doc_content()
        self.assertIn("#### Transformation Business Rules ✅ (Implemented - Phase 9.5.1)", content)
        self.assertIn("**Location**: `hub/apps/transformation/business_rules.py`", content)
        self.assertIn("**Class**: `TransformationBusinessRules`", content)
        self.assertIn("**Registry Name**: `transformation_pipeline_validation`", content)
        self.assertIn("**Phase**: 9.5.1", content)
        self.assertIn("**Overview**:", content)
        self.assertIn("**Validation Methods**:", content)
        self.assertIn("`validate()`", content)
        self.assertIn("`validate_pipeline_structure()`", content)
        self.assertIn("`validate_node_compatibility()`", content)
        self.assertIn("`validate_schema_alignment()`", content)
        self.assertIn("`validate_asset_compatibility()`", content)
        self.assertIn("**Node Type Constraints**:", content)
        self.assertIn("**Required Fields per Node Type**:", content)
        self.assertIn("**Example Usage**:", content)
        self.assertIn("**Integration Points**:", content)

    def test_datamesh_business_rules_documented(self):
        """Test that Data Mesh business rules are documented."""
        content = self._read_doc_content()
        self.assertIn("#### Data Mesh Business Rules ✅ (Implemented - Phase 9.5.2)", content)
        self.assertIn("**Location**: `hub/apps/mesh/business_rules.py`", content)
        self.assertIn("**Classes**: `DataMeshBusinessRules`, `PolicyBusinessRules`, `TopologyBusinessRules`", content)
        self.assertIn("**Registry Names**: `data_mesh_domain_validation`, `policy_validation`, `topology_calculation`", content)
        self.assertIn("**Phase**: 9.5.2", content)
        self.assertIn("**Overview**:", content)
        self.assertIn("##### DataMeshBusinessRules", content)
        self.assertIn("`validate_domain_structure()`", content)
        self.assertIn("`validate_ownership_transfer()`", content)
        self.assertIn("`validate_boundaries()`", content)
        self.assertIn("`validate_policy_conflicts()`", content)
        self.assertIn("##### PolicyBusinessRules", content)
        self.assertIn("##### TopologyBusinessRules", content)

    def test_virtualization_business_rules_documented(self):
        """Test that Virtualization business rules are documented."""
        content = self._read_doc_content()
        self.assertIn("#### Virtualization Business Rules ✅ (Implemented - Phase 9.5.3)", content)
        self.assertIn("**Location**: `hub/apps/virtualization/business_rules.py`", content)
        self.assertIn("**Classes**: `VirtualizationBusinessRules`, `QueryExecutionBusinessRules`, `ResultBusinessRules`", content)
        self.assertIn("**Registry Name**: `virtualization_dataset_validation`", content)
        self.assertIn("**Phase**: 9.5.3", content)
        self.assertIn("**Overview**:", content)
        self.assertIn("##### VirtualizationBusinessRules", content)
        self.assertIn("`validate_query_syntax()`", content)
        self.assertIn("`validate_source_configuration()`", content)
        self.assertIn("`validate_schema_alignment()`", content)
        self.assertIn("`validate_source_compatibility()`", content)
        self.assertIn("**Query Type Support**:", content)
        self.assertIn("**Forbidden Keywords**", content)
        self.assertIn("**Required Keywords**:", content)
        self.assertIn("##### QueryExecutionBusinessRules", content)
        self.assertIn("##### ResultBusinessRules", content)

    def test_framework_common_patterns_documented(self):
        """Test that framework common patterns are documented."""
        content = self._read_doc_content()
        self.assertIn("### Common Patterns", content)
        self.assertIn("#### 1. Initialization Pattern", content)
        self.assertIn("#### 2. Validation Method Pattern", content)
        self.assertIn("#### 3. Error Handling Pattern", content)
        self.assertIn("#### 4. Error Message Pattern", content)
        self.assertIn("#### 5. Context Pattern", content)
        self.assertIn("#### 6. Registry Pattern", content)

    def test_framework_benefits_documented(self):
        """Test that framework benefits are documented."""
        content = self._read_doc_content()
        self.assertIn("### Framework Benefits (Phase 9.7.2)", content)
        self.assertIn("**Consistency**", content)
        self.assertIn("**Maintainability**", content)
        self.assertIn("**Discoverability**", content)
        self.assertIn("**Testability**", content)
        self.assertIn("**Metrics**", content)

    def test_framework_implementation_status_documented(self):
        """Test that framework implementation status is documented."""
        content = self._read_doc_content()
        self.assertIn("### Framework Implementation Status", content)
        self.assertIn("**Phase 9.7.2 Implementation**:", content)
        self.assertIn("✅ Base class (`BusinessRules`) implemented", content)
        self.assertIn("✅ `ValidationResult` standardized", content)
        self.assertIn("✅ `RuleExecutionContext` implemented", content)
        self.assertIn("✅ Common utilities created", content)
        self.assertIn("✅ Registry implemented", content)
        self.assertIn("**Business Rules Using Framework**:", content)
        self.assertIn("✅ TransformationBusinessRules (Phase 9.5.1)", content)
        self.assertIn("✅ DataMeshBusinessRules (Phase 9.5.2)", content)
        self.assertIn("✅ VirtualizationBusinessRules (Phase 9.5.3)", content)

    def test_service_integration_patterns_section_exists(self):
        """Test that service integration patterns section exists."""
        content = self._read_doc_content()
        self.assertIn("## Service Integration Patterns ✅ (Implemented - Phase 9.7.3)", content)
        self.assertIn("**Status**: ✅ Implemented (Phase 9.7.3)", content)
        self.assertIn("**Documentation**: `docs/SERVICE_INTEGRATION_PATTERNS.md`", content)

    def test_integration_patterns_documented(self):
        """Test that all three integration patterns are documented."""
        content = self._read_doc_content()
        self.assertIn("### Pattern 1: Direct Service Calls (Synchronous) ✅", content)
        self.assertIn("### Pattern 2: Event-Driven Coordination (Asynchronous) ✅", content)
        self.assertIn("### Pattern 3: Workflow Orchestration (Multi-Step) ✅", content)
        self.assertIn("**When to Use**:", content)
        self.assertIn("**Implementation**:", content)
        self.assertIn("**Service Clients**:", content)
        self.assertIn("**Event Publishers**:", content)
        self.assertIn("**Workflows**:", content)

    def test_pattern_selection_criteria_documented(self):
        """Test that pattern selection criteria are documented."""
        content = self._read_doc_content()
        self.assertIn("### Pattern Selection Criteria", content)
        self.assertIn("**Use Direct Service Calls when**:", content)
        self.assertIn("**Use Event-Driven when**:", content)
        self.assertIn("**Use Workflow Orchestration when**:", content)

    def test_anti_patterns_documented(self):
        """Test that anti-patterns are documented."""
        content = self._read_doc_content()
        self.assertIn("### Anti-Patterns to Avoid", content)
        self.assertIn("Direct HTTP calls outside service clients", content)
        self.assertIn("Synchronous calls in event handlers", content)
        self.assertIn("Services not extending BaseService", content)
        self.assertIn("Missing circuit breakers", content)
        self.assertIn("Missing retry logic", content)

    def test_best_practices_section_exists(self):
        """Test that best practices section exists."""
        content = self._read_doc_content()
        self.assertIn("## Best Practices", content)
        self.assertIn("### Service Layer", content)
        self.assertIn("### Workflow Integration", content)
        self.assertIn("### Event-Driven Coordination", content)
        self.assertIn("### Business Rules", content)
        self.assertIn("### Service Integration Patterns", content)
        self.assertIn("### Data Consistency", content)

    def test_table_of_contents_exists(self):
        """Test that table of contents exists."""
        content = self._read_doc_content()
        self.assertIn("## Table of Contents", content)
        self.assertIn("[Architecture](#architecture)", content)
        self.assertIn("[Service Layer Coordination](#service-layer-coordination)", content)
        self.assertIn("[Business Rules Framework](#business-rules-framework-implemented---phase-972)", content)
        self.assertIn("[Service Integration Patterns](#service-integration-patterns-implemented---phase-973)", content)

    def test_documentation_cross_references(self):
        """Test that documentation has proper cross-references."""
        content = self._read_doc_content()
        self.assertIn("`docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`", content)
        self.assertIn("`docs/SERVICE_INTEGRATION_PATTERNS.md`", content)
        self.assertIn("`docs/api-audit/SERVICE_INTEGRATION_AUDIT_REPORT.md`", content)
        self.assertIn("`docs/api-audit/SERVICE_INTEGRATION_REMEDIATION_COMPLETE.md`", content)

    def test_code_examples_present(self):
        """Test that code examples are present in documentation."""
        content = self._read_doc_content()
        # Check for Python code blocks
        self.assertIn("```python", content)
        # Check for JSON code blocks
        self.assertIn("```json", content)
        # Check for TypeScript code blocks
        self.assertIn("```typescript", content)

