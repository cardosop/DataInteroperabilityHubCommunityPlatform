"""
Lineage Service

Service layer for lineage operations.
Extracts lineage logic from views and lineage.py module.
"""

from typing import Any, Dict, List, Optional

from hub.apps.contracts.caching import (
    cache_lineage,
    get_cached_lineage,
    invalidate_lineage_cache,
)
from hub.apps.contracts.impact_analysis import ImpactAnalyzer
from hub.apps.contracts.impact_notifications import ImpactNotifier
from hub.apps.contracts.impact_visualization import ImpactVisualizer
from hub.apps.contracts.lineage import (
    LineageTraverser,
    generate_lineage_dot,
    generate_lineage_json,
    generate_lineage_mermaid,
)
from hub.apps.contracts.models import Contract
from hub.apps.core.services.base import BaseService, NotFoundError


class LineageService(BaseService):
    """
    Service for lineage operations.

    Provides business logic for:
    - Contract-level lineage retrieval
    - Model-level lineage retrieval
    - Field-level lineage retrieval
    - Full hierarchical lineage
    - Lineage visualization
    - Impact analysis
    """

    service_name = "lineage_service"

    def get_contract_lineage(
        self, contract_id: str, tenant_id: Optional[str] = None, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get contract-level lineage.

        Args:
            contract_id: Contract ID
            tenant_id: Optional tenant ID for filtering
            use_cache: Whether to use cache (default: True)

        Returns:
            Lineage dictionary with contracts and entries

        Raises:
            NotFoundError: If contract not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache
        if use_cache:
            cached_lineage = get_cached_lineage(contract_id)
            if cached_lineage:
                return cached_lineage

        # Extract lineage from contract
        hub_contract = contract.hub_contract_json
        if not hub_contract:
            return {"contracts": [], "entries": []}

        lineage_data = hub_contract.get("lineage", {})
        result = {
            "contracts": lineage_data.get("contracts", []),
            "entries": lineage_data.get("entries", []),
        }

        # Cache result
        if use_cache:
            cache_lineage(contract_id, result)

        return result

    def get_model_lineage(
        self,
        contract_id: str,
        model_name: str,
        tenant_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Get model-level lineage.

        Args:
            contract_id: Contract ID
            model_name: Model name
            tenant_id: Optional tenant ID for filtering
            use_cache: Whether to use cache (default: True)

        Returns:
            Model lineage dictionary

        Raises:
            NotFoundError: If contract or model not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache
        if use_cache:
            cached_lineage = get_cached_lineage(contract_id, model_name=model_name)
            if cached_lineage:
                return cached_lineage

        # Find model in contract
        hub_contract = contract.hub_contract_json
        if not hub_contract:
            raise NotFoundError("Model", model_name)

        models_list = hub_contract.get("models", [])
        model = None
        for m in models_list:
            if isinstance(m, dict) and m.get("name") == model_name:
                model = m
                break

        if not model:
            raise NotFoundError("Model", model_name)

        # Extract lineage from model
        lineage_data = model.get("lineage", {})
        result = {
            "model_name": model_name,
            "lineage": {
                "models": lineage_data.get("models", []),
                "entries": lineage_data.get("entries", []),
            },
        }

        # Cache result
        if use_cache:
            cache_lineage(contract_id, result, model_name=model_name)

        return result

    def get_field_lineage(
        self,
        contract_id: str,
        field_name: str,
        model_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Get field-level lineage.

        Args:
            contract_id: Contract ID
            field_name: Field name
            model_name: Optional model name (searches all models if not provided)
            tenant_id: Optional tenant ID for filtering
            use_cache: Whether to use cache (default: True)

        Returns:
            Field lineage dictionary

        Raises:
            NotFoundError: If contract or field not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache
        if use_cache:
            cached_lineage = get_cached_lineage(
                contract_id, model_name=model_name, field_name=field_name
            )
            if cached_lineage:
                return cached_lineage

        # Find field in contract
        hub_contract = contract.hub_contract_json
        if not hub_contract:
            raise NotFoundError("Field", field_name)

        models_list = hub_contract.get("models", [])
        field = None
        found_model_name = None

        for model in models_list:
            if isinstance(model, dict):
                model_name_to_check = model.get("name")
                fields_list = model.get("fields", [])
                for f in fields_list:
                    if isinstance(f, dict) and f.get("name") == field_name:
                        # If model_name specified, only match in that model
                        if model_name and model_name_to_check != model_name:
                            continue
                        field = f
                        found_model_name = model_name_to_check
                        break
                if field:
                    break

        if not field:
            raise NotFoundError("Field", field_name)

        # Extract lineage from field
        lineage_data = field.get("lineage", {})
        result = {
            "field_name": field_name,
            "model_name": found_model_name,
            "lineage": {
                "input_fields": lineage_data.get("input_fields", []),
                "transformations": lineage_data.get("transformations", []),
            },
        }

        # Cache result
        if use_cache:
            cache_lineage(contract_id, result, model_name=found_model_name, field_name=field_name)

        return result

    def get_full_lineage(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Get full hierarchical lineage (contract, model, and field levels).

        Args:
            contract_id: Contract ID
            tenant_id: Optional tenant ID for filtering
            max_contract_depth: Maximum contract depth
            max_model_depth: Maximum model depth
            max_field_depth: Maximum field depth
            use_cache: Whether to use cache (default: True)

        Returns:
            Full lineage dictionary with upstream and downstream

        Raises:
            NotFoundError: If contract not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache - use a composite key for full lineage
        # Note: Full lineage cache key includes depth parameters, so we can't use the standard function
        # For now, we'll skip caching for full lineage or use a custom key
        # This is acceptable since full lineage is expensive and depth params vary
        if False:  # Disable cache for full lineage due to depth parameters
            from django.core.cache import cache

            cache_key = f"lineage:full:{contract_id}:{max_contract_depth}:{max_model_depth}:{max_field_depth}"
            cached_lineage = cache.get(cache_key)
            if cached_lineage:
                return cached_lineage

        # Use LineageTraverser to get full lineage
        traverser = LineageTraverser(
            contract,
            max_contract_depth=max_contract_depth,
            max_model_depth=max_model_depth,
            max_field_depth=max_field_depth,
        )
        # Based on traverse_bidirectional: upstream = bottom_up, downstream = top_down
        # upstream: what depends on this contract (dependents)
        upstream = traverser.traverse_bottom_up()
        # downstream: what this contract depends on (sources)
        downstream = traverser.traverse_top_down()

        result = {"upstream": upstream, "downstream": downstream}

        # Cache result - use custom cache key for full lineage
        if use_cache and False:  # Disable cache for full lineage due to depth parameters
            from django.core.cache import cache

            from hub.apps.contracts.caching import CACHE_TTL_LINEAGE

            cache_key = f"lineage:full:{contract_id}:{max_contract_depth}:{max_model_depth}:{max_field_depth}"
            cache.set(cache_key, result, timeout=CACHE_TTL_LINEAGE)

        return result

    def get_lineage_visualization(
        self,
        contract_id: str,
        format: str = "json",
        tenant_id: Optional[str] = None,
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        """
        Get lineage visualization in various formats.

        Args:
            contract_id: Contract ID
            format: Visualization format (json, dot, mermaid)
            tenant_id: Optional tenant ID for filtering
            max_depth: Maximum traversal depth

        Returns:
            Visualization data

        Raises:
            NotFoundError: If contract not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        if format == "json":
            return generate_lineage_json(contract, max_depth=max_depth)
        elif format == "dot":
            return {"dot": generate_lineage_dot(contract, max_depth=max_depth)}
        elif format == "mermaid":
            return {"mermaid": generate_lineage_mermaid(contract, max_depth=max_depth)}
        else:
            from hub.apps.core.services.base import ValidationError

            raise ValidationError(
                f"Invalid format: {format}. Supported formats: json, dot, mermaid"
            )

    def analyze_impact(
        self,
        contract_id: str,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
        include_fields: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze impact of contract changes.

        Args:
            contract_id: Contract ID
            model_name: Optional model name (for model-level impact)
            field_name: Optional field name (for field-level impact)
            tenant_id: Optional tenant ID for filtering
            max_contract_depth: Maximum contract depth
            max_model_depth: Maximum model depth
            max_field_depth: Maximum field depth
            include_fields: Include field-level dependencies

        Returns:
            Impact analysis results

        Raises:
            NotFoundError: If contract not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        analyzer = ImpactAnalyzer(
            max_contract_depth=max_contract_depth,
            max_model_depth=max_model_depth,
            max_field_depth=max_field_depth,
            include_fields=include_fields,
        )

        # Analyze impact using the correct API
        impact_result = analyzer.analyze_impact(
            contract_id=str(contract.id),
            model_name=model_name,
            field_name=field_name,
            tenant_id=tenant_id or str(self.tenant_id),
        )

        # Check for errors
        if "error" in impact_result:
            return impact_result

        # ImpactAnalyzer already calculates scores internally
        # Add visualization to the result
        return {
            **impact_result,
            "visualization": ImpactVisualizer.visualize_impact(impact_result),
        }

    def notify_impact(
        self, contract_id: str, impact_analysis: Dict[str, Any], tenant_id: Optional[str] = None
    ) -> None:
        """
        Send notifications for impact analysis.

        Args:
            contract_id: Contract ID
            impact_analysis: Impact analysis results
            tenant_id: Optional tenant ID for filtering

        Raises:
            NotFoundError: If contract not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        notifier = ImpactNotifier()
        notifier.notify_impact(contract, impact_analysis)
