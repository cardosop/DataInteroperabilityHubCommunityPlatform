"""
Unit tests for lineage traversal algorithms.
"""
from django.test import TestCase
from unittest.mock import Mock, patch

from hub.apps.contracts.lineage import LineageTraverser
from hub.apps.contracts.models import Contract


class TestLineageTraversal(TestCase):
    """Tests for lineage traversal algorithms."""

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

    def test_traverse_top_down_basic(self):
        """Test basic top-down traversal."""
        traverser = LineageTraverser(self.contract)
        result = traverser.traverse_top_down()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], "contract-123")
        self.assertEqual(result["contract_name"], "test-contract")
        self.assertIn("models", result)
        self.assertEqual(len(result["models"]), 1)

    def test_traverse_top_down_with_depth_limits(self):
        """Test top-down traversal with depth limits."""
        traverser = LineageTraverser(
            self.contract, max_contract_depth=1, max_model_depth=1, max_field_depth=1
        )
        result = traverser.traverse_top_down(contract_depth=1)

        self.assertIn("error", result)
        self.assertIn("Max contract depth exceeded", result["error"])

    def test_traverse_top_down_cycle_detection(self):
        """Test cycle detection in top-down traversal."""
        traverser = LineageTraverser(self.contract)
        traverser.visited_contracts.add("contract-123")
        result = traverser.traverse_top_down()

        self.assertIn("error", result)
        self.assertIn("Cycle detected", result["error"])

    def test_traverse_bottom_up_basic(self):
        """Test basic bottom-up traversal."""
        traverser = LineageTraverser(self.contract)
        result = traverser.traverse_bottom_up()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], "contract-123")
        self.assertIn("referenced_by", result)

    def test_traverse_bidirectional(self):
        """Test bidirectional traversal."""
        traverser = LineageTraverser(self.contract)
        result = traverser.traverse_bidirectional()

        self.assertIsNotNone(result)
        self.assertIn("upstream", result)
        self.assertIn("downstream", result)

