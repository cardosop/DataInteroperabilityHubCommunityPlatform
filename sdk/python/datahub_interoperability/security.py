"""Security incident and audit log operations."""
from typing import Any, Dict, Optional
from .client import DataHubClient

class SecurityAPI:
    def __init__(self, client: DataHubClient): self.client = client
    # Incidents
    async def list_incidents(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        return await self.client.get("security/incidents/", params={"page": page, "page_size": page_size})
    async def create_incident(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post("security/incidents/", data=data)
    async def get_incident(self, incident_id: str) -> Dict[str, Any]:
        return await self.client.get(f"security/incidents/{incident_id}/")
    async def update_incident(self, incident_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.patch(f"security/incidents/{incident_id}/", data=data)
    # Audit logs
    async def list_audit_logs(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        return await self.client.get("security/audit-logs/", params={"page": page, "page_size": page_size})
    async def get_audit_log(self, log_id: str) -> Dict[str, Any]:
        return await self.client.get(f"security/audit-logs/{log_id}/")
