"""
Data Mesh operations for DataHub SDK.

Provides methods for managing data mesh domains, topology, policies, and compliance.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class MeshAPI:
    """
    Data Mesh API.

    Provides methods for data mesh domain management, topology operations,
    policy management, and compliance reporting.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Mesh API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    # Domain Management

    async def create_domain(
        self,
        name: str,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
        boundaries: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        resource_quota: Optional[Dict[str, Any]] = None,
        status: str = "ACTIVE",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a new data mesh domain.

        Args:
            name: Domain name (required, unique per tenant)
            description: Domain description (optional)
            owner_id: Owner user ID (optional)
            boundaries: Domain boundaries as dict (optional)
            capabilities: Domain capabilities as dict (optional)
            resource_quota: Resource quotas as dict (optional)
            status: Domain status - "ACTIVE", "INACTIVE", or "ARCHIVED" (default: "ACTIVE")
            **kwargs: Additional domain parameters

        Returns:
            Created domain data

        Raises:
            ValidationError: If domain data is invalid
            ConflictError: If domain name already exists
        """
        data: Dict[str, Any] = {
            "name": name.strip() if name else name,
            "status": status,
        }

        if description is not None:
            data["description"] = description
        if owner_id:
            data["owner_id"] = owner_id
        if boundaries is not None:
            data["boundaries"] = boundaries
        if capabilities is not None:
            data["capabilities"] = capabilities
        if resource_quota is not None:
            data["resource_quota"] = resource_quota
        data.update(kwargs)

        return await self.client.post("mesh/domains/", data=data)

    async def list_domains(
        self,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        search: Optional[str] = None,
        ordering: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        List data mesh domains with filtering and pagination.

        Args:
            status: Filter by status - "ACTIVE", "INACTIVE", or "ARCHIVED" (optional)
            owner_id: Filter by owner user ID (optional)
            search: Search in name and description (optional)
            ordering: Order by field - "name", "status", "created_at", "updated_at".
                     Prefix with "-" for descending (e.g., "-created_at") (optional)
            page: Page number (default: 1)
            page_size: Items per page, max 100 (default: 20)

        Returns:
            Paginated response with domains list
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 100),  # Enforce max page size
        }

        if status:
            params["status"] = status
        if owner_id:
            params["owner_id"] = owner_id
        if search:
            params["search"] = search
        if ordering:
            params["ordering"] = ordering

        return await self.client.get("mesh/domains/", params=params)

    async def get_domain(
        self,
        domain_id: str,
    ) -> Dict[str, Any]:
        """
        Get domain details by ID.

        Args:
            domain_id: Domain UUID

        Returns:
            Domain data

        Raises:
            NotFoundError: If domain not found
        """
        return await self.client.get(f"mesh/domains/{domain_id}/")

    async def update_domain(
        self,
        domain_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
        boundaries: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        resource_quota: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update an existing data mesh domain.

        Args:
            domain_id: Domain UUID
            name: Domain name (optional)
            description: Domain description (optional, can be empty string)
            owner_id: Owner user ID (optional)
            boundaries: Domain boundaries as dict (optional)
            capabilities: Domain capabilities as dict (optional)
            resource_quota: Resource quotas as dict (optional)
            status: Domain status - "ACTIVE", "INACTIVE", or "ARCHIVED" (optional)
            **kwargs: Additional fields to update

        Returns:
            Updated domain data

        Raises:
            NotFoundError: If domain not found
            ValidationError: If update data is invalid
        """
        data: Dict[str, Any] = {}

        if name is not None:
            data["name"] = name.strip() if name else name
        if description is not None:  # Allow empty string
            data["description"] = description
        if owner_id is not None:
            data["owner_id"] = owner_id
        if boundaries is not None:
            data["boundaries"] = boundaries
        if capabilities is not None:
            data["capabilities"] = capabilities
        if resource_quota is not None:
            data["resource_quota"] = resource_quota
        if status is not None:
            data["status"] = status
        data.update(kwargs)

        if not data:
            raise ValueError("At least one field must be provided for update")

        return await self.client.patch(f"mesh/domains/{domain_id}/", data=data)

    async def delete_domain(
        self,
        domain_id: str,
    ) -> None:
        """
        Delete a data mesh domain.

        Args:
            domain_id: Domain UUID

        Raises:
            NotFoundError: If domain not found
        """
        await self.client.delete(f"mesh/domains/{domain_id}/")

    # Topology Operations

    async def get_topology(
        self,
        include_health_metrics: bool = True,
    ) -> Dict[str, Any]:
        """
        Get complete data mesh topology including all domains, relationships, and health metrics.

        Args:
            include_health_metrics: Include health metrics in response (default: True)

        Returns:
            Topology data containing:
            - nodes: List of domain nodes
            - edges: List of domain relationships
            - metadata: Topology metadata (tenant_id, domain_count, relationship_count, generated_at)
            - summary: Summary statistics (total_domains, active_domains, total_relationships, average_health_score)

        Raises:
            ValidationError: If request is invalid
        """
        params: Dict[str, Any] = {
            "include_health_metrics": str(include_health_metrics).lower(),
        }

        return await self.client.get("mesh/topology/", params=params)

    async def get_domain_topology(
        self,
        domain_id: str,
    ) -> Dict[str, Any]:
        """
        Get topology view for a specific domain including its relationships and health metrics.

        Args:
            domain_id: Domain UUID

        Returns:
            Domain topology data containing:
            - domain: Domain node information
            - relationships: List of relationships for this domain
            - health_metrics: Domain health metrics

        Raises:
            NotFoundError: If domain not found
        """
        return await self.client.get(f"mesh/topology/{domain_id}/")

    # Policy Management

    async def apply_policy(
        self,
        domain_id: str,
        policy_id: str,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Apply an access policy to a data mesh domain with optional overrides.

        Args:
            domain_id: Domain UUID
            policy_id: Policy UUID to apply
            overrides: Optional policy overrides as dict (conditions, effect, priority, etc.)

        Returns:
            Policy application data containing:
            - id: Policy application ID
            - domain_id: Domain ID
            - policy_id: Policy ID
            - status: Application status (PENDING, APPLIED, FAILED, REVOKED)
            - overrides: Policy overrides
            - applied_at: Timestamp when policy was applied

        Raises:
            NotFoundError: If domain or policy not found
            ValidationError: If validation fails (policy disabled, domain inactive, invalid overrides)
        """
        data: Dict[str, Any] = {
            "policy_id": policy_id,
        }

        if overrides is not None:
            data["overrides"] = overrides

        return await self.client.post(f"mesh/domains/{domain_id}/policies/apply/", data=data)

    async def list_policies(
        self,
        domain_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        List all policies applied to a data mesh domain with filtering and pagination.

        Args:
            domain_id: Domain UUID
            status: Filter by status - "PENDING", "APPLIED", "FAILED", or "REVOKED" (optional)
            page: Page number (default: 1)
            page_size: Items per page, max 100 (default: 20)

        Returns:
            Paginated response with policies list containing:
            - count: Total number of policies
            - page: Current page number
            - page_size: Items per page
            - total_pages: Total number of pages
            - results: List of policy applications

        Raises:
            NotFoundError: If domain not found
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 100),  # Enforce max page size
        }

        if status:
            params["status"] = status

        return await self.client.get(f"mesh/domains/{domain_id}/policies/", params=params)

    async def remove_policy(
        self,
        domain_id: str,
        policy_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Remove (revoke) a policy application from a data mesh domain.

        Args:
            domain_id: Domain UUID
            policy_id: Policy UUID to remove

        Returns:
            Policy application data with status set to REVOKED, or None if no content returned

        Raises:
            NotFoundError: If domain or policy application not found
        """
        return await self.client.delete(f"mesh/domains/{domain_id}/policies/{policy_id}/")

    # Compliance Operations

    async def check_compliance(
        self,
        domain_id: str,
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check compliance status for a data mesh domain and generate a compliance report.

        Args:
            domain_id: Domain UUID
            asset_id: Optional asset UUID for asset-specific compliance check

        Returns:
            Compliance report data containing:
            - id: Report ID
            - domain_id: Domain ID
            - domain_name: Domain name
            - asset_id: Asset ID (if asset-specific)
            - asset_name: Asset name (if asset-specific)
            - compliance_status: Status (COMPLIANT, NON_COMPLIANT, PARTIAL, UNKNOWN)
            - violations: Violations dict with details
            - violation_count: Number of violations
            - generated_at: Timestamp when report was generated

        Raises:
            NotFoundError: If domain or asset not found
            ValidationError: If validation fails
        """
        data: Dict[str, Any] = {}

        if asset_id:
            data["asset_id"] = asset_id

        return await self.client.post(f"mesh/domains/{domain_id}/compliance/check/", data=data)

    async def get_compliance_report(
        self,
        domain_id: str,
        report_id: str,
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific compliance report for a data mesh domain.

        Args:
            domain_id: Domain UUID
            report_id: Compliance report UUID

        Returns:
            Compliance report data containing:
            - id: Report ID
            - domain_id: Domain ID
            - domain_name: Domain name
            - asset_id: Asset ID (if asset-specific)
            - asset_name: Asset name (if asset-specific)
            - compliance_status: Status (COMPLIANT, NON_COMPLIANT, PARTIAL, UNKNOWN)
            - violations: Violations dict with details
            - violation_count: Number of violations
            - generated_at: Timestamp when report was generated

        Raises:
            NotFoundError: If domain or compliance report not found
        """
        return await self.client.get(f"mesh/domains/{domain_id}/compliance/reports/{report_id}/")
