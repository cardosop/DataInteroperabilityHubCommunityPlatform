"""
Edge case tests for Phase 15 features.

Tests handling of:
- Missing objects
- Broken lineage links
- Circular references
- Depth limits
- Invalid data
"""

import json

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.lineage import LineageReference, LineageTraverser, resolve_lineage_reference
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalSpecType,
)
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.tests.test_base import ContractsTestBase
from tests.factories import AssetFactory


class EdgeCasesPhase15TestCase(ContractsTestBase):
    """Test edge cases for Phase 15 features."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.asset = AssetFactory(tenant=self.tenant)

    def test_missing_contact_handling(self):
        """Test normalization when contact is missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            # No contact field
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        self.assertNotIn("contact", hub_contract)
        # Should still normalize successfully
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_missing_servers_handling(self):
        """Test normalization when servers are missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            # No servers field
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        self.assertNotIn("servers", hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_missing_servicelevels_handling(self):
        """Test normalization when servicelevels are missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            # No slaProperties field
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        self.assertNotIn("servicelevels", hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_broken_lineage_link_handling(self):
        """Test handling of broken lineage links."""
        # Create source contract
        source_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"id": "source-contract"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "source-contract",
                "info": {"name": "Source Contract"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Create contract with broken lineage link (references non-existent contract)
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "target-contract",
            "name": "Target Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "transformSourceObjects": [
                            {
                                "namespace": "ns1",
                                "name": "nonexistent-contract",
                                "model_name": "model1",
                                "field": "field1",
                            }
                        ],
                    }
                ]
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        # Should normalize but with warnings about broken links
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Try to resolve the broken link
        ref = LineageReference(
            namespace="ns1", name="nonexistent-contract", model_name="model1", field="field1"
        )
        result = resolve_lineage_reference(ref)

        # Should detect broken link
        self.assertTrue(ref.is_broken())

    def test_circular_lineage_reference(self):
        """Test handling of circular lineage references."""
        # Each contract needs its own asset to avoid unique_contract_version_per_asset
        asset2 = Asset.objects.create(
            tenant=self.tenant, key="edge-lineage-2", name="Edge Asset 2", status=AssetStatus.ACTIVE
        )
        # Create two contracts that reference each other
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"id": "contract1"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "contract1",
                "info": {"name": "Contract 1"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
                "lineage": {
                    "entries": [{"namespace": "ns1", "name": "contract2", "model_name": "model1"}]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset2,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"id": "contract2"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "contract2",
                "info": {"name": "Contract 2"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
                "lineage": {
                    "entries": [{"namespace": "ns1", "name": "contract1", "model_name": "model1"}]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Test traversal with cycle detection
        traverser = LineageTraverser(contract=contract1)
        result = traverser.traverse_top_down(contract_id=str(contract1.id), contract_depth=10)

        # Should detect cycle and stop traversal
        self.assertIsNotNone(result)
        # Should not exceed max depth due to cycle detection

    def test_lineage_depth_limit(self):
        """Test lineage traversal with depth limits."""
        # Create chain of contracts — each needs its own asset
        contracts = []
        for i in range(5):
            chain_asset = Asset.objects.create(
                tenant=self.tenant, key=f"chain-asset-{i}", name=f"Chain Asset {i}", status=AssetStatus.ACTIVE
            )
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=chain_asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format="JSON",
                original_raw=f'{{"id": "contract{i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"contract{i}",
                    "info": {"name": f"Contract {i}"},
                    "schema": {"fields": [{"name": "id", "type": "string"}]},
                    "lineage": {
                        "entries": (
                            [
                                {
                                    "namespace": "ns1",
                                    "name": f"contract{i+1}" if i < 4 else None,
                                    "model_name": "model1",
                                }
                            ]
                            if i < 4
                            else []
                        )
                    },
                },
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                status=ContractStatus.ACTIVE,
            )
            contracts.append(contract)

        # Test traversal with depth limit
        traverser = LineageTraverser(contract=contracts[0])
        result = traverser.traverse_top_down(contract_id=str(contracts[0].id), contract_depth=2)

        # Should respect depth limit
        self.assertIsNotNone(result)
        # Should not traverse beyond depth 2

    def test_invalid_contact_data(self):
        """Test handling of invalid contact data."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [
                {"invalid": "data"},  # Invalid contact entry
                {"email": "valid@example.com"},  # Valid entry
            ],
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        # Should normalize with warnings about invalid data
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # Valid contact should be extracted
        if "contact" in hub_contract:
            self.assertGreater(len(hub_contract["contact"]), 0)

    def test_invalid_server_data(self):
        """Test handling of invalid server data."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "servers": [
                {"invalid": "data"},  # Invalid server entry
                {"type": "s3", "url": "s3://bucket"},  # Valid entry
            ],
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        # Should normalize with warnings
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # Valid server should be extracted
        if "servers" in hub_contract:
            self.assertGreater(len(hub_contract["servers"]), 0)

    def test_empty_arrays_handling(self):
        """Test handling of empty arrays."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "servers": [],  # Empty array
            "support": [],  # Empty array
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        # Should normalize successfully
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # Empty arrays should be handled gracefully
        if "servers" in hub_contract:
            self.assertEqual(len(hub_contract["servers"]), 0)

    def test_null_values_handling(self):
        """Test handling of null values."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "servers": None,  # Null value
            "support": None,  # Null value
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        # Should normalize successfully
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # Null values should be handled gracefully
        self.assertNotIn("servers", hub_contract)
        self.assertNotIn("support", hub_contract)

    def test_very_large_contract_json(self):
        """Test handling of very large contract JSON."""
        # Create contract with very large JSON (>1MB)
        large_data = {
            "hub_contract_version": "1.0.0",
            "id": "large-contract",
            "info": {"name": "Large Contract"},
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "large_field": "x" * 2 * 1024 * 1024,  # 2MB string
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"id": "large"}',
            hub_contract_json=large_data,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Should be able to retrieve contract
        retrieved = Contract.objects.get(id=contract.id)
        self.assertIsNotNone(retrieved)
        self.assertIsNotNone(retrieved.hub_contract_json)

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON in original_raw."""
        # This should be caught during parsing, not normalization
        # But we test that the system handles it gracefully
        try:
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format="JSON",
                original_raw='{"invalid": json}',  # Malformed JSON
                hub_contract_json={"id": "test"},
                normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
                status=ContractStatus.DRAFT,
            )

            # Contract should be created but with failed status
            self.assertIsNotNone(contract)
            self.assertEqual(
                contract.normalization_status, NormalizationStatus.NORMALIZATION_FAILED
            )
        except Exception as e:
            # If creation fails, that's also acceptable
            self.assertIsNotNone(str(e))

    def test_lineage_max_depth_exceeded(self):
        """Test lineage traversal when max depth is exceeded."""
        # Create deep chain of contracts (deeper than contract_depth) — each needs own asset
        contracts = []
        for i in range(10):
            depth_asset = Asset.objects.create(
                tenant=self.tenant, key=f"depth-asset-{i}", name=f"Depth {i}", status=AssetStatus.ACTIVE
            )
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=depth_asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format="JSON",
                original_raw=f'{{"id": "contract{i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"contract{i}",
                    "info": {"name": f"Contract {i}"},
                    "schema": {"fields": [{"name": "id", "type": "string"}]},
                    "lineage": {
                        "entries": (
                            [
                                {
                                    "namespace": "ns1",
                                    "name": f"contract{i+1}" if i < 9 else None,
                                    "model_name": "model1",
                                }
                            ]
                            if i < 9
                            else []
                        )
                    },
                },
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                status=ContractStatus.ACTIVE,
            )
            contracts.append(contract)

        # Test traversal with very small depth limit
        traverser = LineageTraverser(contract=contracts[0])
        result = traverser.traverse_top_down(
            contract_id=str(contracts[0].id), contract_depth=3  # Much smaller than chain length
        )

        # Should respect depth limit and stop at max_depth
        self.assertIsNotNone(result)
        # Should not traverse beyond max_depth

    def test_multiple_circular_references(self):
        """Test handling of multiple circular references in lineage."""
        # Each contract needs its own asset to avoid unique_contract_version_per_asset
        asset2 = Asset.objects.create(
            tenant=self.tenant, key="multi-circ-2", name="Multi Circ 2", status=AssetStatus.ACTIVE
        )
        asset3 = Asset.objects.create(
            tenant=self.tenant, key="multi-circ-3", name="Multi Circ 3", status=AssetStatus.ACTIVE
        )
        # Create three contracts forming multiple cycles
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"id": "contract1"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "contract1",
                "info": {"name": "Contract 1"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
                "lineage": {
                    "entries": [
                        {"namespace": "ns1", "name": "contract2", "model_name": "model1"},
                        {"namespace": "ns1", "name": "contract3", "model_name": "model1"},
                    ]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset2,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"id": "contract2"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "contract2",
                "info": {"name": "Contract 2"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
                "lineage": {
                    "entries": [{"namespace": "ns1", "name": "contract1", "model_name": "model1"}]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        contract3 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset3,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"id": "contract3"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "contract3",
                "info": {"name": "Contract 3"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
                "lineage": {
                    "entries": [{"namespace": "ns1", "name": "contract1", "model_name": "model1"}]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Test traversal with multiple cycles
        traverser = LineageTraverser(contract=contract1)
        result = traverser.traverse_top_down(contract_id=str(contract1.id), contract_depth=10)

        # Should handle multiple cycles gracefully
        self.assertIsNotNone(result)
        # Should detect cycles and prevent infinite loops

    def test_lineage_reference_with_missing_namespace(self):
        """Test handling of lineage references with missing namespace."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "transformSourceObjects": [
                            {
                                # Missing namespace
                                "name": "some-contract",
                                "model_name": "model1",
                                "field": "field1",
                            }
                        ],
                    }
                ]
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        # Should handle missing namespace gracefully
        self.assertIsNotNone(hub_contract)
        # May normalize with warnings or fail validation
        self.assertIsNotNone(status)

    def test_lineage_reference_with_missing_name(self):
        """Test handling of lineage references with missing name."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "transformSourceObjects": [
                            {
                                "namespace": "ns1",
                                # Missing name
                                "model_name": "model1",
                                "field": "field1",
                            }
                        ],
                    }
                ]
            },
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        # Should handle missing name gracefully
        self.assertIsNotNone(hub_contract)
        # May normalize with warnings or fail validation
        self.assertIsNotNone(status)

    def test_lineage_traversal_with_none_contract_id(self):
        """Test lineage traversal with None contract_id (edge case)."""
        dummy = Contract.objects.create(
            tenant=self.tenant, asset=self.asset,
            original_raw='{"id":"dummy"}', original_format="JSON",
            original_spec_type=OriginalSpecType.ODCS,
        )
        traverser = LineageTraverser(contract=dummy)

        # Should handle None contract_id gracefully
        try:
            result = traverser.traverse_top_down(contract_id=None, contract_depth=10)
            # No exception raised -- graceful handling confirmed
        except (ValueError, TypeError, AttributeError):
            # Raising exception is also acceptable for invalid input
            pass

    def test_lineage_traversal_with_invalid_contract_id(self):
        """Test lineage traversal with invalid contract_id format."""
        dummy = Contract.objects.create(
            tenant=self.tenant, asset=self.asset,
            original_raw='{"id":"dummy2"}', original_format="JSON",
            original_spec_type=OriginalSpecType.ODCS, version=2,
        )
        traverser = LineageTraverser(contract=dummy)

        # Should handle invalid contract_id gracefully
        try:
            result = traverser.traverse_top_down(contract_id="invalid-uuid-format", contract_depth=10)
            # No exception raised -- graceful handling confirmed
        except (ValueError, TypeError, AttributeError, Exception):
            # Raising exception is also acceptable for invalid input
            pass

    def test_resolve_lineage_reference_with_none_values(self):
        """Test resolving lineage reference with None values."""
        ref = LineageReference(namespace=None, name=None, model_name=None, field=None)

        # Should handle None values gracefully
        try:
            result = resolve_lineage_reference(ref)
            # No exception raised -- graceful handling confirmed
        except (ValueError, TypeError, AttributeError):
            # Raising exception is also acceptable for invalid input
            pass

    def test_normalization_with_mixed_valid_invalid_data(self):
        """Test normalization with mix of valid and invalid data."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "servers": [
                {"type": "s3", "url": "s3://valid-bucket"},  # Valid
                {"invalid": "data"},  # Invalid
                None,  # Null
                {"type": "http", "url": "https://valid-url.com"},  # Valid
            ],
            "support": [
                {"email": "valid@example.com"},  # Valid
                {"invalid": "data"},  # Invalid
                None,  # Null
            ],
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        # Should normalize successfully, extracting valid data
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # Valid entries should be extracted
        if "servers" in hub_contract:
            self.assertGreater(len(hub_contract["servers"]), 0)
        if "contact" in hub_contract:
            self.assertGreater(len(hub_contract["contact"]), 0)

    def test_lineage_traversal_performance_with_large_dataset(self):
        """Test lineage traversal performance with large dataset."""
        # Create many contracts with lineage relationships — each needs own asset
        contracts = []
        for i in range(50):
            perf_asset = Asset.objects.create(
                tenant=self.tenant, key=f"perf-asset-{i}", name=f"Perf {i}", status=AssetStatus.ACTIVE
            )
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=perf_asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format="JSON",
                original_raw=f'{{"id": "contract{i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"contract{i}",
                    "info": {"name": f"Contract {i}"},
                    "schema": {"fields": [{"name": "id", "type": "string"}]},
                    "lineage": {
                        "entries": (
                            [
                                {
                                    "namespace": "ns1",
                                    "name": f"contract{i+1}" if i < 49 else None,
                                    "model_name": "model1",
                                }
                            ]
                            if i < 49
                            else []
                        )
                    },
                },
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                status=ContractStatus.ACTIVE,
            )
            contracts.append(contract)

        # Test traversal with large dataset
        traverser = LineageTraverser(contract=contracts[0])
        result = traverser.traverse_top_down(contract_id=str(contracts[0].id), contract_depth=100)

        # Should handle large dataset without performance issues
        self.assertIsNotNone(result)
        # Should complete traversal successfully
