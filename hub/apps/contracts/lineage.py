"""
Multi-level lineage extraction, storage, resolution, traversal, and visualization.

This module implements comprehensive lineage support at three levels:
- Contract-level: Contract-to-contract dependencies
- Model-level: Model-to-model dependencies
- Field-level: Field-to-field dependencies

All lineage references use the format: namespace/name/model_name/field_name
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from django.core.cache import cache
from django.db import models

# Import Contract model - will be available at runtime
try:
    from hub.apps.contracts.models import Contract
except ImportError:
    # For testing or when models aren't available
    Contract = None  # type: ignore


class LineageReference:
    """Represents a lineage reference with lazy resolution capability."""

    def __init__(
        self,
        namespace: Optional[str] = None,
        name: Optional[str] = None,
        model_name: Optional[str] = None,
        field: Optional[str] = None,
    ):
        self.namespace = namespace
        self.name = name
        self.model_name = model_name
        self.field = field
        self._resolved_contract: Optional[Contract] = None
        self._resolved_model: Optional[Dict[str, Any]] = None
        self._resolved_field: Optional[Dict[str, Any]] = None
        self._is_broken: Optional[bool] = None

    def __str__(self) -> str:
        parts = []
        if self.namespace:
            parts.append(self.namespace)
        if self.name:
            parts.append(self.name)
        if self.model_name:
            parts.append(self.model_name)
        if self.field:
            parts.append(self.field)
        return "/".join(parts) if parts else "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {}
        if self.namespace:
            result["namespace"] = self.namespace
        if self.name:
            result["name"] = self.name
        if self.model_name:
            result["model_name"] = self.model_name
        if self.field:
            result["field"] = self.field
        return result

    def resolve_contract(self) -> Optional[Any]:
        """Lazily resolve the contract reference."""
        if Contract is None:
            return None

        if self._resolved_contract is not None:
            return self._resolved_contract if not self._is_broken else None

        if not self.namespace or not self.name:
            self._is_broken = True
            return None

        # Try to find contract by namespace/name
        try:
            # Check cache first
            cache_key = f"lineage:contract:{self.namespace}:{self.name}"
            contract_id = cache.get(cache_key)
            if contract_id:
                try:
                    contract = Contract.objects.get(id=contract_id)
                    self._resolved_contract = contract
                    self._is_broken = False
                    return contract
                except Contract.DoesNotExist:
                    pass

            # Query by hub_contract_json
            contracts = Contract.objects.filter(hub_contract_json__info__name=self.name)
            if self.namespace:
                # Try to match namespace from info or extensions
                contracts = contracts.filter(
                    models.Q(hub_contract_json__info__domain=self.namespace)
                    | models.Q(hub_contract_json__extensions__namespace=self.namespace)
                )

            contract = contracts.first()
            if contract:
                self._resolved_contract = contract
                self._is_broken = False
                # Cache the mapping
                cache.set(cache_key, str(contract.id), timeout=3600)
                return contract
            else:
                self._is_broken = True
                return None
        except Exception:
            self._is_broken = True
            return None

    def resolve_model(self) -> Optional[Dict[str, Any]]:
        """Lazily resolve the model reference."""
        if self._resolved_model is not None:
            return self._resolved_model if not self._is_broken else None

        contract = self.resolve_contract()
        if not contract:
            return None

        hub_contract = contract.hub_contract_json
        if not isinstance(hub_contract, dict):
            self._is_broken = True
            return None

        models_list = hub_contract.get("models", [])
        if not models_list:
            self._is_broken = True
            return None

        # Find model by name
        for model in models_list:
            if isinstance(model, dict) and model.get("name") == self.model_name:
                self._resolved_model = model
                self._is_broken = False
                return model

        self._is_broken = True
        return None

    def resolve_field(self) -> Optional[Dict[str, Any]]:
        """Lazily resolve the field reference."""
        if self._resolved_field is not None:
            return self._resolved_field if not self._is_broken else None

        model = self.resolve_model()
        if not model:
            return None

        fields = model.get("fields", [])
        if not fields:
            self._is_broken = True
            return None

        # Find field by name
        for field in fields:
            if isinstance(field, dict) and field.get("name") == self.field:
                self._resolved_field = field
                self._is_broken = False
                return field

        self._is_broken = True
        return None

    def is_broken(self) -> bool:
        """Check if this reference is broken (cannot be resolved)."""
        if self._is_broken is not None:
            return self._is_broken

        # Try to resolve to determine if broken
        if self.field:
            self.resolve_field()
        elif self.model_name:
            self.resolve_model()
        else:
            self.resolve_contract()

        return self._is_broken is True


def resolve_lineage_reference(ref: Optional[LineageReference]) -> Optional[Any]:
    """
    Resolve a lineage reference to its contract.

    Triggers lazy resolution and returns the resolved contract, or None if
    the reference is broken or unresolvable. Side effect: populates ref._is_broken.
    """
    if ref is None:
        return None
    return ref.resolve_contract()


def extract_contract_level_lineage(odcs_contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract contract-level lineage from ODCS contract.

    Contract-level lineage includes:
    - transformSourceObjects at contract level
    - transformLogic at contract level
    - References to other contracts
    """
    lineage_section = {}

    # Extract transformSourceObjects and transformLogic at contract level
    transform_sources = odcs_contract.get("transformSourceObjects")
    transform_logic = odcs_contract.get("transformLogic")

    entries = []
    if isinstance(transform_sources, list):
        entry = {"input_fields": transform_sources}
        if transform_logic:
            entry["transformations"] = [{"logic": transform_logic}]
        entries.append(entry)
    elif transform_logic:
        entries.append({"transformations": [{"logic": transform_logic}]})

    if entries:
        lineage_section["entries"] = entries

    # Extract contract references from transformSourceObjects
    contract_refs = []
    if isinstance(transform_sources, list):
        for source in transform_sources:
            if isinstance(source, dict):
                # If it's a contract reference (has namespace/name but no model/field)
                if "namespace" in source or "name" in source:
                    if (
                        "model" not in source
                        and "model_name" not in source
                        and "field" not in source
                    ):
                        contract_refs.append(
                            {
                                "namespace": source.get("namespace"),
                                "name": source.get("name"),
                                "version": source.get("version"),
                                "description": source.get("description"),
                            }
                        )

    if contract_refs:
        lineage_section["contracts"] = contract_refs

    return lineage_section if lineage_section else None


