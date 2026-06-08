"""
Unit tests for Asset Dependencies Graph

Tests for dependency graph generation and visualization.
"""

import uuid
import pytest
from django.test import TestCase

from hub.apps.assets.dependencies import AssetDependencyGraph, AssetDependencyService
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AssetDependencyServiceTest(TestCase):
    """Test AssetDependencyService"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-2",
            name="Asset 2",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
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
                "lineage": {"contracts": [{"namespace": "ns1", "name": "contract-2"}]},
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset2,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"apiVersion": "v3", "kind": "DataContract", "id": "contract-2"}',
            hub_contract_json={"id": "contract-2"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Generate graph
        graph = AssetDependencyService.generate_dependency_graph(
            asset_id=str(self.asset1.id),
            tenant_id=str(self.tenant.id),
            direction="both",
            max_depth=10,
        )

        # Verify graph structure
        self.assertGreater(len(graph.nodes), 0)
        self.assertIn(str(self.asset1.id), graph.nodes)

    def test_dependency_graph_format_outputs(self):
        """Test to_dict returns JSON-serializable structure with correct keys."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        json_data = graph.to_dict()
        self.assertIn("nodes", json_data)
        self.assertIn("edges", json_data)
        self.assertEqual(len(json_data["nodes"]), 2)
        self.assertEqual(len(json_data["edges"]), 1)

    def test_dependency_graph_to_d3_format(self):
        """Test to_d3_format returns D3-compatible structure."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        d3_data = graph.to_d3_format()
        self.assertIn("nodes", d3_data)
        self.assertIn("links", d3_data)
        # nodes in D3 format should be a list
        self.assertIsInstance(d3_data["nodes"], list)
        self.assertIsInstance(d3_data["links"], list)

    def test_dependency_graph_to_dot_format(self):
        """Test to_dot_format returns valid DOT digraph string."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        dot_data = graph.to_dot_format()
        self.assertIn("digraph", dot_data)
        self.assertIn("node1", dot_data)
        self.assertIn("node2", dot_data)

    def test_dependency_graph_to_mermaid_format(self):
        """Test to_mermaid_format returns valid Mermaid graph string."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        mermaid_data = graph.to_mermaid_format()
        self.assertIn("graph", mermaid_data)
        self.assertIn("node1", mermaid_data)
        self.assertIn("node2", mermaid_data)

    def test_dependency_stats_returns_correct_counts(self):
        """Test dependency stats returns correct node_count and edge_count."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2", metadata={"direction": "downstream"})

        stats = AssetDependencyService.get_dependency_stats(graph)
        self.assertIn("node_count", stats)
        self.assertIn("edge_count", stats)
        self.assertEqual(stats["node_count"], 2)
        self.assertEqual(stats["edge_count"], 1)

    # ========== EDGE CASES ==========

    def test_generate_dependency_graph_nonexistent_asset(self):
        """Test dependency graph with non-existent asset returns empty graph."""
        fake_asset_id = str(uuid.uuid4())

        graph = AssetDependencyService.generate_dependency_graph(
            asset_id=fake_asset_id,
            tenant_id=str(self.tenant.id),
            direction="both",
            max_depth=10,
        )
        self.assertIsNotNone(graph)
        self.assertEqual(len(graph.nodes), 0)

    def test_generate_dependency_graph_invalid_direction(self):
        """Test dependency graph with invalid direction falls back to 'both'.

        The service treats unknown direction values as 'both' rather than
        raising, which is the documented contract.
        """
        graph = AssetDependencyService.generate_dependency_graph(
            asset_id=str(self.asset1.id),
            tenant_id=str(self.tenant.id),
            direction="INVALID",
            max_depth=10,
        )
        self.assertIsNotNone(graph)
        self.assertIsInstance(graph.nodes, dict)
        # With 'both' direction, the root node is always included
        self.assertGreaterEqual(len(graph.nodes), 1)

    def test_generate_dependency_graph_zero_max_depth(self):
        """Test dependency graph with zero max_depth returns valid graph."""
        graph = AssetDependencyService.generate_dependency_graph(
            asset_id=str(self.asset1.id),
            tenant_id=str(self.tenant.id),
            direction="both",
            max_depth=0,
        )
        self.assertIsNotNone(graph)
        self.assertIsInstance(graph.nodes, dict)

    def test_generate_dependency_graph_very_large_max_depth(self):
        """Test dependency graph with very large max_depth returns valid graph."""
        graph = AssetDependencyService.generate_dependency_graph(
            asset_id=str(self.asset1.id),
            tenant_id=str(self.tenant.id),
            direction="both",
            max_depth=999999,
        )
        self.assertIsNotNone(graph)
        self.assertIsInstance(graph.nodes, dict)

    def test_dependency_graph_empty_graph(self):
        """Test empty dependency graph produces valid empty structure."""
        graph = AssetDependencyGraph()

        json_data = graph.to_dict()
        self.assertIn("nodes", json_data)
        self.assertIn("edges", json_data)
        self.assertEqual(len(json_data["nodes"]), 0)
        self.assertEqual(len(json_data["edges"]), 0)

    def test_dependency_graph_circular_reference(self):
        """Test circular reference produces correct edge count without infinite loop."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")
        graph.add_edge("node2", "node1")

        json_data = graph.to_dict()
        self.assertEqual(len(json_data["edges"]), 2)

    # ========== UTILITY TESTS ==========

    def test_dependency_graph_add_node(self):
        """Test adding a node to the dependency graph."""
        graph = AssetDependencyGraph()

        graph.add_node("node1", self.asset1)
        self.assertIn("node1", graph.nodes)

    def test_dependency_graph_add_edge(self):
        """Test adding an edge between two nodes."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)

        graph.add_edge("node1", "node2")
        self.assertGreater(len(graph.edges), 0)
        # Edges are stored as dicts with source/target keys
        edge_sources = [e["source"] for e in graph.edges]
        edge_targets = [e["target"] for e in graph.edges]
        self.assertIn("node1", edge_sources)
        self.assertIn("node2", edge_targets)
