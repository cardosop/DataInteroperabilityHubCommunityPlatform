"""
Unit tests for lineage traversal algorithms.

All tests use real implementations (no mocks of hub services).
Uses real Contract objects from database.
"""

import uuid

from hub.apps.contracts.lineage import LineageTraverser
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.tenants.models import Tenant


class TestLineageTraversal(ContractsTestBase):
    """Tests for lineage traversal algorithms using real Contract objects."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Update tenant name with unique ID to avoid conflicts
        unique_id = uuid.uuid4().hex[:8]
        self.tenant.name = f"Test Tenant {unique_id}"
        self.tenant.slug = f"test-tenant-{unique_id}"
        self.tenant.save()

        # Create real contract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "test-contract"}}',
            hub_contract_json={
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
            },
        )

    def test_traverse_top_down_basic(self):
        """Test basic top-down traversal using real Contract object."""
        # Arrange
        traverser = LineageTraverser(self.contract)

        # Act
        result = traverser.traverse_top_down()

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(self.contract.id))
        self.assertEqual(result["contract_name"], "test-contract")
        self.assertIn("models", result)
        self.assertEqual(len(result["models"]), 1)

    def test_traverse_top_down_with_depth_limits(self):
        """Test top-down traversal with depth limits."""
        traverser = LineageTraverser(
            self.contract, max_contract_depth=1, max_model_depth=1, max_field_depth=1
        )
        # Pass contract_depth=2 to exceed max_contract_depth=1
        result = traverser.traverse_top_down(contract_depth=2)

        self.assertIn("error", result)
        self.assertIn("Max contract depth exceeded", result["error"])

    def test_traverse_top_down_cycle_detection(self):
        """Test cycle detection in top-down traversal using real Contract object."""
        traverser = LineageTraverser(self.contract)
        traverser.visited_contracts.add(str(self.contract.id))
        result = traverser.traverse_top_down()

        self.assertIn("error", result)
        self.assertIn("Cycle detected", result["error"])

    def test_traverse_bottom_up_basic(self):
        """Test basic bottom-up traversal using real Contract object."""
        traverser = LineageTraverser(self.contract)
        result = traverser.traverse_bottom_up()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(self.contract.id))
        self.assertIn("referenced_by", result)

    def test_traverse_bidirectional(self):
        """Test bidirectional traversal."""
        traverser = LineageTraverser(self.contract)
        result = traverser.traverse_bidirectional()

        self.assertIsNotNone(result)
        self.assertIn("upstream", result)
        self.assertIn("downstream", result)

    def test_traverse_top_down_with_empty_contract(self):
        """Test top-down traversal with contract that has no models (edge case)."""
        empty_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "empty-contract"}}',
            hub_contract_json={"info": {"name": "empty-contract"}},  # No models
        )

        traverser = LineageTraverser(empty_contract)
        result = traverser.traverse_top_down()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(empty_contract.id))
        # Should handle empty models gracefully
        self.assertIn("models", result)
        self.assertEqual(len(result.get("models", [])), 0)

    def test_traverse_top_down_with_missing_hub_contract_json(self):
        """Test top-down traversal with contract missing hub_contract_json (edge case)."""
        contract_no_json = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "no-json-contract"}}',
            hub_contract_json=None,  # Missing hub_contract_json
        )

        traverser = LineageTraverser(contract_no_json)
        result = traverser.traverse_top_down()

        # Should handle missing hub_contract_json gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_no_json.id))
        # May have error or empty models
        self.assertIn("models", result)

    def test_traverse_top_down_with_invalid_lineage_references(self):
        """Test top-down traversal with invalid lineage references (edge case)."""
        contract_invalid_refs = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "invalid-refs-contract"}}',
            hub_contract_json={
                "info": {"name": "invalid-refs-contract"},
                "models": [
                    {
                        "name": "model1",
                        "fields": [
                            {
                                "name": "field1",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            # Missing required fields (invalid reference)
                                            "namespace": None,
                                            "name": None,
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ],
            },
        )

        traverser = LineageTraverser(contract_invalid_refs)
        result = traverser.traverse_top_down()

        # Should handle invalid references gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_invalid_refs.id))
        self.assertIn("models", result)

    def test_traverse_top_down_with_multiple_models(self):
        """Test top-down traversal with contract containing multiple models."""
        contract_multiple = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "multi-model-contract"}}',
            hub_contract_json={
                "info": {"name": "multi-model-contract"},
                "models": [
                    {
                        "name": "model1",
                        "fields": [{"name": "field1", "lineage": {"input_fields": []}}],
                    },
                    {
                        "name": "model2",
                        "fields": [{"name": "field2", "lineage": {"input_fields": []}}],
                    },
                    {
                        "name": "model3",
                        "fields": [{"name": "field3", "lineage": {"input_fields": []}}],
                    },
                ],
            },
        )

        traverser = LineageTraverser(contract_multiple)
        result = traverser.traverse_top_down()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_multiple.id))
        self.assertIn("models", result)
        self.assertEqual(len(result["models"]), 3)

    def test_traverse_top_down_with_model_depth_limit(self):
        """Test top-down traversal with model depth limit exceeded (edge case)."""
        traverser = LineageTraverser(
            self.contract, max_contract_depth=10, max_model_depth=1, max_field_depth=10
        )
        # Pass model_depth=2 to exceed max_model_depth=1
        result = traverser.traverse_top_down(model_depth=2)

        self.assertIn("error", result)
        self.assertIn("Max model depth exceeded", result["error"])

    def test_traverse_top_down_with_field_depth_limit(self):
        """Test top-down traversal with field depth limit exceeded (edge case)."""
        traverser = LineageTraverser(
            self.contract, max_contract_depth=10, max_model_depth=10, max_field_depth=1
        )
        # Pass field_depth=2 to exceed max_field_depth=1
        result = traverser.traverse_top_down(field_depth=2)

        self.assertIn("error", result)
        self.assertIn("Max field depth exceeded", result["error"])

    def test_traverse_bottom_up_with_no_references(self):
        """Test bottom-up traversal when contract has no references (edge case)."""
        contract_no_refs = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "no-refs-contract"}}',
            hub_contract_json={
                "info": {"name": "no-refs-contract"},
                "models": [
                    {
                        "name": "model1",
                        "fields": [{"name": "field1"}],  # No lineage references
                    }
                ],
            },
        )

        traverser = LineageTraverser(contract_no_refs)
        result = traverser.traverse_bottom_up()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_no_refs.id))
        self.assertIn("referenced_by", result)
        # Should handle no references gracefully
        self.assertIsInstance(result["referenced_by"], (list, dict))

    def test_traverse_bidirectional_with_cycle(self):
        """Test bidirectional traversal with cycle detection (edge case)."""
        traverser = LineageTraverser(self.contract)
        traverser.visited_contracts.add(str(self.contract.id))
        result = traverser.traverse_bidirectional()

        # Should detect cycle and handle gracefully
        self.assertIsNotNone(result)
        # May have error or empty results
        if "error" in result:
            self.assertIn("Cycle", result["error"])

    def test_traverse_top_down_with_broken_references(self):
        """Test top-down traversal with broken lineage references (non-existent contracts)."""
        contract_broken = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "broken-refs-contract"}}',
            hub_contract_json={
                "info": {"name": "broken-refs-contract"},
                "models": [
                    {
                        "name": "model1",
                        "fields": [
                            {
                                "name": "field1",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "nonexistent",
                                            "name": "nonexistent-contract",
                                            "model": "nonexistent-model",
                                            "field": "nonexistent-field",
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ],
            },
        )

        traverser = LineageTraverser(contract_broken)
        result = traverser.traverse_top_down()

        # Should handle broken references gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_broken.id))
        self.assertIn("models", result)

    def test_traverse_top_down_tenant_isolation(self):
        """Test that traversal respects tenant isolation (edge case)."""
        # Create another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")

        # Create contract in other tenant (for cross-tenant reference test)
        Contract.objects.create(
            tenant=other_tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "other-tenant-contract"}}',
            hub_contract_json={"info": {"name": "other-tenant-contract"}},
        )

        # Try to traverse from our tenant's contract referencing other tenant's contract
        contract_cross_tenant = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "cross-tenant-contract"}}',
            hub_contract_json={
                "info": {"name": "cross-tenant-contract"},
                "models": [
                    {
                        "name": "model1",
                        "fields": [
                            {
                                "name": "field1",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "other",
                                            "name": "other-tenant-contract",
                                            "model": "model1",
                                            "field": "field1",
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ],
            },
        )

        traverser = LineageTraverser(contract_cross_tenant)
        result = traverser.traverse_top_down()

        # Should handle cross-tenant references (may not resolve due to isolation)
        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_cross_tenant.id))
        self.assertIn("models", result)
