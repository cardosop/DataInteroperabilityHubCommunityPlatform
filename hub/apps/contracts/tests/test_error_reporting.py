"""
Unit tests for error reporting format.
"""
import pytest
from django.test import TestCase
from hub.apps.contracts.cli_client import interpret_validation_status, group_errors_by_category



pytestmark = pytest.mark.django_db(transaction=True)
class ErrorReportingTest(TestCase):
    """Test error reporting format"""
    
    def test_error_structure(self):
        """Test that errors have required structure"""
        result = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '/schema/fields/0',
                    'message': 'Field type is invalid',
                    'rule_id': 'field_type_check'
                }
            ]
        }
        
        status, errors, warnings = interpret_validation_status(result)
        
        self.assertEqual(len(errors), 1)
        error = errors[0]
        
        # Check required fields
        self.assertIn('severity', error)
        self.assertIn('category', error)
        self.assertIn('path', error)
        self.assertIn('message', error)
        self.assertIn('rule_id', error)
        
        self.assertEqual(error['severity'], 'ERROR')
        self.assertEqual(error['category'], 'schema')
        self.assertEqual(error['path'], '/schema/fields/0')
        self.assertEqual(error['message'], 'Field type is invalid')
        self.assertEqual(error['rule_id'], 'field_type_check')
    
    def test_warning_structure(self):
        """Test that warnings have required structure"""
        result = {
            'validation_status': 'WARNING_ONLY',
            'issues': [
                {
                    'severity': 'WARNING',
                    'category': 'style',
                    'path': '/info',
                    'message': 'Missing description',
                    'rule_id': 'missing_description'
                }
            ]
        }
        
        status, errors, warnings = interpret_validation_status(result)
        
        self.assertEqual(len(warnings), 1)
        warning = warnings[0]
        
        # Check required fields
        self.assertIn('severity', warning)
        self.assertIn('category', warning)
        self.assertIn('path', warning)
        self.assertIn('message', warning)
        self.assertIn('rule_id', warning)
        
        self.assertEqual(warning['severity'], 'WARNING')
        self.assertEqual(warning['category'], 'style')
    
    def test_error_grouping_structure(self):
        """Test error grouping maintains structure"""
        errors = [
            {
                'severity': 'ERROR',
                'category': 'schema',
                'path': '/schema',
                'message': 'Schema error 1',
                'rule_id': 'rule1'
            },
            {
                'severity': 'ERROR',
                'category': 'schema',
                'path': '/schema/fields',
                'message': 'Schema error 2',
                'rule_id': 'rule2'
            },
            {
                'severity': 'ERROR',
                'category': 'format',
                'path': '/format',
                'message': 'Format error',
                'rule_id': 'rule3'
            }
        ]
        
        grouped = group_errors_by_category(errors)
        
        # Check structure
        self.assertIn('schema', grouped)
        self.assertIn('format', grouped)
        self.assertEqual(len(grouped['schema']), 2)
        self.assertEqual(len(grouped['format']), 1)
        
        # Check that grouped errors maintain structure
        for error in grouped['schema']:
            self.assertIn('severity', error)
            self.assertIn('category', error)
            self.assertIn('path', error)
            self.assertIn('message', error)
            self.assertIn('rule_id', error)
    
    def test_multiple_severities(self):
        """Test handling of multiple severity levels"""
        result = {
            'validation_status': 'WARNING_ONLY',
            'issues': [
                {'severity': 'ERROR', 'category': 'schema', 'path': '', 'message': 'Error', 'rule_id': ''},
                {'severity': 'WARNING', 'category': 'style', 'path': '', 'message': 'Warning', 'rule_id': ''},
                {'severity': 'INFO', 'category': 'info', 'path': '', 'message': 'Info', 'rule_id': ''},
                {'severity': 'CRITICAL', 'category': 'critical', 'path': '', 'message': 'Critical', 'rule_id': ''}
            ]
        }
        
        status, errors, warnings = interpret_validation_status(result)
        
        # ERROR and CRITICAL should be in errors
        self.assertEqual(len(errors), 2)
        # WARNING and INFO should be in warnings
        self.assertEqual(len(warnings), 2)
    
    def test_empty_issues(self):
        """Test handling of empty issues"""
        result = {
            'validation_status': 'VALID',
            'issues': []
        }
        
        status, errors, warnings = interpret_validation_status(result)
        
        self.assertEqual(status, 'VALID')
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)
    
    def test_missing_fields_in_issue(self):
        """Test handling of issues with missing fields"""
        result = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    # Missing category, path, message, rule_id
                }
            ]
        }
        
        status, errors, warnings = interpret_validation_status(result)
        
        # Should still create error with defaults
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(error['category'], 'unknown')
        self.assertEqual(error['path'], '')
        self.assertEqual(error['message'], '')
        self.assertEqual(error['rule_id'], '')

