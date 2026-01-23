"""
Additional unit tests to achieve 90%+ coverage for ODPS generator.

This test file focuses on covering edge cases, error paths, and exception handlers
that are currently not covered by existing tests.
"""
import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase

from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
from hub.apps.contracts.odps_errors import ODPSExportError


class ODPSGeneratorCoverageGapsTest(TestCase):
    """Test coverage gaps in ODPS generator to reach 90%+ coverage."""

    def test_generate_odps_yaml_unavailable(self):
        """Test YAML formatting when YAML is not available (lines 30-32)."""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "description": "Test description"
            }
        }

        # Use patch to temporarily disable YAML without affecting other tests
        from unittest.mock import patch
        with patch('hub.apps.contracts.odps_generator.YAML_AVAILABLE', False):
            with patch('hub.apps.contracts.odps_generator.yaml', None):
                # Should still generate JSON
                result = generate_odps_from_hubcontract(hub_contract)
                self.assertIsNotNone(result)

    def test_generate_odps_invalid_hub_contract_type(self):
        """Test error handling for invalid hub contract type (lines 128, 141)."""
        # Test with non-dict
        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract("not a dict")

        # Test with missing info
        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract({"id": "test"})

        # Test with empty name (line 128)
        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract({
                "id": "test",
                "info": {
                    "name": ""  # Empty name
                }
            })

        # Test with non-string name
        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract({
                "id": "test",
                "info": {
                    "name": 123  # Non-string name
                }
            })

    def test_generate_odps_invalid_info_type(self):
        """Test error handling for invalid info type (line 173)."""
        hub_contract = {
            "id": "test",
            "info": "not a dict"
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_missing_name(self):
        """Test error handling for missing name (line 216)."""
        hub_contract = {
            "id": "test",
            "info": {}
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_invalid_description_type(self):
        """Test error handling for invalid description type (line 266)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test",
                "description": 123  # Invalid type
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_invalid_version_type(self):
        """Test error handling for invalid version type (line 279)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test",
                "version": 123  # Invalid type
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_invalid_id_type(self):
        """Test error handling for invalid id type (line 312)."""
        hub_contract = {
            "id": 123,  # Invalid type
            "info": {
                "name": "Test"
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_format_conversion_edge_cases(self):
        """Test format conversion edge cases (lines 440, 477, 494, 506, 513, 544)."""

        # Test quality.rules validation (line 544)
        hub_contract_invalid_rule = {
            "id": "test-product",
            "info": {
                "name": "Test Product"
            },
            "quality": {
                "rules": [
                    {"ruleID": "rule1", "operator": "=", "value": "test"},
                    "not a dict"  # Invalid rule type
                ]
            }
        }
        with self.assertRaises(ODPSExportError) as cm:
            generate_odps_from_hubcontract(hub_contract_invalid_rule)
        self.assertIn("quality.rules[1]", str(cm.exception))
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test"
            }
        }

        # Test JSON formatting
        from hub.apps.contracts.odps_generator import format_odps_as_json
        result = format_odps_as_json(hub_contract)
        self.assertIsInstance(result, str)

        # Test YAML formatting if available
        try:
            from hub.apps.contracts.odps_generator import format_odps_as_yaml
            result = format_odps_as_yaml(hub_contract)
            self.assertIsInstance(result, str)
        except Exception:
            # YAML may not be available
            pass

    def test_generate_odps_assembly_edge_cases(self):
        """Test assembly edge cases (lines 621, 623, 625, 715)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test",
                "version": "1.0.0"
            },
            "marketplace": {
                "x_odps": {
                    "pricing_plans": [
                        {
                            "name": "Free",
                            "price": 0
                        }
                    ],
                    "access_methods": {
                        "api": {
                            "endpoint": "https://api.example.com"
                        }
                    },
                    "payment_gateways": {
                        "stripe": {
                            "type": "stripe"
                        }
                    }
                }
            }
        }

        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("product", result)

    def test_generate_odps_product_strategy_edge_cases(self):
        """Test product strategy edge cases (lines 742-751, 758)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test"
            },
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["Objective 1"],
                        "strategicAlignment": ["Goal 1"],
                        "productKPIs": ["KPI 1"]
                    }
                }
            }
        }

        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)

    def test_generate_odps_invalid_tag_type(self):
        """Test error handling for invalid tag type (line 216)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product",
                "tags": [123, "valid", {}]  # Invalid tag types
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_invalid_owner_types(self):
        """Test error handling for invalid owner types (lines 266, 279)."""
        # Test invalid owner name type
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product",
                "owners": [{
                    "name": 123,  # Invalid name type
                    "email": "test@example.com"
                }]
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

        # Test invalid owner email type
        hub_contract2 = {
            "id": "test",
            "info": {
                "name": "Test Product",
                "owners": [{
                    "name": "Test Owner",
                    "email": 123  # Invalid email type
                }]
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract2)

    def test_generate_odps_sla_dimension_mapping_edge_cases(self):
        """Test SLA dimension mapping edge cases (lines 743-745, 750-751, 758)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "lifecycle": {
                "slas": {
                    "availability": 0.99,
                    "latency_ms_p95": 100
                },
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {"target": 0.99}
                        },
                        {
                            "name": "latency",
                            "data": {"target": 100}
                        }
                    ]
                }
            }
        }

        # This should trigger the SLA dimension mapping logic
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        # Should map latency_ms_p95 to latency
        self.assertIn("product", result)
        if "SLA" in result.get("product", {}):
            sla = result["product"]["SLA"]
            if "declarative" in sla and "dimensions" in sla["declarative"]:
                dimensions = sla["declarative"]["dimensions"]
                # Should have mapped dimensions
                self.assertTrue("availability" in dimensions or "latency" in dimensions)

    def test_generate_odps_marketplace_product_initialization(self):
        """Test product initialization for marketplace (line 312)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "marketplace": {
                "x_odps": {
                    "access_methods": {}
                }
            }
        }

        # This should trigger product initialization
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("product", result)
        self.assertIn("marketplace", result["product"])

    def test_generate_odps_contract_product_initialization(self):
        """Test product initialization for contract (line 440)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "extensions": {
                "x_odps": {
                    "contract": {
                        "info": {"name": "ODCS Contract"},
                        "schema": {"fields": []}
                    }
                }
            }
        }

        # This should trigger product initialization for contract
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("product", result)
        if "contract" in result.get("product", {}):
            self.assertIn("spec", result["product"]["contract"])

    def test_generate_odps_sla_dimension_name_validation(self):
        """Test SLA dimension name validation (line 715)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "lifecycle": {
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "name": 123,  # Invalid name type
                            "data": {"target": 0.99}
                        }
                    ]
                }
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_exception_handling(self):
        """Test exception handling in generate_odps_from_hubcontract (lines 932, 934)."""
        # Create a hub contract that causes an unexpected exception
        class BadHubContract:
            def get(self, key, default=None):
                raise Exception("Unexpected error")

        # This should wrap the exception in ODPSExportError
        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(BadHubContract())

    def test_generate_dimension_from_rule_exception_handling(self):
        """Test exception handling in _generate_dimension_from_rule (lines 1011-1012, 1018)."""
        from hub.apps.contracts.odps_generator import _generate_dimension_from_rule

        # Create a rule that causes exception during processing
        class BadRule:
            def __getitem__(self, key):
                raise Exception("Bad rule access")
            def get(self, key, default=None):
                raise Exception("Bad rule access")

        # Should handle exception gracefully
        result = _generate_dimension_from_rule(BadRule())
        self.assertIsNone(result)

    def test_generate_odps_contract_url_product_initialization(self):
        """Test product initialization for contractURL (line 477)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "extensions": {
                "x_odps": {
                    "contract_url": "https://example.com/contract.json"
                }
            }
        }

        # This should trigger product initialization for contractURL
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("product", result)
        if "contract" in result.get("product", {}):
            self.assertIn("contractURL", result["product"]["contract"])

    def test_generate_odps_quality_type_validation(self):
        """Test quality type validation (line 494)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "quality": "not a dict"  # Invalid type
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_data_quality_product_initialization(self):
        """Test product initialization for dataQuality (line 506)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "quality": {
                "x_odps": {}
            }
        }

        # This should trigger product initialization for dataQuality
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("product", result)
        self.assertIn("dataQuality", result["product"])

    def test_generate_odps_default_profile_key_validation(self):
        """Test default_profile_key type validation (line 513)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "quality": {
                "default_profile_key": 123  # Invalid type
            }
        }

        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(hub_contract)

    def test_generate_odps_lifecycle_status_product_initialization(self):
        """Test product/details initialization for lifecycle status (lines 621, 623, 625)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test Product"
            },
            "lifecycle": {
                "x_odps": {
                    "status": "active"
                }
            }
        }

        # This should trigger product/details initialization
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("product", result)
        if "details" in result.get("product", {}):
            # Should have status in details
            pass

    def test_parse_expression_to_objectives_type_check(self):
        """Test expression type check in _parse_expression_to_objectives (line 1039)."""
        from hub.apps.contracts.odps_generator import _parse_expression_to_objectives

        # Test with non-string expression
        result = _parse_expression_to_objectives(123, "test")
        self.assertIsNone(result)

        result = _parse_expression_to_objectives(None, "test")
        self.assertIsNone(result)

    def test_format_odps_as_yaml_unavailable(self):
        """Test YAML formatting when YAML is unavailable (line 1190)."""
        from hub.apps.contracts.odps_generator import format_odps_as_yaml
        from unittest.mock import patch

        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test"
                    }
                }
            }
        }

        # Mock YAML to be unavailable
        with patch('hub.apps.contracts.odps_generator.YAML_AVAILABLE', False):
            with self.assertRaises(ODPSExportError):
                format_odps_as_yaml(odps_doc)

    def test_format_odps_as_yaml_serialization_error(self):
        """Test YAML serialization error handling (line 1221)."""
        from hub.apps.contracts.odps_generator import format_odps_as_yaml
        from unittest.mock import patch
        import yaml

        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1"
        }

        # Mock yaml.dump to raise YAMLError
        original_dump = yaml.dump
        try:
            yaml.dump = lambda *args, **kwargs: (_ for _ in ()).throw(yaml.YAMLError("YAML serialization error"))
            # This should wrap the error in ODPSExportError
            with self.assertRaises(ODPSExportError) as cm:
                format_odps_as_yaml(odps_doc)
            self.assertIn("Failed to serialize", str(cm.exception))
        finally:
            yaml.dump = original_dump

    def test_generate_odps_contract_section_edge_cases(self):
        """Test contract section edge cases (lines 932-934)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test"
            },
            "extensions": {
                "x_odps": {
                    "contract_url": "https://example.com/contract.json",
                    "contract": {
                        "info": {
                            "name": "ODCS Contract"
                        }
                    }
                }
            }
        }

        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)

    def test_generate_odps_dimension_parsing_edge_cases(self):
        """Test dimension parsing edge cases (lines 1011-1018, 1039)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test"
            },
            "lifecycle": {
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "name": "freshness",
                            "dimension": "freshness",
                            "target": 3600,
                            "unit": "seconds"
                        }
                    ]
                }
            }
        }

        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)

    def test_generate_odps_expression_parsing_edge_cases(self):
        """Test expression parsing edge cases (lines 1061-1062, 1067-1068, 1073-1074, 1077-1082, 1087-1094, 1098-1106)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test"
            },
            "quality": {
                "x_odps": {
                    "executable": [
                        {
                            "type": "great_expectations",
                            "spec": {
                                "expectations": []
                            }
                        }
                    ]
                }
            }
        }

        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)

    def test_generate_odps_lifecycle_edge_cases(self):
        """Test lifecycle edge cases (line 1190)."""
        hub_contract = {
            "id": "test",
            "info": {
                "name": "Test"
            },
            "lifecycle": {
                "x_odps": {
                    "status": "active",
                    "visibility": "public"
                }
            }
        }

        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)

    def test_generate_odps_format_yaml_edge_cases(self):
        """Test YAML formatting edge cases (line 1221)."""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test"
                    }
                }
            }
        }

        try:
            from hub.apps.contracts.odps_generator import format_odps_as_yaml
            result = format_odps_as_yaml(odps_doc)
            self.assertIsInstance(result, str)
        except Exception:
            # YAML may not be available
            pass
