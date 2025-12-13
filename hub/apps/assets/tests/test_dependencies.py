"""
Unit tests for Asset Dependencies Graph

Tests for dependency graph generation and visualization.
"""
import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.dependencies import AssetDependencyService, AssetDependencyGraph
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AssetDependencyServiceTest(TestCase):
    """Test AssetDependencyService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-2",
            name="Asset 2",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
    
    def test_generate_dependency_graph(self):
        """Test dependency graph generation"""
        # Create contracts with lineage
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset1,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"apiVersion": "v3", "kind": "DataContract", "id": "contract-1"}',
            hub_contract_json={
                "id": "contract-1",
                "lineage": {
                    "contracts": [
                        {
                            "namespace": "ns1",
                            "name": "contract-2"
                        }
                    ]
                }
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )
        
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset2,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"apiVersion": "v3", "kind": "DataContract", "id": "contract-2"}',
            hub_contract_json={
                "id": "contract-2"
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )
        
        # Generate graph
        graph = AssetDependencyService.generate_dependency_graph(
            asset_id=str(self.asset1.id),
            tenant_id=str(self.tenant.id),
            direction="both",
            max_depth=10
        )
        
        # Verify graph structure
        self.assertGreater(len(graph.nodes), 0)
        self.assertIn(str(self.asset1.id), graph.nodes)
    
    def test_dependency_graph_formats(self):
        """Test graph format conversions"""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")
        
        # Test JSON format
        json_data = graph.to_dict()
        self.assertIn("nodes", json_data)
        self.assertIn("edges", json_data)
        
        # Test D3 format
        d3_data = graph.to_d3_format()
        self.assertIn("nodes", d3_data)
        self.assertIn("links", d3_data)
        
        # Test DOT format
        dot_data = graph.to_dot_format()
        self.assertIn("digraph", dot_data)
        
        # Test Mermaid format
        mermaid_data = graph.to_mermaid_format()
        self.assertIn("graph", mermaid_data)
    
    def test_dependency_stats(self):
        """Test dependency statistics"""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2", metadata={"direction": "downstream"})
        
        stats = AssetDependencyService.get_dependency_stats(graph)
        
        self.assertIn("node_count", stats)
        self.assertIn("edge_count", stats)
        self.assertEqual(stats["node_count"], 2)
        self.assertEqual(stats["edge_count"], 1)

