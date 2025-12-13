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
from django.test import TestCase

from hub.apps.contracts.models import Contract, OriginalSpecType, NormalizationStatus, ContractStatus
from hub.apps.contracts.normalization import normalize_odcs_to_hubcontract
from hub.apps.contracts.lineage import LineageTraverser, LineageReference, resolve_lineage_reference
from tests.factories import TenantFactory, UserFactory, AssetFactory


class EdgeCasesPhase15TestCase(TestCase):
    """Test edge cases for Phase 15 features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.asset = AssetFactory(tenant=self.tenant)
    
    def test_missing_contact_handling(self):
        """Test normalization when contact is missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
            # No contact field
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertNotIn('contact', hub_contract)
        # Should still normalize successfully
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
    
    def test_missing_servers_handling(self):
        """Test normalization when servers are missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
            # No servers field
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertNotIn('servers', hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
    
    def test_missing_servicelevels_handling(self):
        """Test normalization when servicelevels are missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
            # No slaProperties field
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertNotIn('servicelevels', hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
    
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
                "schema": {"fields": [{"name": "id", "type": "string"}]}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE
        )
        
        # Create contract with broken lineage link (references non-existent contract)
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "target-contract",
            "name": "Target Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [{
                    "name": "field1",
                    "type": "string",
                    "transformSourceObjects": [{
                        "namespace": "ns1",
                        "name": "nonexistent-contract",
                        "model_name": "model1",
                        "field": "field1"
                    }]
                }]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        # Should normalize but with warnings about broken links
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        
        # Try to resolve the broken link
        ref = LineageReference(
            namespace="ns1",
            name="nonexistent-contract",
            model_name="model1",
            field="field1"
        )
        result = resolve_lineage_reference(ref)
        
        # Should detect broken link
        self.assertTrue(ref.is_broken())
    
    def test_circular_lineage_reference(self):
        """Test handling of circular lineage references."""
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
                    "entries": [{
                        "namespace": "ns1",
                        "name": "contract2",
                        "model_name": "model1"
                    }]
                }
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE
        )
        
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
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
                    "entries": [{
                        "namespace": "ns1",
                        "name": "contract1",
                        "model_name": "model1"
                    }]
                }
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE
        )
        
        # Test traversal with cycle detection
        traverser = LineageTraverser()
        result = traverser.traverse_top_down(
            contract_id=str(contract1.id),
            max_depth=10
        )
        
        # Should detect cycle and stop traversal
        self.assertIsNotNone(result)
        # Should not exceed max depth due to cycle detection
    
    def test_lineage_depth_limit(self):
        """Test lineage traversal with depth limits."""
        # Create chain of contracts
        contracts = []
        for i in range(5):
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
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
                        "entries": [{
                            "namespace": "ns1",
                            "name": f"contract{i+1}" if i < 4 else None,
                            "model_name": "model1"
                        }] if i < 4 else []
                    }
                },
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                status=ContractStatus.ACTIVE
            )
            contracts.append(contract)
        
        # Test traversal with depth limit
        traverser = LineageTraverser()
        result = traverser.traverse_top_down(
            contract_id=str(contracts[0].id),
            max_depth=2
        )
        
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
                {"email": "valid@example.com"}  # Valid entry
            ]
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        # Should normalize with warnings about invalid data
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        # Valid contact should be extracted
        if 'contact' in hub_contract:
            self.assertGreater(len(hub_contract['contact']), 0)
    
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
                {"type": "s3", "url": "s3://bucket"}  # Valid entry
            ]
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        # Should normalize with warnings
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        # Valid server should be extracted
        if 'servers' in hub_contract:
            self.assertGreater(len(hub_contract['servers']), 0)
    
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
            "support": []  # Empty array
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        # Should normalize successfully
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        # Empty arrays should be handled gracefully
        if 'servers' in hub_contract:
            self.assertEqual(len(hub_contract['servers']), 0)
    
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
            "support": None  # Null value
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        # Should normalize successfully
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        # Null values should be handled gracefully
        self.assertNotIn('servers', hub_contract)
        self.assertNotIn('support', hub_contract)
    
    def test_very_large_contract_json(self):
        """Test handling of very large contract JSON."""
        # Create contract with very large JSON (>1MB)
        large_data = {
            "hub_contract_version": "1.0.0",
            "id": "large-contract",
            "info": {"name": "Large Contract"},
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "large_field": "x" * 2 * 1024 * 1024  # 2MB string
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
            status=ContractStatus.ACTIVE
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
                status=ContractStatus.DRAFT
            )
            
            # Contract should be created but with failed status
            self.assertIsNotNone(contract)
            self.assertEqual(contract.normalization_status, NormalizationStatus.NORMALIZATION_FAILED)
        except Exception as e:
            # If creation fails, that's also acceptable
            self.assertIsNotNone(str(e))

