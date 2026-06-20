"""
Version Impact Analysis

Analyzes the impact of dataset version changes on assets and downstream systems.
"""

from __future__ import annotations

from typing import Any

import structlog

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract

from .models import Dataset

logger = structlog.get_logger(__name__)


class VersionImpactNode:
    """Represents a node in the version impact analysis graph"""

    def __init__(
        self,
        resource_type: str,  # ASSET, DATASET, CONTRACT
        resource_id: str,
        resource_name: str,
        depth: int = 0,
        path: list[str] | None = None,
    ):
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.depth = depth
        self.path = path or []
        self.children: list[VersionImpactNode] = []
        self.impact_score: float = 0.0
        self.severity: str = "LOW"
        self.metadata: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "depth": self.depth,
            "path": self.path,
            "impact_score": self.impact_score,
            "severity": self.severity,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children],
        }


class VersionImpactAnalyzer:
    """
    Analyzes impact of dataset version changes on assets and downstream systems.
    """

    def __init__(self, max_depth: int = 10, include_downstream: bool = True):
        self.max_depth = max_depth
        self.include_downstream = include_downstream
        self.visited_assets: set[str] = set()
        self.visited_datasets: set[str] = set()
        self.visited_contracts: set[str] = set()

    def analyze_impact(self, dataset_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        """
        Analyze impact of a dataset version change.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Optional tenant ID to limit analysis scope

        Returns:
            Impact analysis result with affected resources and scores
        """
        try:
            source_dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return {"error": "Dataset not found", "dataset_id": dataset_id}

        # Reset visited sets
        self.visited_assets.clear()
        self.visited_datasets.clear()
        self.visited_contracts.clear()

        # Build impact graph
        root_node = VersionImpactNode(
            resource_type="DATASET",
            resource_id=str(source_dataset.id),
            resource_name=f"{source_dataset.asset.name if source_dataset.asset else 'No Asset'} - Dataset v{source_dataset.version}",
            depth=0,
            path=[str(source_dataset.id)],
        )

        # Traverse to find affected resources
        self._traverse_impact(root_node, source_dataset, tenant_id=tenant_id, depth=0)

        # Calculate impact scores
        self._calculate_impact_scores(root_node, tenant_id)

        # Build result
        result = {
            "source": {
                "dataset_id": str(source_dataset.id),
                "dataset_version": source_dataset.version,
                "semantic_version": source_dataset.semantic_version,
                "asset_id": str(source_dataset.asset.id) if source_dataset.asset else None,
                "asset_name": source_dataset.asset.name if source_dataset.asset else None,
            },
            "impact_graph": root_node.to_dict(),
            "summary": self._build_summary(root_node),
            "total_affected": self._count_affected(root_node),
            "max_depth": self._get_max_depth(root_node),
        }

        return result

    def _traverse_impact(
        self,
        node: VersionImpactNode,
        dataset: Dataset,
        tenant_id: str | None = None,
        depth: int = 0,
    ):
        """Traverse to find affected resources"""
        if depth > self.max_depth:
            return

        # Find asset that owns this dataset
        if dataset.asset and str(dataset.asset.id) not in self.visited_assets:
            self.visited_assets.add(str(dataset.asset.id))

            asset_node = VersionImpactNode(
                resource_type="ASSET",
                resource_id=str(dataset.asset.id),
                resource_name=dataset.asset.name,
                depth=depth + 1,
                path=node.path + [f"asset:{dataset.asset.id}"],
            )
            node.children.append(asset_node)

            # Find contracts for this asset
            contracts = Contract.objects.filter(asset=dataset.asset, tenant=dataset.tenant)
            if tenant_id:
                contracts = contracts.filter(tenant_id=tenant_id)

            for contract in contracts:
                if str(contract.id) not in self.visited_contracts:
                    self.visited_contracts.add(str(contract.id))

                    contract_node = VersionImpactNode(
                        resource_type="CONTRACT",
                        resource_id=str(contract.id),
                        resource_name=contract.hub_contract_json.get("info", {}).get(
                            "name", "Unnamed Contract"
                        )
                        if isinstance(contract.hub_contract_json, dict)
                        else "Unnamed Contract",
                        depth=depth + 2,
                        path=asset_node.path + [f"contract:{contract.id}"],
                    )
                    asset_node.children.append(contract_node)

        # Find downstream datasets (via lineage or same asset)
        if self.include_downstream:
            # Find other datasets in the same asset (different versions)
            if dataset.asset:
                other_datasets = Dataset.objects.filter(
                    asset=dataset.asset, tenant=dataset.tenant
                ).exclude(id=dataset.id)

                if tenant_id:
                    other_datasets = other_datasets.filter(tenant_id=tenant_id)

                for other_dataset in other_datasets:
                    if str(other_dataset.id) not in self.visited_datasets:
                        self.visited_datasets.add(str(other_dataset.id))

                        dataset_node = VersionImpactNode(
                            resource_type="DATASET",
                            resource_id=str(other_dataset.id),
                            resource_name=f"{other_dataset.asset.name if other_dataset.asset else 'No Asset'} - Dataset v{other_dataset.version}",
                            depth=depth + 1,
                            path=node.path + [f"dataset:{other_dataset.id}"],
                        )
                        node.children.append(dataset_node)

    def _calculate_impact_scores(self, node: VersionImpactNode, tenant_id: str | None = None):
        """Calculate impact scores for nodes"""
        # Base score decreases with depth
        base_score = 100.0 / (node.depth + 1)

        # Resource type weighting
        type_weights = {"ASSET": 1.0, "CONTRACT": 0.8, "DATASET": 0.6}
        type_weight = type_weights.get(node.resource_type, 0.5)

        # Get resource criticality if asset
        criticality_weight = 1.0
        if node.resource_type == "ASSET":
            try:
                asset = Asset.objects.get(id=node.resource_id)
                # Map asset status to criticality
                status_weights = {
                    AssetStatus.ACTIVE: 1.5,
                    AssetStatus.PUBLIC: 2.0,
                    AssetStatus.DRAFT: 0.5,
                    AssetStatus.RETIRED: 0.3,
                }
                criticality_weight = status_weights.get(asset.status, 1.0)
            except Asset.DoesNotExist:
                pass

        # Calculate impact score
        node.impact_score = base_score * type_weight * criticality_weight

        # Determine severity
        if node.impact_score >= 50.0:
            node.severity = "HIGH"
        elif node.impact_score >= 20.0:
            node.severity = "MEDIUM"
        else:
            node.severity = "LOW"

        # Recursively calculate for children
        for child in node.children:
            self._calculate_impact_scores(child, tenant_id)

    def _build_summary(self, node: VersionImpactNode) -> dict[str, Any]:
        """Build summary statistics"""
        summary = {
            "total_assets": 0,
            "total_datasets": 0,
            "total_contracts": 0,
            "high_impact_count": 0,
            "medium_impact_count": 0,
            "low_impact_count": 0,
        }

        def count_nodes(n: VersionImpactNode):
            if n.resource_type == "ASSET":
                summary["total_assets"] += 1
            elif n.resource_type == "DATASET":
                summary["total_datasets"] += 1
            elif n.resource_type == "CONTRACT":
                summary["total_contracts"] += 1

            if n.severity == "HIGH":
                summary["high_impact_count"] += 1
            elif n.severity == "MEDIUM":
                summary["medium_impact_count"] += 1
            else:
                summary["low_impact_count"] += 1

            for child in n.children:
                count_nodes(child)

        count_nodes(node)

        return summary

    def _count_affected(self, node: VersionImpactNode) -> int:
        """Count total affected resources"""
        count = 0

        def count_nodes(n: VersionImpactNode):
            nonlocal count
            count += 1
            for child in n.children:
                count_nodes(child)

        count_nodes(node)
        return count - 1  # Exclude root node

    def _get_max_depth(self, node: VersionImpactNode) -> int:
        """Get maximum depth of impact graph"""
        if not node.children:
            return node.depth

        return max(self._get_max_depth(child) for child in node.children)