def extract_model_level_lineage(odcs_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract model-level lineage from ODCS schema object.

    Model-level lineage includes:
    - transformSourceObjects at schema level
    - transformLogic at schema level
    - References to other models
    """
    lineage_section = {}

    # Extract transformSourceObjects and transformLogic at schema level
    transform_sources = odcs_schema.get("transformSourceObjects")
    transform_logic = odcs_schema.get("transformLogic")

    entries = []
    if isinstance(transform_sources, list):
        entry = {"input_fields": transform_sources}
        if transform_logic:
            entry["transformations"] = [{"logic": transform_logic}]
        entries.append(entry)
    elif transform_logic:
        entries.append({"transformations": [{"logic": transform_logic}]})

    if entries:
        lineage_section["entries"] = entries

    # Extract model references from transformSourceObjects
    model_refs = []
    if isinstance(transform_sources, list):
        for source in transform_sources:
            if isinstance(source, dict):
                # If it's a model reference (has namespace/name/model but no field)
                if ("namespace" in source or "name" in source) and (
                    "model" in source or "model_name" in source
                ):
                    if "field" not in source:
                        model_refs.append(
                            {
                                "namespace": source.get("namespace"),
                                "name": source.get("name"),
                                "model_name": source.get("model") or source.get("model_name"),
                                "description": source.get("description"),
                            }
                        )

    if model_refs:
        lineage_section["models"] = model_refs

    return lineage_section if lineage_section else None


def extract_field_level_lineage(odcs_field: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract field-level lineage from ODCS field definition.

    Field-level lineage includes:
    - transformSourceObjects at field level
    - transformLogic at field level
    - transformDescription at field level
    """
    transform_sources = odcs_field.get("transformSourceObjects")
    transform_logic = odcs_field.get("transformLogic")
    transform_description = odcs_field.get("transformDescription")

    if not transform_sources and not transform_logic and not transform_description:
        return None

    entry: Dict[str, Any] = {}

    if isinstance(transform_sources, list):
        entry["input_fields"] = transform_sources

    if transform_logic or transform_description:
        transform = {}
        if transform_logic:
            transform["logic"] = transform_logic
        if transform_description:
            transform["description"] = transform_description
        entry["transformations"] = [transform]

    return entry if entry else None


class LineageTraverser:
    """Traverses multi-level lineage graphs with cycle detection and depth limits."""

    def __init__(
        self,
        contract: Any,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
    ):
        self.contract = contract
        self.max_contract_depth = max_contract_depth
        self.max_model_depth = max_model_depth
        self.max_field_depth = max_field_depth
        self.visited_contracts: Set[str] = set()
        self.visited_models: Set[Tuple[str, str]] = set()  # (contract_id, model_name)
        self.visited_fields: Set[Tuple[str, str, str]] = (
            set()
        )  # (contract_id, model_name, field_name)

    def traverse_top_down(
        self,
        contract_id: Optional[str] = None,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
        contract_depth: int = 0,
        model_depth: int = 0,
        field_depth: int = 0,
    ) -> Dict[str, Any]:
        """
        Traverse lineage top-down (Contract → Model → Field).

        Returns a hierarchical structure showing all downstream lineage.
        """
        if contract_id is None:
            contract_id = str(self.contract.id)

        # Check depth limits
        if contract_depth > self.max_contract_depth:
            return {"error": "Max contract depth exceeded"}

        if model_depth > self.max_model_depth:
            return {"error": "Max model depth exceeded"}

        if field_depth > self.max_field_depth:
            return {"error": "Max field depth exceeded"}

        # Check for cycles
        if contract_id in self.visited_contracts:
            return {"error": "Cycle detected", "contract_id": contract_id}

        self.visited_contracts.add(contract_id)

        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return {"error": "Contract not found", "contract_id": contract_id}

        hub_contract = contract.hub_contract_json
        if not isinstance(hub_contract, dict):
            return {"contract_id": contract_id, "models": [], "error": "Invalid contract data"}

        result: Dict[str, Any] = {
            "contract_id": contract_id,
            "contract_name": hub_contract.get("info", {}).get("name"),
            "models": [],
        }

        # Get contract-level lineage
        lineage = hub_contract.get("lineage")
        if isinstance(lineage, dict):
            contract_refs = lineage.get("contracts", [])
            if contract_refs:
                result["contract_lineage"] = []
                for ref in contract_refs:
                    ref_obj = LineageReference(
                        namespace=ref.get("namespace"),
                        name=ref.get("name"),
                    )
                    resolved = ref_obj.resolve_contract()
                    if resolved:
                        result["contract_lineage"].append(
                            {
                                "contract_id": str(resolved.id),
                                "contract_name": resolved.hub_contract_json.get("info", {}).get(
                                    "name"
                                ),
                                "namespace": ref.get("namespace"),
                                "name": ref.get("name"),
                            }
                        )

        # Get models
        models_list = hub_contract.get("models", [])
        for model in models_list:
            if not isinstance(model, dict):
                continue

            model_name_curr = model.get("name")
            if model_name and model_name != model_name_curr:
                continue

            model_key = (contract_id, model_name_curr)
            if model_key in self.visited_models:
                continue

            self.visited_models.add(model_key)

            model_result: Dict[str, Any] = {
                "model_name": model_name_curr,
                "fields": [],
            }

            # Get model-level lineage
            model_lineage = model.get("lineage")
            if isinstance(model_lineage, dict):
                model_refs = model_lineage.get("models", [])
                if model_refs:
                    model_result["model_lineage"] = []
                    for ref in model_refs:
                        ref_obj = LineageReference(
                            namespace=ref.get("namespace"),
                            name=ref.get("name"),
                            model_name=ref.get("model_name"),
                        )
                        resolved = ref_obj.resolve_model()
                        if resolved:
                            model_result["model_lineage"].append(
                                {
                                    "namespace": ref.get("namespace"),
                                    "name": ref.get("name"),
                                    "model_name": ref.get("model_name"),
                                }
                            )

            # Get fields
            fields = model.get("fields", [])
            for field in fields:
                if not isinstance(field, dict):
                    continue

                field_name_curr = field.get("name")
                if field_name and field_name != field_name_curr:
                    continue

                field_key = (contract_id, model_name_curr, field_name_curr)
                if field_key in self.visited_fields:
                    continue

                self.visited_fields.add(field_key)

                field_result: Dict[str, Any] = {
                    "field_name": field_name_curr,
                }

                # Get field-level lineage
                field_lineage = field.get("lineage")
                if field_lineage:
                    field_result["lineage"] = field_lineage

                    # Recursively traverse field lineage
                    input_fields = field_lineage.get("input_fields") or field_lineage.get(
                        "inputFields", []
                    )
                    if input_fields:
                        field_result["input_fields"] = []
                        for input_field in input_fields:
                            if isinstance(input_field, dict):
                                ref_obj = LineageReference(
                                    namespace=input_field.get("namespace"),
                                    name=input_field.get("name"),
                                    model_name=input_field.get("model")
                                    or input_field.get("model_name"),
                                    field=input_field.get("field"),
                                )
                                if ref_obj.field:
                                    # Field-level reference - traverse recursively
                                    resolved_contract = ref_obj.resolve_contract()
                                    if resolved_contract:
                                        sub_traverser = LineageTraverser(
                                            resolved_contract,
                                            max_contract_depth=self.max_contract_depth,
                                            max_model_depth=self.max_model_depth,
                                            max_field_depth=self.max_field_depth,
                                        )
                                        sub_traverser.visited_contracts = (
                                            self.visited_contracts.copy()
                                        )
                                        sub_traverser.visited_models = self.visited_models.copy()
                                        sub_traverser.visited_fields = self.visited_fields.copy()
                                        sub_result = sub_traverser.traverse_top_down(
                                            contract_id=str(resolved_contract.id),
                                            model_name=ref_obj.model_name,
                                            field_name=ref_obj.field,
                                            contract_depth=contract_depth + 1,
                                            model_depth=model_depth + 1,
                                            field_depth=field_depth + 1,
                                        )
                                        field_result["input_fields"].append(sub_result)

                model_result["fields"].append(field_result)

            result["models"].append(model_result)

        return result

    def traverse_bottom_up(
        self,
        contract_id: Optional[str] = None,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
        contract_depth: int = 0,
        model_depth: int = 0,
        field_depth: int = 0,
    ) -> Dict[str, Any]:
        """
        Traverse lineage bottom-up (Field → Model → Contract).

        Returns a hierarchical structure showing all upstream lineage.
        """
        # Similar to top-down but in reverse direction
        # Find all contracts/models/fields that reference this one
        if contract_id is None:
            contract_id = str(self.contract.id)

        # Check depth limits
        if contract_depth > self.max_contract_depth:
            return {"error": "Max contract depth exceeded"}

        if model_depth > self.max_model_depth:
            return {"error": "Max model depth exceeded"}

        if field_depth > self.max_field_depth:
            return {"error": "Max field depth exceeded"}

        # Check for cycles
        if contract_id in self.visited_contracts:
            return {"error": "Cycle detected", "contract_id": contract_id}

        self.visited_contracts.add(contract_id)

        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return {"error": "Contract not found", "contract_id": contract_id}

        hub_contract = contract.hub_contract_json
        if not isinstance(hub_contract, dict):
            return {"contract_id": contract_id, "models": [], "error": "Invalid contract data"}

        result: Dict[str, Any] = {
            "contract_id": contract_id,
            "contract_name": hub_contract.get("info", {}).get("name"),
            "referenced_by": [],
        }

        if Contract is None:
            return {"error": "Contract model not available"}

        # Find contracts that reference this contract
        # Filter by tenant_id for performance (root cause fix)
        # This significantly improves performance when there are many contracts
        tenant_id = contract.tenant_id if hasattr(contract, "tenant_id") else None
        queryset = Contract.objects.exclude(id=contract_id)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        all_contracts = queryset
        for other_contract in all_contracts:
            other_hub_contract = other_contract.hub_contract_json
            if not isinstance(other_hub_contract, dict):
                continue

            other_lineage = other_hub_contract.get("lineage")
            if isinstance(other_lineage, dict):
                contract_refs = other_lineage.get("contracts", [])
                for ref in contract_refs:
                    if ref.get("name") == hub_contract.get("info", {}).get("name"):
                        result["referenced_by"].append(
                            {
                                "contract_id": str(other_contract.id),
                                "contract_name": other_hub_contract.get("info", {}).get("name"),
                            }
                        )

        return result

    def traverse_bidirectional(
        self,
        contract_id: Optional[str] = None,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Traverse lineage bidirectionally (both upstream and downstream).

        Returns a structure with both upstream and downstream lineage.
        """
        top_down = self.traverse_top_down(contract_id, model_name, field_name)
        bottom_up = self.traverse_bottom_up(contract_id, model_name, field_name)

        return {
            "upstream": bottom_up,
            "downstream": top_down,
        }


def generate_lineage_json(
    contract: Any, format: str = "json", max_depth: int = 10
) -> Dict[str, Any]:
    """
    Generate lineage graph in JSON format (for D3.js).

    Args:
        contract: Contract instance
        format: Format string (for compatibility, default: "json")
        max_depth: Maximum traversal depth (default: 10)

    Returns:
        Graph structure with nodes and edges.
    """
    traverser = LineageTraverser(
        contract, max_contract_depth=max_depth, max_model_depth=max_depth, max_field_depth=max_depth
    )
    lineage_data = traverser.traverse_bidirectional()

    nodes = []
    edges = []

    # Add root contract node
    hub_contract = contract.hub_contract_json
    if isinstance(hub_contract, dict):
        nodes.append(
            {
                "id": str(contract.id),
                "type": "contract",
                "name": hub_contract.get("info", {}).get("name"),
                "label": hub_contract.get("info", {}).get("name"),
            }
        )

    # Process downstream lineage
    downstream = lineage_data.get("downstream", {})
    _process_lineage_for_visualization(downstream, nodes, edges, "downstream")

    # Process upstream lineage
    upstream = lineage_data.get("upstream", {})
    _process_lineage_for_visualization(upstream, nodes, edges, "upstream")

    return {
        "nodes": nodes,
        "links": edges,
    }


def _process_lineage_for_visualization(
    lineage_data: Dict[str, Any],
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    direction: str,
):
    """Helper to process lineage data for visualization."""
    if not isinstance(lineage_data, dict) or "error" in lineage_data:
        return

    contract_id = lineage_data.get("contract_id")
    contract_name = lineage_data.get("contract_name")

    # Add contract node
    if contract_id and contract_id not in [n["id"] for n in nodes]:
        nodes.append(
            {
                "id": contract_id,
                "type": "contract",
                "name": contract_name,
                "label": contract_name,
            }
        )

    # Process models
    models = lineage_data.get("models", [])
    for model in models:
        if not isinstance(model, dict):
            continue

        model_name = model.get("model_name")
        model_node_id = f"{contract_id}:model:{model_name}"

        if model_node_id not in [n["id"] for n in nodes]:
            nodes.append(
                {
                    "id": model_node_id,
                    "type": "model",
                    "name": model_name,
                    "label": model_name,
                    "contract_id": contract_id,
                }
            )

        # Add edge from contract to model
        edges.append(
            {
                "source": contract_id,
                "target": model_node_id,
                "type": "contains",
                "direction": direction,
            }
        )

        # Process fields
        fields = model.get("fields", [])
        for field in fields:
            if not isinstance(field, dict):
                continue

            field_name = field.get("field_name")
            field_node_id = f"{contract_id}:model:{model_name}:field:{field_name}"

            if field_node_id not in [n["id"] for n in nodes]:
                nodes.append(
                    {
                        "id": field_node_id,
                        "type": "field",
                        "name": field_name,
                        "label": field_name,
                        "model_id": model_node_id,
                        "contract_id": contract_id,
                    }
                )

            # Add edge from model to field
            edges.append(
                {
                    "source": model_node_id,
                    "target": field_node_id,
                    "type": "contains",
                    "direction": direction,
                }
            )

            # Process field lineage
            field_lineage = field.get("lineage")
            if field_lineage:
                input_fields = field_lineage.get("input_fields") or field_lineage.get(
                    "inputFields", []
                )
                for input_field in input_fields:
                    if isinstance(input_field, dict):
                        input_contract_id = input_field.get("contract_id")
                        input_model_name = input_field.get("model_name")
                        input_field_name = input_field.get("field_name")

                        if input_contract_id and input_model_name and input_field_name:
                            input_field_node_id = f"{input_contract_id}:model:{input_model_name}:field:{input_field_name}"
                            edges.append(
                                {
                                    "source": input_field_node_id,
                                    "target": field_node_id,
                                    "type": "lineage",
                                    "direction": direction,
                                }
                            )

                            # Recursively process input field
                            _process_lineage_for_visualization(input_field, nodes, edges, direction)


def generate_lineage_dot(contract: Any, max_depth: int = 10) -> str:
    """
    Generate lineage graph in DOT format (for Graphviz).

    Args:
        contract: Contract instance
        max_depth: Maximum traversal depth (default: 10)

    Returns:
        DOT format string.
    """
    graph_data = generate_lineage_json(contract, format="json", max_depth=max_depth)

    lines = ["digraph Lineage {"]
    lines.append("  rankdir=LR;")
    lines.append("  node [shape=box];")

    # Add nodes
    for node in graph_data["nodes"]:
        node_id = node["id"].replace(":", "_").replace("-", "_")
        node_label = node.get("label", node.get("name", "Unknown"))
        node_type = node.get("type", "unknown")

        if node_type == "contract":
            lines.append(f'  {node_id} [label="{node_label}", style="bold"];')
        elif node_type == "model":
            lines.append(f'  {node_id} [label="{node_label}", style="rounded"];')
        else:
            lines.append(f'  {node_id} [label="{node_label}"];')

    # Add edges
    for edge in graph_data["links"]:
        source = edge["source"].replace(":", "_").replace("-", "_")
        target = edge["target"].replace(":", "_").replace("-", "_")
        edge_type = edge.get("type", "lineage")

        if edge_type == "lineage":
            lines.append(f'  {source} -> {target} [style="dashed"];')
        else:
            lines.append(f"  {source} -> {target};")

    lines.append("}")

    return "\n".join(lines)


def generate_lineage_mermaid(contract: Any, max_depth: int = 10) -> str:
    """
    Generate lineage graph in Mermaid format.

    Args:
        contract: Contract instance
        max_depth: Maximum traversal depth (default: 10)

    Returns:
        Mermaid format string.
    """
    graph_data = generate_lineage_json(contract, format="json", max_depth=max_depth)

    lines = ["graph LR"]

    # Add nodes
    for node in graph_data["nodes"]:
        node_id = node["id"].replace(":", "_").replace("-", "_")
        node_label = node.get("label", node.get("name", "Unknown"))
        node_type = node.get("type", "unknown")

        if node_type == "contract":
            lines.append(f'  {node_id}["{node_label}"]')
        elif node_type == "model":
            lines.append(f'  {node_id}("{node_label}")')
        else:
            lines.append(f"  {node_id}[{node_label}]")

    # Add edges
    for edge in graph_data["links"]:
        source = edge["source"].replace(":", "_").replace("-", "_")
        target = edge["target"].replace(":", "_").replace("-", "_")
        edge_type = edge.get("type", "lineage")

        if edge_type == "lineage":
            lines.append(f"  {source} -.-> {target}")
        else:
            lines.append(f"  {source} --> {target}")

    return "\n".join(lines)
