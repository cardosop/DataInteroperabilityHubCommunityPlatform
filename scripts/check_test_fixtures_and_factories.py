#!/usr/bin/env python3
"""
Check Test Fixtures and Factories

This script searches for test fixture files, factory classes, and checks endpoint URL usage in fixtures.

Usage:
    python scripts/check_test_fixtures_and_factories.py
"""

import ast
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


class TestFixturesAndFactoriesChecker:
    """Checker for test fixtures and factories"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.fixture_files: list[dict[str, Any]] = []
        self.factory_classes: list[dict[str, Any]] = []
        self.endpoint_urls: list[dict[str, Any]] = []
        self.fixture_endpoints: dict[str, list[str]] = defaultdict(list)

    def find_fixture_files(self) -> list[dict[str, Any]]:
        """Find all test fixture files"""
        fixtures = []

        # Search for JSON fixture files
        fixtures_dir = self.project_root / "tests" / "fixtures"
        if fixtures_dir.exists():
            for json_file in fixtures_dir.rglob("*.json"):
                fixtures.append(
                    {
                        "path": str(json_file.relative_to(self.project_root)),
                        "type": "json",
                        "size": json_file.stat().st_size,
                        "endpoints": self._extract_endpoints_from_json(json_file),
                    }
                )

        # Search for Python fixture files
        for py_file in self.project_root.rglob("**/fixtures*.py"):
            # Skip __pycache__ and virtual environments
            if "__pycache__" in str(py_file) or "venv" in str(py_file):
                continue

            # Check if it's in tests directory or has fixture-related content
            if "tests" in str(py_file) or self._has_fixture_content(py_file):
                fixtures.append(
                    {
                        "path": str(py_file.relative_to(self.project_root)),
                        "type": "python",
                        "size": py_file.stat().st_size,
                        "endpoints": self._extract_endpoints_from_python(py_file),
                    }
                )

        # Search for conftest.py files (pytest fixtures)
        for conftest in self.project_root.rglob("**/conftest.py"):
            if "__pycache__" in str(conftest) or "venv" in str(conftest):
                continue

            if "tests" in str(conftest):
                fixtures.append(
                    {
                        "path": str(conftest.relative_to(self.project_root)),
                        "type": "conftest",
                        "size": conftest.stat().st_size,
                        "endpoints": self._extract_endpoints_from_python(conftest),
                    }
                )

        self.fixture_files = fixtures
        return fixtures

    def find_factory_classes(self) -> list[dict[str, Any]]:
        """Find all factory classes"""
        factories = []

        # Search for factory files
        for factory_file in self.project_root.rglob("**/factories*.py"):
            if "__pycache__" in str(factory_file) or "venv" in str(factory_file):
                continue

            if "tests" in str(factory_file) or "factory" in factory_file.name.lower():
                try:
                    with open(factory_file, encoding="utf-8") as f:
                        content = f.read()
                        tree = ast.parse(content, filename=str(factory_file))

                    factory_classes = self._extract_factory_classes(tree, factory_file)
                    factories.extend(factory_classes)
                except Exception:
                    # Skip files that can't be parsed
                    continue

        self.factory_classes = factories
        return factories

    def check_endpoint_url_usage(self) -> list[dict[str, Any]]:
        """Check endpoint URL usage in fixtures"""
        endpoint_patterns = [
            r'/api/v1/[^\s"\'`]+',
            r'http://localhost:\d+/api/v1/[^\s"\'`]+',
            r'https://[^\s"\'`]+/api/v1/[^\s"\'`]+',
            r"localhost:\d+",
            r"api\.example\.com",
            r'http://[^\s"\'`]+:808\d+',
        ]

        endpoints = []

        # Check fixture files
        for fixture in self.fixture_files:
            file_path = self.project_root / fixture["path"]
            if file_path.exists():
                found_endpoints = self._find_endpoints_in_file(file_path, endpoint_patterns)
                for endpoint in found_endpoints:
                    endpoints.append(
                        {
                            "file": fixture["path"],
                            "type": fixture["type"],
                            "endpoint": endpoint,
                            "context": "fixture",
                        }
                    )
                    self.fixture_endpoints[fixture["path"]].append(endpoint)

        # Check factory files
        for factory in self.factory_classes:
            file_path = self.project_root / factory["file_path"]
            if file_path.exists():
                found_endpoints = self._find_endpoints_in_file(file_path, endpoint_patterns)
                for endpoint in found_endpoints:
                    endpoints.append(
                        {
                            "file": factory["file_path"],
                            "type": "factory",
                            "endpoint": endpoint,
                            "context": f"factory_class:{factory['class_name']}",
                        }
                    )

        self.endpoint_urls = endpoints
        return endpoints

    def _extract_endpoints_from_json(self, json_file: Path) -> list[str]:
        """Extract endpoint URLs from JSON fixture file"""
        endpoints = []
        try:
            with open(json_file, encoding="utf-8") as f:
                content = f.read()
                # Try to parse as JSON
                try:
                    data = json.loads(content)
                    endpoints.extend(self._extract_endpoints_from_dict(data))
                except json.JSONDecodeError:
                    # If not valid JSON, search for URL patterns in raw content
                    endpoints.extend(self._find_urls_in_text(content))
        except Exception:
            pass
        return endpoints

    def _extract_endpoints_from_python(self, py_file: Path) -> list[str]:
        """Extract endpoint URLs from Python fixture file"""
        endpoints = []
        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                endpoints.extend(self._find_urls_in_text(content))
        except Exception:
            pass
        return endpoints

    def _extract_endpoints_from_dict(self, data: Any, path: str = "") -> list[str]:
        """Recursively extract endpoints from dictionary"""
        endpoints = []
        if isinstance(data, dict):
            for key, value in data.items():
                endpoints.extend(self._extract_endpoints_from_dict(value, f"{path}.{key}"))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                endpoints.extend(self._extract_endpoints_from_dict(item, f"{path}[{i}]"))
        elif isinstance(data, str):
            # Check if string contains endpoint-like patterns
            if (
                "/api/v1/" in data
                or "localhost:" in data
                or "http://" in data
                or "https://" in data
            ):
                endpoints.append(data)
        return endpoints

    def _find_urls_in_text(self, text: str) -> list[str]:
        """Find URL patterns in text"""
        patterns = [
            r'/api/v1/[^\s"\'`\)]+',
            r'http://localhost:\d+/[^\s"\'`\)]+',
            r'https://[^\s"\'`\)]+/api/v1/[^\s"\'`\)]+',
            r"localhost:\d+",
        ]
        urls = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            urls.extend(matches)
        return list(set(urls))

    def _find_endpoints_in_file(self, file_path: Path, patterns: list[str]) -> list[str]:
        """Find endpoints in a file using patterns"""
        endpoints = []
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    endpoints.extend(matches)
        except Exception:
            pass
        return list(set(endpoints))

    def _has_fixture_content(self, file_path: Path) -> bool:
        """Check if file has fixture-related content"""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read().lower()
                return any(
                    keyword in content
                    for keyword in [
                        "@pytest.fixture",
                        "@fixture",
                        "def fixture",
                        "fixture_data",
                        "test_fixture",
                        "sample_data",
                        "mock_data",
                    ]
                )
        except Exception:
            return False

    def _extract_factory_classes(self, tree: ast.AST, file_path: Path) -> list[dict[str, Any]]:
        """Extract factory class definitions from AST"""
        factories = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a factory class
                is_factory = "Factory" in node.name or any(
                    "factory" in base.id.lower() if isinstance(base, ast.Name) else False
                    for base in node.bases
                )

                if is_factory:
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)

                    factories.append(
                        {
                            "file_path": str(file_path.relative_to(self.project_root)),
                            "class_name": node.name,
                            "line_number": node.lineno,
                            "methods": methods,
                            "method_count": len(methods),
                        }
                    )

        return factories

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive report"""
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_fixture_files": len(self.fixture_files),
                "total_factory_classes": len(self.factory_classes),
                "total_endpoint_urls": len(self.endpoint_urls),
                "fixture_files_by_type": self._count_by_type(self.fixture_files, "type"),
                "factories_by_file": len(set(f["file_path"] for f in self.factory_classes)),
            },
            "fixture_files": self.fixture_files,
            "factory_classes": self.factory_classes,
            "endpoint_urls": self.endpoint_urls,
            "fixture_endpoints": dict(self.fixture_endpoints),
        }

    def _count_by_type(self, items: list[dict[str, Any]], key: str) -> dict[str, int]:
        """Count items by type"""
        counts = defaultdict(int)
        for item in items:
            counts[item.get(key, "unknown")] += 1
        return dict(counts)

    def save_report(self, output_dir: Path | None = None) -> Path:
        """Save report to file"""
        if output_dir is None:
            output_dir = self.project_root / "docs" / "api-audit"
        output_dir.mkdir(parents=True, exist_ok=True)

        report = self.generate_report()

        # Save JSON report
        json_file = output_dir / "test-fixtures-and-factories-report.json"
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)

        # Generate markdown report
        md_file = output_dir / "test-fixtures-and-factories-report.md"
        self._generate_markdown_report(report, md_file)

        return json_file

    def _generate_markdown_report(self, report: dict[str, Any], output_file: Path):
        """Generate markdown report"""
        with open(output_file, "w") as f:
            f.write("# Test Fixtures and Factories Report\n\n")
            f.write(f"**Generated:** {report['generated_at']}\n\n")

            # Summary
            summary = report["summary"]
            f.write("## Summary\n\n")
            f.write(f"- **Total Fixture Files:** {summary['total_fixture_files']}\n")
            f.write(f"- **Total Factory Classes:** {summary['total_factory_classes']}\n")
            f.write(f"- **Total Endpoint URLs Found:** {summary['total_endpoint_urls']}\n")
            f.write(f"- **Factory Files:** {summary['factories_by_file']}\n\n")

            # Fixture files by type
            f.write("### Fixture Files by Type\n\n")
            for file_type, count in summary["fixture_files_by_type"].items():
                f.write(f"- **{file_type}**: {count}\n")
            f.write("\n")

            # Fixture files
            f.write("## Fixture Files\n\n")
            for fixture in report["fixture_files"]:
                f.write(f"### {fixture['path']}\n")
                f.write(f"- **Type:** {fixture['type']}\n")
                f.write(f"- **Size:** {fixture['size']} bytes\n")
                if fixture.get("endpoints"):
                    f.write(f"- **Endpoints Found:** {len(fixture['endpoints'])}\n")
                    for endpoint in fixture["endpoints"][:5]:
                        f.write(f"  - `{endpoint}`\n")
                    if len(fixture["endpoints"]) > 5:
                        f.write(f"  - ... and {len(fixture['endpoints']) - 5} more\n")
                f.write("\n")

            # Factory classes
            f.write("## Factory Classes\n\n")
            factories_by_file = defaultdict(list)
            for factory in report["factory_classes"]:
                factories_by_file[factory["file_path"]].append(factory)

            for file_path, factories in factories_by_file.items():
                f.write(f"### {file_path}\n\n")
                for factory in factories:
                    f.write(f"- **{factory['class_name']}** (line {factory['line_number']})\n")
                    f.write(f"  - Methods: {factory['method_count']}\n")
                    if factory.get("methods"):
                        f.write(f"  - Method names: {', '.join(factory['methods'][:10])}\n")
                        if len(factory["methods"]) > 10:
                            f.write(f"  - ... and {len(factory['methods']) - 10} more methods\n")
                    f.write("\n")

            # Endpoint URLs
            if report["endpoint_urls"]:
                f.write("## Endpoint URLs in Fixtures\n\n")
                endpoints_by_file = defaultdict(list)
                for endpoint_info in report["endpoint_urls"]:
                    endpoints_by_file[endpoint_info["file"]].append(endpoint_info)

                for file_path, endpoints in list(endpoints_by_file.items())[:20]:
                    f.write(f"### {file_path}\n\n")
                    for endpoint_info in endpoints[:10]:
                        f.write(f"- `{endpoint_info['endpoint']}` ({endpoint_info['context']})\n")
                    if len(endpoints) > 10:
                        f.write(f"- ... and {len(endpoints) - 10} more endpoints\n")
                    f.write("\n")

                if len(endpoints_by_file) > 20:
                    f.write(f"\n... and {len(endpoints_by_file) - 20} more files with endpoints\n")


def main():
    """Main entry point"""
    checker = TestFixturesAndFactoriesChecker()

    print("=" * 80)
    print("Test Fixtures and Factories Checker")
    print("=" * 80)
    print()

    print("Searching for fixture files...")
    fixtures = checker.find_fixture_files()
    print(f"  Found {len(fixtures)} fixture files")

    print("Searching for factory classes...")
    factories = checker.find_factory_classes()
    print(f"  Found {len(factories)} factory classes")

    print("Checking endpoint URL usage...")
    endpoints = checker.check_endpoint_url_usage()
    print(f"  Found {len(endpoints)} endpoint URLs in fixtures")

    print("Generating report...")
    report_file = checker.save_report()
    print(f"  Report saved to: {report_file}")

    print()
    print("=" * 80)
    print("Check Complete")
    print("=" * 80)
    print()
    report = checker.generate_report()
    summary = report["summary"]
    print("Summary:")
    print(f"  Fixture Files: {summary['total_fixture_files']}")
    print(f"  Factory Classes: {summary['total_factory_classes']}")
    print(f"  Endpoint URLs: {summary['total_endpoint_urls']}")


if __name__ == "__main__":
    main()
