"""
Unit tests for normalization coverage metrics.
"""
import pytest

from hub.apps.contracts.coverage import (
    CoverageResult,
    SectionCoverage,
    calculate_coverage,
    coverage_report,
)
from hub.apps.contracts.models import OriginalSpecType


class TestCoverageMetrics:
    def test_calculate_coverage_per_section(self):
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "coverage-1",
            "info": {"name": "Coverage", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}], "primary_key": ["id"]},
            "quality": {"default_profile_key": "basic"},
        }

        result = calculate_coverage(hub_contract)

        assert result.overall > 0.0
        assert "info" in result.sections
        assert result.sections["schema"].required_score == 1.0
        assert "coverage-1" not in coverage_report(result)

    def test_calculate_coverage_for_missing_sections(self):
        result = calculate_coverage({})

        assert result.overall < 1.0
        assert result.sections["info"].missing_required == {"name"}
        assert result.sections["schema"].missing_required == {"fields"}

    def test_coverage_result_structure(self):
        """Test CoverageResult dataclass structure."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        result = calculate_coverage(hub_contract, spec_type=OriginalSpecType.ODCS)

        assert isinstance(result, CoverageResult)
        assert result.spec_type == OriginalSpecType.ODCS
        assert isinstance(result.overall, float)
        assert 0.0 <= result.overall <= 1.0
        assert isinstance(result.sections, dict)
        assert isinstance(result.unmapped_fields, list)

    def test_section_coverage_scoring(self):
        """Test SectionCoverage scoring logic."""
        section = SectionCoverage(
            name="test",
            required_fields={"field1", "field2"},
            optional_fields={"field3", "field4"},
            present_required={"field1"},
            present_optional={"field3"},
        )

        assert section.required_score == 0.5  # 1 of 2 required
        assert section.optional_score == 0.5  # 1 of 2 optional
        assert section.missing_required == {"field2"}
        assert section.missing_optional == {"field4"}
        # Weighted score: 0.7 * 0.5 + 0.3 * 0.5 = 0.5
        assert section.score() == 0.5

    def test_coverage_with_all_sections(self):
        """Test coverage calculation with all major sections present."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "full-coverage",
            "info": {"name": "Full Contract", "description": "Test", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "models": [{"name": "default", "fields": [{"name": "id", "data_type": "string"}]}],
            "quality": {"default_profile_key": "basic", "rules": []},
            "contact": [{"name": "Support", "email": "support@example.com"}],
            "servers": [{"type": "postgresql", "url": "postgresql://localhost"}],
            "terms": {"usage": "Internal use only"},
            "servicelevels": [{"name": "availability", "target": "99.9"}],
            "privacy_compliance": {"contains_personal_data": False},
            "lifecycle": {"data_source": "database"},
            "marketplace": {"license_summary": "MIT"},
            "original_spec": {"type": "ODCS", "version": "3.0.2"},
        }

        result = calculate_coverage(hub_contract)

        assert result.overall > 0.5  # Should have good coverage
        assert "info" in result.sections
        assert "schema" in result.sections
        assert "models" in result.sections
        assert "quality" in result.sections
        assert "contact" in result.sections
        assert "servers" in result.sections
        assert "terms" in result.sections
        assert "servicelevels" in result.sections

    def test_coverage_report_formatting(self):
        """Test coverage_report generates readable output."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "report-test",
            "info": {"name": "Report Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        result = calculate_coverage(hub_contract)
        report = coverage_report(result)

        assert isinstance(report, str)
        assert "ODCS" in report or "coverage" in report.lower()
        assert "%" in report  # Should contain percentage

    def test_coverage_with_extensions(self):
        """Test that extensions don't affect coverage calculation."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "ext-test",
            "info": {"name": "Extension Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "extensions": {"custom_field": "value"},
        }

        result = calculate_coverage(hub_contract)

        # Extensions should be in unmapped_fields but not affect section scores
        assert "extensions" not in result.sections
        assert result.overall > 0.0

    def test_coverage_empty_optional_fields(self):
        """Test coverage when optional fields are empty."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "minimal",
            "info": {"name": "Minimal Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            # Empty optional sections
            "quality": {},
            "contact": [],
            "servers": [],
        }

        result = calculate_coverage(hub_contract)

        # Should still calculate coverage (empty sections don't count as missing required)
        assert result.overall >= 0.0
        assert "quality" in result.sections
        assert "contact" in result.sections
        assert "servers" in result.sections
