#!/usr/bin/env python3
"""
Test Impact Report Generator

Comprehensive report generator that compiles test impact data from multiple sources:
- Test endpoint references (from audit-test-endpoints.py)
- Test fixtures and factories (from check_test_fixtures_and_factories.py)
- Test utilities and helpers (from audit-test-utilities.py)

Generates a unified test impact matrix and markdown report.

Usage:
    python generate-test-impact-report.py [options]

Options:
    --test-impact-file PATH    Path to test-impact-analysis.json (default: docs/api-audit/test-impact-analysis.json)
    --fixtures-file PATH        Path to test-fixtures-and-factories-report.json (default: docs/api-audit/test-fixtures-and-factories-report.json)
    --utilities-file PATH       Path to test-utilities-report.json (default: docs/api-audit/test-utilities-report.json)
    --output-file PATH          Output file path (default: docs/api-audit/test-impact-analysis.md)
    --project-root PATH         Project root directory (default: auto-detect)
    --verbose                   Verbose output
    --help                      Show this help message
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


class TestImpactReportGenerator:
    """Generate comprehensive test impact report from multiple data sources"""

    def __init__(
        self,
        test_impact_file: str,
        fixtures_file: str,
        utilities_file: str,
        project_root: str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize the test impact report generator.

        Args:
            test_impact_file: Path to test-impact-analysis.json
            fixtures_file: Path to test-fixtures-and-factories-report.json
            utilities_file: Path to test-utilities-report.json
            project_root: Project root directory (default: auto-detect)
            verbose: Enable verbose output
        """
        self.test_impact_file = Path(test_impact_file)
        self.fixtures_file = Path(fixtures_file)
        self.utilities_file = Path(utilities_file)
        if project_root:
            self.project_root = Path(project_root).resolve()
        else:
            self.project_root = self._find_project_root()
        self.verbose = verbose

        # Data storage
        self.test_endpoint_data: dict[str, Any] = {}
        self.fixtures_data: dict[str, Any] = {}
        self.utilities_data: dict[str, Any] = {}

    def _find_project_root(self) -> Path:
        """Find project root directory"""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (
                (current / "manage.py").exists()
                or (current / "pyproject.toml").exists()
                or (current / "setup.py").exists()
                or (current / ".git").exists()
            ):
                return current
            current = current.parent
        return Path.cwd()

    def _load_test_endpoint_data(self) -> dict[str, Any]:
        """Load test endpoint data from test-impact-analysis.json"""
        if not self.test_impact_file.exists():
            if self.verbose:
                print(f"Warning: Test impact file not found: {self.test_impact_file}")
            return {"summary": {}, "test_mappings": []}

        with open(self.test_impact_file) as f:
            data = json.load(f)

        self.test_endpoint_data = data
        if self.verbose:
            print(
                f"Loaded test endpoint data: {data['summary'].get('total_test_files', 0)} test files"
            )
        return data

    def _load_fixtures_data(self) -> dict[str, Any]:
        """Load fixtures and factories data"""
        if not self.fixtures_file.exists():
            if self.verbose:
                print(f"Warning: Fixtures file not found: {self.fixtures_file}")
            return {"summary": {}, "fixture_files": [], "factory_classes": [], "endpoint_urls": []}

        with open(self.fixtures_file) as f:
            data = json.load(f)

        self.fixtures_data = data
        if self.verbose:
            print(
                f"Loaded fixtures data: {data['summary'].get('total_fixture_files', 0)} fixture files"
            )
        return data

    def _load_utilities_data(self) -> dict[str, Any]:
        """Load utilities data"""
        if not self.utilities_file.exists():
            if self.verbose:
                print(f"Warning: Utilities file not found: {self.utilities_file}")
            return {
                "summary": {},
                "utility_modules": [],
                "helper_functions": [],
                "endpoint_urls": [],
            }

        with open(self.utilities_file) as f:
            data = json.load(f)

        self.utilities_data = data
        if self.verbose:
            print(
                f"Loaded utilities data: {data['summary'].get('total_utility_modules', 0)} utility modules"
            )
        return data

    def _compile_test_references(self) -> dict[str, Any]:
        """
        Compile test file references from all sources.

        Returns:
            Dictionary with compiled test references
        """
        references = {
            "test_files": [],
            "fixture_files": [],
            "factory_files": [],
            "utility_files": [],
            "endpoint_references": defaultdict(list),
        }

        # Compile test files from test endpoint data
        test_files_seen = set()
        for mapping in self.test_endpoint_data.get("test_mappings", []):
            test_file = mapping.get("test_file", "")
            if test_file and test_file not in test_files_seen:
                references["test_files"].append(
                    {
                        "file": test_file,
                        "test_type": mapping.get("test_type", "unknown"),
                        "endpoint_path": mapping.get("endpoint_path", ""),
                        "service": mapping.get("service", ""),
                        "method": mapping.get("method", "GET"),
                        "line_number": mapping.get("line_number", 0),
                        "source": "test_endpoint_audit",
                    }
                )
                test_files_seen.add(test_file)

            # Track endpoint references
            endpoint = mapping.get("endpoint_path", "")
            if endpoint:
                references["endpoint_references"][endpoint].append(
                    {
                        "file": test_file,
                        "type": "test_file",
                        "test_type": mapping.get("test_type", "unknown"),
                        "service": mapping.get("service", ""),
                        "line_number": mapping.get("line_number", 0),
                    }
                )

        # Compile fixture files
        fixture_files_seen = set()
        for fixture in self.fixtures_data.get("fixture_files", []):
            fixture_path = fixture.get("path", "")
            if fixture_path and fixture_path not in fixture_files_seen:
                references["fixture_files"].append(
                    {
                        "file": fixture_path,
                        "type": fixture.get("type", "json"),
                        "endpoints": fixture.get("endpoints", []),
                        "source": "fixtures_audit",
                    }
                )
                fixture_files_seen.add(fixture_path)

            # Track endpoint references in fixtures
            for endpoint in fixture.get("endpoints", []):
                if "/api/v1/" in endpoint:
                    references["endpoint_references"][endpoint].append(
                        {
                            "file": fixture_path,
                            "type": "fixture",
                            "fixture_type": fixture.get("type", "json"),
                        }
                    )

        # Compile factory files
        factory_files_seen = set()
        for factory in self.fixtures_data.get("factory_classes", []):
            factory_file = factory.get("file", "")
            if factory_file and factory_file not in factory_files_seen:
                references["factory_files"].append(
                    {
                        "file": factory_file,
                        "class_name": factory.get("class_name", ""),
                        "methods": factory.get("methods", []),
                        "source": "fixtures_audit",
                    }
                )
                factory_files_seen.add(factory_file)

        # Compile utility files with endpoint URLs
        utility_files_seen = set()
        for util in self.utilities_data.get("utility_modules", []):
            util_path = util.get("path", "")
            if util_path and util.get("has_endpoint_urls", False):
                if util_path not in utility_files_seen:
                    references["utility_files"].append(
                        {
                            "file": util_path,
                            "type": util.get("type", "utility"),
                            "functions": util.get("functions", []),
                            "source": "utilities_audit",
                        }
                    )
                    utility_files_seen.add(util_path)

        # Compile endpoint URLs from utilities
        for endpoint_url in self.utilities_data.get("endpoint_urls", []):
            endpoint = endpoint_url.get("endpoint_path", "")
            if endpoint:
                references["endpoint_references"][endpoint].append(
                    {
                        "file": endpoint_url.get("file", ""),
                        "type": "utility",
                        "function_name": endpoint_url.get("function_name"),
                        "line_number": endpoint_url.get("line_number", 0),
                    }
                )

        return references

    def _generate_impact_matrix(self, references: dict[str, Any]) -> dict[str, Any]:
        """
        Generate test impact matrix.

        Args:
            references: Compiled test references

        Returns:
            Dictionary with impact matrix data
        """
        matrix = {
            "by_endpoint": defaultdict(
                lambda: {
                    "test_files": set(),
                    "fixture_files": set(),
                    "utility_files": set(),
                    "test_types": set(),
                    "services": set(),
                    "total_references": 0,
                }
            ),
            "by_service": defaultdict(
                lambda: {
                    "test_files": set(),
                    "endpoints": set(),
                    "test_types": set(),
                    "total_references": 0,
                }
            ),
            "by_test_type": defaultdict(
                lambda: {
                    "test_files": set(),
                    "endpoints": set(),
                    "services": set(),
                    "total_references": 0,
                }
            ),
        }

        # Build endpoint matrix
        for endpoint, refs in references["endpoint_references"].items():
            for ref in refs:
                matrix["by_endpoint"][endpoint]["total_references"] += 1
                if ref["type"] == "test_file":
                    matrix["by_endpoint"][endpoint]["test_files"].add(ref["file"])
                    matrix["by_endpoint"][endpoint]["test_types"].add(
                        ref.get("test_type", "unknown")
                    )
                    matrix["by_endpoint"][endpoint]["services"].add(ref.get("service", ""))
                elif ref["type"] == "fixture":
                    matrix["by_endpoint"][endpoint]["fixture_files"].add(ref["file"])
                elif ref["type"] == "utility":
                    matrix["by_endpoint"][endpoint]["utility_files"].add(ref["file"])

        # Build service matrix
        for test_file in references["test_files"]:
            service = test_file.get("service", "")
            endpoint = test_file.get("endpoint_path", "")
            test_type = test_file.get("test_type", "unknown")

            if service:
                matrix["by_service"][service]["test_files"].add(test_file["file"])
                matrix["by_service"][service]["endpoints"].add(endpoint)
                matrix["by_service"][service]["test_types"].add(test_type)
                matrix["by_service"][service]["total_references"] += 1

        # Build test type matrix
        for test_file in references["test_files"]:
            test_type = test_file.get("test_type", "unknown")
            endpoint = test_file.get("endpoint_path", "")
            service = test_file.get("service", "")

            matrix["by_test_type"][test_type]["test_files"].add(test_file["file"])
            matrix["by_test_type"][test_type]["endpoints"].add(endpoint)
            matrix["by_test_type"][test_type]["services"].add(service)
            matrix["by_test_type"][test_type]["total_references"] += 1

        # Convert sets to lists for JSON serialization
        def convert_sets(obj):
            if isinstance(obj, dict):
                return {k: convert_sets(v) for k, v in obj.items()}
            elif isinstance(obj, set):
                return list(obj)
            return obj

        return convert_sets(matrix)

    def generate_report(self, output_file: Path):
        """
        Generate comprehensive test impact report.

        Args:
            output_file: Path to output markdown file
        """
        # Load all data sources
        if self.verbose:
            print("Loading data sources...")
        self._load_test_endpoint_data()
        self._load_fixtures_data()
        self._load_utilities_data()

        # Compile references
        if self.verbose:
            print("Compiling test references...")
        references = self._compile_test_references()

        # Generate impact matrix
        if self.verbose:
            print("Generating impact matrix...")
        matrix = self._generate_impact_matrix(references)

        # Generate summary statistics
        summary = self._generate_summary(references, matrix)

        # Generate markdown report
        if self.verbose:
            print(f"Generating markdown report to {output_file}...")
        self._generate_markdown_report(output_file, summary, references, matrix)

        if self.verbose:
            print("Report generation complete!")

    def _generate_summary(
        self, references: dict[str, Any], matrix: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate summary statistics"""
        # Get summaries from source data
        test_summary = self.test_endpoint_data.get("summary", {})
        fixtures_summary = self.fixtures_data.get("summary", {})
        utilities_summary = self.utilities_data.get("summary", {})

        return {
            "total_test_files": len(references["test_files"]),
            "total_fixture_files": len(references["fixture_files"]),
            "total_factory_files": len(references["factory_files"]),
            "total_utility_files": len(references["utility_files"]),
            "total_endpoints_referenced": len(references["endpoint_references"]),
            "total_endpoint_references": sum(
                len(refs) for refs in references["endpoint_references"].values()
            ),
            "test_files_by_type": self._count_by_type(references["test_files"], "test_type"),
            "endpoints_by_service": len(matrix["by_service"]),
            "endpoints_by_test_type": len(matrix["by_test_type"]),
            "source_summaries": {
                "test_endpoints": test_summary,
                "fixtures": fixtures_summary,
                "utilities": utilities_summary,
            },
        }

    def _count_by_type(self, items: list[dict[str, Any]], key: str) -> dict[str, int]:
        """Count items by type"""
        counts = defaultdict(int)
        for item in items:
            counts[item.get(key, "unknown")] += 1
        return dict(counts)

    def _generate_markdown_report(
        self,
        output_file: Path,
        summary: dict[str, Any],
        references: dict[str, Any],
        matrix: dict[str, Any],
    ):
        """Generate markdown report"""
        lines = [
            "# Test Impact Analysis",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Executive Summary",
            "",
            "This report provides a comprehensive analysis of test impact across the codebase, ",
            "compiling data from test files, fixtures, factories, and utilities.",
            "",
            "### Overall Statistics",
            "",
            f"- **Total Test Files**: {summary['total_test_files']}",
            f"- **Total Fixture Files**: {summary['total_fixture_files']}",
            f"- **Total Factory Files**: {summary['total_factory_files']}",
            f"- **Total Utility Files**: {summary['total_utility_files']}",
            f"- **Total Endpoints Referenced**: {summary['total_endpoints_referenced']}",
            f"- **Total Endpoint References**: {summary['total_endpoint_references']}",
            "",
            "### Test Files by Type",
            "",
        ]

        for test_type, count in sorted(summary["test_files_by_type"].items()):
            lines.append(f"- **{test_type}**: {count}")

        lines.extend(
            [
                "",
                "## Impact Matrix by Endpoint",
                "",
                "| Endpoint | Test Files | Fixture Files | Utility Files | Test Types | Services | Total Refs |",
                "|----------|-----------|---------------|---------------|------------|----------|------------|",
            ]
        )

        # Sort endpoints by total references (descending)
        sorted_endpoints = sorted(
            matrix["by_endpoint"].items(), key=lambda x: x[1]["total_references"], reverse=True
        )

        for endpoint, data in sorted_endpoints[:50]:  # Limit to top 50
            lines.append(
                f"| {endpoint} | {len(data['test_files'])} | "
                f"{len(data['fixture_files'])} | {len(data['utility_files'])} | "
                f"{len(data['test_types'])} | {len(data['services'])} | "
                f"{data['total_references']} |"
            )

        if len(sorted_endpoints) > 50:
            lines.append(f"\n... and {len(sorted_endpoints) - 50} more endpoints")

        lines.extend(
            [
                "",
                "## Impact Matrix by Service",
                "",
                "| Service | Test Files | Endpoints | Test Types | Total Refs |",
                "|---------|-----------|-----------|------------|------------|",
            ]
        )

        sorted_services = sorted(
            matrix["by_service"].items(), key=lambda x: x[1]["total_references"], reverse=True
        )

        for service, data in sorted_services:
            lines.append(
                f"| {service} | {len(data['test_files'])} | "
                f"{len(data['endpoints'])} | {len(data['test_types'])} | "
                f"{data['total_references']} |"
            )

        lines.extend(
            [
                "",
                "## Impact Matrix by Test Type",
                "",
                "| Test Type | Test Files | Endpoints | Services | Total Refs |",
                "|-----------|-----------|-----------|----------|------------|",
            ]
        )

        sorted_test_types = sorted(
            matrix["by_test_type"].items(), key=lambda x: x[1]["total_references"], reverse=True
        )

        for test_type, data in sorted_test_types:
            lines.append(
                f"| {test_type} | {len(data['test_files'])} | "
                f"{len(data['endpoints'])} | {len(data['services'])} | "
                f"{data['total_references']} |"
            )

        lines.extend(
            [
                "",
                "## Test Files",
                "",
                "| File | Type | Endpoint | Service | Method |",
                "|------|------|----------|---------|--------|",
            ]
        )

        for test_file in references["test_files"][:100]:  # Limit to first 100
            lines.append(
                f"| {test_file['file']} | {test_file['test_type']} | "
                f"{test_file.get('endpoint_path', 'N/A')} | "
                f"{test_file.get('service', 'N/A')} | {test_file.get('method', 'N/A')} |"
            )

        if len(references["test_files"]) > 100:
            lines.append(f"\n... and {len(references['test_files']) - 100} more test files")

        lines.extend(
            [
                "",
                "## Fixture Files",
                "",
                "| File | Type | Endpoints |",
                "|------|------|-----------|",
            ]
        )

        for fixture in references["fixture_files"][:50]:  # Limit to first 50
            endpoints_str = ", ".join(fixture.get("endpoints", [])[:3])
            if len(fixture.get("endpoints", [])) > 3:
                endpoints_str += "..."
            lines.append(f"| {fixture['file']} | {fixture['type']} | {endpoints_str or 'None'} |")

        if len(references["fixture_files"]) > 50:
            lines.append(f"\n... and {len(references['fixture_files']) - 50} more fixture files")

        lines.extend(
            [
                "",
                "## Utility Files with Endpoints",
                "",
                "| File | Type | Functions |",
                "|------|------|-----------|",
            ]
        )

        for util in references["utility_files"]:
            functions_str = ", ".join(util.get("functions", [])[:5])
            if len(util.get("functions", [])) > 5:
                functions_str += "..."
            lines.append(f"| {util['file']} | {util['type']} | {functions_str or 'None'} |")

        lines.extend(
            [
                "",
                "## Data Sources",
                "",
                "This report compiles data from:",
                "",
                "1. **Test Endpoint Audit** (`test-impact-analysis.json`)",
                f"   - {summary['source_summaries']['test_endpoints'].get('total_test_files', 0)} test files",
                f"   - {summary['source_summaries']['test_endpoints'].get('total_endpoints_referenced', 0)} endpoints referenced",
                "",
                "2. **Fixtures and Factories Audit** (`test-fixtures-and-factories-report.json`)",
                f"   - {summary['source_summaries']['fixtures'].get('total_fixture_files', 0)} fixture files",
                f"   - {summary['source_summaries']['fixtures'].get('total_factory_classes', 0)} factory classes",
                "",
                "3. **Utilities Audit** (`test-utilities-report.json`)",
                f"   - {summary['source_summaries']['utilities'].get('total_utility_modules', 0)} utility modules",
                f"   - {summary['source_summaries']['utilities'].get('total_helper_functions', 0)} helper functions",
                "",
            ]
        )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            f.write("\n".join(lines))


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive test impact report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--test-impact-file",
        type=str,
        default="docs/api-audit/test-impact-analysis.json",
        help="Path to test-impact-analysis.json",
    )
    parser.add_argument(
        "--fixtures-file",
        type=str,
        default="docs/api-audit/test-fixtures-and-factories-report.json",
        help="Path to test-fixtures-and-factories-report.json",
    )
    parser.add_argument(
        "--utilities-file",
        type=str,
        default="docs/api-audit/test-utilities-report.json",
        help="Path to test-utilities-report.json",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="docs/api-audit/test-impact-analysis.md",
        help="Output file path",
    )
    parser.add_argument(
        "--project-root", type=str, help="Project root directory (default: auto-detect)"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Initialize generator
    generator = TestImpactReportGenerator(
        test_impact_file=args.test_impact_file,
        fixtures_file=args.fixtures_file,
        utilities_file=args.utilities_file,
        project_root=args.project_root,
        verbose=args.verbose,
    )

    # Generate report
    output_file = Path(args.output_file)
    generator.generate_report(output_file)

    print(f"\nTest impact report generated: {output_file}")


if __name__ == "__main__":
    main()
