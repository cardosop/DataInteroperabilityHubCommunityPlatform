"""
Unit tests for DataContract CLI client (critical path).
"""
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from hub.apps.contracts.cli_client import (
    DataContractCLIClient,
    interpret_validation_status,
    group_errors_by_category,
    SYNC_TIMEOUT
)


class DataContractCLIClientTest(TestCase):
    """Test DataContract CLI client (critical path for contract validation)"""
    
    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        self.client = DataContractCLIClient()
    
    @patch('hub.apps.contracts.cli_client.httpx.Client')
    def test_validate_success(self, mock_client_class):
        """Test successful contract validation"""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Mock health check for cache key
        with patch.object(self.client, 'health_check', return_value={'cli_version': '1.0.0'}):
            result = self.client.validate(
                raw_contract='{"id": "test", "name": "Test"}',
                format='JSON'
            )
        
        self.assertEqual(result['validation_status'], 'VALID')
        self.assertEqual(result['cli_version'], '1.0.0')
    
    @patch('hub.apps.contracts.cli_client.httpx.Client')
    def test_validate_with_errors(self, mock_client_class):
        """Test validation with errors"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '$.name',
                    'message': 'Name is required',
                    'rule_id': 'required_field'
                }
            ],
            'cli_version': '1.0.0'
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        with patch.object(self.client, 'health_check', return_value={'cli_version': '1.0.0'}):
            result = self.client.validate(
                raw_contract='{"id": "test"}',
                format='JSON'
            )
        
        self.assertEqual(result['validation_status'], 'INVALID')
        self.assertEqual(len(result['issues']), 1)
    
    @patch('hub.apps.contracts.cli_client.httpx.Client')
    def test_validate_with_cache(self, mock_client_class):
        """Test validation with cache hit"""
        # Set up cache
        contract_hash = self.client._compute_contract_hash('{"id": "test"}', 'JSON')
        cache_key = self.client._get_cache_key(contract_hash, '1.0.0', 'validate')
        cached_result = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        cache.set(cache_key, cached_result, 3600)
        
        # Mock health check
        with patch.object(self.client, 'health_check', return_value={'cli_version': '1.0.0'}):
            result = self.client.validate(
                raw_contract='{"id": "test"}',
                format='JSON',
                use_cache=True
            )
        
        # Should return cached result without making HTTP request
        self.assertEqual(result['validation_status'], 'VALID')
        mock_client_class.assert_not_called()
    
    @patch('hub.apps.contracts.cli_client.httpx.Client')
    def test_validate_retry_on_timeout(self, mock_client_class):
        """Test retry logic on timeout"""
        import httpx
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        
        # First attempt times out, second succeeds
        mock_client.post.side_effect = [
            httpx.TimeoutException("Request timeout"),
            Mock(json=lambda: {'validation_status': 'VALID', 'cli_version': '1.0.0'}, raise_for_status=Mock())
        ]
        mock_client_class.return_value = mock_client
        
        with patch.object(self.client, 'health_check', return_value={'cli_version': '1.0.0'}):
            result = self.client.validate(
                raw_contract='{"id": "test"}',
                format='JSON'
            )
        
        self.assertEqual(result['validation_status'], 'VALID')
        self.assertEqual(mock_client.post.call_count, 2)
    
    @patch('hub.apps.contracts.cli_client.httpx.Client')
    def test_lint(self, mock_client_class):
        """Test lint operation"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'issues': [
                {
                    'severity': 'WARNING',
                    'category': 'style',
                    'message': 'Consider adding description'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        result = self.client.lint(
            raw_contract='{"id": "test"}',
            format='JSON'
        )
        
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(result['issues'][0]['severity'], 'WARNING')
    
    @patch('hub.apps.contracts.cli_client.httpx.Client')
    def test_convert(self, mock_client_class):
        """Test convert operation"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'converted_contract': 'id: test\nname: Test',
            'target_format': 'YAML'
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        result = self.client.convert(
            raw_contract='{"id": "test", "name": "Test"}',
            source_format='JSON',
            target_format='YAML'
        )
        
        self.assertIn('converted_contract', result)
        self.assertEqual(result['target_format'], 'YAML')
    
    @patch('hub.apps.contracts.cli_client.httpx.Client')
    def test_health_check(self, mock_client_class):
        """Test health check"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'healthy',
            'cli_version': '1.0.0'
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        result = self.client.health_check()
        
        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['cli_version'], '1.0.0')


class InterpretValidationStatusTest(TestCase):
    """Test validation status interpretation (critical path)"""
    
    def test_interpret_valid_status(self):
        """Test interpreting VALID status"""
        validation_result = {
            'validation_status': 'VALID',
            'issues': []
        }
        
        status, errors, warnings = interpret_validation_status(validation_result)
        
        self.assertEqual(status, 'VALID')
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)
    
    def test_interpret_invalid_with_errors(self):
        """Test interpreting INVALID status with errors"""
        validation_result = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '$.name',
                    'message': 'Name is required',
                    'rule_id': 'required_field'
                },
                {
                    'severity': 'CRITICAL',
                    'category': 'data',
                    'path': '$.id',
                    'message': 'ID must be unique',
                    'rule_id': 'unique_id'
                }
            ]
        }
        
        status, errors, warnings = interpret_validation_status(validation_result)
        
        self.assertEqual(status, 'INVALID')
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(warnings), 0)
        self.assertEqual(errors[0]['severity'], 'ERROR')
        self.assertEqual(errors[1]['severity'], 'CRITICAL')
    
    def test_interpret_warning_only(self):
        """Test interpreting WARNING_ONLY status"""
        validation_result = {
            'validation_status': 'WARNING_ONLY',
            'issues': [
                {
                    'severity': 'WARNING',
                    'category': 'style',
                    'message': 'Consider adding description'
                },
                {
                    'severity': 'INFO',
                    'category': 'metadata',
                    'message': 'Missing tags'
                }
            ]
        }
        
        status, errors, warnings = interpret_validation_status(validation_result)
        
        self.assertEqual(status, 'WARNING_ONLY')
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 2)
    
    def test_interpret_mixed_errors_and_warnings(self):
        """Test interpreting mixed errors and warnings"""
        validation_result = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'message': 'Schema error'
                },
                {
                    'severity': 'WARNING',
                    'category': 'style',
                    'message': 'Style warning'
                }
            ]
        }
        
        status, errors, warnings = interpret_validation_status(validation_result)
        
        self.assertEqual(status, 'INVALID')
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(warnings), 1)


class GroupErrorsByCategoryTest(TestCase):
    """Test error grouping by category (critical path)"""
    
    def test_group_errors_by_category(self):
        """Test grouping errors by category"""
        errors = [
            {
                'category': 'schema',
                'message': 'Schema error 1'
            },
            {
                'category': 'schema',
                'message': 'Schema error 2'
            },
            {
                'category': 'data',
                'message': 'Data error 1'
            }
        ]
        
        grouped = group_errors_by_category(errors)
        
        self.assertEqual(len(grouped['schema']), 2)
        self.assertEqual(len(grouped['data']), 1)
        self.assertEqual(grouped['schema'][0]['message'], 'Schema error 1')
    
    def test_group_errors_with_unknown_category(self):
        """Test grouping errors with unknown category"""
        errors = [
            {
                'message': 'Error without category'
            },
            {
                'category': 'schema',
                'message': 'Schema error'
            }
        ]
        
        grouped = group_errors_by_category(errors)
        
        self.assertEqual(len(grouped['unknown']), 1)
        self.assertEqual(len(grouped['schema']), 1)

