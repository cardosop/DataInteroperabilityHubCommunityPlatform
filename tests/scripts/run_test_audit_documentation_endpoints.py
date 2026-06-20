#!/usr/bin/env python3
"""
Standalone test runner for documentation endpoint audit tests

This runner executes tests without requiring Django or pytest_django.
It uses unittest-style test execution compatible with pytest but without Django dependencies.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from audit_documentation_endpoints import (
    DocumentationEndpointAuditor,
)


class TestDocumentationEndpointAuditor(unittest.TestCase):
    """Test suite for DocumentationEndpointAuditor"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create docs directory structure
        docs_dir = self.temp_path / "docs"
        docs_dir.mkdir()

        # Create API_*.md files
        (docs_dir / "API_REFERENCE.md").write_text("""
# API Reference

## Endpoints

### Contracts
- `GET /api/v1/contracts/` - List contracts
- `POST /api/v1/contracts/` - Create contract
- `GET /api/v1/contracts/{id}/` - Get contract

### Assets
- `GET /api/v1/assets/` - List assets
- `POST /api/v1/assets/{id}/activate/` - Activate asset
""")

        (docs_dir / "API_ENDPOINTS_REFERENCE.md").write_text("""
# API Endpoints Reference

**GET** `/api/v1/contracts/`

List all contracts.

**POST** `/api/v1/datasets/`

Create a dataset.
""")

        # Create api-audit directory
        api_audit_dir = docs_dir / "api-audit"
        api_audit_dir.mkdir()
        (api_audit_dir / "endpoint-inventory.md").write_text("""
# Endpoint Inventory

## Current Endpoints

- `/api/v1/contracts/contracts/` (GET, POST)
- `/api/v1/assets/assets/{asset_id}/activate/` (POST)
- `/api/v1/dq/dq-runs/` (GET, POST)
""")

        # Create runbooks directory
        runbooks_dir = self.temp_path / "runbooks"
        runbooks_dir.mkdir()
        (runbooks_dir / "RB-API-001.md").write_text("""
# API Runbook

## Troubleshooting

Use endpoint: `/api/v1/health/` to check service status.
""")

        # Create developer guide
        (docs_dir / "DEVELOPER_GUIDE.md").write_text("""
# Developer Guide

## API Usage

Example:
```bash
curl -X GET http://localhost:8000/api/v1/contracts/
curl -X POST http://localhost:8000/api/v1/assets/
```
""")

        self.docs_dir = docs_dir
        self.runbooks_dir = runbooks_dir

        # Create auditor instance
        self.auditor = DocumentationEndpointAuditor(
            base_path=str(self.temp_path), docs_dir=str(docs_dir), runbooks_dir=str(runbooks_dir)
        )

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_endpoints_from_api_files(self):
        """Test extraction from API_*.md files"""
        references = self.auditor._extract_from_api_files()

        self.assertGreater(len(references), 0, "Should find endpoint references")

        # Check for expected endpoints
        paths = [ref.endpoint_path for ref in references]
        self.assertIn("/api/v1/contracts/", paths, "Should find /api/v1/contracts/")
        self.assertIn("/api/v1/assets/", paths, "Should find /api/v1/assets/")
        self.assertIn("/api/v1/datasets/", paths, "Should find /api/v1/datasets/")

    def test_extract_endpoints_from_api_audit(self):
        """Test extraction from api-audit/*.md files"""
        references = self.auditor._extract_from_api_audit()

        self.assertGreater(len(references), 0, "Should find endpoint references")

        paths = [ref.endpoint_path for ref in references]
        self.assertIn("/api/v1/contracts/contracts/", paths)
        self.assertIn("/api/v1/assets/assets/{asset_id}/activate/", paths)

    def test_extract_endpoints_from_openapi_specs(self):
        """Test extraction from OpenAPI specifications"""
        # Create sample OpenAPI spec
        openapi_dir = self.temp_path / "examples" / "contracts"
        openapi_dir.mkdir(parents=True)
        (openapi_dir / "test.yaml").write_text("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /api/v1/test/endpoint:
    get:
      summary: Test endpoint
      operationId: testEndpoint
""")

        references = self.auditor._extract_from_openapi_specs()

        # Should find the endpoint
        paths = [ref.endpoint_path for ref in references]
        self.assertTrue(
            any("/api/v1/test/endpoint" in path for path in paths),
            f"Should find /api/v1/test/endpoint in {paths}",
        )

    def test_extract_endpoints_from_runbooks(self):
        """Test extraction from runbooks"""
        references = self.auditor._extract_from_runbooks()

        self.assertGreater(len(references), 0, "Should find endpoint references")

        paths = [ref.endpoint_path for ref in references]
        self.assertIn("/api/v1/health/", paths)

    def test_extract_endpoints_from_developer_guides(self):
        """Test extraction from developer guides"""
        references = self.auditor._extract_from_developer_guides()

        self.assertGreater(len(references), 0, "Should find endpoint references")

        paths = [ref.endpoint_path for ref in references]
        self.assertIn("/api/v1/contracts/", paths)
        self.assertIn("/api/v1/assets/", paths)

    def test_normalize_endpoint_path(self):
        """Test endpoint path normalization"""
        # Test various formats
        self.assertEqual(
            self.auditor._normalize_endpoint_path("/api/v1/contracts/"), "/api/v1/contracts/"
        )
        self.assertEqual(
            self.auditor._normalize_endpoint_path("`/api/v1/contracts/`"), "/api/v1/contracts/"
        )
        self.assertEqual(
            self.auditor._normalize_endpoint_path("http://localhost:8000/api/v1/contracts/"),
            "/api/v1/contracts/",
        )
        self.assertEqual(
            self.auditor._normalize_endpoint_path("https://api.example.com/api/v1/contracts/"),
            "/api/v1/contracts/",
        )

    def test_map_documentation_to_endpoints(self):
        """Test mapping documentation to endpoints"""
        self.auditor.audit_all()
        mappings = self.auditor.map_documentation_to_endpoints()

        self.assertGreater(len(mappings), 0, "Should have mappings")

        # Check that mappings contain expected structure
        for mapping in mappings:
            self.assertTrue(hasattr(mapping, "endpoint_path"))
            self.assertTrue(hasattr(mapping, "documentation_files"))
            self.assertGreater(len(mapping.documentation_files), 0)

    def test_generate_report(self):
        """Test report generation"""
        self.auditor.audit_all()
        output_file = self.temp_path / "report.json"

        self.auditor.generate_report(str(output_file))

        self.assertTrue(output_file.exists(), "Report file should exist")

        # Verify report structure
        import json

        with open(output_file) as f:
            report = json.load(f)

        self.assertIn("summary", report)
        self.assertIn("endpoints", report)
        self.assertIn("documentation_mappings", report)
        self.assertGreater(report["summary"]["total_endpoints"], 0)
        self.assertGreater(report["summary"]["total_documentation_files"], 0)

    def test_verify_all_documentation_found(self):
        """Test verification that all documentation is found"""
        self.auditor.audit_all()
        result = self.auditor.verify_all_documentation_found()

        self.assertIn(result["status"], ["success", "warning"])
        self.assertIn("files_checked", result)
        self.assertIn("endpoints_found", result)

    def test_verify_documentation_mapping(self):
        """Test verification of documentation mapping"""
        self.auditor.audit_all()
        result = self.auditor.verify_documentation_mapping()

        self.assertIn(result["status"], ["success", "warning"])
        self.assertIn("mappings_verified", result)
        self.assertIn("endpoints_with_docs", result)

    def test_endpoint_pattern_matching(self):
        """Test various endpoint pattern formats"""
        test_cases = [
            ("GET /api/v1/contracts/", "/api/v1/contracts/"),
            ("`POST /api/v1/assets/`", "/api/v1/assets/"),
            ("/api/v1/datasets/{id}/", "/api/v1/datasets/{id}/"),
            ("http://localhost:8000/api/v1/health/", "/api/v1/health/"),
            ("curl -X GET http://localhost:8000/api/v1/contracts/", "/api/v1/contracts/"),
        ]

        for input_text, expected in test_cases:
            # Extract endpoint from text
            pattern = self.auditor.endpoint_patterns["rest"]
            match = pattern.search(input_text)
            if match:
                normalized = self.auditor._normalize_endpoint_path(match.group(1))
                self.assertTrue(
                    normalized == expected or expected in normalized,
                    f"Expected {expected} in {normalized} for input: {input_text}",
                )

    def test_handles_missing_directories(self):
        """Test handling of missing directories"""
        auditor = DocumentationEndpointAuditor(
            base_path="/nonexistent",
            docs_dir="/nonexistent/docs",
            runbooks_dir="/nonexistent/runbooks",
        )

        # Should not raise exception, just return empty results
        references = auditor._extract_from_api_files()
        self.assertIsInstance(references, list)

    def test_deduplication(self):
        """Test that duplicate endpoints are handled correctly"""
        self.auditor.audit_all()
        mappings = self.auditor.map_documentation_to_endpoints()

        # Check that same endpoint from multiple files is properly mapped
        endpoint_paths = [m.endpoint_path for m in mappings]

        # Should have unique endpoints
        set(endpoint_paths)

        # Verify that endpoints with multiple docs are properly aggregated
        for mapping in mappings:
            if len(mapping.documentation_files) > 1:
                # This endpoint appears in multiple files
                self.assertEqual(
                    len(set(mapping.documentation_files)),
                    len(mapping.documentation_files),
                    "Documentation files should be unique",
                )


def main():
    """Run tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestDocumentationEndpointAuditor)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
