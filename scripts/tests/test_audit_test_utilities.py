"""
Unit tests for test utilities and helpers audit script

Tests the comprehensive audit of test utility modules and helper functions.
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
script_path = scripts_dir / 'audit-test-utilities.py'
spec = importlib.util.spec_from_file_location('audit_test_utilities', script_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {script_path}")
audit_test_utilities = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_test_utilities)

# Import classes
TestUtilitiesAuditor = audit_test_utilities.TestUtilitiesAuditor


class TestTestUtilitiesAuditor:
    """Test test utilities auditor"""

    def test_find_utility_modules(self):
        """Test finding utility modules"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test utility structure
            utils_dir = Path(tmpdir) / 'tests' / 'utils'
            utils_dir.mkdir(parents=True)

            # Create utility files
            (utils_dir / 'test_helper.py').write_text('''
def helper_function():
    pass
''')
            (utils_dir / 'test_util.py').write_text('''
class TestUtil:
    pass
''')

            auditor = TestUtilitiesAuditor(project_root=Path(tmpdir))
            utilities = auditor._find_utility_modules()

            assert len(utilities) >= 2
            assert any('test_helper.py' in u['path'] for u in utilities)
            assert any('test_util.py' in u['path'] for u in utilities)

    def test_find_helper_functions(self):
        """Test finding helper functions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create conftest file with helper functions
            conftest_file = Path(tmpdir) / 'tests' / 'conftest.py'
            conftest_file.parent.mkdir(parents=True)
            conftest_file.write_text('''
def helper_function():
    """Helper function"""
    pass

def get_api_client():
    """Get API client"""
    pass

class TestHelper:
    def helper_method(self):
        pass
''')

            auditor = TestUtilitiesAuditor(project_root=Path(tmpdir))
            helpers = auditor._find_helper_functions()

            assert len(helpers) >= 2
            assert any('helper_function' in h['name'] for h in helpers)
            assert any('get_api_client' in h['name'] for h in helpers)

    def test_extract_endpoint_urls(self):
        """Test extracting endpoint URLs from utility content"""
        utility_content = '''
def get_api_url():
    return "http://localhost:8000/api/v1/"

def build_endpoint(path):
    return f"/api/v1/{path}"

def make_request():
    url = "/api/v1/assets/"
    return url
'''

        auditor = TestUtilitiesAuditor(project_root=Path('/tmp'))
        dummy_file = Path('/tmp/test_util.py')
        endpoints = auditor._extract_endpoint_urls(utility_content, dummy_file)

        assert len(endpoints) >= 3
        endpoint_paths = [e['endpoint_path'] for e in endpoints]
        assert any('/api/v1/' in ep for ep in endpoint_paths)

    def test_audit_comprehensive(self):
        """Test comprehensive audit workflow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test structure
            utils_dir = Path(tmpdir) / 'tests' / 'utils'
            utils_dir.mkdir(parents=True)

            util_file = utils_dir / 'test_helper.py'
            util_file.write_text('''
def get_api_url():
    return "/api/v1/assets/"
''')

            conftest_file = Path(tmpdir) / 'tests' / 'conftest.py'
            conftest_file.parent.mkdir(parents=True, exist_ok=True)
            conftest_file.write_text('''
def helper_function():
    url = "/api/v1/contracts/"
    return url
''')

            auditor = TestUtilitiesAuditor(project_root=Path(tmpdir))
            result = auditor.audit()

            assert 'summary' in result
            assert 'utility_modules' in result
            assert 'helper_functions' in result
            assert 'endpoint_urls' in result
            assert result['summary']['total_utility_modules'] > 0
            assert result['summary']['total_helper_functions'] > 0

    def test_generate_report(self):
        """Test generating utilities report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            auditor = TestUtilitiesAuditor(project_root=Path(tmpdir))

            # Set mock data
            auditor.utility_modules = [
                {
                    'path': 'tests/utils/test_helper.py',
                    'type': 'utility',
                    'functions': ['helper_function'],
                    'classes': [],
                    'line_count': 10,
                    'has_endpoint_urls': True
                }
            ]
            auditor.helper_functions = [
                {
                    'name': 'helper_function',
                    'file': 'tests/conftest.py',
                    'line_number': 10,
                    'type': 'function'
                }
            ]
            auditor.endpoint_urls = [
                {
                    'endpoint_path': '/api/v1/assets/',
                    'file': 'tests/utils/test_helper.py',
                    'line_number': 5,
                    'context': 'return "/api/v1/assets/"',
                    'function_name': 'get_api_url',
                    'is_dynamic': False
                }
            ]

            report_file = Path(tmpdir) / 'test-utilities-report.json'
            auditor._generate_json_report(report_file)

            assert report_file.exists()
            with open(report_file) as f:
                report_data = json.load(f)
            assert 'summary' in report_data
            assert 'utility_modules' in report_data
            assert 'helper_functions' in report_data
            assert 'endpoint_urls' in report_data

            # Verify summary matches actual data
            assert report_data['summary']['total_utility_modules'] == len(report_data['utility_modules'])
            assert report_data['summary']['total_helper_functions'] == len(report_data['helper_functions'])
            assert report_data['summary']['total_endpoint_urls'] == len(report_data['endpoint_urls'])

            # Verify endpoint URL structure
            if report_data['endpoint_urls']:
                sample_endpoint = report_data['endpoint_urls'][0]
                assert 'endpoint_path' in sample_endpoint
                assert 'file' in sample_endpoint
                assert 'line_number' in sample_endpoint
                assert 'is_dynamic' in sample_endpoint

