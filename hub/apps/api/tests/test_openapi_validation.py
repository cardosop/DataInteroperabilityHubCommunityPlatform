"""
Unit tests for OpenAPI Spec Validation

Tests for OpenAPI specification validation and enhancement.
"""
import pytest
from django.test import TestCase

from hub.apps.api.openapi_validation import OpenAPISpecValidator


pytestmark = pytest.mark.django_db(transaction=True)


class OpenAPISpecValidatorTest(TestCase):
    """Test OpenAPISpecValidator"""
    
    def test_validate_spec_valid(self):
        """Test validation of valid OpenAPI spec"""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0"
            },
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "200": {
                                "description": "Success"
                            }
                        }
                    }
                }
            }
        }
        
        is_valid, errors = OpenAPISpecValidator.validate_spec(spec)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_spec_invalid(self):
        """Test validation of invalid OpenAPI spec"""
        spec = {
            "info": {
                "title": "Test API"
            }
        }
        
        is_valid, errors = OpenAPISpecValidator.validate_spec(spec)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_enhance_spec(self):
        """Test spec enhancement"""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0"
            },
            "paths": {}
        }
        
        enhanced = OpenAPISpecValidator.enhance_spec(spec)
        
        self.assertIn("servers", enhanced)
        self.assertIn("components", enhanced)
        self.assertIn("security", enhanced)
    
    def test_export_spec_json(self):
        """Test JSON export"""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0"
            },
            "paths": {}
        }
        
        json_str = OpenAPISpecValidator.export_spec(spec, format="json")
        self.assertIn("openapi", json_str)
        self.assertIn("3.0.0", json_str)
    
    def test_export_spec_yaml(self):
        """Test YAML export"""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0"
            },
            "paths": {}
        }
        
        yaml_str = OpenAPISpecValidator.export_spec(spec, format="yaml")
        self.assertIn("openapi", yaml_str)
        self.assertIn("3.0.0", yaml_str)
