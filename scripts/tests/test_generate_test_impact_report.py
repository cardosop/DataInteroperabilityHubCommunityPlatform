"""
Unit tests for test impact report generator

Tests the comprehensive compilation of test impact data from multiple sources.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import module with hyphenated name using importlib
script_path = scripts_dir / "generate-test-impact-report.py"
spec = importlib.util.spec_from_file_location("generate_test_impact_report", script_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {script_path}")
generate_test_impact_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_test_impact_report)

# Import classes
TestImpactReportGenerator = generate_test_impact_report.TestImpactReportGenerator


class TestTestImpactReportGenerator:
    """Test test impact report generator"""

    def test_load_test_endpoint_data(self):
        """Test loading test endpoint data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock test impact analysis file
            test_impact_file = Path(tmpdir) / "test-impact-analysis.json"
            test_impact_data = {
                "summary": {
                    "total_test_files": 2,
                    "total_endpoints_referenced": 2,
                    "total_references": 3,
                },
                "test_mappings": [
                    {
                        "test_file": "tests/unit/test_assets.py",
                        "test_type": "unit",
                        "endpoint_path": "/api/v1/assets/",
                        "service": "assets",
                    }
                ],
            }
            with open(test_impact_file, "w") as f:
                json.dump(test_impact_data, f)

            generator = TestImpactReportGenerator(
                test_impact_file=str(test_impact_file),
                fixtures_file=str(Path(tmpdir) / "fixtures.json"),
                utilities_file=str(Path(tmpdir) / "utilities.json"),
                project_root=Path(tmpdir),
            )
            data = generator._load_test_endpoint_data()

            assert data["summary"]["total_test_files"] == 2
            assert len(data["test_mappings"]) == 1

    def test_load_fixtures_data(self):
        """Test loading fixtures and factories data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock fixtures file
            fixtures_file = Path(tmpdir) / "test-fixtures-and-factories-report.json"
            fixtures_data = {
                "summary": {
                    "total_fixture_files": 2,
                    "total_factory_classes": 1,
                    "total_endpoint_urls": 1,
                },
                "fixture_files": [
                    {"path": "tests/fixtures/test.json", "endpoints": ["/api/v1/assets/"]}
                ],
            }
            with open(fixtures_file, "w") as f:
                json.dump(fixtures_data, f)

            generator = TestImpactReportGenerator(
                test_impact_file=str(Path(tmpdir) / "test.json"),
                fixtures_file=str(fixtures_file),
                utilities_file=str(Path(tmpdir) / "utilities.json"),
                project_root=Path(tmpdir),
            )
            data = generator._load_fixtures_data()

            assert data["summary"]["total_fixture_files"] == 2
            assert len(data["fixture_files"]) == 1

    def test_load_utilities_data(self):
        """Test loading utilities data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock utilities file
            utilities_file = Path(tmpdir) / "test-utilities-report.json"
            utilities_data = {
                "summary": {
                    "total_utility_modules": 2,
                    "total_helper_functions": 5,
                    "total_endpoint_urls": 2,
                },
                "utility_modules": [
                    {"path": "tests/utils/test_helper.py", "has_endpoint_urls": True}
                ],
            }
            with open(utilities_file, "w") as f:
                json.dump(utilities_data, f)

            generator = TestImpactReportGenerator(
                test_impact_file=str(Path(tmpdir) / "test.json"),
                fixtures_file=str(Path(tmpdir) / "fixtures.json"),
                utilities_file=str(utilities_file),
                project_root=Path(tmpdir),
            )
            data = generator._load_utilities_data()

            assert data["summary"]["total_utility_modules"] == 2
            assert len(data["utility_modules"]) == 1

    def test_compile_test_references(self):
        """Test compiling test file references"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = TestImpactReportGenerator(
                test_impact_file=str(Path(tmpdir) / "test.json"),
                fixtures_file=str(Path(tmpdir) / "fixtures.json"),
                utilities_file=str(Path(tmpdir) / "utilities.json"),
                project_root=Path(tmpdir),
            )

            # Set mock data
            generator.test_endpoint_data = {
                "test_mappings": [
                    {
                        "test_file": "tests/unit/test_assets.py",
                        "test_type": "unit",
                        "endpoint_path": "/api/v1/assets/",
                        "service": "assets",
                    }
                ]
            }
            generator.fixtures_data = {
                "fixture_files": [
                    {"path": "tests/fixtures/test.json", "endpoints": ["/api/v1/assets/"]}
                ]
            }
            generator.utilities_data = {
                "utility_modules": [
                    {
                        "path": "tests/utils/test_helper.py",
                        "has_endpoint_urls": True,
                        "type": "utility",
                        "functions": ["get_api_url"],
                    }
                ],
                "endpoint_urls": [
                    {"endpoint_path": "/api/v1/assets/", "file": "tests/utils/test_helper.py"}
                ],
            }

            references = generator._compile_test_references()

            assert len(references["test_files"]) >= 1
            assert len(references["fixture_files"]) >= 1
            assert len(references["utility_files"]) >= 1
            assert "endpoint_references" in references

    def test_generate_impact_matrix(self):
        """Test generating test impact matrix"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = TestImpactReportGenerator(
                test_impact_file=str(Path(tmpdir) / "test.json"),
                fixtures_file=str(Path(tmpdir) / "fixtures.json"),
                utilities_file=str(Path(tmpdir) / "utilities.json"),
                project_root=Path(tmpdir),
            )

            # Set mock references
            references = {
                "test_files": [
                    {
                        "file": "tests/unit/test_assets.py",
                        "test_type": "unit",
                        "endpoint_path": "/api/v1/assets/",
                        "service": "assets",
                    }
                ],
                "fixture_files": [],
                "utility_files": [],
                "endpoint_references": {
                    "/api/v1/assets/": [
                        {
                            "file": "tests/unit/test_assets.py",
                            "type": "test_file",
                            "test_type": "unit",
                            "service": "assets",
                        }
                    ]
                },
            }

            matrix = generator._generate_impact_matrix(references)

            assert "by_endpoint" in matrix
            assert "by_service" in matrix
            assert "by_test_type" in matrix

    def test_generate_report(self):
        """Test generating comprehensive test impact report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock data files
            test_impact_file = Path(tmpdir) / "test-impact-analysis.json"
            fixtures_file = Path(tmpdir) / "test-fixtures-and-factories-report.json"
            utilities_file = Path(tmpdir) / "test-utilities-report.json"

            test_impact_data = {"summary": {"total_test_files": 1}, "test_mappings": []}
            fixtures_data = {"summary": {"total_fixture_files": 1}, "fixture_files": []}
            utilities_data = {
                "summary": {"total_utility_modules": 1},
                "utility_modules": [],
                "endpoint_urls": [],
            }

            with open(test_impact_file, "w") as f:
                json.dump(test_impact_data, f)
            with open(fixtures_file, "w") as f:
                json.dump(fixtures_data, f)
            with open(utilities_file, "w") as f:
                json.dump(utilities_data, f)

            generator = TestImpactReportGenerator(
                test_impact_file=str(test_impact_file),
                fixtures_file=str(fixtures_file),
                utilities_file=str(utilities_file),
                project_root=Path(tmpdir),
            )

            report_file = Path(tmpdir) / "test-impact-report.md"
            generator.generate_report(report_file)

            assert report_file.exists()
            content = report_file.read_text()
            assert "# Test Impact Analysis" in content or "# Test Impact Report" in content

    def test_verify_report_completeness(self):
        """Test verifying report completeness with actual generated report"""
        from pathlib import Path

        # Use actual report file if it exists
        report_file = Path("docs/api-audit/test-impact-analysis.md")
        if not report_file.exists():
            pytest.skip("Report file not found - run generate-test-impact-report.py first")

        content = report_file.read_text()

        # Verify all required sections exist
        required_sections = [
            "# Test Impact Analysis",
            "## Executive Summary",
            "## Impact Matrix by Endpoint",
            "## Impact Matrix by Service",
            "## Impact Matrix by Test Type",
            "## Test Files",
            "## Fixture Files",
            "## Utility Files",
            "## Data Sources",
        ]

        for section in required_sections:
            assert section in content, f"Missing required section: {section}"

        # Verify report has content
        assert len(content) > 1000, "Report seems too short"
        assert len(content.splitlines()) > 50, "Report has too few lines"

        # Verify statistics are present
        assert "Total Test Files" in content
        assert "Total Fixture Files" in content
        assert "Total Endpoints Referenced" in content

        # Verify tables are present
        assert "| Endpoint |" in content or "| Test Files |" in content

        print(
            f"✓ Report completeness verified: {len(content)} characters, {len(content.splitlines())} lines"
        )
