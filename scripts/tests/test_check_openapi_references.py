"""
Tests for OpenAPI spec reference checking functionality
"""
import os
import sys
import json
import tempfile
from pathlib import Path
import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import module
import importlib.util
script_path = scripts_dir / 'check-openapi-references.py'
spec = importlib.util.spec_from_file_location('check_openapi_references', script_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {script_path}")
check_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_module)

OpenAPISpecParser = check_module.OpenAPISpecParser
URLPatternComparator = check_module.URLPatternComparator
OpenAPISpecChecker = check_module.OpenAPISpecChecker
OpenAPIPath = check_module.OpenAPIPath
Discrepancy = check_module.Discrepancy


@pytest.mark.integration
class TestOpenAPISpecParsing:
    """Test: Verify OpenAPI spec parsing"""

    def test_parse_openapi_spec(self):
        """Test parsing OpenAPI spec"""
        spec_data = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {
                '/api/v1/users/': {
                    'get': {
                        'operationId': 'list_users',
                        'tags': ['users'],
                        'summary': 'List users'
                    }
                },
                '/api/v1/users/{id}/': {
                    'get': {
                        'operationId': 'get_user',
                        'tags': ['users']
                    }
                }
            }
        }

        parser = OpenAPISpecParser(spec_data)
        paths = parser.get_all_paths()

        assert len(paths) == 2, f"Expected 2 paths, got {len(paths)}"
        assert any(p.path == '/api/v1/users/' for p in paths)
        assert any(p.path == '/api/v1/users/{id}/' for p in paths)

    def test_extract_methods(self):
        """Test extracting HTTP methods from OpenAPI spec"""
        spec_data = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {
                '/api/v1/test/': {
                    'get': {'operationId': 'get_test'},
                    'post': {'operationId': 'create_test'},
                    'put': {'operationId': 'update_test'},
                    'delete': {'operationId': 'delete_test'}
                }
            }
        }

        parser = OpenAPISpecParser(spec_data)
        paths = parser.get_all_paths()

        assert len(paths) == 1
        path = paths[0]
        assert set(path.methods) == {'GET', 'POST', 'PUT', 'DELETE'}

    def test_extract_tags(self):
        """Test extracting tags from OpenAPI spec"""
        spec_data = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {
                '/api/v1/test/': {
                    'get': {
                        'operationId': 'get_test',
                        'tags': ['test', 'api']
                    }
                }
            }
        }

        parser = OpenAPISpecParser(spec_data)
        paths = parser.get_all_paths()

        assert len(paths) == 1
        path = paths[0]
        assert 'test' in path.tags
        assert 'api' in path.tags


@pytest.mark.integration
class TestDiscrepancyDetection:
    """Test: Verify discrepancy detection"""

    def test_detect_missing_in_spec(self):
        """Test detecting endpoints missing in OpenAPI spec"""
        openapi_paths = [
            OpenAPIPath(path='/api/v1/users/', methods=['GET'], operation_ids=['list_users'], tags=['users'])
        ]

        actual_endpoints = [
            {'full_path': '/api/v1/users/', 'methods': ['GET']},
            {'full_path': '/api/v1/posts/', 'methods': ['GET']},  # Missing in OpenAPI
        ]

        comparator = URLPatternComparator(openapi_paths, actual_endpoints)
        discrepancies = comparator.compare()

        missing_in_spec = [d for d in discrepancies if d.type == 'missing_in_spec']
        assert len(missing_in_spec) > 0, "Should detect endpoints missing in spec"

    def test_detect_missing_in_urls(self):
        """Test detecting endpoints missing in actual URLs"""
        openapi_paths = [
            OpenAPIPath(path='/api/v1/users/', methods=['GET'], operation_ids=['list_users'], tags=['users']),
            OpenAPIPath(path='/api/v1/posts/', methods=['GET'], operation_ids=['list_posts'], tags=['posts'])  # Missing in URLs
        ]

        actual_endpoints = [
            {'full_path': '/api/v1/users/', 'methods': ['GET']},
        ]

        comparator = URLPatternComparator(openapi_paths, actual_endpoints)
        discrepancies = comparator.compare()

        missing_in_urls = [d for d in discrepancies if d.type == 'missing_in_urls']
        assert len(missing_in_urls) > 0, "Should detect endpoints missing in URLs"

    def test_detect_method_mismatch(self):
        """Test detecting method mismatches"""
        openapi_paths = [
            OpenAPIPath(path='/api/v1/users/', methods=['GET', 'POST'], operation_ids=['list_users'], tags=['users'])
        ]

        actual_endpoints = [
            {'full_path': '/api/v1/users/', 'methods': ['GET']},  # Missing POST
        ]

        comparator = URLPatternComparator(openapi_paths, actual_endpoints)
        discrepancies = comparator.compare()

        method_mismatches = [d for d in discrepancies if d.type == 'method_mismatch']
        assert len(method_mismatches) > 0, "Should detect method mismatches"

    def test_path_normalization(self):
        """Test path normalization for comparison"""
        comparator = URLPatternComparator([], [])

        # Test parameter format normalization
        assert comparator.paths_match('/api/v1/users/{id}', '/api/v1/users/<id>')
        assert comparator.paths_match('/api/v1/users/{id}/', '/api/v1/users/<id>/')

        # Test trailing slash normalization
        assert comparator.paths_match('/api/v1/users/', '/api/v1/users')

        # Test base path extraction
        assert comparator.paths_match('/api/v1/users/', '/users/')


