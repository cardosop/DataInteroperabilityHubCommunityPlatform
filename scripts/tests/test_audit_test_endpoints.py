"""
Unit tests for test endpoint audit script

Tests the comprehensive audit of test files for endpoint URL references.
"""
import os
import sys
import tempfile
import json
import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict
import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import module with hyphenated name using importlib
script_path = scripts_dir / 'audit-test-endpoints.py'
spec = importlib.util.spec_from_file_location('audit_test_endpoints', script_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {script_path}")
audit_test_endpoints = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_test_endpoints)

# Import classes
TestEndpointAuditor = audit_test_endpoints.TestEndpointAuditor


class TestTestEndpointAuditor:
    """Test test endpoint auditor"""

    def test_load_endpoints_from_inventory(self):
        """Test loading endpoints from inventory file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock inventory file
            inventory_file = Path(tmpdir) / 'endpoint-inventory-current.json'
            inventory_data = {
                'inventory': {
                    'summary': {
                        'total_endpoints': 2,
                        'total_services': 1
                    },
                    'endpoints': [
                        {
                            'full_path': '/api/v1/assets/',
                            'name': 'asset-list',
                            'service': 'assets',
                            'methods': ['GET']
                        },
                        {
                            'full_path': '/api/v1/contracts/',
                            'name': 'contract-list',
                            'service': 'contracts',
                            'methods': ['GET', 'POST']
                        }
                    ]
                }
            }
            with open(inventory_file, 'w') as f:
                json.dump(inventory_data, f)

            auditor = TestEndpointAuditor(
                inventory_file=str(inventory_file),
                project_root=Path(tmpdir)
            )
            endpoints = auditor.load_endpoints()

            assert len(endpoints) == 2
            assert endpoints[0]['full_path'] == '/api/v1/assets/'
            assert endpoints[1]['full_path'] == '/api/v1/contracts/'

    def test_search_test_files(self):
        """Test searching for test files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test directory structure
            test_dirs = {
                'tests/unit': ['test_unit1.py', 'test_unit2.py'],
                'tests/integration': ['test_integration1.py'],
                'tests/e2e': ['test_e2e1.py'],
                'tests/regression': ['test_regression1.py'],
                'hub/apps/test_app/tests': ['test_app1.py']
            }

            for test_dir, files in test_dirs.items():
                test_path = Path(tmpdir) / test_dir
                test_path.mkdir(parents=True, exist_ok=True)
                for file in files:
                    (test_path / file).write_text('# Test file\n')

            auditor = TestEndpointAuditor(
                inventory_file=str(Path(tmpdir) / 'inventory.json'),
                project_root=Path(tmpdir)
            )

            unit_tests = auditor._find_test_files('unit')
            integration_tests = auditor._find_test_files('integration')
            e2e_tests = auditor._find_test_files('e2e')
            regression_tests = auditor._find_test_files('regression')

            # Unit tests include tests in tests/unit and hub/apps/*/tests/
            assert len(unit_tests) >= 2, f"Expected at least 2 unit tests, got {len(unit_tests)}"
            assert any('test_unit1.py' in str(f) for f in unit_tests)
            assert any('test_unit2.py' in str(f) for f in unit_tests)
            # Integration tests
            assert len(integration_tests) >= 1, f"Expected at least 1 integration test, got {len(integration_tests)}"
            assert any('test_integration1.py' in str(f) for f in integration_tests)
            # E2E tests
            assert len(e2e_tests) >= 1, f"Expected at least 1 e2e test, got {len(e2e_tests)}"
            assert any('test_e2e1.py' in str(f) for f in e2e_tests)
            # Regression tests
            assert len(regression_tests) >= 1, f"Expected at least 1 regression test, got {len(regression_tests)}"
            assert any('test_regression1.py' in str(f) for f in regression_tests)

    def test_extract_endpoint_references(self):
        """Test extracting endpoint references from test file content"""
        test_content = '''
        def test_assets():
            response = self.client.get('/api/v1/assets/')
            response = self.client.post('/api/v1/assets/', data)
            response = self.client.get(f'/api/v1/assets/{asset_id}/')
        '''

        auditor = TestEndpointAuditor(
            inventory_file='dummy.json',
            project_root=Path('/tmp')
        )

        endpoints = [
            {'full_path': '/api/v1/assets/', 'name': 'asset-list', 'service': 'assets', 'methods': ['GET', 'POST']},
            {'full_path': '/api/v1/assets/{id}/', 'name': 'asset-detail', 'service': 'assets', 'methods': ['GET']}
        ]

        # Create a dummy file path for the test
        dummy_file = Path('/tmp/test_file.py')
        references = auditor._extract_endpoint_references(test_content, endpoints, dummy_file)

        assert len(references) >= 2, f"Expected at least 2 references, got {len(references)}"
        assert '/api/v1/assets/' in [r['endpoint_path'] for r in references]
        # Check that we found references with different methods
        methods = [r['method'] for r in references]
        assert 'GET' in methods
        assert 'POST' in methods

    def test_map_tests_to_endpoints(self):
        """Test mapping tests to endpoints"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file with endpoint references
            test_file = Path(tmpdir) / 'test_example.py'
            test_file.write_text('''
            def test_assets():
                self.client.get('/api/v1/assets/')
            def test_contracts():
                self.client.get('/api/v1/contracts/')
            ''')

            endpoints = [
                {'full_path': '/api/v1/assets/', 'name': 'asset-list', 'service': 'assets'},
                {'full_path': '/api/v1/contracts/', 'name': 'contract-list', 'service': 'contracts'}
            ]

            auditor = TestEndpointAuditor(
                inventory_file=str(Path(tmpdir) / 'inventory.json'),
                project_root=Path(tmpdir)
            )

            mapping = auditor._map_tests_to_endpoints([test_file], endpoints, 'unit')

            # Multiple patterns may match the same line, so we may get duplicates
            # Check that we have at least the expected endpoints
            assert len(mapping) >= 2, f"Expected at least 2 mappings, got {len(mapping)}"
            # Convert TestEndpointMapping objects to dicts for comparison
            mapping_dicts = [asdict(m) for m in mapping]
            # Get unique endpoint paths
            unique_endpoints = set(m['endpoint_path'] for m in mapping_dicts)
            assert '/api/v1/assets/' in unique_endpoints
            assert '/api/v1/contracts/' in unique_endpoints

    def test_generate_report(self):
        """Test generating test impact report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create TestEndpointMapping objects
            TestEndpointMapping = audit_test_endpoints.TestEndpointMapping
            test_mapping = TestEndpointMapping(
                test_file='tests/unit/test_assets.py',
                test_type='unit',
                endpoint_path='/api/v1/assets/',
                endpoint_name='asset-list',
                service='assets',
                method='GET',
                line_number=10,
                context='response = self.client.get(\'/api/v1/assets/\')',
                is_dynamic=False
            )

            auditor = TestEndpointAuditor(
                inventory_file=str(Path(tmpdir) / 'inventory.json'),
                project_root=Path(tmpdir)
            )
            # Set the test_mappings attribute
            auditor.test_mappings = [test_mapping]

            report_file = Path(tmpdir) / 'test-impact-report.json'
            auditor._generate_json_report(report_file)

            assert report_file.exists()
            with open(report_file) as f:
                report_data = json.load(f)
                assert 'summary' in report_data
                assert 'test_mappings' in report_data
                assert len(report_data['test_mappings']) == 1
                assert report_data['test_mappings'][0]['endpoint_path'] == '/api/v1/assets/'

    def test_comprehensive_audit(self):
        """Test comprehensive audit workflow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create inventory
            inventory_file = Path(tmpdir) / 'endpoint-inventory-current.json'
            inventory_data = {
                'inventory': {
                    'summary': {'total_endpoints': 1, 'total_services': 1},
                    'endpoints': [
                        {
                            'full_path': '/api/v1/assets/',
                            'name': 'asset-list',
                            'service': 'assets',
                            'methods': ['GET']
                        }
                    ]
                }
            }
            with open(inventory_file, 'w') as f:
                json.dump(inventory_data, f)

            # Create test file
            test_dir = Path(tmpdir) / 'tests' / 'unit'
            test_dir.mkdir(parents=True)
            test_file = test_dir / 'test_assets.py'
            test_file.write_text('''
            def test_assets():
                response = self.client.get('/api/v1/assets/')
            ''')

            auditor = TestEndpointAuditor(
                inventory_file=str(inventory_file),
                project_root=Path(tmpdir)
            )

            result = auditor.audit()

            assert 'summary' in result
            assert 'test_mappings' in result
            assert result['summary']['total_test_files'] > 0
            assert result['summary']['total_endpoints_referenced'] > 0
            assert len(result['test_mappings']) > 0

