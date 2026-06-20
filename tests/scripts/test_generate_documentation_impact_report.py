#!/usr/bin/env python3
"""
Tests for documentation impact report generator script

Tests the comprehensive compilation of documentation references and generation
of documentation impact analysis report.
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from generate_documentation_impact_report import (
    DocumentationImpactReportGenerator,
)


class TestDocumentationImpactReportGenerator:
    """Test suite for DocumentationImpactReportGenerator"""

    @pytest.fixture
    def temp_audit_reports(self, tmp_path):
        """Create temporary audit report files"""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        # Documentation endpoint audit
        doc_audit = {
            "summary": {
                "generated_at": "2025-12-28T10:00:00",
                "total_endpoints": 10,
                "total_references": 25,
                "total_documentation_files": 5,
            },
            "endpoints": [
                {
                    "endpoint_path": "/api/v1/contracts/",
                    "normalized_path": "/api/v1/contracts/",
                    "methods": ["GET", "POST"],
                    "documentation_files": ["docs/API_REFERENCE.md"],
                    "total_references": 5,
                }
            ],
        }
        (reports_dir / "documentation-endpoint-audit.json").write_text(
            json.dumps(doc_audit, indent=2)
        )

        # Code examples audit
        code_examples_audit = {
            "summary": {
                "generated_at": "2025-12-28T10:00:00",
                "total_examples": 100,
                "valid_examples": 90,
                "invalid_examples": 10,
                "total_endpoints_found": 20,
                "valid_endpoints": 15,
                "invalid_endpoints": 5,
            },
            "examples": [
                {
                    "example": {
                        "source_file": "docs/API_EXAMPLES.md",
                        "language": "python",
                        "code": "import requests\nurl = 'http://localhost:8000/api/v1/contracts/'",
                    },
                    "is_valid": True,
                    "errors": [],
                    "endpoints_found": ["/api/v1/contracts/"],
                }
            ],
        }
        (reports_dir / "code-examples-audit.json").write_text(
            json.dumps(code_examples_audit, indent=2)
        )

        # Postman collections audit
        postman_audit = {
            "summary": {
                "generated_at": "2025-12-28T10:00:00",
                "total_collections": 2,
                "valid_collections": 1,
                "invalid_collections": 1,
                "total_requests": 10,
                "valid_requests": 8,
                "invalid_requests": 2,
            },
            "collections": [
                {"collection_file": "collections/api.json", "is_valid": True, "requests": []}
            ],
        }
        (reports_dir / "postman-collections-audit.json").write_text(
            json.dumps(postman_audit, indent=2)
        )

        # Inventory review report
        inventory_review = {
            "summary": {
                "generated_at": "2025-12-28T10:00:00",
                "total_endpoints_in_inventory": 10,
                "total_endpoints_in_codebase": 12,
                "discrepancies": 5,
            },
            "discrepancies": [
                {
                    "type": "missing_in_inventory",
                    "endpoint": "/api/v1/new-endpoint/",
                    "methods": ["GET"],
                }
            ],
        }
        (reports_dir / "inventory-review-report.json").write_text(
            json.dumps(inventory_review, indent=2)
        )

        return reports_dir

    def test_generator_initialization(self, temp_audit_reports):
        """Test generator initialization"""
        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(temp_audit_reports))

        assert generator.audit_reports_dir == Path(temp_audit_reports)

    def test_load_audit_reports(self, temp_audit_reports):
        """Test loading audit reports"""
        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(temp_audit_reports))

        reports = generator.load_audit_reports()

        assert "documentation_endpoint_audit" in reports
        assert "code_examples_audit" in reports
        assert "postman_collections_audit" in reports
        assert "inventory_review" in reports

    def test_compile_documentation_references(self, temp_audit_reports):
        """Test compiling documentation references"""
        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(temp_audit_reports))

        generator.load_audit_reports()
        references = generator.compile_documentation_references()

        assert "documentation_files" in references
        assert "endpoints" in references
        assert "code_examples" in references
        assert "postman_collections" in references

    def test_identify_documentation_updates(self, temp_audit_reports):
        """Test identifying documentation updates needed"""
        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(temp_audit_reports))

        generator.load_audit_reports()
        references = generator.compile_documentation_references()
        updates = generator.identify_documentation_updates(references)

        assert "files_to_update" in updates
        assert "endpoints_missing_docs" in updates
        assert "invalid_examples" in updates
        assert "invalid_collections" in updates

    def test_generate_report(self, temp_audit_reports, tmp_path):
        """Test generating markdown report"""
        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(temp_audit_reports))

        report_file = tmp_path / "impact-report.md"
        generator.generate_report(str(report_file))

        assert report_file.exists()
        content = report_file.read_text()
        assert "# Documentation Impact Analysis" in content
        assert "## Summary" in content
        assert "## Documentation Files" in content

    def test_missing_audit_files(self, tmp_path):
        """Test handling of missing audit files"""
        empty_dir = tmp_path / "empty_reports"
        empty_dir.mkdir()

        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(empty_dir))

        reports = generator.load_audit_reports()
        # Should handle gracefully
        assert isinstance(reports, dict)

    def test_report_structure(self, temp_audit_reports, tmp_path):
        """Test report structure completeness"""
        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(temp_audit_reports))

        report_file = tmp_path / "impact-report.md"
        generator.generate_report(str(report_file))

        content = report_file.read_text()

        # Check for required sections
        required_sections = [
            "# Documentation Impact Analysis",
            "## Summary",
            "## Documentation Files",
            "## Endpoints",
            "## Code Examples",
            "## Postman Collections",
            "## Recommendations",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_statistics_calculation(self, temp_audit_reports):
        """Test statistics calculation"""
        generator = DocumentationImpactReportGenerator(audit_reports_dir=str(temp_audit_reports))

        generator.load_audit_reports()
        references = generator.compile_documentation_references()

        assert "statistics" in references
        stats = references["statistics"]
        assert "total_documentation_files" in stats
        assert stats["total_documentation_files"] > 0
        assert "total_code_examples" in stats