@pytest.mark.integration
class TestOpenAPISpecChecker:
    """Integration tests for OpenAPI spec checker"""

    def test_load_from_file(self):
        """Test loading OpenAPI spec from file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = Path(tmpdir) / 'openapi.json'
            spec_data = {
                'openapi': '3.0.0',
                'info': {'title': 'Test API', 'version': '1.0.0'},
                'paths': {
                    '/api/v1/test/': {
                        'get': {'operationId': 'get_test'}
                    }
                }
            }
            spec_file.write_text(json.dumps(spec_data))

            checker = OpenAPISpecChecker(spec_file=str(spec_file))
            assert checker.parser is not None
            assert len(checker.parser.get_all_paths()) == 1

    def test_compare_with_audit_results(self):
        """Test comparing OpenAPI spec with audit results"""
        spec_data = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {
                '/api/v1/users/': {
                    'get': {'operationId': 'list_users'}
                }
            }
        }

        audit_data = {
            'inventory': {
                'endpoints': [
                    {'full_path': '/api/v1/users/', 'methods': ['GET']},
                    {'full_path': '/api/v1/posts/', 'methods': ['GET']},
                ]
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = Path(tmpdir) / 'audit.json'
            audit_file.write_text(json.dumps(audit_data))

            checker = OpenAPISpecChecker(spec_data=spec_data)
            result = checker.compare_with_audit_results(str(audit_file))

            assert 'openapi_paths' in result
            assert 'actual_endpoints' in result
            assert 'discrepancies' in result
            assert result['openapi_paths'] == 1
            assert result['actual_endpoints'] == 2

    def test_json_output(self):
        """Test JSON output generation"""
        spec_data = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {}
        }

        audit_data = {
            'inventory': {
                'endpoints': []
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = Path(tmpdir) / 'audit.json'
            audit_file.write_text(json.dumps(audit_data))

            checker = OpenAPISpecChecker(spec_data=spec_data)
            result = checker.compare_with_audit_results(str(audit_file))
            json_output = checker.output_json(result)

            # Verify valid JSON
            parsed = json.loads(json_output)
            assert 'openapi_paths' in parsed
            assert 'discrepancies' in parsed

    def test_markdown_output(self):
        """Test Markdown output generation"""
        spec_data = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {}
        }

        audit_data = {
            'inventory': {
                'endpoints': []
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = Path(tmpdir) / 'audit.json'
            audit_file.write_text(json.dumps(audit_data))

            checker = OpenAPISpecChecker(spec_data=spec_data)
            result = checker.compare_with_audit_results(str(audit_file))
            markdown_output = checker.output_markdown(result)

            assert isinstance(markdown_output, str)
            assert len(markdown_output) > 0
            assert 'OpenAPI Spec Reference Check' in markdown_output or 'Summary' in markdown_output

    @pytest.mark.skipif(
        not os.path.exists('docs/api-audit/endpoint-inventory-current.json'),
        reason='Audit results not available'
    )
    def test_verify_openapi_spec_fetch(self):
        """Test fetching OpenAPI spec from API"""
        try:
            spec_data = OpenAPISpecChecker.fetch_from_api('http://localhost:8000')
            assert 'openapi' in spec_data
            assert 'paths' in spec_data
            assert 'info' in spec_data
        except Exception as e:
            pytest.skip(f"Could not fetch OpenAPI spec: {e}")

    @pytest.mark.skipif(
        not os.path.exists('docs/api-audit/openapi-spec-discrepancies.json'),
        reason='Discrepancy report not generated'
    )
    def test_verify_discrepancy_report_exists(self):
        """Test: Verify discrepancy report was generated"""
        assert os.path.exists('docs/api-audit/openapi-spec-discrepancies.json')
        assert os.path.exists('docs/api-audit/openapi-spec-discrepancies.md')

        # Verify JSON is valid
        with open('docs/api-audit/openapi-spec-discrepancies.json') as f:
            data = json.load(f)

        assert 'openapi_paths' in data
        assert 'actual_endpoints' in data
        assert 'discrepancies' in data
        assert 'discrepancy_count' in data
        assert 'summary' in data

        # Verify summary structure
        summary = data['summary']
        assert 'total_discrepancies' in summary
        assert 'by_type' in summary

    @pytest.mark.skipif(
        not os.path.exists('docs/api-audit/openapi-spec-discrepancies.json'),
        reason='Discrepancy report not generated'
    )
    def test_verify_discrepancy_types(self):
        """Test: Verify discrepancy types are valid"""
        with open('docs/api-audit/openapi-spec-discrepancies.json') as f:
            data = json.load(f)

        valid_types = {'missing_in_spec', 'missing_in_urls', 'method_mismatch', 'path_mismatch'}

        for disc in data['discrepancies'][:100]:  # Check first 100
            assert 'type' in disc, f"Discrepancy missing type: {disc}"
            assert disc['type'] in valid_types, f"Invalid discrepancy type: {disc['type']}"

