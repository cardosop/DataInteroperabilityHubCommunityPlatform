"""
Lineage Impact Analysis

Implements reverse lineage traversal to find all resources that depend on a given
contract, model, or field. Includes impact scoring, severity calculation, and
visualization support.
"""

from __future__ import annotations

from typing import Any

import structlog

from .models import Contract

logger = structlog.get_logger(__name__)


class ImpactNode:
    """Represents a node in the impact analysis graph"""

    def __init__(
        self,
        resource_type: str = "CONTRACT",  # CONTRACT, MODEL, FIELD
        resource_id: str = "",
        contract_id: str = "",
        model_name: str | None = None,
        field_name: str | None = None,
        contract_name: str | None = None,
        depth: int = 0,
        path: list[str] | None = None,
        impact_score: float = 0.0,
        severity: str = "LOW",
    ):
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.contract_id = contract_id
        self.model_name = model_name
        self.field_name = field_name
        self.contract_name = contract_name
        self.depth = depth
        self.path = path or []
        self.children: list[ImpactNode] = []
        self.impact_score: float = impact_score
        self.severity: str = severity
        self.metadata: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "contract_id": self.contract_id,
            "model_name": self.model_name,
            "field_name": self.field_name,
            "depth": self.depth,
            "path": self.path,
            "impact_score": self.impact_score,
            "severity": self.severity,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children],
        }


