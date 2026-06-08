"""
Unit tests for Impact Visualization

Tests for impact visualization formats (JSON, CSV, DOT, Mermaid) and paths.
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.impact_analysis import ImpactNode
from hub.apps.contracts.impact_visualization import ImpactVisualizer

pytestmark = pytest.mark.django_db(transaction=True)


class ImpactVisualizerTest(TestCase):
    """Test ImpactVisualizer"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock impact result
        self.impact_result = {
            "source": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "contract_name": "Test Contract",
                "model_name": None,
                "field_name": None,
            },
            "impact_graph": {
                "resource_type": "CONTRACT",
                "resource_id": "123e4567-e89b-12d3-a456-426614174000",
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "depth": 0,
                "impact_score": 100.0,
                "severity": "HIGH",
                "metadata": {"contract_name": "Test Contract"},
                "children": [
                    {
                        "resource_type": "CONTRACT",
                        "resource_id": "223e4567-e89b-12d3-a456-426614174001",
                        "contract_id": "223e4567-e89b-12d3-a456-426614174001",
                        "depth": 1,
                        "impact_score": 50.0,
                        "severity": "MEDIUM",
                        "metadata": {"contract_name": "Dependent Contract"},
                        "children": [],
                    }
                ],
            },
            "summary": {
                "total_contracts": 2,
                "total_models": 0,
                "total_fields": 0,
                "severity_distribution": {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 1, "LOW": 0},
                "max_impact_score": 100.0,
                "avg_impact_score": 75.0,
            },
            "total_affected": 2,
            "max_depth": 1,
            "cycles_detected": False,
        }

    def test_generate_impact_json(self):
        """Test JSON format generation"""
        json_result = ImpactVisualizer.generate_impact_json(self.impact_result)

        self.assertIn("nodes", json_result)
        self.assertIn("links", json_result)
        self.assertIn("summary", json_result)
        self.assertGreater(len(json_result["nodes"]), 0)
        self.assertGreater(len(json_result["links"]), 0)

        # Check node properties
        node = json_result["nodes"][0]
        self.assertIn("id", node)
        self.assertIn("severity", node)
        self.assertIn("color", node)
        self.assertIn("impact_score", node)

    def test_generate_impact_dot(self):
        """Test DOT format generation"""
        dot_string = ImpactVisualizer.generate_impact_dot(self.impact_result)

        self.assertIsInstance(dot_string, str)
        self.assertIn("digraph ImpactAnalysis", dot_string)
        self.assertIn("rankdir=LR", dot_string)

    def test_generate_impact_mermaid(self):
        """Test Mermaid format generation"""
        mermaid_string = ImpactVisualizer.generate_impact_mermaid(self.impact_result)

        self.assertIsInstance(mermaid_string, str)
        self.assertIn("graph LR", mermaid_string)
        self.assertIn("classDef", mermaid_string)

    def test_generate_impact_csv(self):
        """Test CSV format generation"""
        csv_string = ImpactVisualizer.generate_impact_csv(self.impact_result)

        self.assertIsInstance(csv_string, str)
        self.assertIn("Resource Type", csv_string)
        self.assertIn("Contract ID", csv_string)
        self.assertIn("Impact Score", csv_string)
        self.assertIn("Severity", csv_string)

    def test_generate_impact_paths(self):
        """Test impact paths generation"""
        paths = ImpactVisualizer.generate_impact_paths(self.impact_result)

        self.assertIsInstance(paths, list)
        self.assertGreater(
            len(paths), 0,
            "Impact result with a populated impact_graph must produce at least one path",
        )
        path = paths[0]
        self.assertIn("path", path)
        self.assertIn("length", path)
        self.assertIn("max_severity", path)
        self.assertIn("total_impact_score", path)

    # Edge cases and error handling tests
    def test_generate_impact_json_with_empty_result(self):
        """Test JSON format generation with empty impact result."""
        empty_result = {
            "source": {"contract_id": "123", "contract_name": "Test"},
            "impact_graph": {},
            "summary": {"total_contracts": 0},
            "total_affected": 0,
            "max_depth": 0,
            "cycles_detected": False,
        }

        json_result = ImpactVisualizer.generate_impact_json(empty_result)

        self.assertIn("nodes", json_result)
        self.assertIn("links", json_result)
        self.assertIn("summary", json_result)
        self.assertIsInstance(json_result["nodes"], list)
        self.assertIsInstance(json_result["links"], list)

    def test_generate_impact_json_with_missing_fields(self):
        """Test JSON format generation with missing optional fields."""
        incomplete_result = {
            "source": {"contract_id": "123"},
            "impact_graph": {
                "resource_type": "CONTRACT",
                "resource_id": "123",
                "contract_id": "123",
                "depth": 0,
                "impact_score": 50.0,
                # Missing severity, metadata, children
            },
            "summary": {},
        }

        json_result = ImpactVisualizer.generate_impact_json(incomplete_result)

        # Should handle missing fields gracefully
        self.assertIn("nodes", json_result)
        self.assertIn("links", json_result)

    def test_generate_impact_dot_with_empty_result(self):
        """Test DOT format generation with empty impact result."""
        empty_result = {
            "source": {"contract_id": "123"},
            "impact_graph": {},
            "summary": {"total_contracts": 0},
        }

        dot_string = ImpactVisualizer.generate_impact_dot(empty_result)

        self.assertIsInstance(dot_string, str)
        self.assertIn("digraph", dot_string.lower())

    def test_generate_impact_dot_with_special_characters(self):
        """Test DOT format generation with special characters in names."""
        result_with_special = {
            "source": {"contract_id": "123", "contract_name": "Contract-Name_v2"},
            "impact_graph": {
                "resource_type": "CONTRACT",
                "resource_id": "123",
                "contract_id": "123",
                "contract_name": "Contract-Name_v2",
                "depth": 0,
                "impact_score": 50.0,
                "severity": "HIGH",
            },
            "summary": {},
        }

        dot_string = ImpactVisualizer.generate_impact_dot(result_with_special)

        self.assertIsInstance(dot_string, str)
        # Should handle special characters in DOT format
        self.assertIn("digraph", dot_string.lower())

    def test_generate_impact_mermaid_with_empty_result(self):
        """Test Mermaid format generation with empty impact result."""
        empty_result = {"source": {"contract_id": "123"}, "impact_graph": {}, "summary": {}}

        mermaid_string = ImpactVisualizer.generate_impact_mermaid(empty_result)

        self.assertIsInstance(mermaid_string, str)
        self.assertIn("graph", mermaid_string.lower())

    def test_generate_impact_mermaid_with_unicode(self):
        """Test Mermaid format generation with unicode characters."""
        result_unicode = {
            "source": {"contract_id": "123", "contract_name": "产品名称"},
            "impact_graph": {
                "resource_type": "CONTRACT",
                "resource_id": "123",
                "contract_id": "123",
                "contract_name": "产品名称",
                "depth": 0,
                "impact_score": 50.0,
                "severity": "HIGH",
            },
            "summary": {},
        }

        mermaid_string = ImpactVisualizer.generate_impact_mermaid(result_unicode)

        self.assertIsInstance(mermaid_string, str)
        # Should handle unicode characters
        self.assertIn("graph", mermaid_string.lower())

    def test_generate_impact_csv_with_empty_result(self):
        """Test CSV format generation with empty impact result."""
        empty_result = {
            "source": {"contract_id": "123"},
            "impact_graph": {},
            "summary": {"total_contracts": 0},
        }

        csv_string = ImpactVisualizer.generate_impact_csv(empty_result)

        self.assertIsInstance(csv_string, str)
        # Should still have headers even if no data
        self.assertIn("Resource Type", csv_string)

    def test_generate_impact_csv_with_missing_fields(self):
        """Test CSV format generation with missing fields."""
        incomplete_result = {
            "source": {"contract_id": "123"},
            "impact_graph": {
                "resource_type": "CONTRACT",
                "resource_id": "123",
                # Missing other fields
            },
            "summary": {},
        }

        csv_string = ImpactVisualizer.generate_impact_csv(incomplete_result)

        self.assertIsInstance(csv_string, str)
        # Should handle missing fields gracefully
        self.assertIn("Resource Type", csv_string)

    def test_generate_impact_paths_with_empty_result(self):
        """Test impact paths generation with empty result."""
        empty_result = {
            "source": {"contract_id": "123"},
            "impact_graph": {},
            "summary": {"total_contracts": 0},
        }

        paths = ImpactVisualizer.generate_impact_paths(empty_result)

        self.assertIsInstance(paths, list)
        self.assertEqual(len(paths), 0,
            "Empty impact graph must produce zero paths")

    def test_generate_impact_paths_with_deep_nesting(self):
        """Test impact paths generation with deeply nested impact graph."""
        deep_result = {
            "source": {"contract_id": "123"},
            "impact_graph": {
                "resource_type": "CONTRACT",
                "resource_id": "123",
                "contract_id": "123",
                "depth": 0,
                "impact_score": 100.0,
                "severity": "HIGH",
                "children": [
                    {
                        "resource_type": "CONTRACT",
                        "resource_id": "223",
                        "contract_id": "223",
                        "depth": 1,
                        "impact_score": 75.0,
                        "severity": "MEDIUM",
                        "children": [
                            {
                                "resource_type": "CONTRACT",
                                "resource_id": "323",
                                "contract_id": "323",
                                "depth": 2,
                                "impact_score": 50.0,
                                "severity": "LOW",
                                "children": [],
                            }
                        ],
                    }
                ],
            },
            "summary": {"total_contracts": 3},
        }

        paths = ImpactVisualizer.generate_impact_paths(deep_result)

        self.assertIsInstance(paths, list)
        self.assertGreater(len(paths), 0,
            "Deeply nested result must produce at least one path")

    def test_generate_impact_json_structure_consistency(self):
        """Test that JSON format has consistent structure."""
        json_result = ImpactVisualizer.generate_impact_json(self.impact_result)

        # Verify structure
        self.assertIsInstance(json_result, dict)
        self.assertIn("nodes", json_result)
        self.assertIn("links", json_result)
        self.assertIn("summary", json_result)

        # Verify nodes structure
        if json_result["nodes"]:
            node = json_result["nodes"][0]
            self.assertIsInstance(node, dict)
            self.assertIn("id", node)
            self.assertIn("severity", node)

    def test_generate_impact_dot_valid_syntax(self):
        """Test that DOT format generates valid syntax."""
        dot_string = ImpactVisualizer.generate_impact_dot(self.impact_result)

        # Basic DOT syntax checks
        self.assertIn("digraph", dot_string.lower())
        self.assertIn("{", dot_string)
        self.assertIn("}", dot_string)
        # Should not have syntax errors
        self.assertNotIn("{{", dot_string)
        self.assertNotIn("}}", dot_string)

    def test_generate_impact_mermaid_valid_syntax(self):
        """Test that Mermaid format generates valid syntax."""
        mermaid_string = ImpactVisualizer.generate_impact_mermaid(self.impact_result)

        # Basic Mermaid syntax checks
        self.assertIn("graph", mermaid_string.lower())
        self.assertIsInstance(mermaid_string, str)
        # Should not have obvious syntax errors
        self.assertNotIn("[[", mermaid_string)

    def test_generate_impact_csv_valid_format(self):
        """Test that CSV format generates valid CSV."""
        csv_string = ImpactVisualizer.generate_impact_csv(self.impact_result)

        # Basic CSV format checks
        self.assertIsInstance(csv_string, str)
        # Should have headers
        self.assertIn("Resource Type", csv_string)
        # Should have newlines for rows
        lines = csv_string.split("\n")
        self.assertGreater(len(lines), 1)  # Header + at least one data row
