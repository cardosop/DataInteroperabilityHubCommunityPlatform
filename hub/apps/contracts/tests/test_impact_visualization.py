"""
Unit tests for Impact Visualization

Tests for impact visualization formats (JSON, CSV, DOT, Mermaid) and paths.
"""
import pytest
from django.test import TestCase

from hub.apps.contracts.impact_visualization import ImpactVisualizer
from hub.apps.contracts.impact_analysis import ImpactNode


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
                "field_name": None
            },
            "impact_graph": {
                "resource_type": "CONTRACT",
                "resource_id": "123e4567-e89b-12d3-a456-426614174000",
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "depth": 0,
                "impact_score": 100.0,
                "severity": "HIGH",
                "metadata": {
                    "contract_name": "Test Contract"
                },
                "children": [
                    {
                        "resource_type": "CONTRACT",
                        "resource_id": "223e4567-e89b-12d3-a456-426614174001",
                        "contract_id": "223e4567-e89b-12d3-a456-426614174001",
                        "depth": 1,
                        "impact_score": 50.0,
                        "severity": "MEDIUM",
                        "metadata": {
                            "contract_name": "Dependent Contract"
                        },
                        "children": []
                    }
                ]
            },
            "summary": {
                "total_contracts": 2,
                "total_models": 0,
                "total_fields": 0,
                "severity_distribution": {
                    "CRITICAL": 0,
                    "HIGH": 1,
                    "MEDIUM": 1,
                    "LOW": 0
                },
                "max_impact_score": 100.0,
                "avg_impact_score": 75.0
            },
            "total_affected": 2,
            "max_depth": 1,
            "cycles_detected": False
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
        if paths:
            path = paths[0]
            self.assertIn("path", path)
            self.assertIn("length", path)
            self.assertIn("max_severity", path)
            self.assertIn("total_impact_score", path)

