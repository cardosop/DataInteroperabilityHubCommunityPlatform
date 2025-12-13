"""
Contract management operations for DataHub SDK.

Provides high-level methods for managing contracts with support for
all new objects (Contact, Server, Terms, Definition, Lineage, ServiceLevel, Models).
"""
from typing import Dict, Any, List, Optional
from .client import DataHubClient


class ContractsAPI:
    """
    Contract management API.
    
    Provides methods for creating, updating, listing, and managing contracts
    with support for all contract objects and filtering.
    """
    
    def __init__(self, client: DataHubClient):
        """
        Initialize Contracts API.
        
        Args:
            client: DataHub client instance
        """
        self.client = client
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 50,
        ordering: Optional[str] = None,
        owner_email: Optional[str] = None,
        owner_name: Optional[str] = None,
        tag: Optional[str] = None,
        quality_profile: Optional[str] = None,
        compliance_regime: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_name: Optional[str] = None,
        server_type: Optional[str] = None,
        server_url: Optional[str] = None,
        min_availability: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List contracts with filtering.
        
        Args:
            page: Page number (default: 1)
            page_size: Items per page (default: 50, max: 100)
            ordering: Sort fields (comma-separated, prefix with '-' for descending)
            owner_email: Filter by owner email (case-insensitive)
            owner_name: Filter by owner name (case-insensitive partial match)
            tag: Filter by tag (can specify multiple)
            quality_profile: Filter by quality profile key
            compliance_regime: Filter by compliance jurisdiction
            contact_email: Filter by contact email (case-insensitive)
            contact_name: Filter by contact name (case-insensitive partial match)
            server_type: Filter by server type
            server_url: Filter by server URL (case-insensitive partial match)
            min_availability: Filter by minimum availability SLA
            max_latency_ms: Filter by maximum latency SLA
            model_name: Filter by model name
        
        Returns:
            Paginated response with contracts
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        
        if ordering:
            params["ordering"] = ordering
        if owner_email:
            params["owner_email"] = owner_email
        if owner_name:
            params["owner_name"] = owner_name
        if tag:
            params["tag"] = tag
        if quality_profile:
            params["quality_profile"] = quality_profile
        if compliance_regime:
            params["compliance_regime"] = compliance_regime
        if contact_email:
            params["contact_email"] = contact_email
        if contact_name:
            params["contact_name"] = contact_name
        if server_type:
            params["server_type"] = server_type
        if server_url:
            params["server_url"] = server_url
        if min_availability is not None:
            params["min_availability"] = min_availability
        if max_latency_ms is not None:
            params["max_latency_ms"] = max_latency_ms
        if model_name:
            params["model_name"] = model_name
        
        return await self.client.get("contracts/contracts/", params=params)
    
    async def get(self, contract_id: str) -> Dict[str, Any]:
        """
        Get contract by ID.
        
        Args:
            contract_id: Contract UUID
        
        Returns:
            Contract data
        """
        return await self.client.get(f"contracts/contracts/{contract_id}/")
    
    async def create(
        self,
        original_raw: str,
        original_format: str = "JSON",
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create contract from ODCS format.
        
        Args:
            original_raw: Original contract content (JSON or YAML string)
            original_format: Format of original contract ("JSON" or "YAML")
            asset_id: Optional asset ID to attach contract to
        
        Returns:
            Created contract data
        """
        data: Dict[str, Any] = {
            "original_raw": original_raw,
            "original_format": original_format,
        }
        if asset_id:
            data["asset_id"] = asset_id
        
        return await self.client.post("contracts/contracts/", data=data)
    
    async def update(
        self,
        contract_id: str,
        original_raw: Optional[str] = None,
        original_format: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update contract (partial update supported).
        
        Args:
            contract_id: Contract UUID
            original_raw: Updated contract content (optional)
            original_format: Format of updated contract (optional)
            **kwargs: Additional fields to update
        
        Returns:
            Updated contract data
        """
        data: Dict[str, Any] = {}
        if original_raw:
            data["original_raw"] = original_raw
        if original_format:
            data["original_format"] = original_format
        data.update(kwargs)
        
        return await self.client.patch(f"contracts/contracts/{contract_id}/", data=data)
    
    async def delete(self, contract_id: str) -> None:
        """
        Delete contract (soft delete: sets status to RETIRED).
        
        Args:
            contract_id: Contract UUID
        """
        await self.client.delete(f"contracts/contracts/{contract_id}/")
    
    async def validate(self, contract_id: str) -> Dict[str, Any]:
        """
        Validate contract.
        
        Args:
            contract_id: Contract UUID
        
        Returns:
            Validation result with errors and warnings
        """
        return await self.client.post(f"contracts/contracts/{contract_id}/validate/")
    
    async def lint(self, contract_id: str) -> Dict[str, Any]:
        """
        Lint contract.
        
        Args:
            contract_id: Contract UUID
        
        Returns:
            Lint result with issues
        """
        return await self.client.post(f"contracts/contracts/{contract_id}/lint/")
    
    # Helper methods for accessing contract objects
    
    def get_contact(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get contact objects from contract.
        
        Args:
            contract: Contract data
        
        Returns:
            List of contact objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("contact")
    
    def get_servers(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get server objects from contract.
        
        Args:
            contract: Contract data
        
        Returns:
            List of server objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("servers")
    
    def get_terms(self, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get terms object from contract.
        
        Args:
            contract: Contract data
        
        Returns:
            Terms object or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("terms")
    
    def get_definitions(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get definition objects from contract.
        
        Args:
            contract: Contract data
        
        Returns:
            List of definition objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("definitions")
    
    def get_lineage(self, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get lineage object from contract.
        
        Args:
            contract: Contract data
        
        Returns:
            Lineage object or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("lineage")
    
    def get_servicelevels(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get service level objects from contract.
        
        Args:
            contract: Contract data
        
        Returns:
            List of service level objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("servicelevels")
    
    def get_models(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get models from contract.
        
        Args:
            contract: Contract data
        
        Returns:
            List of model objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("models")

