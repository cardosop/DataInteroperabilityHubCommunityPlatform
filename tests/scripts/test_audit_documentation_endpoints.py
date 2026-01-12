#!/usr/bin/env python3
"""
Tests for documentation endpoint audit script

Tests the comprehensive audit of documentation files for endpoint URLs.
"""

import json
import pytest
import tempfile
from pathlib import Path
from typing import Dict, List
import sys

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from audit_documentation_endpoints import (
    DocumentationEndpointAuditor,
    EndpointReference,
    DocumentationMapping,
)


class TestDocumentationEndpointAuditor:
    """Test suite for DocumentationEndpointAuditor"""

    @pytest.fixture
    def temp_docs_dir(self, tmp_path):
        """Create temporary docs directory structure"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create API_*.md files
        api_dir = docs_dir
        (api_dir / "API_REFERENCE.md").write_text("""
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

        (api_dir / "API_ENDPOINTS_REFERENCE.md").write_text("""
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
        runbooks_dir = tmp_path / "runbooks"
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

        return docs_dir, runbooks_dir

    @pytest.fixture
    def auditor(self, temp_docs_dir):
        """Create auditor instance"""
        docs_dir, runbooks_dir = temp_docs_dir
        base_path = docs_dir.parent
        return DocumentationEndpointAuditor(
            base_path=str(base_path),
            docs_dir=str(docs_dir),
            runbooks_dir=str(runbooks_dir)
        )

    def test_extract_endpoints_from_api_files(self, auditor, temp_docs_dir):
        """Test extraction from API_*.md files"""
        docs_dir, _ = temp_docs_dir
        references = auditor._extract_from_api_files()

        assert len(references) > 0

        # Check for expected endpoints
        paths = [ref.endpoint_path for ref in references]
        assert "/api/v1/contracts/" in paths
        assert "/api/v1/assets/" in paths
        assert "/api/v1/datasets/" in paths

    def test_extract_endpoints_from_api_audit(self, auditor, temp_docs_dir):
        """Test extraction from api-audit/*.md files"""
        docs_dir, _ = temp_docs_dir
        references = auditor._extract_from_api_audit()

        assert len(references) > 0

        paths = [ref.endpoint_path for ref in references]
        assert "/api/v1/contracts/contracts/" in paths
        assert "/api/v1/assets/assets/{asset_id}/activate/" in paths

    def test_extract_endpoints_from_openapi_specs(self, auditor, temp_docs_dir):
        """Test extraction from OpenAPI specifications"""
        # Create sample OpenAPI spec
        openapi_dir = temp_docs_dir[0].parent / "examples" / "contracts"
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

        references = auditor._extract_from_openapi_specs()

        # Should find the endpoint
        paths = [ref.endpoint_path for ref in references]
        assert any("/api/v1/test/endpoint" in path for path in paths)

    def test_extract_endpoints_from_runbooks(self, auditor, temp_docs_dir):
        """Test extraction from runbooks"""
        references = auditor._extract_from_runbooks()

        assert len(references) > 0

        paths = [ref.endpoint_path for ref in references]
        assert "/api/v1/health/" in paths

    def test_extract_endpoints_from_developer_guides(self, auditor, temp_docs_dir):
        """Test extraction from developer guides"""
        references = auditor._extract_from_developer_guides()

        assert len(references) > 0

        paths = [ref.endpoint_path for ref in references]
        assert "/api/v1/contracts/" in paths
        assert "/api/v1/assets/" in paths

    def test_normalize_endpoint_path(self, auditor):
        """Test endpoint path normalization"""
        # Test various formats
        assert auditor._normalize_endpoint_path("/api/v1/contracts/") == "/api/v1/contracts/"
        assert auditor._normalize_endpoint_path("`/api/v1/contracts/`") == "/api/v1/contracts/"
        assert auditor._normalize_endpoint_path("http://localhost:8000/api/v1/contracts/") == "/api/v1/contracts/"
        assert auditor._normalize_endpoint_path("https://api.example.com/api/v1/contracts/") == "/api/v1/contracts/"

    def test_map_documentation_to_endpoints(self, auditor, temp_docs_dir):
        """Test mapping documentation to endpoints"""
        auditor.audit_all()
        mappings = auditor.map_documentation_to_endpoints()

        assert len(mappings) > 0

        # Check that mappings contain expected structure
        for mapping in mappings:
            assert hasattr(mapping, 'endpoint_path')
            assert hasattr(mapping, 'documentation_files')
            assert len(mapping.documentation_files) > 0

    def test_generate_report(self, auditor, temp_docs_dir, tmp_path):
        """Test report generation"""
        auditor.audit_all()
        output_file = tmp_path / "report.json"

        auditor.generate_report(str(output_file))

        assert output_file.exists()

        # Verify report structure
        with open(output_file) as f:
            report = json.load(f)

        assert "summary" in report
        assert "endpoints" in report
        assert "documentation_mappings" in report
        assert report["summary"]["total_endpoints"] > 0
        assert report["summary"]["total_documentation_files"] > 0

    def test_verify_all_documentation_found(self, auditor, temp_docs_dir):
        """Test verification that all documentation is found"""
        auditor.audit_all()
        result = auditor.verify_all_documentation_found()

        assert result["status"] == "success" or result["status"] == "warning"
        assert "files_checked" in result
        assert "endpoints_found" in result

    def test_verify_documentation_mapping(self, auditor, temp_docs_dir):
        """Test verification of documentation mapping"""
        auditor.audit_all()
        result = auditor.verify_documentation_mapping()

        assert result["status"] == "success" or result["status"] == "warning"
        assert "mappings_verified" in result
        assert "endpoints_with_docs" in result

    def test_endpoint_pattern_matching(self, auditor):
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
            pattern = auditor.endpoint_patterns['rest']
            match = pattern.search(input_text)
            if match:
                normalized = auditor._normalize_endpoint_path(match.group(1))
                assert normalized == expected or expected in normalized

    def test_handles_missing_directories(self):
        """Test handling of missing directories"""
        auditor = DocumentationEndpointAuditor(
            base_path="/nonexistent",
            docs_dir="/nonexistent/docs",
            runbooks_dir="/nonexistent/runbooks"
        )

        # Should not raise exception, just return empty results
        references = auditor._extract_from_api_files()
        assert isinstance(references, list)

    def test_deduplication(self, auditor, temp_docs_dir):
        """Test that duplicate endpoints are handled correctly"""
        auditor.audit_all()
        mappings = auditor.map_documentation_to_endpoints()

        # Check that same endpoint from multiple files is properly mapped
        endpoint_paths = [m.endpoint_path for m in mappings]

        # Should have unique endpoints
        unique_paths = set(endpoint_paths)

        # Verify that endpoints with multiple docs are properly aggregated
        for mapping in mappings:
            if len(mapping.documentation_files) > 1:
                # This endpoint appears in multiple files
                assert len(set(mapping.documentation_files)) == len(mapping.documentation_files)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

