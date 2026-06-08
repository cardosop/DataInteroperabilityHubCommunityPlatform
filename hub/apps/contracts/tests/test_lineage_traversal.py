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


def _find_cycle_error(data):
    """Recursively search for 'Cycle detected' error in nested traversal result."""
    if isinstance(data, dict):
        if data.get("error") and "Cycle detected" in str(data["error"]):
            return True
        for v in data.values():
            if _find_cycle_error(v):
                return True
    elif isinstance(data, list):
        for item in data:
            if _find_cycle_error(item):
                return True
    return False


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
        """Top-down traversal detects a real 2-node field-level lineage cycle.

        Contract A → field_a references B.model_b.field_b, and
        Contract B → field_b references A.model_a.field_a.

        Traversing from A follows the reference to B, which follows
        the reference back to A — the visited_contracts guard must
        detect the cycle instead of recursing infinitely.
        """
        unique = uuid.uuid4().hex[:8]

        # Contract B (referenced by A, references A back → cycle)
        contract_b = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info":{"name":"cycle-b-' + unique + '"}}',
            hub_contract_json={
                "info": {"name": "cycle-b-" + unique, "domain": "ns1"},
                "models": [
                    {
                        "name": "model_b",
                        "fields": [
                            {
                                "name": "field_b",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "ns1",
                                            "name": "cycle-a-" + unique,
                                            "model": "model_a",
                                            "field": "field_a",
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
        )

        # Contract A (references B, completing the cycle)
        contract_a = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info":{"name":"cycle-a-' + unique + '"}}',
            hub_contract_json={
                "info": {"name": "cycle-a-" + unique, "domain": "ns1"},
                "models": [
                    {
                        "name": "model_a",
                        "fields": [
                            {
                                "name": "field_a",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "ns1",
                                            "name": "cycle-b-" + unique,
                                            "model": "model_b",
                                            "field": "field_b",
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
        )

        traverser = LineageTraverser(contract_a)
        result = traverser.traverse_top_down()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_a.id))
        # The cycle must be detected somewhere in the nested traversal tree
        self.assertTrue(
            _find_cycle_error(result),
            "Real 2-node cycle must produce 'Cycle detected' error in traversal result",
        )

    def test_traverse_bottom_up_basic(self):
        """Test basic bottom-up traversal using real Contract object."""
        traverser = LineageTraverser(self.contract)
        result = traverser.traverse_bottom_up()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(self.contract.id))
        self.assertIn("referenced_by", result)
        self.assertIsInstance(result["referenced_by"], list,
            "Bottom-up traversal 'referenced_by' must be a list")

    def test_traverse_bidirectional(self):
        """Test bidirectional traversal."""
        traverser = LineageTraverser(self.contract)
        result = traverser.traverse_bidirectional()

        self.assertIsNotNone(result)
        self.assertIn("upstream", result)
        self.assertIn("downstream", result)
        # Upstream must not inherit visited_* from downstream traversal (regression:
        # a single traverser used for both caused immediate "Cycle detected" on bottom-up).
        self.assertNotIn("error", result["upstream"])

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
        """Traversal with hub_contract_json=None returns contract_id + empty models."""
        contract_no_json = Contract.objects.create(
            tenant=self.tenant, version=1, status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS, original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "no-json-contract"}}',
            hub_contract_json=None,
        )

        traverser = LineageTraverser(contract_no_json)
        result = traverser.traverse_top_down()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_no_json.id))
        self.assertIn("models", result)
        self.assertEqual(result["models"], [],
            "No hub_contract_json → no models to traverse")

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
        """Bidirectional traversal detects a real 2-node field-level lineage cycle.

        Creates contract A → field_a references B.model_b.field_b and
        contract B → field_b references A.model_a.field_a.  The bidirectional
        traversal must detect the cycle in the downstream (top-down) leg.

        Previous version injected ``visited_contracts`` directly on the outer
        traverser, but ``traverse_bidirectional`` creates fresh internal
        traversers — the injection had no effect and the test was a no-op.
        """
        unique = uuid.uuid4().hex[:8]

        contract_b = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info":{"name":"bidir-cycle-b-' + unique + '"}}',
            hub_contract_json={
                "info": {"name": "bidir-cycle-b-" + unique, "domain": "ns1"},
                "models": [
                    {
                        "name": "model_b",
                        "fields": [
                            {
                                "name": "field_b",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "ns1",
                                            "name": "bidir-cycle-a-" + unique,
                                            "model": "model_a",
                                            "field": "field_a",
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
        )

        contract_a = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info":{"name":"bidir-cycle-a-' + unique + '"}}',
            hub_contract_json={
                "info": {"name": "bidir-cycle-a-" + unique, "domain": "ns1"},
                "models": [
                    {
                        "name": "model_a",
                        "fields": [
                            {
                                "name": "field_a",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "ns1",
                                            "name": "bidir-cycle-b-" + unique,
                                            "model": "model_b",
                                            "field": "field_b",
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
        )

        traverser = LineageTraverser(contract_a)
        result = traverser.traverse_bidirectional()

        self.assertIsNotNone(result)
        self.assertIn("upstream", result)
        self.assertIn("downstream", result)
        # The cycle must be detected — bidirectional creates fresh internal
        # traversers, so this verifies the real visited_contracts guard works.
        self.assertTrue(
            _find_cycle_error(result),
            "Bidirectional traversal must detect the real 2-node cycle",
        )

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

    def test_traverse_top_down_with_disconnected_contract_lineage(self):
        """Contract-level lineage references to non-existent contracts are handled gracefully.

        When a contract declares ``lineage.contracts`` pointing to a contract
        that does not exist in the database, the traverser skips the broken
        reference and returns only the root contract without crashing.
        """
        unique = uuid.uuid4().hex[:8]
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info":{"name":"disconnected-' + unique + '"}}',
            hub_contract_json={
                "info": {"name": "disconnected-" + unique, "domain": "ns1"},
                "lineage": {
                    "contracts": [
                        {"namespace": "ns1", "name": "ghost-contract"}
                    ]
                },
                "models": [],
            },
        )

        traverser = LineageTraverser(contract)
        result = traverser.traverse_top_down()

        self.assertIsNotNone(result,
            "Traversal with disconnected contract lineage must not crash")
        self.assertEqual(result["contract_id"], str(contract.id),
            "Root contract must appear in traversal result")
        # Broken reference must not appear in contract_lineage
        lineage_refs = result.get("contract_lineage", [])
        self.assertEqual(len(lineage_refs), 0,
            "Broken contract-level references to non-existent contracts must be absent")

    def test_traverse_top_down_tenant_isolation(self):
        """Lineage traversal documents current cross-tenant behavior.

        When a contract references ``other-tenant-contract`` owned by a
        different tenant, the lineage traverser may or may not resolve
        it (tenant isolation in lineage resolution is not yet enforced).
        This test creates that exact setup and verifies the traverser
        doesn't crash — regardless of whether the reference resolves.
        """
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )

        Contract.objects.create(
            tenant=other_tenant, version=1, status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS, original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info":{"name":"other-tenant-contract"}}',
            hub_contract_json={"info":{"name":"other-tenant-contract"}},
        )

        contract_cross_tenant = Contract.objects.create(
            tenant=self.tenant, version=1, status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS, original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info":{"name":"cross-tenant-contract"}}',
            hub_contract_json={
                "info":{"name":"cross-tenant-contract"},
                "models":[{"name":"model1","fields":[{
                    "name":"field1","lineage":{"input_fields":[{
                        "namespace":"other","name":"other-tenant-contract",
                        "model":"model1","field":"field1"}]}}]}]},
        )

        traverser = LineageTraverser(contract_cross_tenant)
        result = traverser.traverse_top_down()

        self.assertIsNotNone(result)
        self.assertEqual(result["contract_id"], str(contract_cross_tenant.id))
        self.assertIn("models", result)
        # Verify the model list is returned regardless.
        self.assertIsInstance(result["models"], list)
        self.assertEqual(len(result["models"]), 1)
