#!/usr/bin/env python3
"""
Tests for Test Fixtures and Factories Checker

Tests the comprehensive checking of test fixtures and factories.
"""

import json
import unittest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestFixturesAndFactoriesChecker(unittest.TestCase):
    """Test fixtures and factories checker"""

    @property
    def report_path(self):
        """Path to the generated report"""
        return project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'

    @property
    def report(self):
        """Load the report"""
        if not self.report_path.exists():
            raise FileNotFoundError(
                f"Report not found at {self.report_path}. "
                "Run 'python3 scripts/check_test_fixtures_and_factories.py' first."
            )

        with open(self.report_path) as f:
            return json.load(f)

    def test_report_exists(self):
        """Test that the report file exists"""
        self.assertTrue(self.report_path.exists(),
                       f"Report not found at {self.report_path}")

    def test_report_structure(self):
        """Test that the report has the correct structure"""
        report = self.report
        self.assertIn('generated_at', report)
        self.assertIn('summary', report)
        self.assertIn('fixture_files', report)
        self.assertIn('factory_classes', report)
        self.assertIn('endpoint_urls', report)
        self.assertIn('fixture_endpoints', report)

    def test_summary_fields(self):
        """Test that summary contains required fields"""
        report = self.report
        summary = report['summary']
        self.assertIn('total_fixture_files', summary)
        self.assertIn('total_factory_classes', summary)
        self.assertIn('total_endpoint_urls', summary)
        self.assertIn('fixture_files_by_type', summary)
        self.assertIn('factories_by_file', summary)

    def test_summary_values(self):
        """Test that summary values are valid"""
        report = self.report
        summary = report['summary']

        self.assertGreater(summary['total_fixture_files'], 0,
                          "Should have at least one fixture file")
        self.assertGreaterEqual(summary['total_factory_classes'], 0,
                                "Factory classes should be non-negative")
        self.assertGreaterEqual(summary['total_endpoint_urls'], 0,
                               "Endpoint URLs should be non-negative")

    def test_fixture_files_structure(self):
        """Test that fixture files have correct structure"""
        report = self.report
        fixture_files = report['fixture_files']

        self.assertIsInstance(fixture_files, list)
        self.assertGreater(len(fixture_files), 0, "Should have at least one fixture file")

        for fixture in fixture_files:
            self.assertIn('path', fixture)
            self.assertIn('type', fixture)
            self.assertIn('size', fixture)
            self.assertIn('endpoints', fixture)

            self.assertIsInstance(fixture['path'], str)
            self.assertIsInstance(fixture['type'], str)
            self.assertIsInstance(fixture['size'], int)
            self.assertIsInstance(fixture['endpoints'], list)

            # Verify file exists
            file_path = project_root / fixture['path']
            self.assertTrue(file_path.exists(),
                          f"Fixture file should exist: {fixture['path']}")

    def test_factory_classes_structure(self):
        """Test that factory classes have correct structure"""
        report = self.report
        factory_classes = report['factory_classes']

        self.assertIsInstance(factory_classes, list)

        for factory in factory_classes:
            self.assertIn('file_path', factory)
            self.assertIn('class_name', factory)
            self.assertIn('line_number', factory)
            self.assertIn('methods', factory)
            self.assertIn('method_count', factory)

            self.assertIsInstance(factory['file_path'], str)
            self.assertIsInstance(factory['class_name'], str)
            self.assertIsInstance(factory['line_number'], int)
            self.assertIsInstance(factory['methods'], list)
            self.assertIsInstance(factory['method_count'], int)

            # Verify file exists
            file_path = project_root / factory['file_path']
            self.assertTrue(file_path.exists(),
                          f"Factory file should exist: {factory['file_path']}")

            # Verify class name contains Factory
            self.assertIn('Factory', factory['class_name'],
                         f"Factory class name should contain 'Factory': {factory['class_name']}")

    def test_endpoint_urls_structure(self):
        """Test that endpoint URLs have correct structure"""
        report = self.report
        endpoint_urls = report['endpoint_urls']

        self.assertIsInstance(endpoint_urls, list)

        for endpoint_info in endpoint_urls:
            self.assertIn('file', endpoint_info)
            self.assertIn('type', endpoint_info)
            self.assertIn('endpoint', endpoint_info)
            self.assertIn('context', endpoint_info)

            self.assertIsInstance(endpoint_info['file'], str)
            self.assertIsInstance(endpoint_info['endpoint'], str)
            self.assertIsInstance(endpoint_info['context'], str)

            # Verify endpoint looks like a URL or path
            endpoint = endpoint_info['endpoint']
            is_valid_endpoint = (
                '/api/v1/' in endpoint or
                'localhost:' in endpoint or
                'http://' in endpoint or
                'https://' in endpoint or
                '.com' in endpoint or
                '.org' in endpoint or
                '.example' in endpoint or
                endpoint.startswith('/')
            )
            self.assertTrue(
                is_valid_endpoint,
                f"Endpoint should look like a URL or path: {endpoint}"
            )

    def test_fixture_endpoints_structure(self):
        """Test that fixture endpoints dictionary has correct structure"""
        report = self.report
        fixture_endpoints = report['fixture_endpoints']

        self.assertIsInstance(fixture_endpoints, dict)

        for file_path, endpoints in fixture_endpoints.items():
            self.assertIsInstance(file_path, str)
            self.assertIsInstance(endpoints, list)
            self.assertGreater(len(endpoints), 0,
                             f"Should have at least one endpoint for {file_path}")

    def test_fixture_files_match_summary(self):
        """Test that fixture files count matches summary"""
        report = self.report
        summary = report['summary']
        fixture_files = report['fixture_files']

        self.assertEqual(summary['total_fixture_files'], len(fixture_files),
                        "Fixture files count should match summary")

    def test_factory_classes_match_summary(self):
        """Test that factory classes count matches summary"""
        report = self.report
        summary = report['summary']
        factory_classes = report['factory_classes']

        self.assertEqual(summary['total_factory_classes'], len(factory_classes),
                        "Factory classes count should match summary")

    def test_endpoint_urls_match_summary(self):
        """Test that endpoint URLs count matches summary"""
        report = self.report
        summary = report['summary']
        endpoint_urls = report['endpoint_urls']

        self.assertEqual(summary['total_endpoint_urls'], len(endpoint_urls),
                        "Endpoint URLs count should match summary")

    def test_fixture_files_by_type(self):
        """Test that fixture files by type are accurate"""
        report = self.report
        summary = report['summary']
        fixture_files = report['fixture_files']

        # Count by type manually
        manual_count = {}
        for fixture in fixture_files:
            file_type = fixture['type']
            manual_count[file_type] = manual_count.get(file_type, 0) + 1

        # Compare with summary
        summary_by_type = summary['fixture_files_by_type']
        for file_type, count in manual_count.items():
            self.assertEqual(summary_by_type.get(file_type, 0), count,
                            f"Count for {file_type} should match")

    def test_known_fixture_files_exist(self):
        """Test that known fixture files are found"""
        report = self.report
        fixture_files = report['fixture_files']

        fixture_paths = [f['path'] for f in fixture_files]

        # Check for known fixture directories/files
        known_fixtures = [
            'tests/fixtures',
            'tests/fixtures/odps',
            'tests/conftest.py'
        ]

        # At least some known fixtures should be found
        found_known = sum(1 for known in known_fixtures
                         if any(known in path for path in fixture_paths))
        self.assertGreater(found_known, 0,
                          "Should find at least some known fixture files")

    def test_known_factory_files_exist(self):
        """Test that known factory files are found"""
        report = self.report
        factory_classes = report['factory_classes']

        factory_files = set(f['file_path'] for f in factory_classes)

        # Check for known factory files
        known_factories = [
            'tests/factories.py',
            'hub/apps/contracts/tests/factories.py',
            'hub/apps/assets/tests/factories.py',
            'hub/apps/files/tests/factories.py'
        ]

        # At least some known factories should be found
        found_known = sum(1 for known in known_factories if known in factory_files)
        self.assertGreater(found_known, 0,
                          "Should find at least some known factory files")

    def test_endpoints_in_fixtures(self):
        """Test that endpoints are found in fixture files"""
        report = self.report
        fixture_endpoints = report['fixture_endpoints']

        # Should have at least some fixtures with endpoints
        self.assertGreater(len(fixture_endpoints), 0,
                          "Should have at least some fixtures with endpoints")

    def test_factory_method_counts(self):
        """Test that factory method counts are accurate"""
        report = self.report
        factory_classes = report['factory_classes']

        for factory in factory_classes:
            method_count = factory['method_count']
            methods = factory['methods']

            self.assertEqual(method_count, len(methods),
                           f"Method count should match methods list for {factory['class_name']}")

    def test_fixture_file_sizes(self):
        """Test that fixture file sizes are valid"""
        report = self.report
        fixture_files = report['fixture_files']

        for fixture in fixture_files:
            size = fixture['size']
            self.assertGreaterEqual(size, 0,
                                  f"File size should be non-negative: {fixture['path']}")

            # Verify actual file size matches
            file_path = project_root / fixture['path']
            if file_path.exists():
                actual_size = file_path.stat().st_size
                self.assertEqual(size, actual_size,
                               f"Reported size should match actual size for {fixture['path']}")


