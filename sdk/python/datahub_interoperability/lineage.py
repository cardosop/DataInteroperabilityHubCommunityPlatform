"""
Lineage operations for DataHub SDK.

Provides methods for querying multi-level lineage (contract, model, field levels).
"""

from typing import Any, Dict

from .client import DataHubClient


class LineageAPI:
    """
    Lineage API.

    Provides methods for querying lineage at contract, model, and field levels.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Lineage API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def get_contract_lineage(
        self,
        contract_id: str,
    ) -> Dict[str, Any]:
        """
        Get contract-level lineage.

        Args:
            contract_id: Contract UUID

        Returns:
            Contract-level lineage data
        """
        return await self.client.get(f"contracts/{contract_id}/lineage/contracts/")

    async def get_model_lineage(
        self,
        contract_id: str,
        model_name: str,
    ) -> Dict[str, Any]:
        """
        Get model-level lineage.

        Args:
            contract_id: Contract UUID
            model_name: Model name

        Returns:
            Model-level lineage data
        """
        return await self.client.get(f"contracts/{contract_id}/models/{model_name}/lineage/")

    async def get_field_lineage(
        self,
        contract_id: str,
        model_name: str,
        field_name: str,
    ) -> Dict[str, Any]:
        """
        Get field-level lineage.

        Args:
            contract_id: Contract UUID
            model_name: Model name
            field_name: Field name

        Returns:
            Field-level lineage data
        """
        params: Dict[str, Any] = {}
        if model_name:
            params["model_name"] = model_name
        return await self.client.get(
            f"contracts/{contract_id}/fields/{field_name}/lineage/",
            params=params,
        )

    async def get_full_lineage(
        self,
        contract_id: str,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
    ) -> Dict[str, Any]:
        """
        Get complete hierarchical lineage (contract, model, and field levels).

        Args:
            contract_id: Contract UUID
            max_contract_depth: Maximum contract depth (default: 10)
            max_model_depth: Maximum model depth (default: 10)
            max_field_depth: Maximum field depth (default: 10)

        Returns:
            Complete hierarchical lineage data
        """
        params = {
            "max_contract_depth": max_contract_depth,
            "max_model_depth": max_model_depth,
            "max_field_depth": max_field_depth,
        }
        return await self.client.get(f"contracts/{contract_id}/lineage/full/", params=params)

    async def get_visualization(
        self,
        contract_id: str,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Get lineage graph in various visualization formats.

        Args:
            contract_id: Contract UUID
            format: Visualization format - "json", "dot", or "mermaid" (default: "json")

        Returns:
            Visualization data (format depends on format parameter)
        """
        params = {"format": format}
        response = await self.client.request(
            "GET", f"contracts/{contract_id}/lineage/visualization/", params=params
        )

        # For text formats (dot, mermaid), return as text
        if format in ["dot", "mermaid"]:
            return {"format": format, "content": response.text}

        # For JSON format, return parsed JSON
        return response.json()

    async def get_impact_analysis(
        self,
        contract_id: str,
        depth: int = 10,
        include_fields: bool = True,
    ) -> Dict[str, Any]:
        """
        Get impact analysis for a contract.

        Args:
            contract_id: Contract UUID
            depth: Traversal depth (default: 10)
            include_fields: Include field-level impact (default: True)

        Returns:
            Impact analysis data
        """
        params = {
            "depth": depth,
            "include_fields": include_fields,
        }
        return await self.client.get(f"contracts/{contract_id}/impact-analysis/", params=params)

    # Convenience methods with shorter names (matching expected API)
    async def contract(self, contract_id: str) -> Dict[str, Any]:
        """Convenience method for get_contract_lineage"""
        return await self.get_contract_lineage(contract_id)

    async def model(self, contract_id: str, model_name: str) -> Dict[str, Any]:
        """Convenience method for get_model_lineage"""
        return await self.get_model_lineage(contract_id, model_name)

    async def field(self, contract_id: str, model_name: str, field_name: str) -> Dict[str, Any]:
        """Convenience method for get_field_lineage"""
        return await self.get_field_lineage(contract_id, model_name, field_name)

    async def full(
        self,
        contract_id: str,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
    ) -> Dict[str, Any]:
        """Convenience method for get_full_lineage"""
        return await self.get_full_lineage(
            contract_id, max_contract_depth, max_model_depth, max_field_depth
        )

    async def visualize(self, contract_id: str, format: str = "json") -> Dict[str, Any]:
        """Convenience method for get_visualization"""
        return await self.get_visualization(contract_id, format)

    async def impact(
        self,
        contract_id: str,
        depth: int = 10,
        include_fields: bool = True,
    ) -> Dict[str, Any]:
        """Convenience method for get_impact_analysis"""
        return await self.get_impact_analysis(contract_id, depth, include_fields)