class ImpactAnalyzer:
    """
    Analyzes impact of changes to contracts, models, or fields by traversing
    reverse lineage (finding all dependents).
    """

    def __init__(
        self,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
        include_fields: bool = True,
    ):
        self.max_contract_depth = max_contract_depth
        self.max_model_depth = max_model_depth
        self.max_field_depth = max_field_depth
        self.include_fields = include_fields
        self.visited_contracts: set[str] = set()
        self.visited_models: set[tuple[str, str]] = set()  # (contract_id, model_name)
        self.visited_fields: set[tuple[str, str, str]] = (
            set()
        )  # (contract_id, model_name, field_name)
        self.cycle_detection: set[tuple[str, ...]] = set()  # Track paths to detect cycles

    def analyze_impact(
        self,
        contract_id: str,
        model_name: str | None = None,
        field_name: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze impact of changes to a contract, model, or field.

        Args:
            contract_id: Contract UUID
            model_name: Optional model name (for model-level impact)
            field_name: Optional field name (for field-level impact)
            tenant_id: Optional tenant ID to limit analysis scope

        Returns:
            Impact analysis result with affected resources and scores
        """
        try:
            source_contract = Contract.objects.get(id=contract_id)
        except (Contract.DoesNotExist, Exception):
            return {"error": "Contract not found", "contract_id": contract_id}

        if tenant_id is not None:
            cid = getattr(source_contract, "tenant_id", None)
            try:
                if cid is None:
                    return {
                        "error": "Contract not found",
                        "contract_id": contract_id,
                    }
                if str(cid) != str(tenant_id):
                    return {
                        "error": "Contract not found",
                        "contract_id": contract_id,
                    }
            except Exception:
                return {
                    "error": "Contract not found",
                    "contract_id": contract_id,
                }

        # Reset visited sets for new analysis
        self.visited_contracts.clear()
        self.visited_models.clear()
        self.visited_fields.clear()
        self.cycle_detection.clear()

        # Build impact graph
        root_node = ImpactNode(
            resource_type="CONTRACT"
            if not model_name
            else ("MODEL" if not field_name else "FIELD"),
            resource_id=contract_id,
            contract_id=contract_id,
            model_name=model_name,
            field_name=field_name,
            depth=0,
            path=[contract_id],
        )

        # Traverse reverse lineage
        self._traverse_reverse_lineage(
            root_node,
            source_contract,
            model_name=model_name,
            field_name=field_name,
            tenant_id=tenant_id,
            contract_depth=0,
            model_depth=0,
            field_depth=0,
        )

        # Calculate impact scores
        self._calculate_impact_scores(root_node, tenant_id)

        # Build result
        result = {
            "source": {
                "contract_id": contract_id,
                "contract_name": source_contract.hub_contract_json.get("info", {}).get("name")
                if isinstance(source_contract.hub_contract_json, dict)
                else None,
                "model_name": model_name,
                "field_name": field_name,
            },
            "impact_graph": root_node.to_dict(),
            "summary": self._build_summary(root_node),
            "total_affected": self._count_affected(root_node),
            "max_depth": self._get_max_depth(root_node),
            "cycles_detected": len(self.cycle_detection) > 0,
        }

        return result

    def _traverse_reverse_lineage(
        self,
        node: ImpactNode,
        contract: Contract,
        model_name: str | None = None,
        field_name: str | None = None,
        tenant_id: str | None = None,
        contract_depth: int = 0,
        model_depth: int = 0,
        field_depth: int = 0,
    ):
        """Traverse reverse lineage to find dependents"""
        # Check depth limits (>= so that max_depth=0 means no traversal)
        if contract_depth >= self.max_contract_depth:
            return

        if model_depth >= self.max_model_depth:
            return

        if field_depth >= self.max_field_depth:
            return

        # Check for cycles
        path_key = tuple(node.path)
        if path_key in self.cycle_detection:
            logger.warning(
                "Cycle detected in impact analysis", path=node.path, contract_id=str(contract.id)
            )
            return

        self.cycle_detection.add(path_key)

        # Find contracts that reference this contract/model/field
        dependents = self._find_dependents(
            contract, model_name=model_name, field_name=field_name, tenant_id=tenant_id
        )

        for dependent in dependents:
            dependent_contract_id = str(dependent["contract_id"])

            # Skip if already visited at this level
            if dependent_contract_id in self.visited_contracts:
                continue

            self.visited_contracts.add(dependent_contract_id)

            # Create child node
            child_node = ImpactNode(
                resource_type=dependent.get("resource_type", "CONTRACT"),
                resource_id=dependent_contract_id,
                contract_id=dependent_contract_id,
                model_name=dependent.get("model_name"),
                field_name=dependent.get("field_name"),
                depth=node.depth + 1,
                path=node.path + [dependent_contract_id],
            )

            # Add metadata
            child_node.metadata = {
                "contract_name": dependent.get("contract_name"),
                "reference_type": dependent.get("reference_type"),  # CONTRACT, MODEL, FIELD
                "reference_path": dependent.get("reference_path"),
            }

            node.children.append(child_node)

            # Recursively traverse
            try:
                dependent_contract = Contract.objects.get(id=dependent_contract_id)
                self._traverse_reverse_lineage(
                    child_node,
                    dependent_contract,
                    model_name=dependent.get("model_name"),
                    field_name=dependent.get("field_name"),
                    tenant_id=tenant_id,
                    contract_depth=contract_depth + 1,
                    model_depth=model_depth + (1 if dependent.get("model_name") else 0),
                    field_depth=field_depth + (1 if dependent.get("field_name") else 0),
                )
            except Contract.DoesNotExist:
                logger.warning("Dependent contract not found", contract_id=dependent_contract_id)

    def _find_dependents(
        self,
        source_contract: Contract,
        model_name: str | None = None,
        field_name: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find all contracts that reference the source contract/model/field.

        This is the reverse of forward lineage - we search for contracts that
        have lineage references pointing to the source.
        """
        dependents = []

        # Get source contract info
        source_hub_contract = source_contract.hub_contract_json
        if not isinstance(source_hub_contract, dict):
            return dependents

        source_info = source_hub_contract.get("info", {})
        source_contract_name = source_info.get("name")
        source_namespace = source_info.get("domain") or source_info.get("namespace")

        # Query all contracts (can be optimized with indexes)
        queryset = Contract.objects.exclude(id=source_contract.id)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        for contract in queryset:
            hub_contract = contract.hub_contract_json
            if not isinstance(hub_contract, dict):
                continue

            # Check contract-level lineage
            lineage = hub_contract.get("lineage", {})
            if isinstance(lineage, dict):
                contract_refs = lineage.get("contracts", [])
                for ref in contract_refs:
                    if isinstance(ref, dict):
                        ref_name = ref.get("name")
                        ref_namespace = ref.get("namespace")

                        # Match contract reference
                        if ref_name == source_contract_name:
                            if not source_namespace or ref_namespace == source_namespace:
                                dependents.append(
                                    {
                                        "contract_id": contract.id,
                                        "contract_name": hub_contract.get("info", {}).get("name"),
                                        "resource_type": "CONTRACT",
                                        "reference_type": "CONTRACT",
                                        "reference_path": f"{ref_namespace}/{ref_name}"
                                        if ref_namespace
                                        else ref_name,
                                    }
                                )

            # Check model-level lineage
            models_list = hub_contract.get("models", [])
            for model in models_list:
                if not isinstance(model, dict):
                    continue

                model_lineage = model.get("lineage", {})
                if isinstance(model_lineage, dict):
                    model_refs = model_lineage.get("models", [])
                    for ref in model_refs:
                        if isinstance(ref, dict):
                            ref_name = ref.get("name")
                            ref_model_name = ref.get("model_name")

                            # Match model reference
                            if ref_name == source_contract_name and ref_model_name == model_name:
                                dependents.append(
                                    {
                                        "contract_id": contract.id,
                                        "contract_name": hub_contract.get("info", {}).get("name"),
                                        "model_name": model.get("name"),
                                        "resource_type": "MODEL",
                                        "reference_type": "MODEL",
                                        "reference_path": f"{ref_name}/{ref_model_name}",
                                    }
                                )

                # Check field-level lineage
                if self.include_fields and field_name:
                    fields = model.get("fields", [])
                    for field in fields:
                        if not isinstance(field, dict):
                            continue

                        field_lineage = field.get("lineage")
                        if field_lineage:
                            input_fields = field_lineage.get("input_fields") or field_lineage.get(
                                "inputFields", []
                            )
                            for input_field in input_fields:
                                if isinstance(input_field, dict):
                                    input_name = input_field.get("name")
                                    input_model = input_field.get("model") or input_field.get(
                                        "model_name"
                                    )
                                    input_field_name = input_field.get("field")

                                    # Match field reference
                                    if (
                                        input_name == source_contract_name
                                        and input_model == model_name
                                        and input_field_name == field_name
                                    ):
                                        dependents.append(
                                            {
                                                "contract_id": contract.id,
                                                "contract_name": hub_contract.get("info", {}).get(
                                                    "name"
                                                ),
                                                "model_name": model.get("name"),
                                                "field_name": field.get("name"),
                                                "resource_type": "FIELD",
                                                "reference_type": "FIELD",
                                                "reference_path": f"{input_name}/{input_model}/{input_field_name}",
                                            }
                                        )

        return dependents

    def _calculate_impact_scores(self, node: ImpactNode, tenant_id: str | None = None):
        """Calculate impact scores for all nodes in the graph"""
        # Get asset criticality and usage frequency
        try:
            # Get contract and its associated asset
            contract = Contract.objects.get(id=node.contract_id)
            asset = contract.asset

            if asset:
                # Use asset metadata for criticality
                # For now, infer criticality from asset status and visibility
                if asset.status == "ACTIVE" and asset.visibility == "PUBLIC":
                    node.metadata["asset_criticality"] = "HIGH"
                elif asset.status == "ACTIVE":
                    node.metadata["asset_criticality"] = "MEDIUM"
                else:
                    node.metadata["asset_criticality"] = "LOW"

                # Infer usage frequency from asset status
                if asset.status == "ACTIVE":
                    node.metadata["asset_usage_frequency"] = "HIGH"
                elif asset.status == "PUBLIC":
                    node.metadata["asset_usage_frequency"] = "MEDIUM"
                else:
                    node.metadata["asset_usage_frequency"] = "LOW"
            else:
                node.metadata["asset_criticality"] = "MEDIUM"
                node.metadata["asset_usage_frequency"] = "MEDIUM"
        except Contract.DoesNotExist:
            node.metadata["asset_criticality"] = "MEDIUM"
            node.metadata["asset_usage_frequency"] = "MEDIUM"
        except Exception as e:
            logger.warning(
                "Failed to get asset metadata for impact scoring",
                contract_id=node.contract_id,
                error=str(e),
            )
            node.metadata["asset_criticality"] = "MEDIUM"
            node.metadata["asset_usage_frequency"] = "MEDIUM"

        # Calculate base impact score
        # Factors: depth (deeper = lower impact), resource type, criticality, usage
        base_score = 100.0 / (node.depth + 1)  # Deeper nodes have lower base impact

        # Resource type multiplier
        type_multiplier = {"CONTRACT": 1.0, "MODEL": 0.7, "FIELD": 0.5}
        base_score *= type_multiplier.get(node.resource_type, 1.0)

        # Criticality multiplier
        criticality_multiplier = {"CRITICAL": 2.0, "HIGH": 1.5, "MEDIUM": 1.0, "LOW": 0.5}
        criticality = node.metadata.get("asset_criticality", "MEDIUM")
        base_score *= criticality_multiplier.get(criticality, 1.0)

        # Usage frequency multiplier
        usage_multiplier = {"HIGH": 1.5, "MEDIUM": 1.0, "LOW": 0.5}
        usage = node.metadata.get("asset_usage_frequency", "MEDIUM")
        base_score *= usage_multiplier.get(usage, 1.0)

        # Aggregate from children
        children_score = sum(child.impact_score for child in node.children)

        node.impact_score = base_score + (
            children_score * 0.5
        )  # Children contribute 50% of their score

        # Determine severity
        if node.impact_score >= 80:
            node.severity = "CRITICAL"
        elif node.impact_score >= 50:
            node.severity = "HIGH"
        elif node.impact_score >= 20:
            node.severity = "MEDIUM"
        else:
            node.severity = "LOW"

        # Recursively calculate for children
        for child in node.children:
            self._calculate_impact_scores(child, tenant_id)

    def _build_summary(self, node: ImpactNode) -> dict[str, Any]:
        """Build summary statistics from impact graph"""
        summary = {
            "total_contracts": 0,
            "total_models": 0,
            "total_fields": 0,
            "severity_distribution": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "max_impact_score": 0.0,
            "avg_impact_score": 0.0,
        }

        def traverse(node: ImpactNode):
            if node.resource_type == "CONTRACT":
                summary["total_contracts"] += 1
            elif node.resource_type == "MODEL":
                summary["total_models"] += 1
            elif node.resource_type == "FIELD":
                summary["total_fields"] += 1

            summary["severity_distribution"][node.severity] = (
                summary["severity_distribution"].get(node.severity, 0) + 1
            )
            summary["max_impact_score"] = max(summary["max_impact_score"], node.impact_score)

            for child in node.children:
                traverse(child)

        traverse(node)

        # Calculate average
        total_nodes = summary["total_contracts"] + summary["total_models"] + summary["total_fields"]
        if total_nodes > 0:
            # Sum all scores and divide by count
            total_score = 0.0
            count = 0

            def sum_scores(node: ImpactNode):
                nonlocal total_score, count
                total_score += node.impact_score
                count += 1
                for child in node.children:
                    sum_scores(child)

            sum_scores(node)
            summary["avg_impact_score"] = total_score / count if count > 0 else 0.0

        return summary

    def _count_affected(self, node: ImpactNode) -> int:
        """Count total affected resources"""
        count = 1  # Count self
        for child in node.children:
            count += self._count_affected(child)
        return count

    def _get_max_depth(self, node: ImpactNode) -> int:
        """Get maximum depth of impact graph"""
        if not node.children:
            return node.depth

        return max(self._get_max_depth(child) for child in node.children)


class ImpactScorer:
    """
    Calculates impact scores with configurable weights for severity,
    asset criticality, and usage frequency.
    """

    DEFAULT_WEIGHTS = {
        "depth": 1.0,
        "resource_type": 1.0,
        "criticality": 1.0,
        "usage_frequency": 1.0,
        "recency": 0.5,  # How recently the resource was updated
    }

    @staticmethod
    def calculate_severity(impact_score: float) -> str:
        """Calculate severity level from impact score"""
        if impact_score >= 80:
            return "CRITICAL"
        elif impact_score >= 50:
            return "HIGH"
        elif impact_score >= 20:
            return "MEDIUM"
        else:
            return "LOW"

    @staticmethod
    def get_asset_criticality(contract_id: str, tenant_id: str | None = None) -> str:
        """Get asset criticality for a contract"""
        try:
            contract = Contract.objects.get(id=contract_id)
            asset = contract.asset

            if asset:
                # Infer criticality from asset status and visibility
                if asset.status == "ACTIVE" and asset.visibility == "PUBLIC":
                    return "HIGH"
                elif asset.status == "ACTIVE":
                    return "MEDIUM"
                else:
                    return "LOW"
        except (Contract.DoesNotExist, Exception):
            pass

        return "MEDIUM"  # Default

    @staticmethod
    def get_usage_frequency(contract_id: str, tenant_id: str | None = None) -> str:
        """Get usage frequency for a contract"""
        try:
            contract = Contract.objects.get(id=contract_id)
            asset = contract.asset

            if asset:
                # Infer usage frequency from asset status
                if asset.status == "ACTIVE":
                    return "HIGH"
                elif asset.status == "PUBLIC":
                    return "MEDIUM"
                else:
                    return "LOW"
        except (Contract.DoesNotExist, Exception):
            pass

        return "MEDIUM"  # Default