class TestFixturesAndFactoriesCheckerIntegration(unittest.TestCase):
    """Integration tests for fixtures and factories checker"""

    def test_script_runs_successfully(self):
        """Test that the script runs successfully"""
        import subprocess

        script_path = project_root / 'scripts' / 'check_test_fixtures_and_factories.py'
        self.assertTrue(script_path.exists(), "Script should exist")

        # Run script and capture output
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60
        )

        self.assertEqual(result.returncode, 0,
                        f"Script should run successfully. Error: {result.stderr}")

        # Verify report was generated
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        self.assertTrue(report_path.exists(),
                       "Report should be generated after running script")

    def test_fixture_files_are_accessible(self):
        """Test that fixture files found are actually accessible"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        fixture_files = report['fixture_files']
        for fixture in fixture_files[:10]:  # Test first 10
            file_path = project_root / fixture['path']
            self.assertTrue(file_path.exists(),
                          f"Fixture file should be accessible: {fixture['path']}")

    def test_factory_files_are_accessible(self):
        """Test that factory files found are actually accessible"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        factory_classes = report['factory_classes']
        factory_files = set(f['file_path'] for f in factory_classes)

        for file_path_str in list(factory_files)[:10]:  # Test first 10
            file_path = project_root / file_path_str
            self.assertTrue(file_path.exists(),
                          f"Factory file should be accessible: {file_path_str}")

    def test_endpoints_are_valid_patterns(self):
        """Test that endpoints found match expected patterns"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        endpoint_urls = report['endpoint_urls']
        valid_patterns = [
            '/api/v1/',
            'localhost:',
            'http://',
            'https://',
            'api.example.com'
        ]

        for endpoint_info in endpoint_urls:
            endpoint = endpoint_info['endpoint']
            # At least one pattern should match
            matches = any(pattern in endpoint for pattern in valid_patterns)
            self.assertTrue(matches,
                          f"Endpoint should match at least one pattern: {endpoint}")

    def test_fixture_files_are_valid_json(self):
        """Test that JSON fixture files are valid JSON"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        fixture_files = report['fixture_files']
        json_fixtures = [f for f in fixture_files if f['type'] == 'json']

        # Test first 10 JSON fixtures
        for fixture in json_fixtures[:10]:
            file_path = project_root / fixture['path']
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    self.fail(f"JSON fixture file is not valid JSON: {fixture['path']} - {e}")

    def test_factory_classes_have_valid_syntax(self):
        """Test that factory class files have valid Python syntax"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        factory_classes = report['factory_classes']
        factory_files = set(f['file_path'] for f in factory_classes)

        # Test first 5 factory files
        import ast
        for file_path_str in list(factory_files)[:5]:
            file_path = project_root / file_path_str
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    ast.parse(content, filename=str(file_path))
                except SyntaxError as e:
                    self.fail(f"Factory file has syntax errors: {file_path_str} - {e}")

    def test_fixture_endpoints_are_unique(self):
        """Test that endpoints in fixtures are tracked correctly"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        fixture_endpoints = report['fixture_endpoints']

        # Check that endpoints are properly tracked per file
        for file_path, endpoints in fixture_endpoints.items():
            self.assertIsInstance(endpoints, list)
            self.assertGreater(len(endpoints), 0,
                             f"Should have at least one endpoint for {file_path}")

    def test_factory_methods_are_valid(self):
        """Test that factory methods are valid Python identifiers"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        import re

        with open(report_path) as f:
            report = json.load(f)

        factory_classes = report['factory_classes']
        identifier_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

        for factory in factory_classes:
            for method in factory.get('methods', []):
                self.assertTrue(
                    identifier_pattern.match(method),
                    f"Method name should be valid Python identifier: {method} in {factory['class_name']}"
                )

    def test_fixture_files_have_reasonable_sizes(self):
        """Test that fixture files have reasonable sizes"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        fixture_files = report['fixture_files']

        # Fixture files should be reasonable size (not empty, not too large)
        for fixture in fixture_files:
            size = fixture['size']
            self.assertGreater(size, 0,
                             f"Fixture file should not be empty: {fixture['path']}")
            self.assertLess(size, 10 * 1024 * 1024,  # 10MB max
                          f"Fixture file should not be too large: {fixture['path']}")

    def test_factory_classes_have_methods(self):
        """Test that factory classes have at least some methods"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        factory_classes = report['factory_classes']

        # Some factory classes should have at least one method
        # (Some might be base classes or use class-level attributes)
        factories_with_methods = [f for f in factory_classes if f['method_count'] > 0]
        self.assertGreater(len(factories_with_methods), 0,
                          "Should have at least some factory classes with methods")

        # Check that factories with methods have valid method lists
        for factory in factories_with_methods:
            self.assertGreater(len(factory['methods']), 0,
                             f"Factory {factory['class_name']} should have methods if method_count > 0")

    def test_endpoint_urls_have_context(self):
        """Test that endpoint URLs have meaningful context"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        endpoint_urls = report['endpoint_urls']

        for endpoint_info in endpoint_urls:
            context = endpoint_info['context']
            self.assertIsInstance(context, str)
            self.assertGreater(len(context), 0,
                             f"Endpoint context should not be empty: {endpoint_info['endpoint']}")

    def test_report_completeness(self):
        """Test that report is complete with all required data"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        # Check that we have data from all sources
        self.assertGreater(len(report['fixture_files']), 0,
                          "Should have at least one fixture file")
        self.assertGreaterEqual(len(report['factory_classes']), 0,
                               "Should have factory classes (can be 0)")
        self.assertGreaterEqual(len(report['endpoint_urls']), 0,
                               "Should have endpoint URLs (can be 0)")

    def test_fixture_files_in_tests_directory(self):
        """Test that fixture files are in tests directory"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        fixture_files = report['fixture_files']

        # Most fixture files should be in tests directory
        tests_fixtures = [f for f in fixture_files if 'tests' in f['path']]
        self.assertGreater(len(tests_fixtures), len(fixture_files) * 0.8,
                          "At least 80% of fixture files should be in tests directory")

    def test_factory_files_in_expected_locations(self):
        """Test that factory files are in expected locations"""
        report_path = project_root / 'docs' / 'api-audit' / 'test-fixtures-and-factories-report.json'
        if not report_path.exists():
            self.skipTest("Report not found. Run script first.")

        with open(report_path) as f:
            report = json.load(f)

        factory_classes = report['factory_classes']
        factory_files = set(f['file_path'] for f in factory_classes)

        # Factory files should be in tests or app tests directories
        expected_locations = ['tests/', '/tests/factories', 'tests/factories']
        factories_in_expected = sum(
            1 for file_path in factory_files
            if any(loc in file_path for loc in expected_locations)
        )

        self.assertGreater(factories_in_expected, 0,
                          "Should have at least some factories in expected locations")


if __name__ == '__main__':
    unittest.main()

