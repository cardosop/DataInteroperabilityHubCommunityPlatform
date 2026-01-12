"""
Test CKAN Fixtures Loading

This test verifies that all CKAN fixtures can be loaded correctly.
"""
import unittest
from pathlib import Path
import json

from tests.fixtures.marketplace.ckan import (
    load_fixture,
    get_api_response_fixture,
    get_dataset_fixture,
    get_resource_fixture,
    FIXTURES_DIR
)


class TestCKANFixturesLoading(unittest.TestCase):
    """Test that all CKAN fixtures load correctly"""

    def test_fixtures_directory_exists(self):
        """Test that fixtures directory exists"""
        self.assertTrue(FIXTURES_DIR.exists(), f"Fixtures directory not found: {FIXTURES_DIR}")
        self.assertTrue(FIXTURES_DIR.is_dir())

    def test_api_response_fixtures_load(self):
        """Test that all API response fixtures load correctly"""
        api_responses = [
            'status_show',
            'package_list',
            'package_search',
            'package_show',
            'package_create',
            'package_update',
            'package_delete',
            'resource_show',
            'error_not_found',
            'error_validation',
            'error_permission',
        ]

        for action in api_responses:
            with self.subTest(action=action):
                fixture = get_api_response_fixture(action)
                self.assertIsInstance(fixture, dict)
                # All API responses should have 'success' key (or 'error' for error responses)
                self.assertTrue('success' in fixture or 'error' in fixture)

    def test_dataset_fixtures_load(self):
        """Test that all dataset fixtures load correctly"""
        datasets = [
            'sample_dataset',
            'multilingual_dataset',
            'dataset_with_odps_metadata',
            'dataset_with_odcs_metadata',
            'minimal_dataset',
        ]

        for dataset_name in datasets:
            with self.subTest(dataset=dataset_name):
                fixture = get_dataset_fixture(dataset_name)
                self.assertIsInstance(fixture, dict)
                # All datasets should have 'id' and 'name' keys
                self.assertIn('id', fixture)
                self.assertIn('name', fixture)

    def test_resource_fixtures_load(self):
        """Test that all resource fixtures load correctly"""
        resources = [
            'sample_csv_resource',
            'sample_json_resource',
            'sample_api_resource',
            'minimal_resource',
        ]

        for resource_name in resources:
            with self.subTest(resource=resource_name):
                fixture = get_resource_fixture(resource_name)
                self.assertIsInstance(fixture, dict)
                # All resources should have 'id' and 'url' keys
                self.assertIn('id', fixture)
                self.assertIn('url', fixture)

    def test_load_fixture_with_relative_path(self):
        """Test loading fixture with relative path"""
        fixture = load_fixture('api_responses/status_show.json')
        self.assertIsInstance(fixture, dict)
        self.assertTrue(fixture.get('success'))

    def test_fixture_file_not_found_raises_error(self):
        """Test that loading non-existent fixture raises FileNotFoundError"""
        with self.assertRaises(FileNotFoundError):
            load_fixture('nonexistent/fixture.json')

    def test_api_response_fixture_structure(self):
        """Test that API response fixtures have correct structure"""
        # Test successful response
        status_fixture = get_api_response_fixture('status_show')
        self.assertTrue(status_fixture['success'])
        self.assertIn('result', status_fixture)

        # Test error response
        error_fixture = get_api_response_fixture('error_not_found')
        self.assertFalse(error_fixture['success'])
        self.assertIn('error', error_fixture)

    def test_dataset_fixture_structure(self):
        """Test that dataset fixtures have correct structure"""
        dataset = get_dataset_fixture('sample_dataset')
        self.assertIn('id', dataset)
        self.assertIn('name', dataset)
        self.assertIn('title', dataset)
        self.assertIn('type', dataset)
        self.assertEqual(dataset['type'], 'dataset')

    def test_resource_fixture_structure(self):
        """Test that resource fixtures have correct structure"""
        resource = get_resource_fixture('sample_csv_resource')
        self.assertIn('id', resource)
        self.assertIn('package_id', resource)
        self.assertIn('url', resource)
        self.assertIn('format', resource)

    def test_multilingual_dataset_fixture(self):
        """Test multilingual dataset fixture structure"""
        dataset = get_dataset_fixture('multilingual_dataset')
        # Multilingual fields may be dicts
        self.assertIn('title', dataset)
        # Title can be string or dict
        self.assertTrue(isinstance(dataset['title'], (str, dict)))

    def test_odps_metadata_dataset_fixture(self):
        """Test ODPS metadata dataset fixture"""
        dataset = get_dataset_fixture('dataset_with_odps_metadata')
        self.assertIn('extras', dataset)
        # Check for ODPS metadata in extras
        odps_extras = [e for e in dataset.get('extras', []) if e.get('key') == 'x_odps']
        self.assertGreater(len(odps_extras), 0)

    def test_odcs_metadata_dataset_fixture(self):
        """Test ODCS metadata dataset fixture"""
        dataset = get_dataset_fixture('dataset_with_odcs_metadata')
        self.assertIn('extras', dataset)
        # Check for ODCS metadata in extras
        odcs_extras = [e for e in dataset.get('extras', []) if e.get('key') == 'x_odcs']
        self.assertGreater(len(odcs_extras), 0)

    def test_all_fixture_files_are_valid_json(self):
        """Test that all fixture files contain valid JSON"""
        fixtures_dir = FIXTURES_DIR

        # Find all JSON files recursively
        json_files = list(fixtures_dir.rglob('*.json'))
        self.assertGreater(len(json_files), 0, "No JSON fixture files found")

        for json_file in json_files:
            with self.subTest(file=json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                        self.assertIsInstance(data, (dict, list))
                    except json.JSONDecodeError as e:
                        self.fail(f"Invalid JSON in {json_file}: {e}")


if __name__ == '__main__':
    unittest.main()

