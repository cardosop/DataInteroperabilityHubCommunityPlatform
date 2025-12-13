"""
Unit tests for lineage visualization formats.
"""
from django.test import TestCase
from unittest.mock import Mock

from hub.apps.contracts.lineage import generate_lineage_dot, generate_lineage_json, generate_lineage_mermaid
from hub.apps.contracts.models import Contract


class TestLineageVisualization(TestCase):
    """Tests for lineage visualization formats."""

    def setUp(self):
        """Set up test fixtures."""
        self.contract = Mock(spec=Contract)
        self.contract.id = "contract-123"
        self.contract.hub_contract_json = {
            "info": {"name": "test-contract"},
            "models": [
                {
                    "name": "model1",
                    "fields": [
                        {
                            "name": "field1",
                            "lineage": {
                                "input_fields": [
                                    {
                                        "namespace": "ns1",
                                        "name": "source-contract",
                                        "model": "source-model",
                                        "field": "source-field",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    def test_generate_lineage_json(self):
        """Test JSON format generation."""
        result = generate_lineage_json(self.contract)

        self.assertIsNotNone(result)
        self.assertIn("nodes", result)
        self.assertIn("links", result)
        self.assertIsInstance(result["nodes"], list)
        self.assertIsInstance(result["links"], list)

    def test_generate_lineage_json_has_contract_node(self):
        """Test that JSON includes contract node."""
        result = generate_lineage_json(self.contract)

        contract_nodes = [n for n in result["nodes"] if n.get("type") == "contract"]
        self.assertGreater(len(contract_nodes), 0)

    def test_generate_lineage_dot(self):
        """Test DOT format generation."""
        result = generate_lineage_dot(self.contract)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertIn("digraph Lineage", result)
        self.assertIn("node [shape=box]", result)

    def test_generate_lineage_mermaid(self):
        """Test Mermaid format generation."""
        result = generate_lineage_mermaid(self.contract)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertIn("graph LR", result)

