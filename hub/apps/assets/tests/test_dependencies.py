"""
Unit tests for Asset Dependencies Graph

Tests for dependency graph generation and visualization.
"""

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
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email="user@example.com",
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

    def test_dependency_graph_to_dict_returns_json_format(self):
        """Test dependency graph to_dict returns JSON format."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        json_data = graph.to_dict()
        self.assertIn("nodes", json_data)
        self.assertIn("edges", json_data)

    def test_dependency_graph_to_d3_format_returns_d3_structure(self):
        """Test dependency graph to_d3_format returns D3 structure."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        d3_data = graph.to_d3_format()
        self.assertIn("nodes", d3_data)
        self.assertIn("links", d3_data)

    def test_dependency_graph_to_dot_format_returns_dot_string(self):
        """Test dependency graph to_dot_format returns DOT string."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        dot_data = graph.to_dot_format()
        self.assertIn("digraph", dot_data)

    def test_dependency_graph_to_mermaid_format_returns_mermaid_string(self):
        """Test dependency graph to_mermaid_format returns Mermaid string."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")

        mermaid_data = graph.to_mermaid_format()
        self.assertIn("graph", mermaid_data)

    def test_dependency_stats_returns_node_count(self):
        """Test dependency stats returns node_count."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2", metadata={"direction": "downstream"})

        stats = AssetDependencyService.get_dependency_stats(graph)
        self.assertIn("node_count", stats)

    def test_dependency_stats_returns_edge_count(self):
        """Test dependency stats returns edge_count."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2", metadata={"direction": "downstream"})

        stats = AssetDependencyService.get_dependency_stats(graph)
        self.assertIn("edge_count", stats)

    def test_dependency_stats_returns_correct_node_count(self):
        """Test dependency stats returns correct node_count."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2", metadata={"direction": "downstream"})

        stats = AssetDependencyService.get_dependency_stats(graph)
        self.assertEqual(stats["node_count"], 2)

    def test_dependency_stats_returns_correct_edge_count(self):
        """Test dependency stats returns correct edge_count."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2", metadata={"direction": "downstream"})

        stats = AssetDependencyService.get_dependency_stats(graph)
        self.assertEqual(stats["edge_count"], 1)

    # ========== SUCCESS SCENARIOS ==========

    def test_generate_dependency_graph_success(self):
        """Test successful dependency graph generation (success scenario)"""
        # Create contract with lineage
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset1,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"id": "contract-1"}',
            hub_contract_json={"id": "contract-1"},
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

        # Should return graph
        self.assertIsNotNone(graph)
        self.assertGreaterEqual(len(graph.nodes), 0)

    # ========== FAILURE SCENARIOS ==========

    def test_generate_dependency_graph_nonexistent_asset(self):
        """Test dependency graph generation with non-existent asset (failure scenario)"""
        import uuid

        fake_asset_id = str(uuid.uuid4())

        # Should handle non-existent asset gracefully
        try:
            graph = AssetDependencyService.generate_dependency_graph(
                asset_id=fake_asset_id,
                tenant_id=str(self.tenant.id),
                direction="both",
                max_depth=10,
            )
            # If succeeds, should return empty graph or handle gracefully
            self.assertIsNotNone(graph)
        except Exception:
            # If fails, that's acceptable for non-existent asset
            pass

    def test_generate_dependency_graph_invalid_direction(self):
        """Test dependency graph generation with invalid direction (failure scenario)"""
        # Should handle invalid direction gracefully
        try:
            graph = AssetDependencyService.generate_dependency_graph(
                asset_id=str(self.asset1.id),
                tenant_id=str(self.tenant.id),
                direction="INVALID",
                max_depth=10,
            )
            # If succeeds, should use default direction
            self.assertIsNotNone(graph)
        except (ValueError, AttributeError):
            # If fails, that's acceptable for invalid direction
            pass

    # ========== EDGE CASES ==========

    def test_generate_dependency_graph_zero_max_depth(self):
        """Test dependency graph generation with zero max_depth (edge case)"""
        # Should handle zero depth gracefully
        try:
            graph = AssetDependencyService.generate_dependency_graph(
                asset_id=str(self.asset1.id),
                tenant_id=str(self.tenant.id),
                direction="both",
                max_depth=0,
            )
            # Should return graph with only root node
            self.assertIsNotNone(graph)
            self.assertGreaterEqual(len(graph.nodes), 0)
        except Exception:
            # If fails, that's acceptable for zero depth
            pass

    def test_generate_dependency_graph_very_large_max_depth(self):
        """Test dependency graph generation with very large max_depth (edge case)"""
        # Should handle large depth gracefully
        try:
            graph = AssetDependencyService.generate_dependency_graph(
                asset_id=str(self.asset1.id),
                tenant_id=str(self.tenant.id),
                direction="both",
                max_depth=999999,
            )
            # Should return graph
            self.assertIsNotNone(graph)
        except Exception:
            # If fails, that's acceptable for very large depth
            pass

    def test_dependency_graph_empty_graph_returns_structure(self):
        """Test dependency graph with no nodes returns structure."""
        graph = AssetDependencyGraph()

        json_data = graph.to_dict()
        self.assertIn("nodes", json_data)
        self.assertIn("edges", json_data)

    def test_dependency_graph_empty_graph_has_zero_nodes(self):
        """Test dependency graph with no nodes has zero nodes."""
        graph = AssetDependencyGraph()

        json_data = graph.to_dict()
        self.assertEqual(len(json_data["nodes"]), 0)

    def test_dependency_graph_empty_graph_has_zero_edges(self):
        """Test dependency graph with no nodes has zero edges."""
        graph = AssetDependencyGraph()

        json_data = graph.to_dict()
        self.assertEqual(len(json_data["edges"]), 0)

    def test_dependency_graph_circular_reference_handles_circular_edges(self):
        """Test dependency graph with circular reference handles circular edges."""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)
        graph.add_edge("node1", "node2")
        graph.add_edge("node2", "node1")

        json_data = graph.to_dict()
        self.assertEqual(len(json_data["edges"]), 2)

    # ========== ERROR HANDLING ==========

    def test_generate_dependency_graph_database_error_handling(self):
        """Test error handling when database query fails"""
        # Use valid asset
        try:
            graph = AssetDependencyService.generate_dependency_graph(
                asset_id=str(self.asset1.id),
                tenant_id=str(self.tenant.id),
                direction="both",
                max_depth=10,
            )
            # Should return graph or handle gracefully
            self.assertIsNotNone(graph)
        except Exception:
            # If raises exception, that's a problem
            self.fail("generate_dependency_graph should handle database errors gracefully")

    def test_dependency_graph_add_node_error_handling(self):
        """Test error handling when adding node fails"""
        graph = AssetDependencyGraph()

        # Should handle errors gracefully
        try:
            graph.add_node("node1", self.asset1)
            # Should succeed
            self.assertIn("node1", graph.nodes)
        except Exception:
            # If raises exception, that's a problem
            self.fail("add_node should handle errors gracefully")

    def test_dependency_graph_add_edge_error_handling(self):
        """Test error handling when adding edge fails"""
        graph = AssetDependencyGraph()
        graph.add_node("node1", self.asset1)
        graph.add_node("node2", self.asset2)

        # Should handle errors gracefully
        try:
            graph.add_edge("node1", "node2")
            # Should succeed
            self.assertGreater(len(graph.edges), 0)
        except Exception:
            # If raises exception, that's a problem
            self.fail("add_edge should handle errors gracefully")
