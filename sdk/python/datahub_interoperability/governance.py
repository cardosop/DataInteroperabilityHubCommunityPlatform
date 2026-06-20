"""
Governance operations for DataHub SDK.

Provides methods for data classification, retention policies, access workflows, and compliance reporting.
"""

from typing import Any, Dict, List, Optional

from .client import DataHubClient


class GovernanceAPI:
    """
    Governance API.

    Provides methods for data governance and compliance operations.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Governance API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    # Classification

    async def get_classification(
        self,
        asset_id: str,
    ) -> Dict[str, Any]:
        """
        Get data classification for asset.

        Args:
            asset_id: Asset UUID

        Returns:
            Classification data
        """
        return await self.client.get(f"assets/{asset_id}/classification/")

    async def classify_asset(
        self,
        asset_id: str,
        classification: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Classify asset.

        Args:
            asset_id: Asset UUID
            classification: Classification data

        Returns:
            Updated classification
        """
        return await self.client.post(f"assets/{asset_id}/classify/", data=classification)

    # Retention Policies

    async def get_retention_policies(
        self,
        asset_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List retention policies.

        Args:
            asset_id: Filter by asset ID (optional)
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with retention policies
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if asset_id:
            params["asset_id"] = asset_id

        return await self.client.get("governance/retention-policies/", params=params)

    async def create_retention_policy(
        self,
        asset_id: str,
        retention_period_days: int,
        action: str = "DELETE",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create retention policy.

        Args:
            asset_id: Asset UUID
            retention_period_days: Retention period in days
            action: Action to take ("DELETE", "ARCHIVE", "ANONYMIZE")
            **kwargs: Additional policy parameters

        Returns:
            Created retention policy
        """
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "retention_period_days": retention_period_days,
            "action": action,
        }
        data.update(kwargs)

        return await self.client.post("governance/retention-policies/", data=data)

    async def update_retention_policy(
        self,
        policy_id: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update retention policy.

        Args:
            policy_id: Policy UUID
            **kwargs: Fields to update

        Returns:
            Updated retention policy
        """
        return await self.client.patch(f"governance/retention-policies/{policy_id}/", data=kwargs)

    async def delete_retention_policy(self, policy_id: str) -> None:
        """
        Delete retention policy.

        Args:
            policy_id: Policy UUID
        """
        await self.client.delete(f"governance/retention-policies/{policy_id}/")

    # Access Requests

    async def create_access_request(
        self,
        asset_id: str,
        reason: str,
        requested_access_type: str = "READ",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create access request.

        Args:
            asset_id: Asset UUID
            reason: Request reason
            requested_access_type: Access type ("READ", "WRITE", "DELETE")
            **kwargs: Additional request parameters

        Returns:
            Created access request
        """
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "reason": reason,
            "requested_access_type": requested_access_type,
        }
        data.update(kwargs)

        return await self.client.post("governance/access-requests/", data=data)

    async def list_access_requests(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List access requests.

        Args:
            status: Filter by status (optional)
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with access requests
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status

        return await self.client.get("governance/access-requests/", params=params)

    async def approve_access_request(
        self,
        request_id: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Approve access request.

        Args:
            request_id: Request UUID
            **kwargs: Additional approval parameters

        Returns:
            Updated access request
        """
        return await self.client.post(
            f"governance/access-requests/{request_id}/approve/", data=kwargs
        )

    async def reject_access_request(
        self,
        request_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Reject access request.

        Args:
            request_id: Request UUID
            reason: Rejection reason

        Returns:
            Updated access request
        """
        return await self.client.post(
            f"governance/access-requests/{request_id}/reject/", data={"reason": reason}
        )

    # Compliance Reporting

    async def generate_compliance_report(
        self,
        regime: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        asset_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate compliance report.

        Args:
            regime: Compliance regime (GDPR, HIPAA, SOX, LGPD, CCPA)
            start_date: Start date (ISO 8601, optional)
            end_date: End date (ISO 8601, optional)
            asset_ids: Filter by asset IDs (optional)

        Returns:
            Compliance report data
        """
        data: Dict[str, Any] = {
            "regime": regime,
        }
        if start_date:
            data["start_date"] = start_date
        if end_date:
            data["end_date"] = end_date
        if asset_ids:
            data["asset_ids"] = asset_ids

        return await self.client.post("governance/compliance-reports/", data=data)

    async def get_compliance_report(
        self,
        report_id: str,
    ) -> Dict[str, Any]:
        """
        Get compliance report by ID.

        Args:
            report_id: Report UUID

        Returns:
            Compliance report data
        """
        return await self.client.get(f"governance/compliance-reports/{report_id}/")

    # ── 118F.19: Expanded governance methods ─────────────

    async def get_access_request_expiration(self, request_id: str) -> dict:
        data = await self.client.get(f"governance/access-requests/{request_id}/")
        return {"expires_at": data.get("expires_at")}

    async def set_access_request_expiration(self, request_id: str, expires_at: str) -> dict:
        return await self.client.patch(
            f"governance/access-requests/{request_id}/",
            data={"expires_at": expires_at},
        )
