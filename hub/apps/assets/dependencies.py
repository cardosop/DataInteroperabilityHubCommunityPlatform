"""
Asset Dependencies Graph

Generate and visualize asset dependency graphs based on lineage relationships.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
from django.db.models import Q
import structlog

from .models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.contracts.lineage import LineageTraverser

logger = structlog.get_logger(__name__)


class AssetDependencyGraph:
    """
    Represents an asset dependency graph with nodes and edges.
    """
    
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.visited: Set[str] = set()
    
    def add_node(self, asset_id: str, asset: Asset, metadata: Optional[Dict[str, Any]] = None):
        """Add a node to the graph"""
        if asset_id in self.nodes:
            return
        
        self.nodes[asset_id] = {
            "id": str(asset.id),
            "key": asset.key,
            "name": asset.name,
            "status": asset.status,
            "domain": asset.domain,
            "dq_status": asset.dq_status,
            "compliance_status": asset.compliance_status,
            "health_score": asset.health_score,
            "popularity_score": asset.popularity_score,
            **(metadata or {})
        }
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str = "lineage",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add an edge to the graph"""
        edge = {
            "source": source_id,
            "target": target_id,
            "type": edge_type,
            **(metadata or {})
        }
        self.edges.append(edge)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to dictionary format"""
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges
        }
    
    def to_d3_format(self) -> Dict[str, Any]:
        """Convert to D3.js format"""
        return {
            "nodes": [
                {
                    **node,
                    "group": self._get_node_group(node)
                }
                for node in self.nodes.values()
            ],
            "links": [
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "value": 1,
                    "type": edge.get("type", "lineage")
                }
                for edge in self.edges
            ]
        }
    
    def to_dot_format(self) -> str:
        """Convert to Graphviz DOT format"""
        lines = ["digraph AssetDependencies {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")
        
        # Add nodes
        for node_id, node in self.nodes.items():
            label = f"{node['name']}\\n({node['key']})"
            lines.append(f'  "{node_id}" [label="{label}"];')
        
        # Add edges
        for edge in self.edges:
            lines.append(f'  "{edge["source"]}" -> "{edge["target"]}";')
        
        lines.append("}")
        return "\n".join(lines)
    
    def to_mermaid_format(self) -> str:
        """Convert to Mermaid format"""
        lines = ["graph LR"]
        
        # Add nodes
        for node_id, node in self.nodes.items():
            label = f"{node['name']}({node['key']})"
            lines.append(f'  {node_id}["{label}"]')
        
        # Add edges
        for edge in self.edges:
            lines.append(f'  {edge["source"]} --> {edge["target"]}')
        
        return "\n".join(lines)
    
    def _get_node_group(self, node: Dict[str, Any]) -> int:
        """Get node group for D3 visualization"""
        if node.get("status") == AssetStatus.PUBLIC:
            return 1
        elif node.get("status") == AssetStatus.ACTIVE:
            return 2
        else:
            return 3


class AssetDependencyService:
    """
    Service for generating asset dependency graphs.
    """
    
    @staticmethod
    def generate_dependency_graph(
        asset_id: str,
        tenant_id: str,
        direction: str = "both",
        max_depth: int = 10,
        include_metadata: bool = True
    ) -> AssetDependencyGraph:
        """
        Generate dependency graph for an asset.
        
        Args:
            asset_id: Source asset UUID
            tenant_id: Tenant UUID
            direction: "upstream", "downstream", or "both"
            max_depth: Maximum traversal depth
            include_metadata: Include asset metadata in nodes
        
        Returns:
            AssetDependencyGraph instance
        """
        graph = AssetDependencyGraph()
        
        try:
            source_asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
        except Asset.DoesNotExist:
            logger.warning("Asset not found for dependency graph", asset_id=asset_id)
            return graph
        
        # Add source node
        graph.add_node(str(source_asset.id), source_asset)
        
        # Traverse dependencies
        if direction in ["upstream", "both"]:
            AssetDependencyService._traverse_upstream(
                source_asset,
                graph,
                tenant_id,
                max_depth,
                include_metadata
            )
        
        if direction in ["downstream", "both"]:
            AssetDependencyService._traverse_downstream(
                source_asset,
                graph,
                tenant_id,
                max_depth,
                include_metadata
            )
        
        return graph
    
    @staticmethod
    def _traverse_upstream(
        asset: Asset,
        graph: AssetDependencyGraph,
        tenant_id: str,
        max_depth: int,
        include_metadata: bool,
        current_depth: int = 0,
        visited: Optional[Set[str]] = None
    ):
        """Traverse upstream dependencies (assets this asset depends on)"""
        if visited is None:
            visited = set()
        
        if current_depth >= max_depth:
            return
        
        if str(asset.id) in visited:
            return
        
        visited.add(str(asset.id))
        
        # Get contracts for asset
        contracts = Contract.objects.filter(
            tenant_id=tenant_id,
            asset=asset
        )
        
        for contract in contracts:
            if not contract.hub_contract_json:
                continue
            
            hub_contract = contract.hub_contract_json
            
            # Get lineage references
            lineage = hub_contract.get("lineage", {})
            contracts_list = lineage.get("contracts", [])
            
            # Find upstream assets
            for lineage_contract in contracts_list:
                # Find contracts with matching namespace/name
                upstream_contracts = Contract.objects.filter(
                    tenant_id=tenant_id,
                    hub_contract_json__contains={
                        "id": lineage_contract.get("name")
                    }
                )
                
                for upstream_contract in upstream_contracts:
                    if upstream_contract.asset and upstream_contract.asset.id != asset.id:
                        upstream_asset = upstream_contract.asset
                        
                        # Add upstream node
                        graph.add_node(str(upstream_asset.id), upstream_asset)
                        
                        # Add edge (upstream -> current)
                        graph.add_edge(
                            str(upstream_asset.id),
                            str(asset.id),
                            edge_type="lineage",
                            metadata={"direction": "upstream"}
                        )
                        
                        # Recursively traverse
                        AssetDependencyService._traverse_upstream(
                            upstream_asset,
                            graph,
                            tenant_id,
                            max_depth,
                            include_metadata,
                            current_depth + 1,
                            visited
                        )
    
    @staticmethod
    def _traverse_downstream(
        asset: Asset,
        graph: AssetDependencyGraph,
        tenant_id: str,
        max_depth: int,
        include_metadata: bool,
        current_depth: int = 0,
        visited: Optional[Set[str]] = None
    ):
        """Traverse downstream dependencies (assets that depend on this asset)"""
        if visited is None:
            visited = set()
        
        if current_depth >= max_depth:
            return
        
        if str(asset.id) in visited:
            return
        
        visited.add(str(asset.id))
        
        # Find contracts that reference this asset's contracts
        contracts = Contract.objects.filter(
            tenant_id=tenant_id,
            asset=asset
        )
        
        # Get contract names/IDs
        contract_names = []
        for contract in contracts:
            if contract.hub_contract_json:
                contract_id = contract.hub_contract_json.get("id")
                if contract_id:
                    contract_names.append(contract_id)
        
        # Find downstream contracts that reference these contracts
        for contract_name in contract_names:
            downstream_contracts = Contract.objects.filter(
                tenant_id=tenant_id,
                hub_contract_json__lineage__contracts__contains=[{"name": contract_name}]
            )
            
            for downstream_contract in downstream_contracts:
                if downstream_contract.asset and downstream_contract.asset.id != asset.id:
                    downstream_asset = downstream_contract.asset
                    
                    # Add downstream node
                    graph.add_node(str(downstream_asset.id), downstream_asset)
                    
                    # Add edge (current -> downstream)
                    graph.add_edge(
                        str(asset.id),
                        str(downstream_asset.id),
                        edge_type="lineage",
                        metadata={"direction": "downstream"}
                    )
                    
                    # Recursively traverse
                    AssetDependencyService._traverse_downstream(
                        downstream_asset,
                        graph,
                        tenant_id,
                        max_depth,
                        include_metadata,
                        current_depth + 1,
                        visited
                    )
    
    @staticmethod
    def get_dependency_stats(graph: AssetDependencyGraph) -> Dict[str, Any]:
        """Get statistics about the dependency graph"""
        return {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "upstream_count": sum(
                1 for e in graph.edges
                if e.get("metadata", {}).get("direction") == "upstream"
            ),
            "downstream_count": sum(
                1 for e in graph.edges
                if e.get("metadata", {}).get("direction") == "downstream"
            )
        }

