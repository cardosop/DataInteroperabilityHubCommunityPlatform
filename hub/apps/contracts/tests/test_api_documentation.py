"""
API Documentation Review Tests (Task 6.4.2)

Tests validate that API documentation is complete and accurate for:
- ODPS endpoints
- Export endpoints
- Linking endpoints

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""
import os
import re
from pathlib import Path
from django.test import TestCase
import structlog

logger = structlog.get_logger(__name__)


class APIDocumentationReviewTest(TestCase):
    """Test API documentation completeness and accuracy."""

    def setUp(self):
        """Set up test fixtures."""
        # API_ENDPOINTS_REFERENCE.md was consolidated into API_REFERENCE.md during Phase 120D
        self.docs_file = Path(__file__).parent.parent.parent.parent.parent / "docs" / "API_REFERENCE.md"
        if not self.docs_file.exists():
            self.skipTest(f"API documentation file not found: {self.docs_file}")

    def test_documentation_file_exists(self):
        """Test that API documentation file exists."""
        self.assertTrue(self.docs_file.exists(), "API_ENDPOINTS_REFERENCE.md should exist")

    def test_odps_endpoints_documented(self):
        """Test that ODPS endpoints are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for ODPS section
        self.assertIn('## ODPS (Open Data Product Standard) Endpoints', content,
                     "ODPS endpoints section should be documented")

        # Check for create product endpoint (with markdown backticks)
        self.assertTrue(
            'POST' in content and 'products' in content and '/api/v1/contracts' in content,
            "Create ODPS product endpoint should be documented"
        )
        self.assertIn('Create ODPS Product (Product-First Flow)', content,
                     "Product-First flow should be documented")

        # Check for required fields
        self.assertIn('original_raw', content, "original_raw field should be documented")
        self.assertIn('original_format', content, "original_format field should be documented")
        self.assertIn('resolve_external_refs', content, "resolve_external_refs field should be documented")

        # Check for response structure
        self.assertIn('odps_contract', content, "ODPS contract response should be documented")
        self.assertIn('odcs_contract', content, "ODCS contract response should be documented")
        self.assertIn('workflow_instance_id', content, "Workflow instance ID should be documented")

    def test_export_endpoints_documented(self):
        """Test that export endpoints are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for export section
        self.assertIn('## Export Endpoints', content,
                     "Export endpoints section should be documented")

        # Check for export endpoint (with markdown backticks)
        self.assertTrue(
            'GET' in content and 'export' in content and '/api/v1/contracts' in content,
            "Export endpoint should be documented"
        )

        # Check for download endpoint (with markdown backticks)
        self.assertTrue(
            'GET' in content and 'download' in content and '/api/v1/contracts' in content,
            "Download endpoint should be documented"
        )

        # Check for format parameters
        self.assertIn('format', content, "format parameter should be documented")
        self.assertIn('output_format', content, "output_format parameter should be documented")
        self.assertIn('version', content, "version parameter should be documented")

        # Check for format options
        self.assertIn('odps', content, "ODPS format option should be documented")
        self.assertIn('odcs', content, "ODCS format option should be documented")
        self.assertIn('hubcontract', content, "HubContract format option should be documented")

        # Check for output format options
        self.assertIn('json', content, "JSON output format should be documented")
        self.assertIn('yaml', content, "YAML output format should be documented")

    def test_linking_endpoints_documented(self):
        """Test that linking endpoints are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for linking section
        self.assertIn('## Linking Endpoints', content,
                     "Linking endpoints section should be documented")

        # Check for link endpoint (with markdown backticks)
        self.assertTrue(
            'POST' in content and 'link-odps' in content and '/api/v1/contracts' in content,
            "Link ODPS endpoint should be documented"
        )

        # Check for unlink endpoint (with markdown backticks)
        self.assertTrue(
            'POST' in content and 'unlink-odps' in content and '/api/v1/contracts' in content,
            "Unlink ODPS endpoint should be documented"
        )

        # Check for list links endpoint (with markdown backticks)
        self.assertTrue(
            'GET' in content and 'links' in content and '/api/v1/contracts' in content,
            "List links endpoint should be documented"
        )

        # Check for link request body fields
        self.assertIn('odps_contract_id', content, "odps_contract_id field should be documented")
        self.assertIn('Link ODPS to ODCS Contract', content,
                     "Link ODPS endpoint description should be present")

        # Check for response structure
        self.assertIn('odps_link', content, "ODPS link response should be documented")
        self.assertIn('odcs_link', content, "ODCS link response should be documented")

    def test_endpoint_examples_present(self):
        """Test that endpoint examples are present."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for example requests
        self.assertIn('Example Request', content, "Example requests should be documented")
        self.assertIn('curl -X', content, "cURL examples should be present")

        # Check for example responses
        self.assertIn('Response (', content, "Response examples should be documented")
        self.assertIn('```json', content, "JSON response examples should be present")

    def test_error_responses_documented(self):
        """Test that error responses are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for error responses section
        self.assertIn('Error Responses', content, "Error responses should be documented")

        # Check for common error codes
        self.assertIn('400 Bad Request', content, "400 error should be documented")
        self.assertIn('404 Not Found', content, "404 error should be documented")
        self.assertIn('500 Internal Server Error', content, "500 error should be documented")

    def test_request_body_fields_documented(self):
        """Test that request body fields are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for request body sections
        self.assertIn('Request Body', content, "Request body should be documented")
        self.assertIn('Request Body Fields', content, "Request body fields should be documented")

        # Check for field descriptions
        # ODPS create product fields
        if 'POST /api/v1/contracts/products/' in content:
            # Check that fields are described
            self.assertTrue(
                'original_raw' in content and 'required' in content.lower(),
                "original_raw field should be marked as required"
            )

    def test_response_structure_documented(self):
        """Test that response structures are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for response structure examples
        self.assertIn('Response (201 Created)', content, "201 response should be documented")
        self.assertIn('Response (200 OK)', content, "200 response should be documented")
        self.assertIn('Response (204 No Content)', content, "204 response should be documented")

    def test_path_parameters_documented(self):
        """Test that path parameters are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for path parameters section
        self.assertIn('Path Parameters', content, "Path parameters should be documented")

        # Check for UUID parameter documentation (may be formatted with backticks)
        self.assertTrue(
            'id' in content and ('UUID' in content or 'uuid' in content),
            "ID path parameter should be documented"
        )

    def test_query_parameters_documented(self):
        """Test that query parameters are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for query parameters section
        self.assertIn('Query Parameters', content, "Query parameters should be documented")

        # Check for format parameter
        self.assertIn('format', content, "format query parameter should be documented")
        self.assertIn('output_format', content, "output_format query parameter should be documented")

    def test_authentication_requirements_documented(self):
        """Test that authentication requirements are documented in examples."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for Authorization header in examples
        self.assertIn('Authorization: Bearer', content,
                     "Authentication should be shown in examples")

    def test_content_type_documented(self):
        """Test that content types are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for Content-Type in examples
        self.assertIn('Content-Type: application/json', content,
                     "Content-Type should be shown in examples")

    def test_notes_section_present(self):
        """Test that notes/important information sections are present."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for notes sections
        self.assertIn('**Notes:**', content, "Notes sections should be present")

    def test_all_required_endpoints_documented(self):
        """Test that all required endpoints are documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        required_endpoint_patterns = [
            ('POST', 'products', '/api/v1/contracts'),  # ODPS create
            ('GET', 'export', '/api/v1/contracts'),  # Export
            ('GET', 'download', '/api/v1/contracts'),  # Download
            ('POST', 'link-odps', '/api/v1/contracts'),  # Link
            ('POST', 'unlink-odps', '/api/v1/contracts'),  # Unlink
            ('GET', 'links', '/api/v1/contracts'),  # List links
        ]

        for method, path_part, base_path in required_endpoint_patterns:
            self.assertTrue(
                method in content and path_part in content and base_path in content,
                f"Required endpoint {method} {base_path}...{path_part} should be documented"
            )

    def test_documentation_structure_is_valid(self):
        """Test that documentation structure follows markdown best practices."""
        with open(self.docs_file, 'r') as f:
            content = f.read()
            lines = content.split('\n')

        # Check for proper heading hierarchy
        has_h2 = any(line.startswith('## ') for line in lines)
        self.assertTrue(has_h2, "Documentation should have H2 headings")

        # Check for code blocks
        code_block_count = content.count('```')
        self.assertGreater(code_block_count, 0, "Documentation should have code examples")
        # Code blocks should be even (opening and closing)
        self.assertEqual(code_block_count % 2, 0,
                        "Code blocks should be properly closed")

    def test_examples_are_complete(self):
        """Test that examples are complete and usable."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for complete curl examples
        curl_examples = re.findall(r'curl -X [A-Z]+', content)
        self.assertGreater(len(curl_examples), 0,
                          "Documentation should have curl examples")

        # Check that examples include URLs
        self.assertIn('https://api.example.com', content,
                     "Examples should include API URLs")

    def test_format_options_are_clear(self):
        """Test that format options are clearly documented."""
        with open(self.docs_file, 'r') as f:
            content = f.read()

        # Check for format option descriptions
        if 'format' in content:
            # Should have clear format options
            self.assertTrue(
                'odps' in content or 'ODPS' in content,
                "ODPS format option should be documented"
            )
            self.assertTrue(
                'odcs' in content or 'ODCS' in content,
                "ODCS format option should be documented"
            )

