"""
Unit tests for lineage reference resolution.
"""
from django.test import TestCase
from unittest.mock import Mock, patch

from hub.apps.contracts.lineage import LineageReference


class TestLineageReference(TestCase):
    """Tests for LineageReference class."""

    def test_lineage_reference_str(self):
        """Test string representation of lineage reference."""
        ref = LineageReference(namespace="ns1", name="contract1", model_name="model1", field="field1")
        self.assertEqual(str(ref), "ns1/contract1/model1/field1")

    def test_lineage_reference_str_partial(self):
        """Test string representation with partial reference."""
        ref = LineageReference(namespace="ns1", name="contract1")
        self.assertEqual(str(ref), "ns1/contract1")

    def test_lineage_reference_to_dict(self):
        """Test conversion to dictionary."""
        ref = LineageReference(namespace="ns1", name="contract1", model_name="model1", field="field1")
        result = ref.to_dict()
        self.assertEqual(result["namespace"], "ns1")
        self.assertEqual(result["name"], "contract1")
        self.assertEqual(result["model_name"], "model1")
        self.assertEqual(result["field"], "field1")

    def test_lineage_reference_to_dict_partial(self):
        """Test conversion to dictionary with partial reference."""
        ref = LineageReference(namespace="ns1", name="contract1")
        result = ref.to_dict()
        self.assertEqual(result["namespace"], "ns1")
        self.assertEqual(result["name"], "contract1")
        self.assertNotIn("model_name", result)
        self.assertNotIn("field", result)

    @patch("hub.apps.contracts.lineage.Contract")
    def test_resolve_contract_success(self, mock_contract_model):
        """Test successful contract resolution."""
        # Mock contract
        mock_contract = Mock()
        mock_contract.id = "contract-id-123"
        mock_contract.hub_contract_json = {"info": {"name": "test-contract"}}

        # Mock queryset
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.first.return_value = mock_contract
        mock_contract_model.objects.filter.return_value = mock_queryset

        ref = LineageReference(namespace="ns1", name="test-contract")
        result = ref.resolve_contract()

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "contract-id-123")

    @patch("hub.apps.contracts.lineage.Contract")
    def test_resolve_contract_not_found(self, mock_contract_model):
        """Test contract resolution when contract not found."""
        # Mock queryset returning None
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.first.return_value = None
        mock_contract_model.objects.filter.return_value = mock_queryset

        ref = LineageReference(namespace="ns1", name="nonexistent")
        result = ref.resolve_contract()

        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

    def test_resolve_contract_missing_namespace_or_name(self):
        """Test contract resolution when namespace or name is missing."""
        ref = LineageReference(namespace="ns1")  # Missing name
        result = ref.resolve_contract()

        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

        ref2 = LineageReference(name="contract1")  # Missing namespace
        result2 = ref2.resolve_contract()

        self.assertIsNone(result2)
        self.assertTrue(ref2.is_broken())

    @patch("hub.apps.contracts.lineage.Contract")
    def test_resolve_model_success(self, mock_contract_model):
        """Test successful model resolution."""
        # Mock contract with models
        mock_contract = Mock()
        mock_contract.id = "contract-id-123"
        mock_contract.hub_contract_json = {
            "info": {"name": "test-contract"},
            "models": [
                {"name": "model1", "fields": []},
                {"name": "model2", "fields": []},
            ],
        }

        # Mock queryset
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.first.return_value = mock_contract
        mock_contract_model.objects.filter.return_value = mock_queryset

        ref = LineageReference(namespace="ns1", name="test-contract", model_name="model1")
        result = ref.resolve_model()

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "model1")

    @patch("hub.apps.contracts.lineage.Contract")
    def test_resolve_model_not_found(self, mock_contract_model):
        """Test model resolution when model not found."""
        # Mock contract without the requested model
        mock_contract = Mock()
        mock_contract.id = "contract-id-123"
        mock_contract.hub_contract_json = {
            "info": {"name": "test-contract"},
            "models": [{"name": "other-model", "fields": []}],
        }

        # Mock queryset
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.first.return_value = mock_contract
        mock_contract_model.objects.filter.return_value = mock_queryset

        ref = LineageReference(namespace="ns1", name="test-contract", model_name="nonexistent-model")
        result = ref.resolve_model()

        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

    @patch("hub.apps.contracts.lineage.Contract")
    def test_resolve_field_success(self, mock_contract_model):
        """Test successful field resolution."""
        # Mock contract with models and fields
        mock_contract = Mock()
        mock_contract.id = "contract-id-123"
        mock_contract.hub_contract_json = {
            "info": {"name": "test-contract"},
            "models": [
                {
                    "name": "model1",
                    "fields": [
                        {"name": "field1", "type": "string"},
                        {"name": "field2", "type": "integer"},
                    ],
                },
            ],
        }

        # Mock queryset
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.first.return_value = mock_contract
        mock_contract_model.objects.filter.return_value = mock_queryset

        ref = LineageReference(
            namespace="ns1", name="test-contract", model_name="model1", field="field1"
        )
        result = ref.resolve_field()

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "field1")
        self.assertEqual(result["type"], "string")

    @patch("hub.apps.contracts.lineage.Contract")
    def test_resolve_field_not_found(self, mock_contract_model):
        """Test field resolution when field not found."""
        # Mock contract without the requested field
        mock_contract = Mock()
        mock_contract.id = "contract-id-123"
        mock_contract.hub_contract_json = {
            "info": {"name": "test-contract"},
            "models": [
                {
                    "name": "model1",
                    "fields": [{"name": "other-field", "type": "string"}],
                },
            ],
        }

        # Mock queryset
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.first.return_value = mock_contract
        mock_contract_model.objects.filter.return_value = mock_queryset

        ref = LineageReference(
            namespace="ns1", name="test-contract", model_name="model1", field="nonexistent-field"
        )
        result = ref.resolve_field()

        self.assertIsNone(result)
        self.assertTrue(ref.is_broken())

